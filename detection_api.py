"""Accept JPEG camera frames from the local Sign Assist dashboard."""

import argparse
import pickle
import re
from functools import partial
from pathlib import Path
from zipfile import BadZipFile

import cv2
import numpy as np
from tornado.ioloop import IOLoop
from tornado.web import Application, HTTPError, RequestHandler

from detector import CHECKPOINT, load_detector
from gtsrb import CAMERA_CLASSES, LABELS as GTSRB_LABELS, read_previews
from gtsrb_classifier import CLASSIFIER, CROP_SIZE, ONCOMING_CLASSIFIER, ONCOMING_LABELS, classify_crops, load_classifier


DEFAULT_IMGSZ = 640
DEFAULT_CONFIDENCE = 0.40
GTSRB_PROPOSAL_CONFIDENCE = 0.08
GTSRB_MATCH_CONFIDENCE = 0.70
GTSRB_CLASS_CONFIDENCE = 0.88
GTSRB_DETECTOR_CONFIDENCE = 0.64
SIGN_KINDS = {
    "stop": "stop",
    "red light": "red_light",
    "green light": "green_light",
    "yield": "yield",
    "give way": "yield",
    "no entry": "no_entry",
    "no overtaking": "no_overtaking",
    "parking": "parking",
    "no parking": "no_parking",
    "priority": "priority",
    "priority road": "priority",
    "yield to oncoming traffic": "oncoming_has_priority",
    "priority over oncoming traffic": "priority_over_oncoming",
    "pedestrian": "pedestrian",
    "pedestrian crossing": "pedestrian",
    "roundabout": "roundabout",
    "warning": "warning",
}


def sign_for_class(name):
    name = re.sub(r"[\s_-]+", " ", name.strip().casefold())
    speed = re.fullmatch(r"speed limit (\d+)(?:\s*km/h)?", name)
    if speed:
        return {"kind": "speed", "value": int(speed[1])}
    gtsrb = re.fullmatch(r"gtsrb (\d+)(?: .+)?", name)
    if gtsrb and 0 <= (index := int(gtsrb[1])) < len(GTSRB_LABELS):
        return {"kind": "gtsrb", "value": index, "label": GTSRB_LABELS[index]}
    kind = SIGN_KINDS.get(name)
    return {"kind": kind} if kind else None


def gtsrb_signs(names, include_oncoming=False):
    active = [sign_for_class(name) for name in names.values()]
    signs = {}
    for index in range(len(GTSRB_LABELS)):
        sign = sign_for_class(CAMERA_CLASSES.get(index, f"GTSRB {index:02d}"))
        if sign in active:
            signs[index] = sign
    if include_oncoming:
        for index, kind in ONCOMING_LABELS.items():
            sign = {"kind": kind}
            if sign in active:
                signs[index] = sign
    return signs


def predict_sign(frame, detector, imgsz, conf, classifier):
    model, device, lock = detector
    predict_conf = min(conf, GTSRB_PROPOSAL_CONFIDENCE) if classifier else conf
    with lock:
        result = model.predict(frame, device=device, imgsz=imgsz, conf=predict_conf, verbose=False)[0]
        scores = result.boxes.conf.tolist()
        class_ids = result.boxes.cls.int().tolist()
        boxes = result.boxes.xyxy.tolist() if classifier else []

    signs = [sign_for_class(result.names[index]) for index in class_ids]
    refinements = {}
    options = {}
    eligible = []
    if classifier:
        reader, options = classifier
        eligible = [sign in options.values() for sign in signs]
        check_oncoming = any(index in options for index in ONCOMING_LABELS)
        candidates = [
            index for index, sign in enumerate(signs) if eligible[index] or (check_oncoming and sign)
        ][:12]
        found = classify_crops(reader, frame, [boxes[index] for index in candidates])
        refinements = {candidates[index]: prediction for index, prediction in found.items()}

    best_sign = None
    best_score = 0.0
    for index, (score, sign) in enumerate(zip(scores, signs)):
        if classifier:
            prediction = refinements.get(index)
            alternative = options.get(prediction.class_id) if prediction else None
            oncoming = sign is not None and sign["kind"] in ONCOMING_LABELS.values()
            can_reclassify = eligible[index] and not (oncoming and score >= conf)
            if (
                eligible[index] and prediction and alternative == sign
                and prediction.confidence >= GTSRB_MATCH_CONFIDENCE and prediction.margin >= 0.18
            ):
                score = max(score, (score + prediction.confidence) / 2)
            elif (
                prediction and alternative and (can_reclassify or prediction.class_id in ONCOMING_LABELS)
                and prediction.confidence >= GTSRB_CLASS_CONFIDENCE and prediction.margin >= 0.30
            ):
                sign = alternative
                score = min(0.75, (score + prediction.confidence) / 2)
            elif eligible[index]:
                if oncoming:
                    x1, y1, x2, y2 = boxes[index]
                    if min(x2 - x1, y2 - y1) < CROP_SIZE:
                        continue
                elif score < GTSRB_DETECTOR_CONFIDENCE:
                    continue
        if sign is not None and score >= conf and score > best_score:
            best_sign = sign
            best_score = score
    return best_sign


def detect_sign(
    jpeg, *, detector=None, imgsz=DEFAULT_IMGSZ, conf=DEFAULT_CONFIDENCE, previews=None, classifier=None
):
    if not jpeg.startswith(b"\xff\xd8"):
        raise ValueError("Expected a JPEG frame.")
    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode the camera frame.")

    loaded = detector or load_detector()
    best_sign = predict_sign(frame, loaded, imgsz, conf, classifier)
    if best_sign is None and classifier and imgsz == DEFAULT_IMGSZ:
        training_size = loaded[0].overrides.get("imgsz")
        if isinstance(training_size, int) and 0 < training_size < imgsz:
            best_sign = predict_sign(frame, loaded, training_size, conf, classifier)
    if best_sign and best_sign["kind"] == "gtsrb" and previews:
        image = previews.get(best_sign["value"])
        if image:
            return {**best_sign, "image": image}
    return best_sign


class DetectHandler(RequestHandler):
    def initialize(self, detect):
        self.detect = detect

    async def post(self):
        if self.request.headers.get("Content-Type", "").split(";")[0] != "image/jpeg":
            raise HTTPError(415, reason="Expected image/jpeg.")
        try:
            sign = await IOLoop.current().run_in_executor(None, self.detect, self.request.body)
        except ValueError as error:
            raise HTTPError(400, reason=str(error)) from error
        self.set_header("Cache-Control", "no-store")
        self.write({"sign": sign})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=CHECKPOINT)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ, help="Inference image size (default: 640)")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONFIDENCE)
    parser.add_argument("--device", default="auto", help="auto, mps, cpu, or a CUDA device index")
    parser.add_argument("--classifier", type=Path, help="Override the optional crop classifier")
    args = parser.parse_args()

    weights = args.weights.expanduser().resolve()
    if not weights.is_file():
        parser.error(f"Lipsește modelul {weights}. Rulează scripts/train_model.py.")
    if args.imgsz < 1:
        parser.error("--imgsz trebuie să fie pozitiv.")
    if not 0 < args.conf <= 1:
        parser.error("--conf trebuie să fie în (0, 1].")

    detector = load_detector(weights, args.device)
    model, device, _ = detector
    previews = {}
    classifier = None
    if any(name.startswith("GTSRB ") for name in model.names.values()):
        try:
            previews = read_previews()
        except (OSError, ValueError, KeyError, EOFError, pickle.UnpicklingError, BadZipFile, cv2.error) as error:
            print(f"Imaginile de referință GTSRB nu s-au putut încărca ({error}).", flush=True)
        has_oncoming = any(sign_for_class(name) == {"kind": "oncoming_has_priority"} for name in model.names.values())
        default_classifier = ONCOMING_CLASSIFIER if has_oncoming and ONCOMING_CLASSIFIER.is_file() else CLASSIFIER
        reader = load_classifier((args.classifier or default_classifier).expanduser())
        if reader is not None:
            output_count = list(reader.parameters())[-1].numel()
            classifier = reader, gtsrb_signs(model.names, include_oncoming=output_count > max(ONCOMING_LABELS))
    detect = partial(
        detect_sign, detector=detector, imgsz=args.imgsz, conf=args.conf, previews=previews, classifier=classifier
    )
    Application([(r"/api/detect", DetectHandler, {"detect": detect})]).listen(
        8510, address="127.0.0.1", max_body_size=1024 * 1024
    )
    print(
        f"Detectorul ascultă la http://127.0.0.1:8510 ({weights.name}, {device}, {len(model.names)} clase"
        f"{', clasificator GTSRB activ' if classifier else ''})",
        flush=True,
    )
    IOLoop.current().start()


if __name__ == "__main__":
    main()

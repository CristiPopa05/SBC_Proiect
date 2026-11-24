"""Accept JPEG camera frames from the local Sign Assist dashboard."""

import re

import cv2
import numpy as np
from tornado.ioloop import IOLoop
from tornado.web import Application, HTTPError, RequestHandler

from detector import CHECKPOINT, load_detector


def detect_sign(jpeg):
    if not jpeg.startswith(b"\xff\xd8"):
        raise ValueError("Expected a JPEG frame.")
    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode the camera frame.")

    model, device, lock = load_detector()
    with lock:
        result = model.predict(frame, device=device, imgsz=640, conf=0.25, verbose=False)[0]
        if not len(result.boxes):
            return None
        strongest = result.boxes.conf.argmax().item()
        name = result.names[int(result.boxes.cls[strongest].item())]

    speed = re.fullmatch(r"Speed Limit (\d+)", name)
    if speed:
        return {"kind": "speed", "value": int(speed[1])}
    kind = {"Stop": "stop", "Red Light": "red_light", "Green Light": "green_light"}.get(name)
    return {"kind": kind} if kind else None


class DetectHandler(RequestHandler):
    async def post(self):
        if self.request.headers.get("Content-Type", "").split(";")[0] != "image/jpeg":
            raise HTTPError(415, reason="Expected image/jpeg.")
        try:
            sign = await IOLoop.current().run_in_executor(None, detect_sign, self.request.body)
        except ValueError as error:
            raise HTTPError(400, reason=str(error)) from error
        self.set_header("Cache-Control", "no-store")
        self.write({"sign": sign})


if __name__ == "__main__":
    if not CHECKPOINT.is_file():
        raise SystemExit("Lipsește models/best.pt. Rulează scripts/train_model.py.")
    load_detector()
    Application([(r"/api/detect", DetectHandler)]).listen(
        8510, address="127.0.0.1", max_body_size=1024 * 1024
    )
    print("Detectorul ascultă la http://127.0.0.1:8510", flush=True)
    IOLoop.current().start()

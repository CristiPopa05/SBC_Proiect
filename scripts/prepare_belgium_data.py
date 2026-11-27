"""Extend the traffic-sign detector with Belgian road scenes and sign crops."""

import argparse
import csv
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from tarfile import TarError, open as open_tar
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import cv2
import numpy as np
import yaml

if __package__:
    from .prepare_priority_data import add_composites, background_boxes, read_image, write_example
else:
    from prepare_priority_data import add_composites, background_boxes, read_image, write_example


ROOT = Path(__file__).resolve().parents[1]
BELGIUM_CLASSES = {
    "E9a": (45, "Parking"),
    "E1": (40, "No Parking"),
    "C1": (22, "No Entry"),
    "C35": (31, "No Overtaking"),
    "F49": (56, "Pedestrian Crossing"),
    "D5": (37, "Roundabout"),
    "A51": (13, "Warning"),
}
KNOWN_SIGNS = {"B1": "Yield", "B5": "Stop", "B9": "Priority road"}
CAMERAS = ("camera00.tar", "camera01.tar")


def training_split(pole):
    return "val" if pole % 5 == 0 else "train"


def decode_image(data, source):
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode {source}.")
    return image


def read_crops(source, classes, target_classes=BELGIUM_CLASSES):
    patches = {split: defaultdict(list) for split in ("train", "val", "test")}
    for file, directory in (("crops_train.zip", "Training"), ("crops_test.zip", "Testing")):
        with ZipFile(source / file) as archive:
            for crop_id, name in target_classes.values():
                label = classes[name]
                folder = f"{directory}/{crop_id:05d}"
                data = archive.read(f"{folder}/GT-{crop_id:05d}.csv").decode("utf-8-sig")
                for row in csv.DictReader(data.splitlines(), delimiter=";"):
                    filename = row["Filename"]
                    pole = int(filename.split("_", 1)[0])
                    split = "test" if directory == "Testing" else training_split(pole)
                    member = f"{folder}/{filename}"
                    frame = decode_image(archive.read(member), member)
                    x1, y1, x2, y2 = (int(row[f"Roi.{key}"]) for key in ("X1", "Y1", "X2", "Y2"))
                    patches[split][label].append(frame[y1:y2, x1:x2].copy())
    return patches


def read_road_boxes(source, classes, target_classes=BELGIUM_CLASSES):
    belgium_names = {code: name for code, (_, name) in {**BELGIUM_CLASSES, **target_classes}.items()}
    known = {code: name for code, name in {**KNOWN_SIGNS, **belgium_names}.items() if name in classes}
    boxes = defaultdict(list)
    splits = defaultdict(set)
    with ZipFile(source / "annotations.zip") as archive:
        for split in ("training", "testing"):
            data = archive.read(f"BelgiumTSD_annotations/BTSD_{split}_GT.txt").decode("latin-1")
            for line in data.splitlines():
                row = line.split(";")
                code = row[11]
                if code not in known:
                    continue
                file = row[0]
                points = [float(point) for point in row[1:5]]
                boxes[file].append((classes[known[code]], *points))
                if code in target_classes:
                    splits[file].add("test" if split == "testing" else training_split(int(row[7])))
    # An image containing signs assigned to different splits is skipped.
    return {file: (next(iter(split)), boxes[file]) for file, split in splits.items() if len(split) == 1}


def add_road_frames(source, output, classes, target_classes=BELGIUM_CLASSES, cameras=CAMERAS):
    scenes = read_road_boxes(source, classes, target_classes)
    counts = Counter()
    manifest = []
    for file in cameras:
        with open_tar(source / file, mode="r:") as archive:
            for member in archive:
                if not member.isfile() or member.name not in scenes:
                    continue
                split, boxes = scenes[member.name]
                with archive.extractfile(member) as image_file:
                    frame = decode_image(image_file.read(), member.name)
                height, width = frame.shape[:2]
                labels = []
                for sign, x1, y1, x2, y2 in boxes:
                    x1, y1 = max(0, math.floor(x1)), max(0, math.floor(y1))
                    x2, y2 = min(width, math.ceil(x2)), min(height, math.ceil(y2))
                    if x1 < x2 and y1 < y2:
                        labels.append((sign, x1, y1, x2, y2))
                stem = PurePosixPath(member.name).with_suffix("").as_posix().replace("/", "_")
                name = f"btsd_{stem}"
                write_example(output, split, name, frame, labels)
                counts[split] += 1
                if split == "test":
                    manifest.append(f"./images/test/{name}.jpg")
    if set(counts) != {"train", "val", "test"}:
        raise ValueError("Expected road scenes for training, validation, and test.")
    return counts, sorted(manifest)


def add_speed_limit_examples(base, output, classes):
    targets = {classes[name] for name in ("Speed Limit 10", "Speed Limit 20")}
    patches = defaultdict(list)
    for image in sorted((base / "images/train").glob("*.jpg")):
        label = base / "labels/train" / f"{image.stem}.txt"
        if not any(int(line.split()[0]) in targets for line in label.read_text().splitlines() if line.strip()):
            continue
        frame = read_image(image)
        height, width = frame.shape[:2]
        for sign, x1, y1, x2, y2 in background_boxes(label, width, height):
            if sign in targets and x2 - x1 >= 12 and y2 - y1 >= 12:
                patches[sign].append(frame[math.floor(y1):math.ceil(y2), math.floor(x1):math.ceil(x2)].copy())
    return add_composites(base, output, patches, 110, prefix="speed")


def prepare(base, source, output):
    if output.exists():
        raise FileExistsError(f"{output} already exists. Use an unused --output directory.")
    names = yaml.safe_load((base / "data.yaml").read_text())["names"]
    new_names = [name for _, name in BELGIUM_CLASSES.values()]
    if not isinstance(names, list) or set(names) & set(new_names):
        raise ValueError("Expected the YOLO dataset with the original 17 class names.")
    names = [*names, *new_names]
    classes = {name: index for index, name in enumerate(names)}
    patches = read_crops(source, classes)

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".prepare-belgium-", dir=output.parent) as scratch:
        staged = Path(scratch) / "dataset"
        config = {split: f"images/{split}" for split in ("train", "val", "test")}
        for split in config:
            for kind in ("images", "labels"):
                shutil.copytree(base / kind / split, staged / kind / split)
        counts, test_images = add_road_frames(source, staged, classes)
        train = add_composites(base, staged, patches["train"], 150, prefix="btsd")
        val = add_composites(base, staged, patches["val"], 16, split="val", prefix="btsd")
        speed = add_speed_limit_examples(base, staged, classes)
        for sign, samples in patches["test"].items():
            for index, image in enumerate(samples):
                height, width = image.shape[:2]
                corner = max(10, round(max(height, width) * 0.45))
                frame = cv2.copyMakeBorder(image, corner, corner, corner, corner, cv2.BORDER_CONSTANT, value=(164, 167, 172))
                name = f"btsd_crop_{sign}_{index:04d}"
                labels = [(sign, corner, corner, corner + width, corner + height)]
                write_example(staged, "test", name, frame, labels)
        config["names"] = names
        (staged / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        (staged / "belgium-test.txt").write_text("\n".join(test_images) + "\n")
        (staged / "data_belgium_test.yaml").write_text(
            yaml.safe_dump({**config, "test": "belgium-test.txt"}, sort_keys=False)
        )
        staged.rename(output)
    return counts, train, val, speed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "dataset" / "detection_priority")
    parser.add_argument("--source", type=Path, default=ROOT / "raw_data" / "belgiumts")
    parser.add_argument("--output", type=Path, default=ROOT / "dataset" / "detection_belgium")
    args = parser.parse_args()
    try:
        counts, train, val, speed = prepare(args.base, args.source, args.output)
    except (OSError, ValueError, KeyError, BadZipFile, TarError, cv2.error, yaml.YAMLError) as error:
        parser.exit(1, f"Error preparing BelgiumTS: {error}\n")
    print(f"Prepared {args.output}. Road frames: {dict(counts)}. Composites: train={train + speed}, val={val}.")


if __name__ == "__main__":
    main()

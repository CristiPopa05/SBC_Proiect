"""Prepare full-frame YOLO data for all GTSRB classes using GTSRB and GTSDB."""

import argparse
import pickle
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import cv2
import yaml

from gtsrb import ARCHIVE, CAMERA_CLASSES, LABELS, read_class_names, read_samples
from scripts.prepare_priority_data import IMAGE_EXTENSIONS, add_composites, read_image, write_example


ROOT = Path(__file__).resolve().parents[1]
GTSDB_FRAME = re.compile(r"gtsdb_\d{5}")


def paths_for(base, split, replace_gtsdb):
    return sorted(
        path for path in (base / "images" / split).iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        and not (replace_gtsdb and GTSDB_FRAME.fullmatch(path.stem))
    )


def training_replay(base, images, limit=90):
    by_class = defaultdict(list)
    for image in images:
        label = base / "labels/train" / f"{image.stem}.txt"
        classes = {int(row.split()[0]) for row in label.read_text().splitlines() if row.strip()}
        for index in classes or {None}:
            by_class[index].append(image)
    rng = random.Random(73)
    return sorted({
        image for examples in by_class.values()
        for image in rng.sample(examples, min(len(examples), limit))
    })


def copy_base(base, output, *, replay_per_class=90, replace_gtsdb=True):
    for split in ("train", "val", "test"):
        images = paths_for(base, split, replace_gtsdb)
        if split == "train":
            images = training_replay(base, images, replay_per_class)
        image_dir = output / "images" / split
        label_dir = output / "labels" / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for image in images:
            label = base / "labels" / split / f"{image.stem}.txt"
            shutil.copy2(image, image_dir / image.name)
            shutil.copy2(label, label_dir / label.name)


def road_examples(gtsdb, output, classes):
    scenes = defaultdict(list)
    for line in (gtsdb / "gt.txt").read_text().splitlines():
        if not line.strip():
            continue
        filename, x1, y1, x2, y2, sign = line.split(";")
        index = int(sign)
        if index in classes:
            scenes[Path(filename).stem].append((classes[index], int(x1), int(y1), int(x2), int(y2)))
    test_paths = []
    for stem, labels in sorted(scenes.items()):
        image = gtsdb / f"{stem}.jpg"
        if not image.is_file():
            image = gtsdb / f"{stem}.ppm"
        index = int(stem)
        split = "test" if index >= 600 else "val" if 400 <= index < 500 else "train"
        name = f"gtsdb_{stem}"
        write_example(output, split, name, read_image(image), labels)
        if split == "test":
            test_paths.append(f"./images/test/{name}.jpg")
    return test_paths


def image_patches(archive, filename, class_ids):
    frames, labels = read_samples(archive, filename)
    # The recognition archive already crops each physical sign with a small border.
    return {
        target: [cv2.cvtColor(frame[2:-2, 2:-2], cv2.COLOR_RGB2BGR) for frame in frames[labels == source]]
        for source, target in class_ids.items()
    }


def write_test_config(output, config, name, test_images):
    manifest = f"{name}-test.txt"
    (output / manifest).write_text("\n".join(test_images) + "\n", encoding="utf-8")
    (output / f"data_{name}_test.yaml").write_text(
        yaml.safe_dump({**config, "test": manifest}, sort_keys=False), encoding="utf-8"
    )


def prepare(base, gtsrb, gtsdb, output):
    if output.exists():
        raise FileExistsError(f"{output} already exists. Use an unused --output directory.")
    base_names = yaml.safe_load((base / "data.yaml").read_text())["names"]
    with ZipFile(gtsrb) as archive:
        english_names = read_class_names(archive)
        new_names = {i: f"GTSRB {i:02d} - {english_names[i]}" for i in range(len(LABELS)) if i not in CAMERA_CLASSES}
        names = [*base_names, *new_names.values()]
        if len(names) != len(set(names)):
            raise ValueError("Expected a base detector dataset without the new GTSRB classes.")
        class_ids = {i: names.index(name) for i, name in {**CAMERA_CLASSES, **new_names}.items()}
        new_ids = {i: class_ids[i] for i in new_names}
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".prepare-gtsrb-", dir=output.parent) as temp:
            staged = Path(temp) / "dataset"
            copy_base(base, staged)
            road_test = road_examples(gtsdb, staged, class_ids)
            train = add_composites(base, staged, image_patches(archive, "train.p", new_ids), 72, prefix="gtsrb")
            val = add_composites(
                base, staged, image_patches(archive, "valid.p", new_ids), 10, split="val", prefix="gtsrb"
            )
            add_composites(
                base, staged, image_patches(archive, "test.p", class_ids), 20, split="test", prefix="gtsrb"
            )
            cropped_test = sorted(
                f"./images/test/{file.name}" for file in (staged / "images/test").glob("gtsrb_composite_*.jpg")
            )
            config = {split: f"images/{split}" for split in ("train", "val", "test")}
            config["names"] = names
            (staged / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            write_test_config(staged, config, "gtsdb", road_test)
            write_test_config(staged, config, "gtsrb", cropped_test)
            staged.rename(output)
    return len(names), train, val, len(road_test), len(cropped_test)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "dataset" / "detection_belgium")
    parser.add_argument("--gtsrb", type=Path, default=ARCHIVE)
    parser.add_argument("--gtsdb", type=Path, default=ROOT / "raw_data" / "gtsdb")
    parser.add_argument("--output", type=Path, default=ROOT / "dataset" / "detection_gtsrb")
    args = parser.parse_args()
    try:
        classes, train, val, road_test, cropped_test = prepare(args.base, args.gtsrb, args.gtsdb, args.output)
    except (OSError, ValueError, KeyError, EOFError, pickle.UnpicklingError, BadZipFile, cv2.error, yaml.YAMLError) as error:
        parser.exit(1, f"Error preparing GTSRB: {error}\n")
    print(f"Prepared {args.output} with {classes} classes, {train} composites for train and {val} for val.")
    print(f"Test sets include {road_test} GTSDB road frames and {cropped_test} GTSRB composites.")


if __name__ == "__main__":
    main()

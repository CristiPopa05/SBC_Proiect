"""Add Yield and Priority road to the YOLO dataset using GTSDB road scenes."""

import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import yaml


ROOT = Path(__file__).resolve().parents[1]
GTSDB_NAMES = {
    0: "Speed Limit 20",
    1: "Speed Limit 30",
    2: "Speed Limit 50",
    3: "Speed Limit 60",
    4: "Speed Limit 70",
    5: "Speed Limit 80",
    7: "Speed Limit 100",
    8: "Speed Limit 120",
    12: "Priority road",
    13: "Yield",
    14: "Stop",
}
NEW_CLASSES = ("Priority road", "Yield")
IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}


def read_annotations(directory, names):
    class_ids = {index: names.index(name) for index, name in GTSDB_NAMES.items() if name in names}
    boxes = defaultdict(list)
    for line in (directory / "gt.txt").read_text().splitlines():
        if not line.strip():
            continue
        filename, x1, y1, x2, y2, sign = line.split(";")
        sign = int(sign)
        if sign in class_ids:
            boxes[Path(filename).stem].append((class_ids[sign], int(x1), int(y1), int(x2), int(y2)))
    return boxes


def read_image(path):
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Cannot read image {path}.")
    return image


def write_example(output, split, name, image, boxes):
    height, width = image.shape[:2]
    labels = []
    for sign, x1, y1, x2, y2 in boxes:
        values = (
            (x1 + x2) / (2 * width),
            (y1 + y2) / (2 * height),
            (x2 - x1) / width,
            (y2 - y1) / height,
        )
        labels.append(f"{sign} " + " ".join(f"{value:.6f}" for value in values))
    path = output / "images" / split / f"{name}.jpg"
    if not cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise OSError(f"Could not write {path}.")
    (output / "labels" / split / f"{name}.txt").write_text("\n".join(labels) + "\n")


def crop_scene(image, boxes, target):
    _, x1, y1, x2, y2 = target
    height, width = image.shape[:2]
    side = min(height, width, max(160, 4 * max(x2 - x1, y2 - y1)))
    left = max(0, min(width - side, (x1 + x2 - side) // 2))
    top = max(0, min(height - side, (y1 + y2 - side) // 2))
    cropped = []
    for sign, x1, y1, x2, y2 in boxes:
        x1, y1 = max(0, x1 - left), max(0, y1 - top)
        x2, y2 = min(side, x2 - left), min(side, y2 - top)
        if x2 > x1 and y2 > y1:
            cropped.append((sign, x1, y1, x2, y2))
    return image[top:top + side, left:left + side], cropped


def add_road_scenes(gtsdb, output, names):
    patches = defaultdict(list)
    test_images = []
    counts = defaultdict(int)
    new_ids = {names.index(name) for name in NEW_CLASSES}
    for stem, boxes in sorted(read_annotations(gtsdb, names).items()):
        targets = [box for box in boxes if box[0] in new_ids]
        if not targets:
            continue
        filename = gtsdb / f"{stem}.jpg"
        if not filename.is_file():
            filename = gtsdb / f"{stem}.ppm"
        if not filename.is_file():
            raise FileNotFoundError(f"Missing GTSDB frame {stem} in {gtsdb}.")
        index = int(stem)
        # Keep the official evaluation split and use a contiguous training block for validation.
        split = "test" if index >= 600 else "val" if 400 <= index < 500 else "train"
        image = read_image(filename)
        name = f"gtsdb_{stem}"
        write_example(output, split, name, image, boxes)
        counts[split] += 1
        if split == "test":
            test_images.append(f"./images/test/{name}.jpg")
            continue
        for i, target in enumerate(targets):
            write_example(output, split, f"{name}_crop_{i}", *crop_scene(image, boxes, target))
            if split == "train":
                sign, x1, y1, x2, y2 = target
                patches[sign].append(image[y1:y2, x1:x2].copy())
    if set(patches) != new_ids or set(counts) != {"train", "val", "test"}:
        raise ValueError("Expected both classes and all three GTSDB splits.")
    (output / "gtsdb-test.txt").write_text("\n".join(test_images) + "\n")
    return patches, dict(counts)


def background_boxes(label, width, height):
    boxes = []
    for line in label.read_text().splitlines():
        if not line.strip():
            continue
        sign, x, y, w, h = line.split()
        x, y, w, h = map(float, (x, y, w, h))
        boxes.append((
            int(sign),
            max(0, (x - w / 2) * width),
            max(0, (y - h / 2) * height),
            min(width, (x + w / 2) * width),
            min(height, (y + h / 2) * height),
        ))
    return boxes


def add_composites(base, output, patches, count, *, split="train", prefix="gtsdb"):
    rng = random.Random(42)
    backgrounds = sorted(
        path
        for path in (base / "images" / split).iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    added = 0
    for sign, sources in sorted(patches.items()):
        for index in range(count):
            background = rng.choice(backgrounds)
            image = read_image(background)
            height, width = image.shape[:2]
            label = base / "labels" / split / f"{background.stem}.txt"
            boxes = background_boxes(label, width, height)
            patch = rng.choice(sources)
            aspect = patch.shape[1] / patch.shape[0]
            scale = min(width, height) * rng.uniform(0.07, 0.50)
            w = max(2, round(scale * min(1, aspect)))
            h = max(2, round(scale * min(1, 1 / aspect)))
            for _ in range(25):
                x, y = rng.randint(0, width - w), rng.randint(0, height - h)
                if any(
                    x < x2 and x + w > x1 and y < y2 and y + h > y1
                    for _, x1, y1, x2, y2 in boxes
                ):
                    continue
                center = (x + w // 2, y + h // 2)
                if w >= 12 and h >= 12 and index % 3 == 0:
                    patch = cv2.resize(patch, (w, h), interpolation=cv2.INTER_CUBIC)
                    mask = patch[:, :, 0].copy()
                    mask.fill(255)
                    image = cv2.seamlessClone(patch, image, mask, center, cv2.MIXED_CLONE)
                else:
                    image[y:y + h, x:x + w] = cv2.resize(patch, (w, h), interpolation=cv2.INTER_CUBIC)
                boxes.append((sign, x, y, x + w, y + h))
                name = f"{prefix}_composite_{sign}_{index:04d}"
                write_example(output, split, name, image, boxes)
                added += 1
                break
    return added


def prepare(base, gtsdb, output, composites):
    if output.exists():
        raise FileExistsError(f"{output} already exists. Use a new --output directory.")
    names = yaml.safe_load((base / "data.yaml").read_text())["names"]
    if not isinstance(names, list) or any(name in names for name in NEW_CLASSES):
        raise ValueError("Expected the original YOLO dataset with a list of class names.")
    names = [*names, *NEW_CLASSES]
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".prepare-priority-", dir=output.parent) as directory:
        staged = Path(directory) / "dataset"
        config = {split: f"images/{split}" for split in ("train", "val", "test")}
        for split in config:
            for kind in ("images", "labels"):
                shutil.copytree(base / kind / split, staged / kind / split)
        patches, counts = add_road_scenes(gtsdb, staged, names)
        added = add_composites(base, staged, patches, composites)
        config["names"] = names
        (staged / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        (staged / "data_gtsdb_test.yaml").write_text(
            yaml.safe_dump({**config, "test": "gtsdb-test.txt"}, sort_keys=False)
        )
        staged.rename(output)
    return counts, added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "dataset" / "detection_grouped")
    parser.add_argument("--gtsdb", type=Path, default=ROOT / "raw_data" / "gtsdb")
    parser.add_argument("--output", type=Path, default=ROOT / "dataset" / "detection_priority")
    parser.add_argument("--composites", type=int, default=300, help="Training composites per new class")
    args = parser.parse_args()
    if args.composites < 0:
        parser.error("--composites must be zero or positive.")
    try:
        counts, composites = prepare(args.base, args.gtsdb, args.output, args.composites)
    except (OSError, ValueError, KeyError, cv2.error, yaml.YAMLError) as error:
        parser.exit(1, f"Error preparing priority classes: {error}\n")
    print(f"Prepared {args.output}. GTSDB road frames: {counts}. Synthetic training frames: {composites}.")


if __name__ == "__main__":
    main()

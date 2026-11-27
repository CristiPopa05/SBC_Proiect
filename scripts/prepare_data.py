"""Prepare the Kaggle Traffic Signs Detection archive for Ultralytics YOLO."""

import argparse
import re
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PurePosixPath("car")
# Keep related images in the first split they appear in, starting with test.
SPLITS = {"test": "test", "valid": "val", "train": "train"}
IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}
GTSRB_FRAME = re.compile(r"(\d{5}_\d{5})_\d{5}_png", re.IGNORECASE)


def read_classes(archive):
    config = yaml.safe_load(archive.read(str(SOURCE_ROOT / "data.yaml")))
    names = config.get("names") if isinstance(config, dict) else None
    if not isinstance(names, list) or not names or any(
        not isinstance(name, str) or not name.strip() for name in names
    ):
        raise ValueError("The source data.yaml must contain a list of class names.")
    if config.get("nc") != len(names) or len(set(names)) != len(names):
        raise ValueError("The source data.yaml has inconsistent class names or count.")
    return names


def files_by_stem(members, directory, extensions):
    files = {}
    for path, member in members:
        if path.parent != directory or path.suffix.lower() not in extensions:
            continue
        if path.stem in files or "\\" in path.name or ":" in path.name:
            raise ValueError(f"Duplicate or invalid dataset filename: {member.filename}")
        files[path.stem] = member
    return files


def validate_labels(contents, source, class_count):
    for line_number, line in enumerate(contents.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            class_id, *coordinates = line.split()
            x, y, width, height = map(float, coordinates)
            valid = (
                0 <= int(class_id) < class_count
                and 0 <= x <= 1
                and 0 <= y <= 1
                and 0 < width <= 1
                and 0 < height <= 1
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f"Invalid YOLO label in {source} on line {line_number}.")


def source_group(stem):
    original = stem.partition(".rf.")[0]
    # GTSRB filenames encode the class, the sign's track and the frame number.
    frame = GTSRB_FRAME.fullmatch(original)
    return frame[1] if frame else original


def prepare_dataset(archive_path, output):
    if output.exists():
        raise FileExistsError(f"{output} already exists. Use an unused --output directory.")

    output.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    image_splits = {}
    source_splits = {}
    excluded = 0
    with ZipFile(archive_path) as archive, TemporaryDirectory(
        prefix=".prepare-", dir=output.parent
    ) as temp:
        names = read_classes(archive)
        members = [
            (PurePosixPath(member.filename), member)
            for member in archive.infolist()
            if not member.is_dir()
        ]
        staged = Path(temp) / "dataset"
        config = {split: f"images/{split}" for split in ("train", "val", "test")}
        config["names"] = names
        for source_split, split in SPLITS.items():
            source = SOURCE_ROOT / source_split
            images = files_by_stem(members, source / "images", IMAGE_EXTENSIONS)
            labels = files_by_stem(members, source / "labels", {".txt"})
            if not images or images.keys() != labels.keys():
                raise ValueError(f"{source} must contain matching images and labels.")

            image_dir = staged / "images" / split
            label_dir = staged / "labels" / split
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            counts[split] = 0
            for stem, image in images.items():
                image_bytes = archive.read(image)
                digest = sha256(image_bytes).digest()
                group = source_group(stem)
                if (
                    image_splits.get(digest, split) != split
                    or source_splits.get(group, split) != split
                ):
                    excluded += 1
                    continue
                image_splits[digest] = split
                source_splits[group] = split
                label = labels[stem]
                contents = archive.read(label)
                validate_labels(contents, label.filename, len(names))
                (label_dir / f"{stem}.txt").write_bytes(contents)
                image_name = PurePosixPath(image.filename).name
                (image_dir / image_name).write_bytes(image_bytes)
                counts[split] += 1

            if not counts[split]:
                raise ValueError(f"{source} has no images after grouping sources across splits.")

        (staged / "data.yaml").write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        staged.rename(output)
    return counts, len(names), excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT / "raw_data" / "cardetection" / "cardetection.zip",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dataset" / "detection")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    try:
        counts, class_count, excluded = prepare_dataset(args.archive.expanduser(), output)
    except (OSError, ValueError, BadZipFile, KeyError, yaml.YAMLError) as error:
        parser.exit(1, f"Error preparing the dataset: {error}\n")

    sizes = ", ".join(f"{split}={counts[split]}" for split in ("train", "val", "test"))
    print(f"Prepared {output} ({sizes}, {class_count} classes).")
    print(f"Excluded {excluded} files with matching images or source groups in another split.")


if __name__ == "__main__":
    main()

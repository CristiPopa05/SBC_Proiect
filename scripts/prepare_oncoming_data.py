"""Extend the detector with the two oncoming-priority signs in BelgiumTS."""

import argparse
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

import yaml

from scripts.prepare_belgium_data import CAMERAS, add_road_frames, read_crops, read_road_boxes
from scripts.prepare_gtsrb_data import copy_base, write_test_config
from scripts.prepare_priority_data import add_composites


ROOT = Path(__file__).resolve().parents[1]
ONCOMING_CLASSES = {
    "B19": (20, "Yield to oncoming traffic"),
    "B21": (44, "Priority over oncoming traffic"),
}


def prepare(base, source, output):
    if output.exists():
        raise FileExistsError(f"{output} already exists. Use an unused --output directory.")
    names = yaml.safe_load((base / "data.yaml").read_text())["names"]
    names = [*names, *(name for _, name in ONCOMING_CLASSES.values())]
    if len(set(names)) != len(names):
        raise ValueError("The base dataset already includes an oncoming-priority class.")
    classes = {name: index for index, name in enumerate(names)}
    crops = read_crops(source, classes, ONCOMING_CLASSES)
    road_stems = {
        "btsd_" + PurePosixPath(file).with_suffix("").as_posix().replace("/", "_")
        for file in read_road_boxes(source, classes, ONCOMING_CLASSES)
    }
    config = {split: f"images/{split}" for split in ("train", "val", "test")}
    config["names"] = names
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".prepare-oncoming-", dir=output.parent) as temporary:
        staged = Path(temporary) / "dataset"
        copy_base(base, staged, replay_per_class=40, replace_gtsdb=False)
        for split in ("train", "val", "test"):
            for stem in road_stems:
                (staged / "images" / split / f"{stem}.jpg").unlink(missing_ok=True)
                (staged / "labels" / split / f"{stem}.txt").unlink(missing_ok=True)
        counts, test_images = add_road_frames(source, staged, classes, ONCOMING_CLASSES, (*CAMERAS, "camera05.tar"))
        train = add_composites(base, staged, crops["train"], 160, prefix="oncoming")
        val = add_composites(base, staged, crops["val"], 25, split="val", prefix="oncoming")
        (staged / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        write_test_config(staged, config, "oncoming", test_images)
        staged.rename(output)
    print(f"Prepared {len(names)} classes. Road frames: {dict(counts)}. Composites: train={train}, val={val}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "dataset" / "detection_gtsrb")
    parser.add_argument("--source", type=Path, default=ROOT / "raw_data" / "belgiumts")
    parser.add_argument("--output", type=Path, default=ROOT / "dataset" / "detection_oncoming")
    args = parser.parse_args()
    prepare(args.base, args.source, args.output)


if __name__ == "__main__":
    main()

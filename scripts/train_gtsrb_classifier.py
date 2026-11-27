"""Train a classifier on GTSRB sign crops and background crops."""

import argparse
import random
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
import yaml

from gtsrb import ARCHIVE, CAMERA_CLASSES, LABELS, read_samples
from gtsrb_classifier import CLASSIFIER, sign_crop
from scripts.prepare_priority_data import background_boxes, read_image


ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = len(LABELS)


def conv(in_channels, out_channels, stride=1):
    return [
        nn.Conv2d(in_channels, out_channels, 3, stride=stride, padding=1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(),
    ]


def classifier():
    return nn.Sequential(
        *conv(3, 24, stride=2),
        *conv(24, 32),
        *conv(32, 48),
        *conv(48, 64, stride=2),
        *conv(64, 80, stride=2),
        nn.Flatten(),
        nn.Linear(1280, 144),
        nn.BatchNorm1d(144),
        nn.ReLU(),
        nn.Dropout(0.1),
        nn.Linear(144, BACKGROUND + 1),
    )


def negative_crops(base, split, count):
    names = yaml.safe_load((base / "data.yaml").read_text())["names"]
    excluded_classes = {i for i, name in enumerate(names) if name not in CAMERA_CLASSES.values()}
    candidates = sorted((base / "images" / split).glob("*.jpg"))
    rng = random.Random(81)
    crops = []
    for path in rng.sample(candidates, min(count, len(candidates))):
        frame = read_image(path)
        height, width = frame.shape[:2]
        boxes = background_boxes(base / "labels" / split / f"{path.stem}.txt", width, height)
        for index, x1, y1, x2, y2 in boxes:
            if index in excluded_classes:
                crop = sign_crop(frame, (x1, y1, x2, y2))
                if crop is not None:
                    crops.append(crop)
        max_size = min(height, width) // 3
        if max_size < 18:
            continue
        for _ in range(5):
            size = rng.randint(18, max_size)
            x, y = rng.randint(0, width - size), rng.randint(0, height - size)
            margin = size / 8
            if any(
                x - margin < x2 and x + size + margin > x1
                and y - margin < y2 and y + size + margin > y1
                for _, x1, y1, x2, y2 in boxes
            ):
                continue
            crops.append(sign_crop(frame, (x, y, x + size, y + size)))
            break
    return np.stack(crops)


def samples(archive, member, base, split, negatives):
    images, labels = read_samples(archive, member)
    background = negative_crops(base, split, negatives)
    all_images = torch.from_numpy(np.concatenate((images, background))).permute(0, 3, 1, 2)
    all_labels = torch.from_numpy(np.concatenate((labels, np.full(len(background), BACKGROUND, dtype=np.uint8))))
    return all_images, all_labels.long()


def augment(pixels):
    count = len(pixels)
    angle = torch.empty(count).uniform_(-0.20, 0.20)
    scale = torch.empty(count).uniform_(0.86, 1.15)
    matrix = torch.zeros(count, 2, 3)
    matrix[:, 0, 0] = matrix[:, 1, 1] = angle.cos() * scale
    matrix[:, 0, 1] = angle.sin() * scale
    matrix[:, 1, 0] = -matrix[:, 0, 1]
    matrix[:, :, 2].uniform_(-0.08, 0.08)
    grid = F.affine_grid(matrix, pixels.shape, align_corners=False)
    translated = F.grid_sample(pixels, grid, padding_mode="border", align_corners=False)
    gains = torch.empty(count, 3, 1, 1).uniform_(0.7, 1.3)
    return (translated * gains).clamp(0, 1)


def validate(model, images, labels):
    model.eval()
    with torch.inference_mode():
        predictions = torch.cat([model(batch.float() / 255).argmax(1) for batch in images.split(256)])
    totals = torch.bincount(labels, minlength=BACKGROUND + 1)
    correct = torch.bincount(labels[predictions == labels], minlength=BACKGROUND + 1)
    return float((correct / totals.clamp_min(1)).mean()), float((predictions == labels).float().mean())


def train(archive_path, base, output, epochs):
    torch.set_num_threads(2)
    torch.manual_seed(18)
    with ZipFile(archive_path) as archive:
        images, labels = samples(archive, "train.p", base, "train", 1800)
        val_images, val_labels = samples(archive, "valid.p", base, "val", 350)
    print(f"Training on {len(labels)} crops. Validation on {len(val_labels)} crops.", flush=True)
    model = classifier()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs, eta_min=0.00015)
    weights = torch.bincount(labels, minlength=BACKGROUND + 1).float().clamp_min(1).rsqrt()
    output.parent.mkdir(parents=True, exist_ok=True)
    best = 0.0
    for epoch in range(epochs):
        model.train()
        for index in torch.randperm(len(labels)).split(192):
            if len(index) < 2:
                continue
            batch = augment(images[index].float() / 255)
            optimizer.zero_grad(set_to_none=True)
            loss = F.cross_entropy(model(batch), labels[index], weight=weights)
            loss.backward()
            optimizer.step()
        schedule.step()
        mean_recall, accuracy = validate(model, val_images, val_labels)
        print(f"Epoch {epoch + 1}/{epochs}: balanced recall={mean_recall:.3f}, accuracy={accuracy:.3f}", flush=True)
        if mean_recall > best:
            best = mean_recall
            with TemporaryDirectory(dir=output.parent) as scratch:
                staged = Path(scratch) / output.name
                torch.jit.script(model).save(str(staged))
                staged.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "dataset" / "detection_belgium")
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, default=CLASSIFIER)
    parser.add_argument("--epochs", type=int, default=8)
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be positive.")
    train(args.archive, args.base, args.output, args.epochs)


if __name__ == "__main__":
    main()

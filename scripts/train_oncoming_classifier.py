"""Teach the existing crop classifier the two additional BelgiumTS classes."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from gtsrb import ARCHIVE, read_samples
from gtsrb_classifier import CLASSIFIER, ONCOMING_CLASSIFIER, ONCOMING_LABELS, load_classifier
from scripts.prepare_belgium_data import read_crops
from scripts.prepare_oncoming_data import ONCOMING_CLASSES
from scripts.train_gtsrb_classifier import BACKGROUND, augment, classifier, negative_crops


ROOT = Path(__file__).resolve().parents[1]


def train(source, base, output):
    torch.set_num_threads(3)
    torch.manual_seed(61)
    rng = np.random.default_rng(61)
    model = classifier()
    model.load_state_dict(load_classifier(CLASSIFIER).state_dict())
    model.eval()
    features = model[:-1]
    original = model[-1]
    targets = dict(zip((name for _, name in ONCOMING_CLASSES.values()), ONCOMING_LABELS))
    added = read_crops(source, targets, ONCOMING_CLASSES)["train"]
    with ZipFile(ARCHIVE) as archive:
        old_images, old_labels = read_samples(archive, "train.p")
    examples = []
    class_ids = []
    for index in range(BACKGROUND):
        indices = np.flatnonzero(old_labels == index)
        chosen = rng.choice(indices, size=min(len(indices), 140), replace=False)
        examples.extend(old_images[chosen])
        class_ids.extend([index] * len(chosen))
    negatives = negative_crops(base, "train", 700)
    examples.extend(negatives)
    class_ids.extend([BACKGROUND] * len(negatives))

    def embed(images, augmented=False):
        pixels = torch.from_numpy(np.stack(images)).permute(0, 3, 1, 2).float() / 255
        with torch.no_grad():
            return torch.cat([features(augment(batch) if augmented else batch) for batch in pixels.split(256)])

    embeddings = [embed(examples)]
    for index, crops in sorted(added.items()):
        resized = [cv2.cvtColor(cv2.resize(crop, (32, 32)), cv2.COLOR_BGR2RGB) for crop in crops]
        embeddings.append(embed(resized * 26, augmented=True))
        class_ids.extend([index] * (len(resized) * 26))
    data = torch.cat(embeddings)
    labels = torch.tensor(class_ids)
    with torch.no_grad():
        existing_logits = original(data)
    extension = nn.Linear(original.in_features, len(targets))
    optimizer = torch.optim.LBFGS(extension.parameters(), max_iter=100, line_search_fn="strong_wolfe")
    weights = torch.bincount(labels, minlength=max(targets.values()) + 1).float().clamp_min(1).rsqrt()

    def objective():
        optimizer.zero_grad()
        logits = torch.cat((existing_logits, extension(data)), dim=1)
        loss = F.cross_entropy(logits, labels, weight=weights) + 0.001 * extension.weight.square().mean()
        loss.backward()
        return loss

    optimizer.step(objective)
    merged = nn.Linear(original.in_features, original.out_features + extension.out_features)
    with torch.no_grad():
        merged.weight.copy_(torch.cat((original.weight, extension.weight)))
        merged.bias.copy_(torch.cat((original.bias, extension.bias)))
    model[-1] = merged
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / output.name
        torch.jit.script(model.eval()).save(str(staged))
        staged.replace(output)
    print(f"Saved crop classifier with {len(targets)} extra classes to {output}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "raw_data" / "belgiumts")
    parser.add_argument("--base", type=Path, default=ROOT / "dataset" / "detection_belgium")
    parser.add_argument("--output", type=Path, default=ONCOMING_CLASSIFIER)
    args = parser.parse_args()
    train(args.source, args.base, args.output)

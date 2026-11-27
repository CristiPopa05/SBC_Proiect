"""Prepare sign crops for the GTSRB classifier."""

from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np


CLASSIFIER = Path(__file__).resolve().parent / "models" / "gtsrb_classifier.pt"
ONCOMING_CLASSIFIER = CLASSIFIER.with_name("oncoming_classifier.pt")
ONCOMING_LABELS = {44: "oncoming_has_priority", 45: "priority_over_oncoming"}
CROP_SIZE = 32
CROP_PADDING = (0.10, 0.0, 0.21)


class CropPrediction(NamedTuple):
    class_id: int
    confidence: float
    margin: float


def sign_crop(frame, box, padding=0.10):
    x1, y1, x2, y2 = box
    height, width = frame.shape[:2]
    dx, dy = (x2 - x1) * padding, (y2 - y1) * padding
    left, top = max(0, int(x1 - dx)), max(0, int(y1 - dy))
    right, bottom = min(width, round(x2 + dx)), min(height, round(y2 + dy))
    if right <= left or bottom <= top:
        return None
    crop = frame[top:bottom, left:right]
    resized = cv2.resize(crop, (CROP_SIZE, CROP_SIZE), interpolation=cv2.INTER_LINEAR)
    return cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)


def load_classifier(path=CLASSIFIER):
    if not path.is_file():
        return None
    import torch

    return torch.jit.load(str(path), map_location="cpu").eval()


def classify_crops(model, frame, boxes):
    import torch

    crops = []
    indices = []
    for index, box in enumerate(boxes):
        x1, y1, x2, y2 = box
        if min(x2 - x1, y2 - y1) < 16:
            continue
        views = [sign_crop(frame, box, padding) for padding in CROP_PADDING]
        if all(view is not None for view in views):
            crops.extend(views)
            indices.append(index)
    if not crops:
        return {}
    pixels = torch.from_numpy(np.stack(crops)).permute(0, 3, 1, 2).float() / 255
    with torch.inference_mode():
        probabilities = model(pixels).softmax(dim=-1).reshape(len(indices), len(CROP_PADDING), -1)
        winners = probabilities.argmax(dim=-1)
        classes = winners.mode(dim=-1).values
        votes = (winners == classes[:, None]).sum(dim=-1)
        median = probabilities.median(dim=1).values
        confidence = median.gather(1, classes[:, None]).squeeze(1)
        median.scatter_(1, classes[:, None], 0.0)
        margins = confidence - median.max(dim=-1).values
    return {
        index: CropPrediction(label, score, margin)
        for index, label, score, margin, votes_for_label in zip(
            indices, classes.tolist(), confidence.tolist(), margins.tolist(), votes.tolist()
        )
        if votes_for_label >= 2
    }

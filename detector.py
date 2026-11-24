"""Load the local traffic-sign model for camera inference."""

import os
from functools import lru_cache
from pathlib import Path
from threading import Lock


ROOT = Path(__file__).resolve().parent
CHECKPOINT = ROOT / "models" / "best.pt"


@lru_cache(maxsize=1)
def load_detector(checkpoint=CHECKPOINT):
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runs" / ".ultralytics"))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    import torch
    from ultralytics import YOLO

    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "0"
    else:
        device = "cpu"
    return YOLO(str(checkpoint), task="detect"), device, Lock()

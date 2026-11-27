"""Train YOLOv8n on full frames and save the best traffic sign detector."""

import argparse
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
BASE_WEIGHTS = ROOT / "models" / "yolov8n.pt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "dataset" / "detection" / "data.yaml")
    parser.add_argument(
        "--weights", type=Path, default=BASE_WEIGHTS, help="Starting checkpoint for fine-tuning"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "models" / "best.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--warmup-epochs", type=float, default=3.0)
    parser.add_argument("--device", default="auto", help="auto, mps, cpu, or a CUDA device index")
    args = parser.parse_args()

    data = args.data.expanduser().resolve()
    if not data.is_file():
        parser.error(f"Dataset configuration missing at {data}. Run scripts/prepare_data.py first.")
    if min(args.epochs, args.imgsz, args.batch) < 1:
        parser.error("--epochs, --imgsz, and --batch must be positive.")
    if not args.warmup_epochs >= 0:
        parser.error("--warmup-epochs must be zero or positive.")
    weights = args.weights.expanduser().resolve()
    if weights != BASE_WEIGHTS and not weights.is_file():
        parser.error(f"Starting checkpoint missing at {weights}.")

    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runs" / ".ultralytics"))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    import torch
    from ultralytics import YOLO

    device = args.device
    if device == "auto":
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "0"
        else:
            device = "cpu"

    output = args.output.expanduser().resolve()
    weights.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights), task="detect")
    model.train(
        data=str(data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        warmup_epochs=args.warmup_epochs,
        device=device,
        # Mirroring turns speed-limit digits and STOP lettering backwards.
        fliplr=0.0,
        close_mosaic=min(10, args.epochs // 5),
        workers=0,
        project=str(ROOT / "runs" / "detect"),
        name="traffic_signs",
    )
    best = Path(model.trainer.best)
    if not best.is_file():
        raise FileNotFoundError(f"Training finished without the expected checkpoint: {best}")

    with TemporaryDirectory(prefix=".checkpoint-", dir=output.parent) as temp:
        staged = Path(temp) / output.name
        shutil.copy2(best, staged)
        staged.replace(output)
    print(f"Saved the best checkpoint to {output}. Run artifacts: {model.trainer.save_dir}")


if __name__ == "__main__":
    main()

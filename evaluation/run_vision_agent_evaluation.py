#!/usr/bin/env python3
"""Reproduce the five-case chest and skin vision-agent evaluations."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

CHEST_CASES = (
    ("covid-example-01.jpg", "covid19"),
    ("covid-example-02.jpeg", "covid19"),
    ("covid-19-pneumonia-101.png", "covid19"),
    ("NORMAL2-IM-0362-0001.jpeg", "normal"),
    ("NORMAL2-IM-0374-0001.jpeg", "normal"),
)
SKIN_CASES = (
    "ISIC_0012558.jpg",
    "ISIC_0012559.jpg",
    "ISIC_0012560.jpg",
    "ISIC_0012563.jpg",
    "ISIC_0012564.jpg",
)
CHEST_IMAGE_DIR = REPOSITORY_ROOT / "sample_images/chest_x-ray_covid_and_normal"
SKIN_IMAGE_DIR = REPOSITORY_ROOT / "sample_images/skin_lesion_images"
CHEST_CHECKPOINT = REPOSITORY_ROOT / (
    "agents/image_analysis_agent/chest_xray_agent/models/covid_chest_xray_model.pth"
)
SKIN_CHECKPOINT = REPOSITORY_ROOT / (
    "agents/image_analysis_agent/skin_lesion_agent/models/checkpointN25_.pth.tar"
)
CSV_FIELDS = (
    "agent",
    "image",
    "reference_label",
    "prediction",
    "correct",
    "foreground_percentage",
    "nonempty_mask",
)


def probability(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number between 0 and 1") from exc
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1 inclusive")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "evaluation/results",
        help="artifact directory (default: evaluation/results)",
    )
    parser.add_argument("--skin-threshold", type=probability, default=0.5)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    return parser.parse_args()


def require_inputs() -> None:
    missing_images = [
        path
        for path in (
            *(CHEST_IMAGE_DIR / name for name, _ in CHEST_CASES),
            *(SKIN_IMAGE_DIR / name for name in SKIN_CASES),
        )
        if not path.is_file()
    ]
    if missing_images:
        joined = "\n  ".join(str(path) for path in missing_images)
        raise FileNotFoundError(f"Required evaluation image(s) are missing:\n  {joined}")
    if not CHEST_CHECKPOINT.is_file():
        raise FileNotFoundError(f"Chest X-ray checkpoint is missing: {CHEST_CHECKPOINT}")


def exact_binomial_interval(successes: int, trials: int, confidence: float = 0.95) -> list[float]:
    from scipy.stats import beta

    alpha = 1.0 - confidence
    lower = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    return [lower, upper]


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def environment_details(torch: Any, torchvision: Any, cv2: Any, numpy: Any) -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "opencv": cv2.__version__,
        "numpy": numpy.__version__,
    }


def main() -> int:
    args = parse_args()
    try:
        import cv2
        import numpy as np
        import torch
        import torchvision
        from agents.image_analysis_agent.chest_xray_agent.covid_chest_xray_inference import (
            ChestXRayClassification,
        )
        from agents.image_analysis_agent.skin_lesion_agent.skin_lesion_inference import (
            SkinLesionSegmentation,
        )
    except (ImportError, OSError) as exc:
        print(f"Dependency error: {exc}\nInstall the project requirements and retry.", file=sys.stderr)
        return 2

    try:
        require_inputs()
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("--device cuda was requested, but CUDA is not available")

        print(f"Device: {args.device}")
        print("Loading chest X-ray checkpoint...")
        chest_agent = ChestXRayClassification(str(CHEST_CHECKPOINT), device=torch.device(args.device))
        records: list[dict[str, Any]] = []
        for filename, truth in CHEST_CASES:
            prediction = chest_agent.predict(str(CHEST_IMAGE_DIR / filename))
            if prediction is None:
                raise RuntimeError(f"Chest X-ray inference failed for {filename}")
            correct = prediction == truth
            records.append(
                {
                    "agent": "chest_xray",
                    "image": filename,
                    "reference_label": truth,
                    "prediction": prediction,
                    "correct": correct,
                    "foreground_percentage": "",
                    "nonempty_mask": "",
                }
            )
            print(f"Chest {filename}: truth={truth}, prediction={prediction}, correct={correct}")

        tp = sum(r["reference_label"] == "covid19" and r["prediction"] == "covid19" for r in records)
        tn = sum(r["reference_label"] == "normal" and r["prediction"] == "normal" for r in records)
        fp = sum(r["reference_label"] == "normal" and r["prediction"] == "covid19" for r in records)
        fn = sum(r["reference_label"] == "covid19" and r["prediction"] == "normal" for r in records)
        accuracy = ratio(tp + tn, len(CHEST_CASES))
        sensitivity = ratio(tp, tp + fn)
        specificity = ratio(tn, tn + fp)
        precision = ratio(tp, tp + fp)
        f1 = None if precision is None or sensitivity is None or precision + sensitivity == 0 else 2 * precision * sensitivity / (precision + sensitivity)

        print("Loading skin-lesion checkpoint (downloaded automatically if absent)...")
        skin_agent = SkinLesionSegmentation(str(SKIN_CHECKPOINT), device=args.device)
        skin_records = []
        for filename in SKIN_CASES:
            mask = skin_agent.predict_mask(str(SKIN_IMAGE_DIR / filename), threshold=args.skin_threshold)
            foreground_percentage = float(np.count_nonzero(mask) / mask.size * 100.0)
            nonempty = bool(np.any(mask))
            record = {
                "agent": "skin_lesion",
                "image": filename,
                "reference_label": "",
                "prediction": "",
                "correct": "",
                "foreground_percentage": f"{foreground_percentage:.4f}",
                "nonempty_mask": nonempty,
            }
            records.append(record)
            skin_records.append(record)
            print(f"Skin  {filename}: foreground={foreground_percentage:.2f}%, nonempty={nonempty}")

        chest_summary = {
            "positive_class": "covid19",
            "confusion_counts": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "metrics": {
                "accuracy": accuracy,
                "sensitivity": sensitivity,
                "specificity": specificity,
                "precision": precision,
                "f1": f1,
                "accuracy_exact_binomial_95_ci": exact_binomial_interval(tp + tn, len(CHEST_CASES)),
            },
        }
        summary = {
            "models": {
                "chest_xray": {"architecture": "DenseNet-121", "checkpoint": str(CHEST_CHECKPOINT.relative_to(REPOSITORY_ROOT))},
                "skin_lesion": {"architecture": "U-Net", "checkpoint": str(SKIN_CHECKPOINT.relative_to(REPOSITORY_ROOT))},
            },
            "thresholds": {"skin_probability": args.skin_threshold},
            "environment": {**environment_details(torch, torchvision, cv2, np), "device": args.device},
            "sample_counts": {"chest_xray": len(CHEST_CASES), "skin_lesion": len(SKIN_CASES), "total": len(records)},
            "chest_xray": chest_summary,
            "skin_lesion": {
                "successful_inferences": len(skin_records),
                "nonempty_masks": sum(r["nonempty_mask"] for r in skin_records),
                "foreground_percentage": {r["image"]: float(r["foreground_percentage"]) for r in skin_records},
                "segmentation_accuracy": None,
                "accuracy_note": "Expert reference masks are unavailable; foreground percentage is descriptive, not segmentation accuracy.",
            },
        }

        args.output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = args.output_dir / "vision_agent_results.csv"
        json_path = args.output_dir / "vision_agent_summary.json"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(records)
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
            handle.write("\n")

        print(f"\nProcessed {len(records)}/10 cases successfully.")
        print(f"Chest confusion counts: TP={tp}, TN={tn}, FP={fp}, FN={fn}; accuracy={accuracy:.1%}")
        print(f"Artifacts: {csv_path}\n           {json_path}")
        return 0
    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

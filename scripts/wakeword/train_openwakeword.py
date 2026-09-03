"""Training plan and manifest generator for custom openWakeWord Heyino model.

Provides configuration generation for training a custom openWakeWord model
with a minimum of 50,000 augmented positive samples and balanced hard negatives.
Maintains lazy/optional imports for heavy training dependencies (PyTorch) so that
the normal runtime remains lean and dependency-free.
Never claims a trained model when assets or dependencies are absent.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.wakeword.heyino_corpus_spec import (
    ALLOWED_PRONUNCIATION_VARIANTS,
    CANONICAL_WAKE_LABEL,
    HARD_NEGATIVE_FAMILIES,
    CorpusClip,
    load_manifest,
    validate_manifest,
)

MIN_PLANNED_POSITIVE_COUNT: int = 50_000


@dataclass(slots=True)
class AugmentationSpec:
    """Acoustic augmentation parameters for generating robust positive training data."""

    target_positive_count: int = MIN_PLANNED_POSITIVE_COUNT
    pitch_shift_semitones: list[int] = field(default_factory=lambda: [-2, -1, 1, 2])
    time_stretch_rates: list[float] = field(
        default_factory=lambda: [0.85, 0.90, 0.95, 1.05, 1.10, 1.15]
    )
    snr_db_range: list[float] = field(default_factory=lambda: [-5.0, 20.0])
    rir_reverberation: bool = True
    noise_mix_probability: float = 0.8
    volume_perturbation_db: list[float] = field(default_factory=lambda: [-6.0, 6.0])
    bandpass_frequency_ranges: list[list[int]] = field(
        default_factory=lambda: [[300, 3400], [100, 7500]]
    )


@dataclass(slots=True)
class NegativeAllocationSpec:
    """Planned distribution of hard-negative confusers and ambient backgrounds."""

    phonetic_confusers_count: int = 20_000
    egyptian_conversation_count: int = 30_000
    english_conversation_count: int = 15_000
    announcements_count: int = 10_000
    crowd_music_claps_count: int = 15_000
    bumps_impulse_count: int = 5_000
    tts_bleed_count: int = 5_000
    total_planned_negatives: int = 100_000


@dataclass(slots=True)
class FeaturePipelineSpec:
    """Feature extraction parameters matching openWakeWord inference architecture."""

    sample_rate_hz: int = 16000
    window_step_samples: int = 1280  # 80ms at 16kHz
    clip_duration_seconds: float = 1.5
    feature_type: str = "google_speech_embedding"
    embedding_dim: int = 96


@dataclass(slots=True)
class TrainingHyperparameters:
    """Hyperparameters for training the custom openWakeWord classifier."""

    batch_size: int = 256
    learning_rate: float = 0.001
    epochs: int = 50
    loss_function: str = "focal_loss"
    weight_decay: float = 1e-4
    early_stopping_patience: int = 5
    lr_schedule: str = "cosine_annealing"


@dataclass(slots=True)
class TrainingPlan:
    """Complete blueprint and manifest for custom Heyino openWakeWord training."""

    target_phrase: str = CANONICAL_WAKE_LABEL
    model_name: str = "heyino_openwakeword_v0"
    model_architecture: str = "dnn"
    min_planned_positive_count: int = MIN_PLANNED_POSITIVE_COUNT
    allowed_variants: list[str] = field(
        default_factory=lambda: list(ALLOWED_PRONUNCIATION_VARIANTS)
    )
    augmentation: AugmentationSpec = field(default_factory=AugmentationSpec)
    negative_allocation: NegativeAllocationSpec = field(default_factory=NegativeAllocationSpec)
    feature_pipeline: FeaturePipelineSpec = field(default_factory=FeaturePipelineSpec)
    hyperparameters: TrainingHyperparameters = field(default_factory=TrainingHyperparameters)
    negative_families: dict[str, list[str]] = field(
        default_factory=lambda: dict(HARD_NEGATIVE_FAMILIES)
    )
    split_policy: dict[str, str] = field(
        default_factory=lambda: {
            "training_split": "train",
            "validation_split": "calibration",
            "held_out_split": "held_out (strictly excluded from training and tuning)",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save_to_json(self, output_path: Path | str) -> None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        dumped = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        p.write_text(dumped, encoding="utf-8")


@dataclass(slots=True)
class TrainingPrerequisitesStatus:
    """Readiness status for openWakeWord training prerequisites."""

    ready: bool
    status: str
    has_torch: bool
    has_openwakeword: bool
    train_positives_found: int
    train_negatives_found: int
    reasons: list[str] = field(default_factory=list)


def generate_training_plan(
    output_path: Path | str | None = None,
    min_planned_positives: int = MIN_PLANNED_POSITIVE_COUNT,
) -> TrainingPlan:
    """Generate a validated training plan for custom Heyino openWakeWord.

    Enforces Gate 5C.0 requirement of a minimum 50,000 augmented positive examples.
    """
    if min_planned_positives < MIN_PLANNED_POSITIVE_COUNT:
        raise ValueError(
            f"Gate 5C.0 requires a minimum planned positive count of "
            f"{MIN_PLANNED_POSITIVE_COUNT}, got {min_planned_positives}."
        )

    aug_spec = AugmentationSpec(target_positive_count=min_planned_positives)
    plan = TrainingPlan(
        min_planned_positive_count=min_planned_positives,
        augmentation=aug_spec,
    )

    if output_path is not None:
        plan.save_to_json(output_path)

    return plan


def verify_training_prerequisites(
    manifest_path: Path | str | None = None,
) -> TrainingPrerequisitesStatus:
    """Check whether training dependencies and data assets exist.

    Never claims model readiness when data or dependencies are absent.
    """
    has_torch = importlib.util.find_spec("torch") is not None
    has_oww = importlib.util.find_spec("openwakeword") is not None

    reasons: list[str] = []
    train_pos = 0
    train_neg = 0

    if not has_torch:
        reasons.append("PyTorch is not installed in the runtime environment.")
    if not has_oww:
        reasons.append("openwakeword is not installed in the runtime environment.")

    if manifest_path is None:
        reasons.append("No corpus manifest provided (DATA_PENDING).")
    else:
        m_path = Path(manifest_path)
        if not m_path.is_file():
            reasons.append(f"Manifest file not found at '{m_path}' (DATA_PENDING).")
        else:
            try:
                clips: list[CorpusClip] = load_manifest(m_path)
                val_res = validate_manifest(clips)
                if not val_res.valid:
                    reasons.append(f"Manifest validation failed with errors: {val_res.errors}")
                else:
                    train_clips = [c for c in clips if c.split == "train"]
                    train_pos = sum(1 for c in train_clips if c.is_positive)
                    train_neg = sum(1 for c in train_clips if not c.is_positive)
                    if train_pos == 0:
                        reasons.append(
                            "Zero positive training clips found in manifest (DATA_PENDING)."
                        )
                    if train_neg == 0:
                        reasons.append(
                            "Zero negative training clips found in manifest (DATA_PENDING)."
                        )
            except Exception as err:
                reasons.append(f"Failed to read manifest: {err}")

    ready = has_torch and has_oww and train_pos > 0 and train_neg > 0 and len(reasons) == 0

    if not has_torch or not has_oww:
        status_str = "DEPENDENCIES_PENDING"
    elif train_pos == 0 or train_neg == 0:
        status_str = "DATA_PENDING"
    elif not ready:
        status_str = "PREREQUISITES_NOT_MET"
    else:
        status_str = "READY"

    return TrainingPrerequisitesStatus(
        ready=ready,
        status=status_str,
        has_torch=has_torch,
        has_openwakeword=has_oww,
        train_positives_found=train_pos,
        train_negatives_found=train_neg,
        reasons=reasons,
    )


def run_training_lazy(
    training_plan_path: Path | str,
    manifest_path: Path | str,
    output_model_path: Path | str,
) -> None:
    """Execute training using lazy-imported packages.

    Fails cleanly if PyTorch or data are absent; never produces fake model assets.
    """
    prereqs = verify_training_prerequisites(manifest_path)
    if not prereqs.ready:
        raise RuntimeError(
            f"Cannot train custom openWakeWord model: {prereqs.status}. Reasons: {prereqs.reasons}"
        )

    # Lazy import heavy packages only when actually training
    try:
        import torch  # noqa: F401
    except ImportError as err:
        raise RuntimeError(
            "PyTorch is required for model training but is not installed."
        ) from err

    try:
        import openwakeword  # noqa: F401
    except ImportError as err:
        raise RuntimeError(
            "openwakeword is required for model training but is not installed."
        ) from err

    # Model training requires full external builder pipeline
    raise RuntimeError(
        "Model training for custom openWakeWord requires the external builder workflow "
        "(openWakeWord training pipeline) and cannot be executed by this local runtime helper. "
        "Use the generated training plan with the builder environment. "
        "This helper will not generate or claim a trained model."
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for training plan generation and verification."""
    parser = argparse.ArgumentParser(
        description="Heyino custom openWakeWord training plan and manifest generator"
    )
    parser.add_argument(
        "--generate-plan",
        type=Path,
        default=Path("scripts/wakeword/heyino_training_plan.json"),
        help="Target output path for the training plan JSON file",
    )
    parser.add_argument(
        "--min-positives",
        type=int,
        default=MIN_PLANNED_POSITIVE_COUNT,
        help=f"Minimum planned positive count (must be >= {MIN_PLANNED_POSITIVE_COUNT})",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to corpus manifest.json to verify data readiness",
    )
    parser.add_argument(
        "--check-prerequisites",
        action="store_true",
        help="Check whether dependencies and training corpus are ready",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Execute offline model training if prerequisites are satisfied",
    )
    parser.add_argument(
        "--output-model",
        type=Path,
        default=Path("models/wake/heyino_openwakeword_v0.onnx"),
        help="Target output path for trained ONNX model",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point for train_openwakeword."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.check_prerequisites:
        status = verify_training_prerequisites(args.manifest)
        print("=== Training Prerequisites Check ===")
        print(f"Status: {status.status}")
        print(f"Ready: {status.ready}")
        print(f"PyTorch available: {status.has_torch}")
        print(f"openWakeWord available: {status.has_openwakeword}")
        print(f"Train positive clips: {status.train_positives_found}")
        print(f"Train negative clips: {status.train_negatives_found}")
        if status.reasons:
            print("Reasons / Blockers:")
            for r in status.reasons:
                print(f"  - {r}")
        return 0 if status.ready else 1

    if args.train:
        print("Starting training process...")
        try:
            run_training_lazy(
                training_plan_path=args.generate_plan,
                manifest_path=args.manifest or Path("recordings/heyino_corpus/manifest.json"),
                output_model_path=args.output_model,
            )
            return 0
        except Exception as err:
            print(f"Training failed: {err}", file=sys.stderr)
            return 1

    # Default action: generate training plan
    try:
        plan = generate_training_plan(
            output_path=args.generate_plan,
            min_planned_positives=args.min_positives,
        )
        print(f"Successfully generated training plan: {args.generate_plan.resolve()}")
        print(f"Target phrase: {plan.target_phrase}")
        print(f"Min planned positive examples: {plan.min_planned_positive_count:,}")
        print(f"Planned negative samples: {plan.negative_allocation.total_planned_negatives:,}")
        return 0
    except Exception as err:
        print(f"Failed to generate training plan: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

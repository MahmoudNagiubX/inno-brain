"""Interactive and batch corpus recorder for the Heyino wake dataset.

Records 16kHz mono PCM16 audio clips with structured metadata, writes to
organized subdirectories, and maintains a validated manifest.
Supports offline mock injection for safe testing without microphone hardware.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from innobrain.audio.io import write_pcm16_wav
from scripts.wakeword.heyino_corpus_spec import (
    ALLOWED_PRONUNCIATION_VARIANTS,
    CANONICAL_WAKE_LABEL,
    DISTANCE_BUCKETS,
    HARD_NEGATIVE_FAMILIES,
    NOISE_CONDITIONS,
    VALID_SPLITS,
    CorpusClip,
    load_manifest,
    save_manifest,
    validate_manifest,
)

AudioRecorderFn = Callable[[float, int], np.ndarray]


def default_microphone_recorder(duration_seconds: float, sample_rate_hz: int) -> np.ndarray:
    """Record audio using sounddevice if available."""
    try:
        from innobrain.audio.io import record_mono

        return record_mono(duration_seconds=duration_seconds, sample_rate_hz=sample_rate_hz)
    except Exception as err:
        raise RuntimeError(f"Microphone recording failed: {err}") from err


def mock_audio_recorder(duration_seconds: float, sample_rate_hz: int) -> np.ndarray:
    """Generate synthetic silent/gentle test audio without accessing microphone hardware."""
    num_samples = int(duration_seconds * sample_rate_hz)
    # Generate 16-bit PCM silence with mild low-level dither
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    # 440 Hz gentle tone at low volume for synthetic test verification
    signal = (np.sin(2 * np.pi * 440 * t) * 500).astype(np.int16)
    return signal


def create_clip_id(split: str, label: str, speaker_id: str | None) -> str:
    """Generate a clean, reproducible, collision-free clip ID."""
    clean_label = label.replace(" ", "_").replace("/", "_").lower()
    spk = speaker_id.replace(" ", "_").lower() if speaker_id else "anon"
    short_uuid = uuid.uuid4().hex[:8]
    ts = int(time.time())
    return f"{split}_{clean_label}_{spk}_{ts}_{short_uuid}"


def record_and_save_clip(
    output_dir: Path,
    split: str,
    label: str,
    is_positive: bool,
    duration_sec: float = 2.5,
    sample_rate_hz: int = 16000,
    pronunciation: str | None = None,
    speaker_id: str | None = None,
    distance: str | None = None,
    noise_condition: str | None = None,
    confuser_family: str | None = None,
    transcript: str | None = None,
    metadata: dict[str, Any] | None = None,
    recorder_fn: AudioRecorderFn | None = None,
) -> CorpusClip:
    """Record a single audio clip, save the WAV, and update manifest safely."""
    if recorder_fn is None:
        recorder_fn = default_microphone_recorder

    # Validate enum inputs
    if split not in VALID_SPLITS:
        raise ValueError(f"Invalid split '{split}'. Must be one of {VALID_SPLITS}.")
    if distance is not None and distance not in DISTANCE_BUCKETS:
        raise ValueError(f"Invalid distance '{distance}'. Must be one of {DISTANCE_BUCKETS}.")
    if noise_condition is not None and noise_condition not in NOISE_CONDITIONS:
        raise ValueError(
            f"Invalid noise_condition '{noise_condition}'. Must be one of {NOISE_CONDITIONS}."
        )

    # Check for path traversal characters
    for name, val in [("split", split), ("label", label), ("speaker_id", speaker_id)]:
        if val and (".." in val or val.startswith(("/", "\\"))):
            raise ValueError(f"Unsafe path traversal detected in {name}: '{val}'")

    output_dir = Path(output_dir).resolve()

    clip_id = create_clip_id(split, label, speaker_id)
    folder_label = label.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()
    rel_path = Path(split) / folder_label / f"{clip_id}.wav"
    abs_path = (output_dir / rel_path).resolve()

    # Enforce path containment under output_dir
    try:
        abs_path.relative_to(output_dir)
    except ValueError as err:
        raise ValueError(
            f"Unsafe path traversal: target path '{abs_path}' is outside output directory "
            f"'{output_dir}'"
        ) from err

    output_dir.mkdir(parents=True, exist_ok=True)
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    # Capture audio samples
    samples = recorder_fn(duration_sec, sample_rate_hz)
    if not isinstance(samples, np.ndarray) or samples.dtype != np.int16:
        samples = np.asarray(samples, dtype=np.int16)

    # Write WAV file
    write_pcm16_wav(abs_path, samples, sample_rate_hz)

    actual_duration = float(len(samples)) / float(sample_rate_hz)

    clip = CorpusClip(
        clip_id=clip_id,
        file_path=str(rel_path.as_posix()),
        split=split,
        label=label,
        is_positive=is_positive,
        pronunciation=pronunciation,
        speaker_id=speaker_id,
        distance=distance,
        noise_condition=noise_condition,
        confuser_family=confuser_family,
        duration_sec=actual_duration,
        sample_rate_hz=sample_rate_hz,
        channels=1,
        bits_per_sample=16,
        transcript=transcript,
        metadata=metadata or {},
    )

    manifest_path = output_dir / "manifest.json"
    existing_clips: list[CorpusClip] = []
    if manifest_path.is_file():
        existing_clips = load_manifest(manifest_path)

    existing_clips.append(clip)

    # Validate updated manifest
    val_res = validate_manifest(existing_clips, base_dir=output_dir, check_file_exists=True)
    if not val_res.valid:
        # If invalid (e.g. data leakage), clean up WAV and abort
        if abs_path.is_file():
            abs_path.unlink()
        raise ValueError(
            f"Manifest validation failed after adding clip '{clip_id}': {val_res.errors}"
        )

    save_manifest(manifest_path, existing_clips)
    return clip


def run_interactive_session(output_dir: Path, recorder_fn: AudioRecorderFn) -> int:
    """Run an interactive prompt session for recording Heyino corpus clips."""
    print("=== InnoBrain Heyino Corpus Recorder (Gate 5C.0) ===")
    print(f"Target directory: {output_dir.resolve()}\n")

    split = input(f"Select split {VALID_SPLITS} [train]: ").strip() or "train"
    if split not in VALID_SPLITS:
        print(f"Invalid split '{split}'. Must be one of {VALID_SPLITS}")
        return 1

    speaker_id = input("Enter Speaker ID (e.g. spk_01): ").strip()
    if not speaker_id:
        print("Speaker ID is recommended for split isolation.")

    distance = input(f"Select distance {DISTANCE_BUCKETS} [mid_1_5m]: ").strip() or "mid_1_5m"
    noise_condition = (
        input(f"Select noise {NOISE_CONDITIONS} [clean_quiet]: ").strip() or "clean_quiet"
    )

    is_pos_str = input("Is this a positive wake clip? (y/n) [y]: ").strip().lower()
    is_positive = is_pos_str in ("y", "yes", "")

    if is_positive:
        print(f"Allowed variants: {ALLOWED_PRONUNCIATION_VARIANTS}")
        label = input(f"Enter label [{CANONICAL_WAKE_LABEL}]: ").strip() or CANONICAL_WAKE_LABEL
        pronunciation = label
        confuser_family = None
    else:
        print("Negative families:", list(HARD_NEGATIVE_FAMILIES.keys()))
        confuser_family = input("Enter negative family: ").strip() or "phonetic_confusers"
        label = input("Enter negative prompt text: ").strip() or "negative"
        pronunciation = None

    duration = float(input("Enter duration in seconds [2.5]: ").strip() or "2.5")

    print(f"\nReady to record clip '{label}' for speaker '{speaker_id}'...")
    input("Press Enter to begin 3-second countdown...")

    for i in (3, 2, 1):
        print(f"{i}...", flush=True)
        time.sleep(1.0)
    print(">>> RECORDING NOW <<<", flush=True)

    clip = record_and_save_clip(
        output_dir=output_dir,
        split=split,
        label=label,
        is_positive=is_positive,
        duration_sec=duration,
        pronunciation=pronunciation,
        speaker_id=speaker_id,
        distance=distance,
        noise_condition=noise_condition,
        confuser_family=confuser_family,
        recorder_fn=recorder_fn,
    )

    print(f"\nSuccessfully recorded and validated clip: {clip.clip_id}")
    print(f"File saved to: {clip.file_path}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for corpus recording."""
    parser = argparse.ArgumentParser(
        description="Heyino Wake Word Corpus Recorder and Manifest Builder"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("recordings/heyino_corpus"),
        help="Base output directory for audio clips and manifest.json",
    )
    parser.add_argument(
        "--split",
        choices=VALID_SPLITS,
        default="train",
        help="Corpus partition split",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=CANONICAL_WAKE_LABEL,
        help="Clip label text (canonical 'heyino', allowed variant, or negative text)",
    )
    parser.add_argument(
        "--is-positive",
        action="store_true",
        default=True,
        help="Mark clip as positive wake detection target",
    )
    parser.add_argument(
        "--is-negative",
        action="store_true",
        help="Mark clip as negative confuser/background audio",
    )
    parser.add_argument(
        "--speaker-id",
        type=str,
        default="spk_dev",
        help="Speaker identifier string",
    )
    parser.add_argument(
        "--distance",
        choices=DISTANCE_BUCKETS,
        default="mid_1_5m",
        help="Microphone distance category",
    )
    parser.add_argument(
        "--noise",
        choices=NOISE_CONDITIONS,
        default="clean_quiet",
        help="Acoustic background noise condition",
    )
    parser.add_argument(
        "--confuser-family",
        type=str,
        default=None,
        help="Hard negative family name if recording negative audio",
    )
    parser.add_argument(
        "--pronunciation",
        type=str,
        default=None,
        help="Pronunciation variant name",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.5,
        help="Recording duration in seconds",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Audio sample rate (must be 16000)",
    )
    parser.add_argument(
        "--mock-audio",
        action="store_true",
        help="Generate synthetic test audio without accessing real microphone",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run guided interactive recording prompts",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing manifest and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point for record_heyino_corpus."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.validate_only:
        manifest_path = args.output_dir / "manifest.json"
        if not manifest_path.is_file():
            print(f"Error: Manifest not found at {manifest_path}", file=sys.stderr)
            return 1
        clips = load_manifest(manifest_path)
        res = validate_manifest(clips, base_dir=args.output_dir, check_file_exists=True)
        if res.valid:
            print(f"Manifest valid: {res.clip_count} clips, {res.total_duration_sec:.2f}s total.")
            for s_name, s_info in res.splits_summary.items():
                print(f"  {s_name}: {s_info['total_clips']} clips ({s_info['duration_sec']:.2f}s)")
            return 0
        else:
            print("Manifest validation errors:", file=sys.stderr)
            for err in res.errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

    recorder_fn = mock_audio_recorder if args.mock_audio else default_microphone_recorder

    if args.interactive:
        return run_interactive_session(args.output_dir, recorder_fn)

    is_pos = not args.is_negative and args.is_positive
    pronunciation = args.pronunciation or (args.label if is_pos else None)

    try:
        clip = record_and_save_clip(
            output_dir=args.output_dir,
            split=args.split,
            label=args.label,
            is_positive=is_pos,
            duration_sec=args.duration,
            sample_rate_hz=args.sample_rate,
            pronunciation=pronunciation,
            speaker_id=args.speaker_id,
            distance=args.distance,
            noise_condition=args.noise,
            confuser_family=args.confuser_family,
            recorder_fn=recorder_fn,
        )
        print(f"Recorded clip: {clip.clip_id}")
        print(f"Saved to: {args.output_dir / clip.file_path}")
        return 0
    except Exception as err:
        print(f"Recording failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

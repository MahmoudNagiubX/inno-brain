"""Interactive and batch corpus recorder for the Heyino wake dataset.

Records 16kHz mono PCM16 audio clips with structured metadata, writes to
organized subdirectories, and maintains a validated manifest.
Supports offline mock injection for safe testing without microphone hardware.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

# Safe direct-script project-root bootstrap
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from innobrain.audio.io import write_pcm16_wav  # noqa: E402
from scripts.wakeword.heyino_corpus_spec import (  # noqa: E402
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
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    # 440 Hz gentle tone at low volume for synthetic test verification
    signal = (np.sin(2 * np.pi * 440 * t) * 500).astype(np.int16)
    return signal


def create_clip_id(split: str, label: str, speaker_id: str | None) -> str:
    """Generate a clean, reproducible, collision-free clip ID."""
    clean_label = label.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()
    spk = (
        speaker_id.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()
        if speaker_id
        else "anon"
    )
    short_uuid = uuid.uuid4().hex[:8]
    ts = int(time.time())
    return f"{split}_{clean_label}_{spk}_{ts}_{short_uuid}"


def record_and_save_clip(
    output_dir: Path | str,
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
    """Record a single audio clip, save the WAV safely, and update manifest.

    Preflights pre-existing manifest and speaker isolation BEFORE audio capture.
    Captures using atomic temporary WAV write. Never unlinks final recorded audio
    due to unrelated historical manifest flaws.
    """
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

    # Validate label constraints prior to capture
    if is_positive:
        if label not in ALLOWED_PRONUNCIATION_VARIANTS:
            raise ValueError(
                f"Positive clip has invalid label '{label}'. "
                f"Must be one of {ALLOWED_PRONUNCIATION_VARIANTS}."
            )
    else:
        if label in ALLOWED_PRONUNCIATION_VARIANTS:
            raise ValueError(f"Negative clip cannot have positive wake label '{label}'.")

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

    # Preflight pre-existing corpus before microphone capture. The structural
    # audit is required in addition to schema/file validation: a WAV can exist
    # while its manifest filename or embedded speaker identity is inconsistent.
    manifest_path = output_dir / "manifest.json"
    existing_clips: list[CorpusClip] = []
    if manifest_path.is_file():
        try:
            existing_clips = load_manifest(manifest_path)
        except Exception as err:
            raise ValueError(
                f"Preflight failed: existing manifest at {manifest_path} is invalid: {err}"
            ) from err

        from scripts.wakeword.repair_heyino_corpus import audit_corpus

        audit_res = audit_corpus(output_dir)
        if not audit_res.is_healthy:
            raise ValueError(
                f"Preflight failed: existing corpus audit found issues: "
                f"{[issue.message for issue in audit_res.issues]}"
            )

        pre_val = validate_manifest(existing_clips, base_dir=output_dir, check_file_exists=True)
        if not pre_val.valid:
            raise ValueError(
                f"Preflight failed: existing manifest has validation errors: {pre_val.errors}"
            )
    elif output_dir.is_dir():
        existing_wavs = sorted(output_dir.rglob("*.wav"))
        if existing_wavs:
            rel_wavs = [str(w.relative_to(output_dir).as_posix()) for w in existing_wavs]
            raise ValueError(
                f"Preflight failed: corpus contains WAV files but no manifest.json: {rel_wavs}"
            )

    # Check for speaker leakage across splits before capturing
    if speaker_id:
        for c in existing_clips:
            if c.speaker_id == speaker_id and c.split != split:
                raise ValueError(
                    f"SPEAKER LEAKAGE: Speaker '{speaker_id}' already exists in split '{c.split}', "
                    f"cannot record into split '{split}'."
                )

    # Check for duplicate clip ID or path before capture
    norm_new_path = str(rel_path.as_posix()).lower()
    for c in existing_clips:
        if c.clip_id == clip_id:
            raise ValueError(f"Duplicate clip_id '{clip_id}' detected.")
        if str(Path(c.file_path).as_posix()).lower() == norm_new_path:
            raise ValueError(f"Duplicate file_path '{rel_path}' detected.")

    # All preflights passed: safe to call recorder_fn now
    samples = recorder_fn(duration_sec, sample_rate_hz)
    if not isinstance(samples, np.ndarray) or samples.dtype != np.int16:
        samples = np.asarray(samples, dtype=np.int16)

    # Write WAV safely via temp file + atomic replace
    output_dir.mkdir(parents=True, exist_ok=True)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_wav = abs_path.with_name(f".{abs_path.name}.tmp_{uuid.uuid4().hex[:8]}")
    try:
        write_pcm16_wav(tmp_wav, samples, sample_rate_hz)
        os.replace(tmp_wav, abs_path)
    finally:
        if tmp_wav.is_file():
            try:
                tmp_wav.unlink()
            except OSError:
                pass

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

    updated_clips = list(existing_clips) + [clip]

    # Validate updated manifest
    val_res = validate_manifest(updated_clips, base_dir=output_dir, check_file_exists=True)
    if not val_res.valid:
        raise ValueError(
            f"Manifest validation failed after adding clip '{clip_id}': {val_res.errors}"
        )

    # Atomic manifest save
    save_manifest(manifest_path, updated_clips)
    return clip


def run_interactive_session(
    output_dir: Path,
    recorder_fn: AudioRecorderFn,
    *,
    initial_split: str = "train",
    initial_is_negative: bool = False,
    initial_confuser_family: str | None = None,
    initial_label: str | None = None,
    initial_speaker_id: str | None = None,
    initial_distance: str = "mid_1_5m",
    initial_noise: str = "clean_quiet",
    initial_duration: float = 2.5,
) -> int:
    """Run an interactive prompt session for recording Heyino corpus clips."""
    print("=== InnoBrain Heyino Corpus Recorder (Gate 5C.0) ===")
    print(f"Target directory: {output_dir.resolve()}\n")

    split_prompt = f"Select split {VALID_SPLITS} [{initial_split}]: "
    split = input(split_prompt).strip() or initial_split
    if split not in VALID_SPLITS:
        print(f"Invalid split '{split}'. Must be one of {VALID_SPLITS}")
        return 1

    spk_default = (
        initial_speaker_id
        if (initial_speaker_id and initial_speaker_id != "spk_dev")
        else ""
    )
    spk_prompt = (
        f"Enter Speaker ID (e.g. spk_01) [{spk_default}]: "
        if spk_default
        else "Enter Speaker ID (e.g. spk_01): "
    )
    speaker_id = input(spk_prompt).strip() or spk_default
    if not speaker_id:
        print("Speaker ID is recommended for split isolation.")

    dist_default = (
        initial_distance if initial_distance in DISTANCE_BUCKETS else "mid_1_5m"
    )
    distance = (
        input(f"Select distance {DISTANCE_BUCKETS} [{dist_default}]: ").strip()
        or dist_default
    )

    noise_default = (
        initial_noise if initial_noise in NOISE_CONDITIONS else "clean_quiet"
    )
    noise_condition = (
        input(f"Select noise {NOISE_CONDITIONS} [{noise_default}]: ").strip()
        or noise_default
    )

    default_pos_choice = "n" if initial_is_negative else "y"
    is_pos_str = (
        input(f"Is this a positive wake clip? (y/n) [{default_pos_choice}]: ")
        .strip()
        .lower()
    )
    if not is_pos_str:
        is_positive = not initial_is_negative
    else:
        is_positive = is_pos_str in ("y", "yes")

    if is_positive:
        print(f"Allowed variants: {ALLOWED_PRONUNCIATION_VARIANTS}")
        default_label = (
            initial_label
            if (initial_label and initial_label in ALLOWED_PRONUNCIATION_VARIANTS)
            else CANONICAL_WAKE_LABEL
        )
        label = input(f"Enter label [{default_label}]: ").strip() or default_label
        pronunciation = label
        confuser_family = None
    else:
        print("Negative families:", list(HARD_NEGATIVE_FAMILIES.keys()))
        default_fam = initial_confuser_family or "phonetic_confusers"
        confuser_family = (
            input(f"Enter negative family [{default_fam}]: ").strip() or default_fam
        )
        default_label = (
            initial_label
            if (initial_label and initial_label != CANONICAL_WAKE_LABEL)
            else "negative"
        )
        label = (
            input(f"Enter negative prompt text [{default_label}]: ").strip()
            or default_label
        )
        pronunciation = None

    dur_default = str(initial_duration) if initial_duration > 0 else "2.5"
    duration = float(
        input(f"Enter duration in seconds [{dur_default}]: ").strip() or dur_default
    )

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


def main(argv: Sequence[str] | None = None) -> int:
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
            print(
                f"Manifest valid: {res.clip_count} clips, {res.total_duration_sec:.2f}s total."
            )
            for s_name, s_info in res.splits_summary.items():
                print(
                    f"  {s_name}: {s_info['total_clips']} clips ({s_info['duration_sec']:.2f}s)"
                )
            return 0
        else:
            print("Manifest validation errors:", file=sys.stderr)
            for err in res.errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

    recorder_fn = mock_audio_recorder if args.mock_audio else default_microphone_recorder

    if args.interactive:
        is_negative = bool(args.is_negative)
        return run_interactive_session(
            output_dir=args.output_dir,
            recorder_fn=recorder_fn,
            initial_split=args.split,
            initial_is_negative=is_negative,
            initial_confuser_family=args.confuser_family,
            initial_label=args.label,
            initial_speaker_id=args.speaker_id,
            initial_distance=args.distance,
            initial_noise=args.noise,
            initial_duration=args.duration,
        )

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

"""Heyino wake word corpus specification, metadata schema, and validation.

Defines the canonical label, allowed pronunciation variants, hard-negative
confuser families, and manifest validation logic for the Heyino wake dataset.
Guarantees strict separation between train, calibration, and held-out splits.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Canonical semantic label locked across InnoBrain Gate 5C.0
CANONICAL_WAKE_LABEL: str = "heyino"

# Allowed pronunciation variants representing natural dialect and acoustic variation
ALLOWED_PRONUNCIATION_VARIANTS: tuple[str, ...] = (
    "heyino",
    "hey_ino",
    "hayino",
    "heyno",
    "heyinno",
    "hayinno",
    "he_yino",
    "هاي إينو",
    "هي إينو",
    "هيينو",
    "هايينو",
)

# Mandatory split partition names
VALID_SPLITS: tuple[str, ...] = ("train", "calibration", "held_out")

# Distance bucket standards
DISTANCE_BUCKETS: tuple[str, ...] = (
    "near_0_5m",
    "mid_1_5m",
    "far_3_0m",
)

# Noise condition categories
NOISE_CONDITIONS: tuple[str, ...] = (
    "clean_quiet",
    "office_ambient",
    "event_crowd",
    "music_playback",
    "announcements",
    "mic_bumps",
)

# Hard-negative confuser families specified in Gate 5C.0 requirements
HARD_NEGATIVE_FAMILIES: dict[str, list[str]] = {
    "phonetic_confusers": [
        "hey",
        "inno",
        "hey no",
        "hey now",
        "I know",
        "i know",
        "hey you",
        "hello",
        "Nino",
        "hey Nino",
        "eno",
        "aino",
        "ayno",
        "hino",
        "inno hey",
        "hey dino",
        "ino",
    ],
    "egyptian_conversation": [
        "ازيك يا باشا",
        "صباح الخير",
        "فين قاعة المؤتمر",
        "ممكن تساعدني",
        "ايوه انا هنا",
        "معلش سؤال تاني",
        "شكرا جزيلا",
        "عايز اعرف الجدول",
    ],
    "english_conversation": [
        "can you tell me where the keynote is",
        "where is the registration desk",
        "what time does the next session start",
        "excuse me do you know",
        "hello there",
        "thanks for the help",
    ],
    "announcements": [
        "attention please keynote starts in 5 minutes",
        "lunch is now served in the main hall",
        "final call for workshop attendees",
        "paging doctor ahmed",
    ],
    "crowd_music_claps": [
        "audience applause and claps",
        "background lounge music playback",
        "crowd chatter and hall hum",
        "laughter and cheer",
    ],
    "bumps_impulse": [
        "table bumps and taps",
        "microphone handling thumps",
        "footsteps and chair movement",
        "door close and clicks",
    ],
    "tts_bleed": [
        "robot tts self playback",
        "smart speaker synthesized reply",
        "phone virtual assistant prompt",
    ],
}

ALL_NEGATIVE_FAMILIES: tuple[str, ...] = tuple(HARD_NEGATIVE_FAMILIES.keys())


@dataclass(slots=True)
class CorpusClip:
    """Represents a single audio clip entry in the corpus manifest."""

    clip_id: str
    file_path: str
    split: str
    label: str
    is_positive: bool
    pronunciation: str | None = None
    speaker_id: str | None = None
    distance: str | None = None
    noise_condition: str | None = None
    confuser_family: str | None = None
    duration_sec: float = 0.0
    sample_rate_hz: int = 16000
    channels: int = 1
    bits_per_sample: int = 16
    transcript: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorpusClip:
        if not isinstance(data, dict):
            raise TypeError(
                f"Expected dictionary for CorpusClip, got {type(data).__name__}"
            )
        required_fields = {"clip_id", "file_path", "split", "label", "is_positive"}
        missing = required_fields - set(data.keys())
        if missing:
            raise ValueError(
                f"Missing required manifest field(s) in CorpusClip dictionary: {sorted(missing)}"
            )
        valid_fields = {
            "clip_id",
            "file_path",
            "split",
            "label",
            "is_positive",
            "pronunciation",
            "speaker_id",
            "distance",
            "noise_condition",
            "confuser_family",
            "duration_sec",
            "sample_rate_hz",
            "channels",
            "bits_per_sample",
            "transcript",
            "metadata",
        }
        unknown = set(data.keys()) - valid_fields
        if unknown:
            raise ValueError(
                f"Unknown manifest key(s) in CorpusClip dictionary: {sorted(unknown)}"
            )
        return cls(**data)


@dataclass(slots=True)
class ManifestValidationResult:
    """Summary of corpus manifest validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    clip_count: int = 0
    total_duration_sec: float = 0.0
    splits_summary: dict[str, dict[str, Any]] = field(default_factory=dict)


def validate_manifest(
    clips: Sequence[CorpusClip | dict[str, Any]],
    base_dir: Path | str | None = None,
    check_file_exists: bool = False,
) -> ManifestValidationResult:
    """Validate a list or sequence of corpus clips against Gate 5C.0 requirements.

    Checks required fields, audio parameters, label constraints, split names,
    and strictly enforces zero data leakage (audio paths and speakers) between
    train, calibration, and held-out splits.
    """
    errors: list[str] = []
    warnings: list[str] = []
    seen_clip_ids: set[str] = set()

    split_clips: dict[str, list[CorpusClip]] = {s: [] for s in VALID_SPLITS}
    split_paths: dict[str, set[str]] = {s: set() for s in VALID_SPLITS}
    split_speakers: dict[str, set[str]] = {s: set() for s in VALID_SPLITS}

    total_duration = 0.0
    parsed_clips: list[CorpusClip] = []

    base_path = Path(base_dir) if base_dir is not None else None

    for idx, item in enumerate(clips):
        if isinstance(item, dict):
            try:
                clip = CorpusClip.from_dict(item)
            except (TypeError, ValueError) as err:
                errors.append(f"Clip at index {idx} failed to parse: {err}")
                continue
        elif isinstance(item, CorpusClip):
            clip = item
        else:
            errors.append(f"Clip at index {idx} has invalid type {type(item)}.")
            continue

        parsed_clips.append(clip)

        # Validate clip_id uniqueness
        if not clip.clip_id:
            errors.append(f"Clip at index {idx} has an empty clip_id.")
        elif clip.clip_id in seen_clip_ids:
            errors.append(f"Duplicate clip_id '{clip.clip_id}' found at index {idx}.")
        else:
            seen_clip_ids.add(clip.clip_id)

        # Validate split
        if clip.split not in VALID_SPLITS:
            errors.append(
                f"Clip '{clip.clip_id}' has invalid split '{clip.split}'. "
                f"Expected one of {VALID_SPLITS}."
            )
        else:
            split_clips[clip.split].append(clip)
            norm_path = str(Path(clip.file_path).as_posix()).lower()
            split_paths[clip.split].add(norm_path)
            if clip.speaker_id:
                split_speakers[clip.split].add(clip.speaker_id)

        # Validate audio specs
        if clip.sample_rate_hz != 16000:
            errors.append(
                f"Clip '{clip.clip_id}' sample rate {clip.sample_rate_hz} != 16000 Hz."
            )
        if clip.channels != 1:
            errors.append(
                f"Clip '{clip.clip_id}' channels {clip.channels} != 1 (mono required)."
            )
        if clip.bits_per_sample != 16:
            errors.append(
                f"Clip '{clip.clip_id}' bits_per_sample {clip.bits_per_sample} != 16."
            )
        if clip.duration_sec < 0:
            errors.append(
                f"Clip '{clip.clip_id}' has negative duration {clip.duration_sec}."
            )
        elif clip.duration_sec == 0:
            warnings.append(f"Clip '{clip.clip_id}' has zero duration.")

        total_duration += max(0.0, clip.duration_sec)

        # Validate positive / negative label invariants
        if clip.is_positive:
            if clip.label not in ALLOWED_PRONUNCIATION_VARIANTS:
                errors.append(
                    f"Positive clip '{clip.clip_id}' has invalid label '{clip.label}'. "
                    f"Must be one of {ALLOWED_PRONUNCIATION_VARIANTS}."
                )
        else:
            if clip.label in ALLOWED_PRONUNCIATION_VARIANTS:
                errors.append(
                    f"Negative clip '{clip.clip_id}' cannot have positive label '{clip.label}'."
                )
            if clip.confuser_family and clip.confuser_family not in ALL_NEGATIVE_FAMILIES:
                warnings.append(
                    f"Negative clip '{clip.clip_id}' has unrecognized confuser family "
                    f"'{clip.confuser_family}'."
                )

        # Validate file existence if requested
        if check_file_exists:
            target = Path(clip.file_path)
            if not target.is_absolute() and base_path is not None:
                target = base_path / target
            if not target.is_file():
                errors.append(f"Clip '{clip.clip_id}' audio file not found: {target}")

    # Enforce strict data isolation between train, calibration, and held-out
    # 1. Path overlap check
    train_holdout_overlap = split_paths["train"] & split_paths["held_out"]
    if train_holdout_overlap:
        errors.append(
            f"DATA LEAKAGE DETECTED: Files present in both train and held_out: "
            f"{sorted(train_holdout_overlap)}"
        )

    calib_holdout_overlap = split_paths["calibration"] & split_paths["held_out"]
    if calib_holdout_overlap:
        errors.append(
            f"DATA LEAKAGE DETECTED: Files present in both calibration and held_out: "
            f"{sorted(calib_holdout_overlap)}"
        )

    train_calib_overlap = split_paths["train"] & split_paths["calibration"]
    if train_calib_overlap:
        errors.append(
            f"DATA LEAKAGE DETECTED: Files present in both train and calibration: "
            f"{sorted(train_calib_overlap)}"
        )

    # 2. Speaker overlap check across all pairs of splits
    train_calib_speakers = split_speakers["train"] & split_speakers["calibration"]
    if train_calib_speakers:
        errors.append(
            f"SPEAKER LEAKAGE DETECTED: Speakers present in both train and calibration: "
            f"{sorted(train_calib_speakers)}"
        )

    train_holdout_speakers = split_speakers["train"] & split_speakers["held_out"]
    if train_holdout_speakers:
        errors.append(
            f"SPEAKER LEAKAGE DETECTED: Speakers present in both train and held_out: "
            f"{sorted(train_holdout_speakers)}"
        )

    calib_holdout_speakers = split_speakers["calibration"] & split_speakers["held_out"]
    if calib_holdout_speakers:
        errors.append(
            f"SPEAKER LEAKAGE DETECTED: Speakers present in both calibration and held_out: "
            f"{sorted(calib_holdout_speakers)}"
        )

    # Build summary per split
    splits_summary: dict[str, dict[str, Any]] = {}
    for split_name in VALID_SPLITS:
        c_list = split_clips[split_name]
        pos = sum(1 for c in c_list if c.is_positive)
        neg = sum(1 for c in c_list if not c.is_positive)
        dur = sum(c.duration_sec for c in c_list)
        splits_summary[split_name] = {
            "total_clips": len(c_list),
            "positive_clips": pos,
            "negative_clips": neg,
            "duration_sec": dur,
            "speakers": sorted(split_speakers[split_name]),
        }

    is_valid = len(errors) == 0
    return ManifestValidationResult(
        valid=is_valid,
        errors=errors,
        warnings=warnings,
        clip_count=len(parsed_clips),
        total_duration_sec=total_duration,
        splits_summary=splits_summary,
    )


def load_manifest(path: Path | str) -> list[CorpusClip]:
    """Load a corpus manifest from a JSON or JSONL file.

    Tolerates standard UTF-8 and UTF-8-BOM. Robustly distinguishes JSON array
    from JSONL format and preserves strict CorpusClip schema.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Corpus manifest file not found: {p}")

    clips: list[CorpusClip] = []
    # utf-8-sig transparently decodes both UTF-8 and UTF-8-BOM
    text = p.read_text(encoding="utf-8-sig").lstrip("\ufeff").strip()
    if not text:
        return []

    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            # Check if lines could be independent JSONL objects despite leading '['
            try:
                parsed_jsonl: list[CorpusClip] = []
                for line in text.splitlines():
                    stripped_line = line.strip()
                    if stripped_line:
                        item = json.loads(stripped_line)
                        if not isinstance(item, dict):
                            raise ValueError(f"Line is not a dict: {type(item)}")
                        parsed_jsonl.append(CorpusClip.from_dict(item))
                return parsed_jsonl
            except Exception:
                raise ValueError(
                    f"Failed to parse JSON array manifest from {p}: {err}"
                ) from err

        if not isinstance(data, list):
            raise ValueError(
                f"Manifest {p} contains {type(data).__name__}, expected JSON array or JSONL"
            )
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Manifest entry {idx} in {p} is not an object: {type(item).__name__}"
                )
            clips.append(CorpusClip.from_dict(item))
        return clips

    # JSONL format: each non-empty line must be a valid JSON object
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        try:
            item = json.loads(stripped_line)
        except json.JSONDecodeError as err:
            raise ValueError(
                f"Invalid JSON on line {line_no} of manifest {p}: {err}"
            ) from err
        if not isinstance(item, dict):
            raise ValueError(
                f"Manifest line {line_no} in {p} must be a JSON object, got {type(item).__name__}"
            )
        clips.append(CorpusClip.from_dict(item))

    return clips


def save_manifest(path: Path | str, clips: Sequence[CorpusClip | dict[str, Any]]) -> None:
    """Save corpus clips to a formatted JSON manifest file atomically.

    Uses a temporary file in the manifest directory, flushes and fsyncs,
    and replaces the target file atomically with os.replace. Cleans temporary
    file on failure and preserves existing manifest.
    """
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = [
        c.to_dict() if isinstance(c, CorpusClip) else CorpusClip.from_dict(c).to_dict()
        for c in clips
    ]
    encoded = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=p.parent,
            prefix=f".{p.name}.tmp_",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(encoded)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, p)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

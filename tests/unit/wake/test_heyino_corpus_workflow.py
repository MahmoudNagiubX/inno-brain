"""Regression and unit tests for Heyino corpus recording, repair, and spec workflows.

Tests verify:
- Subprocess execution for direct and module --help forms.
- UTF-8 and UTF-8-BOM manifest parsing across JSON array and JSONL formats.
- Preflight failure before microphone capture on stale or broken manifests.
- Detection of filename mismatches, renamed speaker/split/label metadata mismatches.
- Reporting of ambiguous orphan WAV matches without guessing or modifying corpus.
- Atomic reconciliation of unique rename/path-only cases leaving audio untouched.
- No accidental WAV unlinking on pre-capture failure or save error.
- Normal positive and hard-negative recording flows with mock audio injection.
- Seeding of interactive session defaults for negative recording commands.
- Atomic manifest writing and safe error cleanup.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from innobrain.audio.io import read_pcm16_wav, write_pcm16_wav
from scripts.wakeword.heyino_corpus_spec import (
    ALLOWED_PRONUNCIATION_VARIANTS,
    CANONICAL_WAKE_LABEL,
    CorpusClip,
    load_manifest,
    save_manifest,
    validate_manifest,
)
from scripts.wakeword.record_heyino_corpus import (
    mock_audio_recorder,
    record_and_save_clip,
    run_interactive_session,
)
from scripts.wakeword.repair_heyino_corpus import (
    audit_corpus,
    repair_corpus,
)


def _make_dummy_wav(path: Path, sample_rate: int = 16000, duration_sec: float = 0.5) -> None:
    """Create a valid dummy mono PCM16 WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    samples = np.zeros(num_samples, dtype=np.int16)
    write_pcm16_wav(path, samples, sample_rate)


# ---------------------------------------------------------------------------
# 1. Direct and Module Execution via Subprocess
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cmd_args",
    [
        ["scripts/wakeword/record_heyino_corpus.py", "--help"],
        ["-m", "scripts.wakeword.record_heyino_corpus", "--help"],
        ["scripts/wakeword/repair_heyino_corpus.py", "--help"],
        ["-m", "scripts.wakeword.repair_heyino_corpus", "--help"],
    ],
)
def test_direct_and_module_execution_help(cmd_args: list[str]) -> None:
    """Ensure both direct and module -m forms succeed with exit code 0 from project root."""
    cmd = [sys.executable, *cmd_args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Command {cmd} failed with stderr: {proc.stderr}"
    assert "Heyino Wake Word Corpus" in proc.stdout
    assert "--help" in proc.stdout


# ---------------------------------------------------------------------------
# 2. UTF-8 and UTF-8-BOM Handling across JSON Array and JSONL Formats
# ---------------------------------------------------------------------------
def test_load_manifest_utf8_and_bom(tmp_path: Path) -> None:
    """Test loading manifests encoded in UTF-8 and UTF-8 with BOM for array and JSONL."""
    clip_dict = {
        "clip_id": "train_heyino_spk01_001",
        "file_path": "train/heyino/train_heyino_spk01_001.wav",
        "split": "train",
        "label": "heyino",
        "is_positive": True,
        "speaker_id": "spk_01",
        "duration_sec": 1.0,
    }

    # 1. JSON array with UTF-8 BOM
    bom_array_path = tmp_path / "manifest_bom_array.json"
    json_bytes = json.dumps([clip_dict]).encode("utf-8")
    bom_array_path.write_bytes(b"\xef\xbb\xbf" + json_bytes)

    loaded = load_manifest(bom_array_path)
    assert len(loaded) == 1
    assert loaded[0].clip_id == "train_heyino_spk01_001"
    assert loaded[0].label == "heyino"

    # 2. JSONL with UTF-8 BOM
    bom_jsonl_path = tmp_path / "manifest_bom.jsonl"
    jsonl_bytes = (json.dumps(clip_dict) + "\n").encode("utf-8")
    bom_jsonl_path.write_bytes(b"\xef\xbb\xbf" + jsonl_bytes)

    loaded_jsonl = load_manifest(bom_jsonl_path)
    assert len(loaded_jsonl) == 1
    assert loaded_jsonl[0].clip_id == "train_heyino_spk01_001"

    # 3. Plain UTF-8 JSON array
    plain_array_path = tmp_path / "manifest_plain.json"
    save_manifest(plain_array_path, [CorpusClip.from_dict(clip_dict)])
    loaded_plain = load_manifest(plain_array_path)
    assert len(loaded_plain) == 1
    assert loaded_plain[0].clip_id == "train_heyino_spk01_001"


def test_manifest_strict_schema_enforcement() -> None:
    """Ensure CorpusClip strictly requires essential fields and rejects unknown fields."""
    valid_dict = {
        "clip_id": "c1",
        "file_path": "train/c1.wav",
        "split": "train",
        "label": "heyino",
        "is_positive": True,
    }
    clip = CorpusClip.from_dict(valid_dict)
    assert clip.clip_id == "c1"

    # Missing required field
    missing_dict = dict(valid_dict)
    del missing_dict["split"]
    with pytest.raises(ValueError, match="Missing required manifest field"):
        CorpusClip.from_dict(missing_dict)

    # Unknown unexpected field
    unknown_dict = dict(valid_dict)
    unknown_dict["invented_metadata"] = 123
    with pytest.raises(ValueError, match="Unknown manifest key"):
        CorpusClip.from_dict(unknown_dict)


# ---------------------------------------------------------------------------
# 3. Preflight Failure on Stale/Broken Manifest Before Audio Capture
# ---------------------------------------------------------------------------
def test_stale_missing_file_preflight(tmp_path: Path) -> None:
    """If existing manifest has missing audio, preflight must fail before mic capture."""
    corpus_dir = tmp_path / "stale_corpus"
    corpus_dir.mkdir(parents=True)

    # Create manifest referencing nonexistent file
    stale_clip = CorpusClip(
        clip_id="train_heyino_spk01_stale",
        file_path="train/heyino/train_heyino_spk01_stale.wav",
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
    )
    save_manifest(corpus_dir / "manifest.json", [stale_clip])

    call_count = 0

    def spy_recorder(duration: float, sr: int) -> np.ndarray:
        nonlocal call_count
        call_count += 1
        return mock_audio_recorder(duration, sr)

    # Attempt recording into corpus with stale manifest
    with pytest.raises(ValueError, match="Preflight failed"):
        record_and_save_clip(
            output_dir=corpus_dir,
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_02",
            recorder_fn=spy_recorder,
        )

    # Recorder must NOT have been called
    assert call_count == 0


def test_existing_filename_mismatch_preflight_fails_before_capture(tmp_path: Path) -> None:
    """Structural filename/clip-id defects must block capture before the mic is used."""
    corpus_dir = tmp_path / "mismatch_preflight"
    wav_path = corpus_dir / "train" / "heyino" / "wrong_name.wav"
    _make_dummy_wav(wav_path)
    save_manifest(
        corpus_dir / "manifest.json",
        [
            CorpusClip(
                clip_id="train_heyino_spk_01_1000_11112222",
                file_path="train/heyino/wrong_name.wav",
                split="train",
                label="heyino",
                is_positive=True,
                speaker_id="spk_01",
                duration_sec=0.5,
            )
        ],
    )

    called = False

    def spy_recorder(duration: float, sample_rate: int) -> np.ndarray:
        nonlocal called
        called = True
        return mock_audio_recorder(duration, sample_rate)

    with pytest.raises(ValueError, match="Preflight failed"):
        record_and_save_clip(
            output_dir=corpus_dir,
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_02",
            recorder_fn=spy_recorder,
        )

    assert called is False
    assert wav_path.is_file()


def test_manifestless_wav_preflight_fails_without_deletion(tmp_path: Path) -> None:
    """Unindexed audio is preserved and blocks a new capture rather than being adopted."""
    corpus_dir = tmp_path / "manifestless_corpus"
    wav_path = corpus_dir / "train" / "heyino" / "unindexed.wav"
    _make_dummy_wav(wav_path)
    called = False

    def spy_recorder(duration: float, sample_rate: int) -> np.ndarray:
        nonlocal called
        called = True
        return mock_audio_recorder(duration, sample_rate)

    with pytest.raises(ValueError, match="no manifest.json"):
        record_and_save_clip(
            output_dir=corpus_dir,
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_01",
            recorder_fn=spy_recorder,
        )

    assert called is False
    assert wav_path.is_file()


def test_malformed_manifest_preflight(tmp_path: Path) -> None:
    """If existing manifest is malformed JSON, preflight fails before recorder is invoked."""
    corpus_dir = tmp_path / "broken_manifest_corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "manifest.json").write_text("{broken json content", encoding="utf-8")

    call_count = 0

    def spy_recorder(duration: float, sr: int) -> np.ndarray:
        nonlocal call_count
        call_count += 1
        return mock_audio_recorder(duration, sr)

    with pytest.raises(ValueError, match="Preflight failed: existing manifest"):
        record_and_save_clip(
            output_dir=corpus_dir,
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_01",
            recorder_fn=spy_recorder,
        )

    assert call_count == 0


# ---------------------------------------------------------------------------
# 4. Detection of Renamed Speaker, Filename, and Metadata Mismatches
# ---------------------------------------------------------------------------
def test_renamed_speaker_and_filename_mismatches(tmp_path: Path) -> None:
    """Audit must detect filename mismatches, split mismatches, and renamed speaker metadata."""
    corpus_dir = tmp_path / "mismatch_corpus"
    corpus_dir.mkdir(parents=True)

    # 1. Clip with filename stem != clip_id
    wav1 = corpus_dir / "train" / "heyino" / "wrong_filename.wav"
    _make_dummy_wav(wav1)
    clip1 = CorpusClip(
        clip_id="train_heyino_spk01_1000_11112222",
        file_path="train/heyino/wrong_filename.wav",
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
        duration_sec=0.5,
    )

    # 2. Clip with speaker_id metadata != embedded speaker in clip_id
    wav2 = corpus_dir / "train" / "heyino" / "train_heyino_spk01_2000_33334444.wav"
    _make_dummy_wav(wav2)
    clip2 = CorpusClip(
        clip_id="train_heyino_spk01_2000_33334444",
        file_path="train/heyino/train_heyino_spk01_2000_33334444.wav",
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_02",  # Mismatch: clip_id has spk01
        duration_sec=0.5,
    )

    # 3. Clip with split metadata != embedded split in clip_id
    wav3 = corpus_dir / "held_out" / "heyino" / "train_heyino_spk03_3000_55556666.wav"
    _make_dummy_wav(wav3)
    clip3 = CorpusClip(
        clip_id="train_heyino_spk03_3000_55556666",
        file_path="held_out/heyino/train_heyino_spk03_3000_55556666.wav",
        split="held_out",  # Mismatch: clip_id has train_
        label="heyino",
        is_positive=True,
        speaker_id="spk_03",
        duration_sec=0.5,
    )

    save_manifest(corpus_dir / "manifest.json", [clip1, clip2, clip3])

    report = audit_corpus(corpus_dir)
    assert not report.is_healthy

    categories = [iss.category for iss in report.issues]
    assert "filename_clip_id_mismatch" in categories
    assert "metadata_mismatch" in categories

    messages = " ".join(iss.message for iss in report.issues)
    assert "Filename stem 'wrong_filename' does not match clip_id" in messages
    assert "Speaker mismatch" in messages
    assert "Split mismatch" in messages


# ---------------------------------------------------------------------------
# 5. Ambiguous Orphan WAVs: Report and Make No Changes
# ---------------------------------------------------------------------------
def test_ambiguous_orphan_wav_makes_no_changes(tmp_path: Path) -> None:
    """When multiple orphan WAVs match a missing clip_id, report ambiguity and refuse to guess."""
    corpus_dir = tmp_path / "ambiguous_corpus"
    corpus_dir.mkdir(parents=True)

    clip_id = "train_heyino_spk01_1234_abcdef12"
    # Create missing manifest entry pointing to wrong path
    clip = CorpusClip(
        clip_id=clip_id,
        file_path="train/heyino/nonexistent.wav",
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
        duration_sec=0.5,
    )
    manifest_file = corpus_dir / "manifest.json"
    save_manifest(manifest_file, [clip])
    manifest_bytes_before = manifest_file.read_bytes()

    # Create TWO orphan WAVs with the exact same stem matching clip_id in different dirs
    orphan1 = corpus_dir / "train" / "dir1" / f"{clip_id}.wav"
    orphan2 = corpus_dir / "train" / "dir2" / f"{clip_id}.wav"
    _make_dummy_wav(orphan1)
    _make_dummy_wav(orphan2)

    audit = audit_corpus(corpus_dir)
    assert any(iss.category == "ambiguous_match" for iss in audit.issues)

    # Attempt repair
    repaired_report = repair_corpus(corpus_dir)
    assert repaired_report.repaired is False

    # Manifest must be completely untouched
    manifest_bytes_after = manifest_file.read_bytes()
    assert manifest_bytes_before == manifest_bytes_after

    # Audio files must be completely untouched
    assert orphan1.is_file()
    assert orphan2.is_file()


def test_missing_manifest_audit_reports_orphan_wavs(tmp_path: Path) -> None:
    """The repair command must not hide audio when the manifest itself is absent."""
    corpus_dir = tmp_path / "missing_manifest"
    wav_path = corpus_dir / "train" / "heyino" / "unindexed.wav"
    _make_dummy_wav(wav_path)

    report = audit_corpus(corpus_dir)

    assert report.is_healthy is False
    assert "missing_manifest" in [issue.category for issue in report.issues]
    assert "orphan_wav" in [issue.category for issue in report.issues]
    assert report.orphan_wavs == ["train/heyino/unindexed.wav"]


# ---------------------------------------------------------------------------
# 6. Unique Rename/Path Recovery (Atomic and Audio Untouched)
# ---------------------------------------------------------------------------
def test_unique_rename_path_recovery(tmp_path: Path) -> None:
    """When an in-corpus WAV basename uniquely matches a missing clip, reconcile path atomically."""
    corpus_dir = tmp_path / "recovery_corpus"
    corpus_dir.mkdir(parents=True)

    clip_id = "train_heyino_spk_01_9999_abcdabcd"
    wrong_path = "train/wrong_folder/train_heyino_spk_01_9999_abcdabcd.wav"
    clip = CorpusClip(
        clip_id=clip_id,
        file_path=wrong_path,
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
        duration_sec=0.5,
    )
    save_manifest(corpus_dir / "manifest.json", [clip])

    # Put the actual WAV file in the correct folder
    correct_wav = corpus_dir / "train" / "heyino" / f"{clip_id}.wav"
    _make_dummy_wav(correct_wav)
    original_audio_bytes = correct_wav.read_bytes()

    # Pre-repair audit
    audit = audit_corpus(corpus_dir)
    assert not audit.is_healthy
    missing_issue = next(
        (i for i in audit.issues if i.category == "missing_file" and i.clip_id == clip_id),
        None,
    )
    assert missing_issue is not None
    assert missing_issue.reconcilable is True
    assert missing_issue.proposed_file_path == "train/heyino/train_heyino_spk_01_9999_abcdabcd.wav"

    # Execute repair
    repaired = repair_corpus(corpus_dir)
    assert repaired.repaired is True
    assert clip_id in repaired.reconciled_clips

    # Audio file must be completely untouched
    assert correct_wav.is_file()
    assert correct_wav.read_bytes() == original_audio_bytes

    # Manifest must now point to the correct relative path
    loaded = load_manifest(corpus_dir / "manifest.json")
    assert loaded[0].file_path == "train/heyino/train_heyino_spk_01_9999_abcdabcd.wav"

    # Post-repair audit must report healthy
    post_audit = audit_corpus(corpus_dir)
    assert post_audit.is_healthy


# ---------------------------------------------------------------------------
# 7. No Accidental WAV Deletion and Pre-Capture Failure
# ---------------------------------------------------------------------------
def test_pre_capture_speaker_leakage_rejection(tmp_path: Path) -> None:
    """Preflight must reject speaker split leakage before calling recorder_fn."""
    corpus_dir = tmp_path / "leakage_corpus"
    corpus_dir.mkdir(parents=True)

    # Record first clip in train with speaker spk_01
    clip1 = record_and_save_clip(
        output_dir=corpus_dir,
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
        recorder_fn=mock_audio_recorder,
    )
    assert (corpus_dir / clip1.file_path).is_file()

    call_count = 0

    def spy_recorder(dur: float, sr: int) -> np.ndarray:
        nonlocal call_count
        call_count += 1
        return mock_audio_recorder(dur, sr)

    # Attempt to record clip with SAME speaker in held_out
    with pytest.raises(ValueError, match="SPEAKER LEAKAGE"):
        record_and_save_clip(
            output_dir=corpus_dir,
            split="held_out",
            label="heyino",
            is_positive=True,
            speaker_id="spk_01",
            recorder_fn=spy_recorder,
        )

    # Audio recorder must not be called
    assert call_count == 0

    # Train clip and manifest must remain intact
    manifest_clips = load_manifest(corpus_dir / "manifest.json")
    assert len(manifest_clips) == 1
    assert manifest_clips[0].speaker_id == "spk_01"


def test_manifest_write_failure_preserves_existing_manifest(tmp_path: Path) -> None:
    """If manifest writing fails, existing manifest is preserved and final WAV is not unlinked."""
    corpus_dir = tmp_path / "save_fail_corpus"
    corpus_dir.mkdir(parents=True)

    # Initial good clip
    record_and_save_clip(
        output_dir=corpus_dir,
        split="train",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
        recorder_fn=mock_audio_recorder,
    )
    manifest_content_before = (corpus_dir / "manifest.json").read_text(encoding="utf-8")

    # Simulate failure in save_manifest on second clip
    with patch(
        "scripts.wakeword.record_heyino_corpus.save_manifest",
        side_effect=OSError("Disk write simulated failure"),
    ):
        with pytest.raises(OSError, match="Disk write simulated failure"):
            record_and_save_clip(
                output_dir=corpus_dir,
                split="train",
                label="heyino",
                is_positive=True,
                speaker_id="spk_01",
                recorder_fn=mock_audio_recorder,
            )

    # Existing manifest is preserved intact
    manifest_content_after = (corpus_dir / "manifest.json").read_text(encoding="utf-8")
    assert manifest_content_before == manifest_content_after


# ---------------------------------------------------------------------------
# 8. Normal Positive Recording Flow
# ---------------------------------------------------------------------------
def test_normal_positive_flow(tmp_path: Path) -> None:
    """Verify normal positive clip recording, 16kHz mono format, and manifest validation."""
    corpus_dir = tmp_path / "positive_corpus"

    clip = record_and_save_clip(
        output_dir=corpus_dir,
        split="train",
        label=CANONICAL_WAKE_LABEL,
        is_positive=True,
        duration_sec=1.5,
        speaker_id="spk_pos",
        recorder_fn=mock_audio_recorder,
    )

    wav_file = corpus_dir / clip.file_path
    assert wav_file.is_file()

    samples, sr = read_pcm16_wav(wav_file)
    assert sr == 16000
    assert len(samples) == int(1.5 * 16000)

    # Manifest contains clip
    manifest_clips = load_manifest(corpus_dir / "manifest.json")
    assert len(manifest_clips) == 1
    assert manifest_clips[0].clip_id == clip.clip_id
    assert manifest_clips[0].is_positive is True
    assert manifest_clips[0].label in ALLOWED_PRONUNCIATION_VARIANTS

    val_res = validate_manifest(manifest_clips, base_dir=corpus_dir, check_file_exists=True)
    assert val_res.valid is True


# ---------------------------------------------------------------------------
# 9. Hard-Negative Recording Flow
# ---------------------------------------------------------------------------
def test_hard_negative_flow(tmp_path: Path) -> None:
    """Verify recording hard-negative confusers with metadata and validation."""
    corpus_dir = tmp_path / "negative_corpus"

    clip = record_and_save_clip(
        output_dir=corpus_dir,
        split="train",
        label="hey",
        is_positive=False,
        confuser_family="phonetic_confusers",
        duration_sec=1.0,
        speaker_id="spk_neg",
        recorder_fn=mock_audio_recorder,
    )

    wav_file = corpus_dir / clip.file_path
    assert wav_file.is_file()

    manifest_clips = load_manifest(corpus_dir / "manifest.json")
    assert len(manifest_clips) == 1
    assert manifest_clips[0].is_positive is False
    assert manifest_clips[0].confuser_family == "phonetic_confusers"
    assert manifest_clips[0].label == "hey"

    val_res = validate_manifest(manifest_clips, base_dir=corpus_dir, check_file_exists=True)
    assert val_res.valid is True


# ---------------------------------------------------------------------------
# 10. Interactive Session Seeding for Negative Recording
# ---------------------------------------------------------------------------
def test_interactive_session_seeding_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify seeded defaults for negative recording interactive sessions."""
    corpus_dir = tmp_path / "interactive_corpus"

    # Simulate user inputs:
    # 1. Split [train] -> Enter (accept default)
    # 2. Speaker ID -> "spk_user"
    # 3. Distance [mid_1_5m] -> Enter
    # 4. Noise [clean_quiet] -> Enter
    # 5. Is positive [n] -> Enter (accept seeded default 'n')
    # 6. Negative family [phonetic_confusers] -> Enter (accept seeded default)
    # 7. Negative prompt [negative] -> Enter
    # 8. Duration [2.5] -> "1.0"
    # 9. Countdown confirmation -> Enter
    inputs = [
        "",  # split: accept train
        "spk_user",  # speaker
        "",  # distance
        "",  # noise
        "",  # positive: accept n
        "",  # confuser family: accept phonetic_confusers
        "",  # label: accept negative
        "1.0",  # duration
        "",  # countdown confirmation Enter
    ]
    input_stream = io.StringIO("\n".join(inputs) + "\n")
    monkeypatch.setattr("sys.stdin", input_stream)
    monkeypatch.setattr("time.sleep", lambda s: None)

    ret = run_interactive_session(
        output_dir=corpus_dir,
        recorder_fn=mock_audio_recorder,
        initial_split="train",
        initial_is_negative=True,
        initial_confuser_family="phonetic_confusers",
        initial_duration=2.5,
    )

    assert ret == 0

    manifest_clips = load_manifest(corpus_dir / "manifest.json")
    assert len(manifest_clips) == 1
    clip = manifest_clips[0]
    assert clip.split == "train"
    assert clip.is_positive is False
    assert clip.confuser_family == "phonetic_confusers"
    assert clip.speaker_id == "spk_user"
    assert clip.duration_sec == pytest.approx(1.0, 0.05)


# ---------------------------------------------------------------------------
# 11. Atomic Manifest Save Safety
# ---------------------------------------------------------------------------
def test_save_manifest_atomic_safety(tmp_path: Path) -> None:
    """save_manifest writes atomically and leaves target untouched on failure."""
    manifest_path = tmp_path / "atomic_manifest.json"
    initial_clip = CorpusClip(
        clip_id="c_init",
        file_path="train/init.wav",
        split="train",
        label="heyino",
        is_positive=True,
    )
    save_manifest(manifest_path, [initial_clip])
    content_before = manifest_path.read_text(encoding="utf-8")

    # Attempt save with invalid object causing serialization error
    class Unserializable:
        def to_dict(self) -> dict[str, object]:
            return {"bad": object()}

    with pytest.raises(TypeError):
        save_manifest(manifest_path, [Unserializable()])  # type: ignore[list-item]

    # Target manifest remains intact and unchanged
    content_after = manifest_path.read_text(encoding="utf-8")
    assert content_before == content_after

    # No leftover temporary files
    leftover_tmps = list(tmp_path.glob(".*.tmp_*"))
    assert len(leftover_tmps) == 0

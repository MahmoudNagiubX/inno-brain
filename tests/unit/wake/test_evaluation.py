"""Unit tests for Heyino wake word evaluation, corpus spec, recording, and training plan tooling.

Validates:
- Manifest validation with strict data/speaker leakage detection between splits.
- Zero-duration negative sets handled safely without division by zero.
- Empty manifests handled safely.
- Safe local recording and WAV generation using mock audio injection (no mic hardware).
- Training plan generator enforcing minimum 50,000 augmented positives.
- Lazy import safety and DATA_PENDING status when assets are absent.
- Offline evaluation core with injected engines, threshold sweeps, latency percentiles,
  and granular slice breakdowns.
- JSON, CSV, and Markdown report exporters.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from innobrain.audio.io import read_pcm16_wav
from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineHealth,
    WakeWordEngine,
)
from scripts.wakeword.evaluate_wakeword import (
    CalibratedThreshold,
    ClipEvaluationResult,
    EvaluationMetrics,
    compute_percentile,
    compute_slice_metrics,
    evaluate_dataset,
    generate_markdown_summary,
    run_two_stage_evaluation,
    select_calibrated_threshold,
    sweep_thresholds,
    write_csv_clip_results,
    write_json_report,
)
from scripts.wakeword.heyino_corpus_spec import (
    ALLOWED_PRONUNCIATION_VARIANTS,
    HARD_NEGATIVE_FAMILIES,
    VALID_SPLITS,
    CorpusClip,
    load_manifest,
    save_manifest,
    validate_manifest,
)
from scripts.wakeword.record_heyino_corpus import (
    create_clip_id,
    mock_audio_recorder,
    record_and_save_clip,
)
from scripts.wakeword.train_openwakeword import (
    generate_training_plan,
    run_training_lazy,
    verify_training_prerequisites,
)


# ---------------------------------------------------------------------------
# Injected Test Engine for Deterministic Evaluation Testing
# ---------------------------------------------------------------------------
class ConfigurableMockWakeEngine:
    """Deterministic WakeWordEngine for testing offline evaluation."""

    def __init__(
        self,
        threshold: float = 0.5,
        trigger_on_pattern: bytes | None = None,
        score_to_return: float = 0.85,
        frame_length: int = 1280,
    ) -> None:
        self._threshold = threshold
        self._trigger_on_pattern = trigger_on_pattern
        self._score_to_return = score_to_return
        self._frame_length = frame_length
        self._sample_rate_hz = SAMPLE_RATE_HZ
        self.reset_call_count = 0
        self.process_call_count = 0

    @property
    def sample_rate_hz(self) -> int:
        return self._sample_rate_hz

    @property
    def frame_length(self) -> int:
        return self._frame_length

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(ready=True, engine_name="mock_engine")

    def process(self, pcm16: bytes) -> WakeDetection | None:
        self.process_call_count += 1
        # If trigger pattern specified, match; otherwise trigger if score >= threshold
        if self._trigger_on_pattern is not None:
            if self._trigger_on_pattern in pcm16:
                if self._score_to_return >= self._threshold:
                    return WakeDetection(
                        label=CANONICAL_WAKE_LABEL,
                        detector="mock_engine",
                        detected_at_monotonic=100.0,
                        score=self._score_to_return,
                    )
            return None

        # General score-based trigger
        if self._score_to_return >= self._threshold:
            return WakeDetection(
                label=CANONICAL_WAKE_LABEL,
                detector="mock_engine",
                detected_at_monotonic=100.0,
                score=self._score_to_return,
            )
        return None

    def reset(self) -> None:
        self.reset_call_count += 1

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Test Suite 1: Corpus Specification & Manifest Validation
# ---------------------------------------------------------------------------
def test_corpus_spec_constants() -> None:
    assert CANONICAL_WAKE_LABEL == "heyino"
    assert "heyino" in ALLOWED_PRONUNCIATION_VARIANTS
    assert "hayino" in ALLOWED_PRONUNCIATION_VARIANTS
    assert "heyno" in ALLOWED_PRONUNCIATION_VARIANTS
    assert set(VALID_SPLITS) == {"train", "calibration", "held_out"}

    # Hard-negative families must cover all Gate 5C.0 required groups
    required_families = {
        "phonetic_confusers",
        "egyptian_conversation",
        "english_conversation",
        "announcements",
        "crowd_music_claps",
        "bumps_impulse",
        "tts_bleed",
    }
    assert required_families.issubset(set(HARD_NEGATIVE_FAMILIES.keys()))
    assert "hey" in HARD_NEGATIVE_FAMILIES["phonetic_confusers"]
    assert "inno" in HARD_NEGATIVE_FAMILIES["phonetic_confusers"]
    assert "I know" in HARD_NEGATIVE_FAMILIES["phonetic_confusers"]
    assert "Nino" in HARD_NEGATIVE_FAMILIES["phonetic_confusers"]


def test_manifest_validation_valid() -> None:
    clips = [
        CorpusClip(
            clip_id="c1",
            file_path="train/heyino/c1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_01",
            duration_sec=2.0,
        ),
        CorpusClip(
            clip_id="c2",
            file_path="train/confusers/c2.wav",
            split="train",
            label="hey no",
            is_positive=False,
            speaker_id="spk_01",
            confuser_family="phonetic_confusers",
            duration_sec=2.5,
        ),
        CorpusClip(
            clip_id="c3",
            file_path="calibration/heyino/c3.wav",
            split="calibration",
            label="heyino",
            is_positive=True,
            speaker_id="spk_02",
            duration_sec=1.8,
        ),
        CorpusClip(
            clip_id="c4",
            file_path="held_out/heyino/c4.wav",
            split="held_out",
            label="heyino",
            is_positive=True,
            speaker_id="spk_03",
            duration_sec=2.1,
        ),
    ]

    res = validate_manifest(clips)
    assert res.valid is True
    assert len(res.errors) == 0
    assert res.clip_count == 4
    assert res.splits_summary["train"]["total_clips"] == 2
    assert res.splits_summary["calibration"]["total_clips"] == 1
    assert res.splits_summary["held_out"]["total_clips"] == 1


def test_manifest_validation_malformed_fields() -> None:
    # 1. Invalid sample rate
    res_sr = validate_manifest([
        CorpusClip(
            clip_id="bad_sr",
            file_path="train/c1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            sample_rate_hz=44100,
        )
    ])
    assert res_sr.valid is False
    assert any("sample rate" in err.lower() for err in res_sr.errors)

    # 2. Invalid channels
    res_ch = validate_manifest([
        CorpusClip(
            clip_id="bad_ch",
            file_path="train/c1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            channels=2,
        )
    ])
    assert res_ch.valid is False
    assert any("mono required" in err.lower() for err in res_ch.errors)

    # 3. Negative duration
    res_dur = validate_manifest([
        CorpusClip(
            clip_id="bad_dur",
            file_path="train/c1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            duration_sec=-1.5,
        )
    ])
    assert res_dur.valid is False
    assert any("negative duration" in err.lower() for err in res_dur.errors)

    # 4. Invalid split name
    res_split = validate_manifest([
        CorpusClip(
            clip_id="bad_split",
            file_path="dev/c1.wav",
            split="development",
            label="heyino",
            is_positive=True,
        )
    ])
    assert res_split.valid is False
    assert any("invalid split" in err.lower() for err in res_split.errors)

    # 5. Positive clip with disallowed label
    res_lbl = validate_manifest([
        CorpusClip(
            clip_id="bad_lbl",
            file_path="train/c1.wav",
            split="train",
            label="unrecognized_phrase",
            is_positive=True,
        )
    ])
    assert res_lbl.valid is False
    assert any("invalid label" in err.lower() for err in res_lbl.errors)

    # 6. Negative clip with positive wake label
    res_neg_lbl = validate_manifest([
        CorpusClip(
            clip_id="bad_neg_lbl",
            file_path="train/c1.wav",
            split="train",
            label="heyino",
            is_positive=False,
        )
    ])
    assert res_neg_lbl.valid is False
    assert any("cannot have positive label" in err.lower() for err in res_neg_lbl.errors)

    # 7. Duplicate clip_id
    res_dup = validate_manifest([
        CorpusClip(
            clip_id="c1",
            file_path="train/1.wav",
            split="train",
            label="heyino",
            is_positive=True,
        ),
        CorpusClip(
            clip_id="c1",
            file_path="train/2.wav",
            split="train",
            label="heyino",
            is_positive=True,
        ),
    ])
    assert res_dup.valid is False
    assert any("duplicate clip_id" in err.lower() for err in res_dup.errors)


def test_manifest_data_leakage_detection() -> None:
    # 1. File path leakage between train and held_out
    clips_file_leak = [
        CorpusClip(
            clip_id="c1",
            file_path="shared/sample.wav",
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_01",
        ),
        CorpusClip(
            clip_id="c2",
            file_path="shared/sample.wav",
            split="held_out",
            label="heyino",
            is_positive=True,
            speaker_id="spk_02",
        ),
    ]
    res_file = validate_manifest(clips_file_leak)
    assert res_file.valid is False
    assert any("DATA LEAKAGE DETECTED" in err for err in res_file.errors)

    # 2. Speaker leakage between train and held_out
    clips_spk_leak = [
        CorpusClip(
            clip_id="c1",
            file_path="train/spk1_1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_overlap",
        ),
        CorpusClip(
            clip_id="c2",
            file_path="held_out/spk1_2.wav",
            split="held_out",
            label="heyino",
            is_positive=True,
            speaker_id="spk_overlap",
        ),
    ]
    res_spk = validate_manifest(clips_spk_leak)
    assert res_spk.valid is False
    assert any("SPEAKER LEAKAGE DETECTED" in err for err in res_spk.errors)


def test_zero_duration_negative_sets_safely_handled() -> None:
    """Safe handling of zero-duration negative sets without division by zero."""
    clips = [
        CorpusClip(
            clip_id="c1",
            file_path="train/1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            duration_sec=2.0,
        )
    ]
    # No negative clips at all
    res = validate_manifest(clips)
    assert res.valid is True

    # Evaluation with 0 negative hours
    mock_eng = ConfigurableMockWakeEngine(threshold=0.5, score_to_return=0.9)
    metrics, _ = evaluate_dataset(
        engine=mock_eng,
        clips=clips,
        threshold=0.5,
        audio_loader=lambda c, b: b"\x00\x00" * 16000,
    )
    assert metrics.total_negative == 0
    assert metrics.total_negative_hours == 0.0
    # Safe handling: false_activations_per_hour should be None or 0.0, no ZeroDivisionError!
    assert metrics.false_activations_per_hour is None or metrics.false_activations_per_hour == 0.0


def test_empty_manifest_safely_handled() -> None:
    res = validate_manifest([])
    assert res.valid is True
    assert res.clip_count == 0
    assert res.total_duration_sec == 0.0


def test_manifest_serialization(tmp_path: Path) -> None:
    clips = [
        CorpusClip(
            clip_id="c1",
            file_path="train/1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_01",
            duration_sec=1.5,
        )
    ]
    json_path = tmp_path / "manifest.json"
    save_manifest(json_path, clips)
    assert json_path.is_file()

    loaded = load_manifest(json_path)
    assert len(loaded) == 1
    assert loaded[0].clip_id == "c1"
    assert loaded[0].label == "heyino"


# ---------------------------------------------------------------------------
# Test Suite 2: Corpus Recorder Tooling
# ---------------------------------------------------------------------------
def test_create_clip_id() -> None:
    cid = create_clip_id(split="train", label="heyino", speaker_id="spk_01")
    assert cid.startswith("train_heyino_spk_01_")


def test_mock_audio_recorder() -> None:
    samples = mock_audio_recorder(duration_seconds=1.0, sample_rate_hz=16000)
    assert isinstance(samples, np.ndarray)
    assert samples.dtype == np.int16
    assert len(samples) == 16000


def test_record_and_save_clip_mock(tmp_path: Path) -> None:
    output_dir = tmp_path / "test_corpus"

    clip = record_and_save_clip(
        output_dir=output_dir,
        split="train",
        label="heyino",
        is_positive=True,
        duration_sec=1.0,
        speaker_id="spk_test",
        recorder_fn=mock_audio_recorder,
    )

    wav_path = output_dir / clip.file_path
    assert wav_path.is_file()

    samples, sr = read_pcm16_wav(wav_path)
    assert sr == 16000
    assert len(samples) == 16000
    assert clip.duration_sec == pytest.approx(1.0, 0.01)

    # Manifest should be present and valid
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.is_file()
    clips = load_manifest(manifest_path)
    assert len(clips) == 1
    assert clips[0].clip_id == clip.clip_id

    # Verify manifest validation passes with real file existence check
    val_res = validate_manifest(clips, base_dir=output_dir, check_file_exists=True)
    assert val_res.valid is True


# ---------------------------------------------------------------------------
# Test Suite 3: Training Plan Generator
# ---------------------------------------------------------------------------
def test_training_plan_minimum_50k_positives() -> None:
    plan = generate_training_plan(min_planned_positives=50_000)
    assert plan.min_planned_positive_count >= 50_000
    assert plan.augmentation.target_positive_count >= 50_000

    # Gate 5C.0 requirement: minimum 50,000 augmented examples enforced
    with pytest.raises(ValueError, match="minimum planned positive count of 50000"):
        generate_training_plan(min_planned_positives=49_999)


def test_training_plan_negative_families_and_serialization(tmp_path: Path) -> None:
    plan_path = tmp_path / "heyino_plan.json"
    plan = generate_training_plan(output_path=plan_path, min_planned_positives=50_000)
    assert plan_path.is_file()
    assert plan.target_phrase == "heyino"

    loaded = json.loads(plan_path.read_text(encoding="utf-8"))
    assert loaded["target_phrase"] == "heyino"
    assert loaded["min_planned_positive_count"] == 50_000
    assert loaded["negative_allocation"]["total_planned_negatives"] == 100_000


def test_verify_training_prerequisites_data_pending(tmp_path: Path) -> None:
    # When no manifest or data is present, prerequisites must report DATA_PENDING
    status = verify_training_prerequisites(manifest_path=None)
    assert status.ready is False
    assert "DATA_PENDING" in status.status or "DEPENDENCIES_PENDING" in status.status
    assert not status.ready

    # When manifest has 0 train positive clips
    empty_manifest = tmp_path / "empty_manifest.json"
    save_manifest(empty_manifest, [])
    status_empty = verify_training_prerequisites(manifest_path=empty_manifest)
    assert status_empty.ready is False
    assert any("DATA_PENDING" in r for r in status_empty.reasons)


# ---------------------------------------------------------------------------
# Test Suite 4: Offline Evaluation Core & Metrics Calculation
# ---------------------------------------------------------------------------
def test_compute_percentile() -> None:
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    p50 = compute_percentile(vals, 50.0)
    assert p50 == 30.0
    assert compute_percentile([], 90.0) is None


def test_compute_slice_metrics() -> None:
    results = [
        ClipEvaluationResult(
            clip_id="1",
            file_path="f1",
            split="test",
            label="heyino",
            is_positive=True,
            detected=True,
            score=0.9,
            threshold=0.5,
            latency_ms=120.0,
            is_tp=True,
            is_fn=False,
            is_tn=False,
            is_fp=False,
            duration_sec=2.0,
            distance="near_0_5m",
        ),
        ClipEvaluationResult(
            clip_id="2",
            file_path="f2",
            split="test",
            label="heyino",
            is_positive=True,
            detected=False,
            score=0.4,
            threshold=0.5,
            latency_ms=None,
            is_tp=False,
            is_fn=True,
            is_tn=False,
            is_fp=False,
            duration_sec=2.0,
            distance="near_0_5m",
        ),
    ]

    metrics = compute_slice_metrics("distance", "near_0_5m", results)
    assert metrics.total_clips == 2
    assert metrics.positive_clips == 2
    assert metrics.tp == 1
    assert metrics.fn == 1
    assert metrics.recall == 0.5
    assert metrics.frr == 0.5


def test_offline_evaluation_dataset_and_breakdowns() -> None:
    # 2 positive clips (one detected, one missed)
    # 2 negative clips (one false alarm, one true negative)
    clips = [
        CorpusClip(
            clip_id="p1",
            file_path="p1.wav",
            split="calibration",
            label="heyino",
            is_positive=True,
            speaker_id="spk_A",
            distance="mid_1_5m",
            noise_condition="clean_quiet",
            pronunciation="canonical",
            duration_sec=3.0,
        ),
        CorpusClip(
            clip_id="p2",
            file_path="p2.wav",
            split="calibration",
            label="heyino",
            is_positive=True,
            speaker_id="spk_B",
            distance="far_3_0m",
            noise_condition="event_crowd",
            pronunciation="hayino",
            duration_sec=3.0,
        ),
        CorpusClip(
            clip_id="n1",
            file_path="n1.wav",
            split="calibration",
            label="hey no",
            is_positive=False,
            speaker_id="spk_A",
            distance="mid_1_5m",
            noise_condition="clean_quiet",
            confuser_family="phonetic_confusers",
            duration_sec=3600.0,  # 1 hour
        ),
        CorpusClip(
            clip_id="n2",
            file_path="n2.wav",
            split="calibration",
            label="table knock",
            is_positive=False,
            speaker_id=None,
            distance=None,
            noise_condition="mic_bumps",
            confuser_family="bumps_impulse",
            duration_sec=3600.0,  # 1 hour
        ),
    ]

    # Create dummy audio payload
    # p1 and n1 contain b"TRIGGER", p2 and n2 do not
    audio_map = {
        "p1": b"\x01\x00" * 1280 + b"TRIGGER" + b"\x00\x00" * 1280,
        "p2": b"\x00\x00" * 2560,
        "n1": b"\x01\x00" * 1280 + b"TRIGGER" + b"\x00\x00" * 1280,
        "n2": b"\x00\x00" * 2560,
    }

    mock_engine = ConfigurableMockWakeEngine(
        threshold=0.5,
        trigger_on_pattern=b"TRIGGER",
        score_to_return=0.88,
    )

    metrics, results = evaluate_dataset(
        engine=mock_engine,
        clips=clips,
        threshold=0.5,
        split_name="calibration",
        audio_loader=lambda c, b: audio_map[c.clip_id],
    )

    assert metrics.total_clips == 4
    assert metrics.total_positive == 2
    assert metrics.total_negative == 2
    assert metrics.tp == 1
    assert metrics.fn == 1
    assert metrics.fp == 1
    assert metrics.tn == 1
    assert metrics.recall == 0.5
    assert metrics.frr == 0.5

    # 1 FP across 2.0 total negative hours = 0.5 FA/hour
    assert metrics.total_negative_hours == pytest.approx(2.0, 0.01)
    assert metrics.false_activations_per_hour == pytest.approx(0.5, 0.01)

    # Latency measured on TP (p1 triggered on second chunk)
    assert metrics.latency_p50_ms is not None
    assert metrics.latency_p50_ms > 0

    # Slices
    assert "mid_1_5m" in metrics.by_distance
    assert metrics.by_distance["mid_1_5m"].recall == 1.0
    assert "far_3_0m" in metrics.by_distance
    assert metrics.by_distance["far_3_0m"].recall == 0.0

    assert "phonetic_confusers" in metrics.by_confuser_family
    assert metrics.by_confuser_family["phonetic_confusers"].fp == 1
    assert "bumps_impulse" in metrics.by_confuser_family
    assert metrics.by_confuser_family["bumps_impulse"].fp == 0


def test_threshold_sweep_and_two_stage_evaluation(tmp_path: Path) -> None:
    # Build a calibrated manifest with distinct calibration and held-out splits
    manifest_clips = [
        # Calibration positive and negative
        CorpusClip(
            clip_id="cal_pos",
            file_path="cal_pos.wav",
            split="calibration",
            label="heyino",
            is_positive=True,
            speaker_id="spk_cal",
            duration_sec=2.0,
        ),
        CorpusClip(
            clip_id="cal_neg",
            file_path="cal_neg.wav",
            split="calibration",
            label="hey no",
            is_positive=False,
            speaker_id="spk_cal",
            duration_sec=7200.0,  # 2 hours
        ),
        # Held-out positive and negative (disjoint speaker!)
        CorpusClip(
            clip_id="hold_pos",
            file_path="hold_pos.wav",
            split="held_out",
            label="heyino",
            is_positive=True,
            speaker_id="spk_hold",
            duration_sec=2.0,
        ),
        CorpusClip(
            clip_id="hold_neg",
            file_path="hold_neg.wav",
            split="held_out",
            label="inno",
            is_positive=False,
            speaker_id="spk_hold",
            duration_sec=7200.0,  # 2 hours
        ),
    ]

    manifest_file = tmp_path / "eval_manifest.json"
    save_manifest(manifest_file, manifest_clips)

    # Engine factory where score is 0.75 for positive and 0.40 for negative
    def factory(thresh: float) -> WakeWordEngine:
        # Returns engine that triggers if threshold <= 0.70 on positive, never on negative
        class DynamicEngine(ConfigurableMockWakeEngine):
            def process(self, pcm16: bytes) -> WakeDetection | None:
                if b"POS" in pcm16 and thresh <= 0.70:
                    return WakeDetection(
                        label=CANONICAL_WAKE_LABEL,
                        detector="dynamic",
                        detected_at_monotonic=1.0,
                        score=0.75,
                    )
                return None

        return DynamicEngine(threshold=thresh)

    def audio_loader(c: CorpusClip, b: Path | None) -> bytes:
        if c.is_positive:
            return b"POS" + (b"\x00\x00" * 1280)
        return b"NEG" + (b"\x00\x00" * 1280)

    calib_m, held_m = run_two_stage_evaluation(
        manifest_path=manifest_file,
        engine_factory=factory,
        threshold_sweep=[0.3, 0.5, 0.7, 0.9],
        output_dir=tmp_path / "reports",
        audio_loader=audio_loader,
        model_name="mock_candidate",
    )

    # At threshold <= 0.70, recall is 1.0, FA/hr is 0.0
    assert calib_m.recall == 1.0
    assert held_m.recall == 1.0
    assert held_m.frr == 0.0
    assert held_m.false_activations_per_hour == 0.0

    # Reports exported
    assert (tmp_path / "reports" / "mock_candidate_held_out_metrics.json").is_file()
    assert (tmp_path / "reports" / "mock_candidate_held_out_clips.csv").is_file()
    assert (tmp_path / "reports" / "mock_candidate_held_out_report.md").is_file()


def test_select_calibrated_threshold() -> None:
    # Candidate 1: low threshold -> high recall, but high FA/hr
    m1 = sweep_thresholds(
        engine_factory=lambda t: ConfigurableMockWakeEngine(threshold=t, score_to_return=0.8),
        clips=[
            CorpusClip(
                clip_id="1",
                file_path="1",
                split="calibration",
                label="heyino",
                is_positive=True,
                duration_sec=1.0,
            ),
            CorpusClip(
                clip_id="2",
                file_path="2",
                split="calibration",
                label="neg",
                is_positive=False,
                duration_sec=3600.0,
            ),
        ],
        thresholds=[0.3],
        audio_loader=lambda c, b: b"\x00\x00" * 1280,
    )[0]
    # In m1, mock engine triggers for both -> FP=1 (1.0 FA/hr), TP=1 (Recall=1.0)
    assert m1.false_activations_per_hour == pytest.approx(1.0, 0.01)

    # Candidate 2: higher threshold -> score_to_return < threshold -> 0 FA/hr, 0 recall
    m2 = sweep_thresholds(
        engine_factory=lambda t: ConfigurableMockWakeEngine(threshold=t, score_to_return=0.8),
        clips=[
            CorpusClip(
                clip_id="1",
                file_path="1",
                split="calibration",
                label="heyino",
                is_positive=True,
                duration_sec=1.0,
            ),
            CorpusClip(
                clip_id="2",
                file_path="2",
                split="calibration",
                label="neg",
                is_positive=False,
                duration_sec=3600.0,
            ),
        ],
        thresholds=[0.9],
        audio_loader=lambda c, b: b"\x00\x00" * 1280,
    )[0]
    assert m2.false_activations_per_hour == pytest.approx(0.0, 0.01)

    # When min_recall=0.0 is permitted, candidate 2 (0.9) meets FA target
    best_thresh_zero_recall = select_calibrated_threshold(
        [m1, m2], max_fa_per_hour=0.5, min_recall=0.0
    )
    assert best_thresh_zero_recall == 0.9

    # With default min_recall=0.98, candidate 1 (0.3) is honored for meeting recall
    best_thresh_rec = select_calibrated_threshold([m1, m2], max_fa_per_hour=0.5)
    assert best_thresh_rec == 0.3
    assert best_thresh_rec.status == "FALLBACK_RECALL_MET_FA_EXCEEDED"


def test_report_exporters(tmp_path: Path) -> None:
    mock_eng = ConfigurableMockWakeEngine(threshold=0.5, score_to_return=0.9)
    clip = CorpusClip(
        clip_id="test_clip",
        file_path="test.wav",
        split="held_out",
        label="heyino",
        is_positive=True,
        speaker_id="spk_01",
        distance="near_0_5m",
        noise_condition="clean_quiet",
        pronunciation="canonical",
        duration_sec=2.0,
    )
    metrics, clip_results = evaluate_dataset(
        engine=mock_eng,
        clips=[clip],
        threshold=0.5,
        split_name="held_out",
        audio_loader=lambda c, b: b"\x00\x00" * 2560,
    )

    # JSON export
    json_path = tmp_path / "report.json"
    write_json_report(json_path, metrics, clip_results)
    assert json_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["recall"] == 1.0
    assert len(data["clips"]) == 1

    # CSV export
    csv_path = tmp_path / "results.csv"
    write_csv_clip_results(csv_path, clip_results)
    assert csv_path.is_file()
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # header + 1 row
    assert "test_clip" in lines[1]

    # Markdown export
    md_content = generate_markdown_summary(
        metrics,
        title="Heyino Benchmark Test",
        model_name="openwakeword",
        acceptance_state="PROVISIONAL",
    )
    assert "# Heyino Benchmark Test" in md_content
    assert "Recall (Detection Rate)" in md_content
    assert "PROVISIONAL" in md_content


# ---------------------------------------------------------------------------
# Test Suite 5: Review Findings Regressions & Hardened Boundaries
# ---------------------------------------------------------------------------
def test_corpus_clip_from_dict_strict_rejection() -> None:
    valid_data = {
        "clip_id": "c1",
        "file_path": "train/1.wav",
        "split": "train",
        "label": "heyino",
        "is_positive": True,
    }
    clip = CorpusClip.from_dict(valid_data)
    assert clip.clip_id == "c1"

    # Strict: unknown manifest keys must raise ValueError, not silently drop
    invalid_data = dict(valid_data)
    invalid_data["unknown_key"] = "bad_value"
    with pytest.raises(ValueError, match="Unknown manifest key"):
        CorpusClip.from_dict(invalid_data)


def test_manifest_speaker_isolation_train_calibration() -> None:
    # Speaker overlap between train and calibration must be detected as leakage
    clips = [
        CorpusClip(
            clip_id="c1",
            file_path="train/spk1.wav",
            split="train",
            label="heyino",
            is_positive=True,
            speaker_id="spk_shared",
        ),
        CorpusClip(
            clip_id="c2",
            file_path="calibration/spk2.wav",
            split="calibration",
            label="heyino",
            is_positive=True,
            speaker_id="spk_shared",
        ),
    ]
    res = validate_manifest(clips)
    assert res.valid is False
    assert any(
        "Speakers present in both train and calibration" in err
        for err in res.errors
    )


def test_select_calibrated_threshold_honors_min_recall() -> None:
    # Candidate 1: meets min_recall (0.98), FA/hr is 0.8
    # Candidate 2: meets min_recall (0.98), FA/hr is 0.10 -> meets max_fa_per_hour
    # Candidate 3: recall 0.92 (< 0.98), FA/hr is 0.0 (lowest FA, but recall fails)
    c1 = EvaluationMetrics(
        threshold=0.3,
        split="calibration",
        total_clips=100,
        total_positive=50,
        total_negative=50,
        total_duration_sec=36000.0,
        total_negative_hours=10.0,
        tp=49,
        fn=1,
        fp=8,
        tn=42,
        recall=0.98,
        frr=0.02,
        false_positive_rate=0.16,
        false_activations_per_hour=0.8,
        latency_p50_ms=150.0,
        latency_p90_ms=200.0,
        latency_p95_ms=220.0,
        latency_p99_ms=250.0,
        latency_mean_ms=160.0,
    )
    c2 = EvaluationMetrics(
        threshold=0.5,
        split="calibration",
        total_clips=100,
        total_positive=50,
        total_negative=50,
        total_duration_sec=36000.0,
        total_negative_hours=10.0,
        tp=49,
        fn=1,
        fp=1,
        tn=49,
        recall=0.98,
        frr=0.02,
        false_positive_rate=0.02,
        false_activations_per_hour=0.10,
        latency_p50_ms=160.0,
        latency_p90_ms=210.0,
        latency_p95_ms=230.0,
        latency_p99_ms=260.0,
        latency_mean_ms=170.0,
    )
    c3 = EvaluationMetrics(
        threshold=0.7,
        split="calibration",
        total_clips=100,
        total_positive=50,
        total_negative=50,
        total_duration_sec=36000.0,
        total_negative_hours=10.0,
        tp=46,
        fn=4,
        fp=0,
        tn=50,
        recall=0.92,
        frr=0.08,
        false_positive_rate=0.0,
        false_activations_per_hour=0.0,
        latency_p50_ms=180.0,
        latency_p90_ms=240.0,
        latency_p95_ms=260.0,
        latency_p99_ms=280.0,
        latency_mean_ms=190.0,
    )

    # With min_recall=0.98 and max_fa_per_hour=0.10, c2 must be selected over c3
    chosen = select_calibrated_threshold([c1, c2, c3], max_fa_per_hour=0.10, min_recall=0.98)
    assert chosen == 0.5
    assert isinstance(chosen, CalibratedThreshold)
    assert chosen.targets_met is True
    assert chosen.status == "TARGETS_MET"


def test_select_calibrated_threshold_zero_neg_duration_unmeasured() -> None:
    # Missing negative duration must NOT be treated as measured zero FA/hour
    m = EvaluationMetrics(
        threshold=0.5,
        split="calibration",
        total_clips=10,
        total_positive=10,
        total_negative=0,
        total_duration_sec=20.0,
        total_negative_hours=0.0,
        tp=10,
        fn=0,
        fp=0,
        tn=0,
        recall=1.0,
        frr=0.0,
        false_positive_rate=0.0,
        false_activations_per_hour=None,  # Unmeasured
        latency_p50_ms=150.0,
        latency_p90_ms=180.0,
        latency_p95_ms=190.0,
        latency_p99_ms=200.0,
        latency_mean_ms=160.0,
    )
    chosen = select_calibrated_threshold([m], max_fa_per_hour=0.10, min_recall=0.98)
    assert chosen == 0.5
    # Must NOT claim targets_met because negative hours are unmeasured
    assert chosen.targets_met is False
    assert chosen.status == "FALLBACK_UNMEASURED_FA"


def test_select_calibrated_threshold_fallback_state() -> None:
    # No candidate meets both targets: recall=0.90 (< 0.98), FA/hr=1.5 (> 0.10)
    m = EvaluationMetrics(
        threshold=0.6,
        split="calibration",
        total_clips=20,
        total_positive=10,
        total_negative=10,
        total_duration_sec=7200.0,
        total_negative_hours=2.0,
        tp=9,
        fn=1,
        fp=3,
        tn=7,
        recall=0.90,
        frr=0.10,
        false_positive_rate=0.30,
        false_activations_per_hour=1.5,
        latency_p50_ms=150.0,
        latency_p90_ms=180.0,
        latency_p95_ms=190.0,
        latency_p99_ms=200.0,
        latency_mean_ms=160.0,
    )
    chosen = select_calibrated_threshold([m], max_fa_per_hour=0.10, min_recall=0.98)
    assert chosen.targets_met is False
    assert "FALLBACK" in chosen.status
    assert len(chosen.reason) > 0


def test_generate_markdown_summary_never_marks_unmeasured_pass() -> None:
    # 0 negative clips, no latency -> must show NOT_MEASURED, never PASS
    metrics = EvaluationMetrics(
        threshold=0.5,
        split="held_out",
        total_clips=5,
        total_positive=5,
        total_negative=0,
        total_duration_sec=10.0,
        total_negative_hours=0.0,
        tp=5,
        fn=0,
        fp=0,
        tn=0,
        recall=1.0,
        frr=0.0,
        false_positive_rate=0.0,
        false_activations_per_hour=None,
        latency_p50_ms=None,
        latency_p90_ms=None,
        latency_p95_ms=None,
        latency_p99_ms=None,
        latency_mean_ms=None,
    )

    md = generate_markdown_summary(metrics, acceptance_state="PROVISIONAL")
    # False Activations / Hour row must NOT say PASS
    for line in md.splitlines():
        if "False Activations / Hour" in line:
            assert "PASS" not in line
            assert "NOT_MEASURED" in line
        if "Median Detection Latency" in line or "P95 Detection Latency" in line:
            assert "PASS" not in line
            assert "NOT_MEASURED" in line

    # When acceptance_state is DATA_PENDING, all metric statuses must say DATA_PENDING
    md_dp = generate_markdown_summary(metrics, acceptance_state="DATA_PENDING")
    for line in md_dp.splitlines():
        if "Recall (Detection Rate)" in line:
            assert "DATA_PENDING" in line
            assert "PASS" not in line


def test_two_stage_evaluation_exports_calibration_sweep(tmp_path: Path) -> None:
    manifest_clips = [
        CorpusClip(
            clip_id="c_pos",
            file_path="c_pos.wav",
            split="calibration",
            label="heyino",
            is_positive=True,
            speaker_id="spk_cal_1",
            duration_sec=2.0,
        ),
        CorpusClip(
            clip_id="c_neg",
            file_path="c_neg.wav",
            split="calibration",
            label="hey no",
            is_positive=False,
            speaker_id="spk_cal_2",
            duration_sec=3600.0,
        ),
        CorpusClip(
            clip_id="h_pos",
            file_path="h_pos.wav",
            split="held_out",
            label="heyino",
            is_positive=True,
            speaker_id="spk_hold_1",
            duration_sec=2.0,
        ),
        CorpusClip(
            clip_id="h_neg",
            file_path="h_neg.wav",
            split="held_out",
            label="inno",
            is_positive=False,
            speaker_id="spk_hold_2",
            duration_sec=3600.0,
        ),
    ]
    manifest_file = tmp_path / "manifest.json"
    save_manifest(manifest_file, manifest_clips)

    def factory(thresh: float) -> WakeWordEngine:
        return ConfigurableMockWakeEngine(threshold=thresh, score_to_return=0.85)

    def loader(c: CorpusClip, b: Path | None) -> bytes:
        return b"\x00\x00" * 1280

    out_dir = tmp_path / "eval_out"
    run_two_stage_evaluation(
        manifest_path=manifest_file,
        engine_factory=factory,
        threshold_sweep=[0.4, 0.6],
        output_dir=out_dir,
        audio_loader=loader,
        model_name="test_engine",
    )

    # Must export calibration sweep JSON and CSV
    calib_json = out_dir / "test_engine_calibration_sweep.json"
    calib_csv = out_dir / "test_engine_calibration_sweep.csv"
    assert calib_json.is_file()
    assert calib_csv.is_file()

    calib_data = json.loads(calib_json.read_text(encoding="utf-8"))
    assert calib_data["metadata"]["stage"] == "calibration_sweep"
    assert calib_data["metadata"]["split"] == "calibration"
    assert "selected_threshold" in calib_data["metadata"]
    assert len(calib_data["sweep"]) == 2

    # Held out files and metadata
    holdout_json = out_dir / "test_engine_held_out_metrics.json"
    assert holdout_json.is_file()
    holdout_data = json.loads(holdout_json.read_text(encoding="utf-8"))
    assert holdout_data["metadata"]["stage"] == "held_out_evaluation"
    assert holdout_data["metadata"]["threshold_origin"] == "calibration_split_only"


def test_run_training_lazy_explicit_builder_only_failure(tmp_path: Path) -> None:
    # Must fail explicitly explaining model training requires external builder workflow
    dummy_plan = tmp_path / "plan.json"
    dummy_plan.write_text("{}", encoding="utf-8")
    dummy_manifest = tmp_path / "manifest.json"
    dummy_manifest.write_text("[]", encoding="utf-8")

    with pytest.raises(
        RuntimeError,
        match="Cannot train custom openWakeWord model|external builder workflow",
    ):
        run_training_lazy(
            training_plan_path=dummy_plan,
            manifest_path=dummy_manifest,
            output_model_path=tmp_path / "out.onnx",
        )

def test_record_heyino_corpus_hardened_path_traversal(tmp_path: Path) -> None:
    out_dir = tmp_path / "safe_corpus"

    # Traversal in label
    with pytest.raises(ValueError, match="Unsafe path|outside"):
        record_and_save_clip(
            output_dir=out_dir,
            split="train",
            label="../../escaped_label",
            is_positive=False,
            recorder_fn=mock_audio_recorder,
        )

    # Traversal in speaker_id
    with pytest.raises(ValueError, match="Unsafe path|outside"):
        record_and_save_clip(
            output_dir=out_dir,
            split="train",
            label="heyino",
            speaker_id="../escaped_spk",
            is_positive=True,
            recorder_fn=mock_audio_recorder,
        )

    # Traversal in split
    with pytest.raises(ValueError, match="Invalid split|Unsafe path"):
        record_and_save_clip(
            output_dir=out_dir,
            split="../evil_split",
            label="heyino",
            is_positive=True,
            recorder_fn=mock_audio_recorder,
        )


def test_record_heyino_corpus_invalid_enum_rejected(tmp_path: Path) -> None:
    out_dir = tmp_path / "safe_corpus"

    # Invalid distance
    with pytest.raises(ValueError, match="Invalid distance"):
        record_and_save_clip(
            output_dir=out_dir,
            split="train",
            label="heyino",
            distance="invalid_distance",
            is_positive=True,
            recorder_fn=mock_audio_recorder,
        )

    # Invalid noise_condition
    with pytest.raises(ValueError, match="Invalid noise_condition"):
        record_and_save_clip(
            output_dir=out_dir,
            split="train",
            label="heyino",
            noise_condition="invalid_noise",
            is_positive=True,
            recorder_fn=mock_audio_recorder,
        )

"""Offline evaluation and calibration framework for Heyino wake word engines.

Supports threshold sweeping, calibration on distinct calibration splits,
and held-out split evaluation. Computes Recall, False Rejection Rate (FRR),
False Activations Per Hour (FA/hr), latency percentiles, and granular
breakdowns by speaker, distance, noise condition, pronunciation variant,
and hard-negative confuser family.
Safely validates manifests, prevents train/holdout leakage, and handles
zero-duration negative sets without division by zero.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from innobrain.audio.io import read_pcm16_wav
from innobrain.wake.contracts import WakeWordEngine
from scripts.wakeword.heyino_corpus_spec import (
    CorpusClip,
    load_manifest,
    validate_manifest,
)

WakeWordEngineFactory = Callable[[float], WakeWordEngine]
AudioLoaderFn = Callable[[CorpusClip, Path | None], bytes]

# Gate 5C.0 Acceptance Targets
GATE5C0_TARGET_QUIET_RECALL: float = 0.98
GATE5C0_TARGET_VARIANTS_RECALL: float = 0.95
GATE5C0_TARGET_FAR_RECALL: float = 0.93
GATE5C0_TARGET_MAX_FA_PER_HOUR: float = 0.10
GATE5C0_TARGET_STRETCH_FA_PER_HOUR: float = 0.05
GATE5C0_TARGET_MEDIAN_LATENCY_MS: float = 300.0


class CalibratedThreshold(float):
    """Float threshold subclass carrying calibration selection status and audit metadata."""

    status: str
    targets_met: bool
    reason: str

    def __new__(
        cls,
        value: float,
        status: str = "CALIBRATED",
        targets_met: bool = True,
        reason: str = "Calibrated threshold",
    ) -> CalibratedThreshold:
        obj = super().__new__(cls, value)
        obj.status = status
        obj.targets_met = targets_met
        obj.reason = reason
        return obj

    def __reduce__(self) -> tuple[Any, ...]:
        return (
            CalibratedThreshold,
            (float(self), self.status, self.targets_met, self.reason),
        )


def default_audio_loader(clip: CorpusClip, base_dir: Path | None = None) -> bytes:
    """Load PCM16 bytes from WAV file specified in clip."""
    path = Path(clip.file_path)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path

    if not path.is_file():
        raise FileNotFoundError(f"Audio file for clip '{clip.clip_id}' not found at: {path}")

    samples, _sr = read_pcm16_wav(path)
    return samples.tobytes()


@dataclass(slots=True)
class ClipEvaluationResult:
    """Per-clip evaluation outcome."""

    clip_id: str
    file_path: str
    split: str
    label: str
    is_positive: bool
    detected: bool
    score: float | None
    threshold: float
    latency_ms: float | None
    is_tp: bool
    is_fn: bool
    is_tn: bool
    is_fp: bool
    duration_sec: float
    speaker_id: str | None = None
    distance: str | None = None
    noise_condition: str | None = None
    pronunciation: str | None = None
    confuser_family: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SliceMetrics:
    """Aggregated evaluation metrics for a specific slice."""

    slice_name: str
    slice_value: str
    total_clips: int = 0
    positive_clips: int = 0
    negative_clips: int = 0
    tp: int = 0
    fn: int = 0
    fp: int = 0
    tn: int = 0
    recall: float = 0.0
    frr: float = 0.0
    false_alarm_rate: float = 0.0
    negative_hours: float = 0.0
    false_activations_per_hour: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvaluationMetrics:
    """Overall evaluation summary for a dataset or split at a given threshold."""

    threshold: float
    split: str
    total_clips: int
    total_positive: int
    total_negative: int
    total_duration_sec: float
    total_negative_hours: float
    tp: int
    fn: int
    fp: int
    tn: int
    recall: float
    frr: float
    false_positive_rate: float
    false_activations_per_hour: float | None
    latency_p50_ms: float | None
    latency_p90_ms: float | None
    latency_p95_ms: float | None
    latency_p99_ms: float | None
    latency_mean_ms: float | None
    by_speaker: dict[str, SliceMetrics] = field(default_factory=dict)
    by_distance: dict[str, SliceMetrics] = field(default_factory=dict)
    by_noise: dict[str, SliceMetrics] = field(default_factory=dict)
    by_pronunciation: dict[str, SliceMetrics] = field(default_factory=dict)
    by_confuser_family: dict[str, SliceMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        # Convert nested dataclasses to dicts cleanly
        for key in (
            "by_speaker",
            "by_distance",
            "by_noise",
            "by_pronunciation",
            "by_confuser_family",
        ):
            res[key] = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in res[key].items()}
        return res


def compute_slice_metrics(
    slice_name: str,
    slice_value: str,
    results: Sequence[ClipEvaluationResult],
) -> SliceMetrics:
    """Compute aggregated metrics for a specific metadata slice."""
    total = len(results)
    pos_clips = [r for r in results if r.is_positive]
    neg_clips = [r for r in results if not r.is_positive]

    tp = sum(1 for r in pos_clips if r.is_tp)
    fn = sum(1 for r in pos_clips if r.is_fn)
    fp = sum(1 for r in neg_clips if r.is_fp)
    tn = sum(1 for r in neg_clips if r.is_tn)

    recall = (float(tp) / float(len(pos_clips))) if pos_clips else 0.0
    frr = (float(fn) / float(len(pos_clips))) if pos_clips else 0.0
    far = (float(fp) / float(len(neg_clips))) if neg_clips else 0.0

    neg_dur_sec = sum(r.duration_sec for r in neg_clips)
    neg_hours = neg_dur_sec / 3600.0

    # Safe zero-duration handling
    fa_per_hour: float | None = None
    if neg_hours > 0.0:
        fa_per_hour = float(fp) / neg_hours
    elif neg_clips:
        fa_per_hour = 0.0

    return SliceMetrics(
        slice_name=slice_name,
        slice_value=slice_value,
        total_clips=total,
        positive_clips=len(pos_clips),
        negative_clips=len(neg_clips),
        tp=tp,
        fn=fn,
        fp=fp,
        tn=tn,
        recall=recall,
        frr=frr,
        false_alarm_rate=far,
        negative_hours=neg_hours,
        false_activations_per_hour=fa_per_hour,
    )


def compute_percentile(sorted_values: Sequence[float], percentile: float) -> float | None:
    """Compute percentile from sorted list of numbers using nearest-rank method."""
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_values[int(k)])
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return float(d0 + d1)


def evaluate_clip(
    engine: WakeWordEngine,
    pcm16_bytes: bytes,
    clip: CorpusClip,
    threshold: float,
) -> ClipEvaluationResult:
    """Stream audio frames through engine and record detection metrics."""
    engine.reset()

    frame_bytes = engine.frame_length * 2
    detected = False
    best_score: float | None = None
    detected_latency_ms: float | None = None

    samples_processed = 0
    offset = 0
    total_bytes = len(pcm16_bytes)

    while offset < total_bytes:
        chunk = pcm16_bytes[offset : offset + frame_bytes]
        offset += frame_bytes

        # Only process full frames if engine requires exact sizing, or pass remaining
        detection = engine.process(chunk)
        samples_processed += len(chunk) // 2

        if detection is not None:
            detected = True
            if detection.score is not None:
                if best_score is None or detection.score > best_score:
                    best_score = detection.score
            if detected_latency_ms is None:
                # Approximate latency from start of audio to trigger frame
                samples_flt = float(samples_processed)
                sr_flt = float(engine.sample_rate_hz)
                detected_latency_ms = (samples_flt / sr_flt) * 1000.0

    engine.reset()

    if clip.is_positive:
        is_tp = detected
        is_fn = not detected
        is_tn = False
        is_fp = False
    else:
        is_tp = False
        is_fn = False
        is_tn = not detected
        is_fp = detected

    return ClipEvaluationResult(
        clip_id=clip.clip_id,
        file_path=clip.file_path,
        split=clip.split,
        label=clip.label,
        is_positive=clip.is_positive,
        detected=detected,
        score=best_score,
        threshold=threshold,
        latency_ms=detected_latency_ms if is_tp else None,
        is_tp=is_tp,
        is_fn=is_fn,
        is_tn=is_tn,
        is_fp=is_fp,
        duration_sec=clip.duration_sec,
        speaker_id=clip.speaker_id,
        distance=clip.distance,
        noise_condition=clip.noise_condition,
        pronunciation=clip.pronunciation,
        confuser_family=clip.confuser_family,
    )


def evaluate_dataset(
    engine: WakeWordEngine,
    clips: Sequence[CorpusClip],
    threshold: float,
    split_name: str = "all",
    audio_loader: AudioLoaderFn | None = None,
    base_dir: Path | None = None,
) -> tuple[EvaluationMetrics, list[ClipEvaluationResult]]:
    """Evaluate a wake word engine across a collection of corpus clips."""
    loader = audio_loader or default_audio_loader
    results: list[ClipEvaluationResult] = []

    for clip in clips:
        audio_bytes = loader(clip, base_dir)
        res = evaluate_clip(engine, audio_bytes, clip, threshold)
        results.append(res)

    total_clips = len(results)
    pos_clips = [r for r in results if r.is_positive]
    neg_clips = [r for r in results if not r.is_positive]

    tp = sum(1 for r in pos_clips if r.is_tp)
    fn = sum(1 for r in pos_clips if r.is_fn)
    fp = sum(1 for r in neg_clips if r.is_fp)
    tn = sum(1 for r in neg_clips if r.is_tn)

    total_dur_sec = sum(r.duration_sec for r in results)
    neg_dur_sec = sum(r.duration_sec for r in neg_clips)
    neg_hours = neg_dur_sec / 3600.0

    recall = (float(tp) / float(len(pos_clips))) if pos_clips else 0.0
    frr = (float(fn) / float(len(pos_clips))) if pos_clips else 0.0
    fpr = (float(fp) / float(len(neg_clips))) if neg_clips else 0.0

    # Safe zero-duration handling for negative audio
    fa_per_hour: float | None = None
    if neg_hours > 0.0:
        fa_per_hour = float(fp) / neg_hours
    elif neg_clips:
        fa_per_hour = 0.0

    # Latency percentiles on true positive detections
    latencies = sorted([r.latency_ms for r in pos_clips if r.latency_ms is not None])
    lat_p50 = compute_percentile(latencies, 50.0)
    lat_p90 = compute_percentile(latencies, 90.0)
    lat_p95 = compute_percentile(latencies, 95.0)
    lat_p99 = compute_percentile(latencies, 99.0)
    lat_mean = (float(sum(latencies)) / float(len(latencies))) if latencies else None

    # Compute slice breakdowns
    by_speaker: dict[str, SliceMetrics] = {}
    speakers = {r.speaker_id for r in results if r.speaker_id is not None}
    for spk in sorted(speakers):
        by_speaker[spk] = compute_slice_metrics(
            "speaker", spk, [r for r in results if r.speaker_id == spk]
        )

    by_dist: dict[str, SliceMetrics] = {}
    distances = {r.distance for r in results if r.distance is not None}
    for dist in sorted(distances):
        by_dist[dist] = compute_slice_metrics(
            "distance", dist, [r for r in results if r.distance == dist]
        )

    by_noise: dict[str, SliceMetrics] = {}
    noises = {r.noise_condition for r in results if r.noise_condition is not None}
    for n in sorted(noises):
        by_noise[n] = compute_slice_metrics(
            "noise", n, [r for r in results if r.noise_condition == n]
        )

    by_pron: dict[str, SliceMetrics] = {}
    prons = {r.pronunciation for r in results if r.pronunciation is not None}
    for p in sorted(prons):
        by_pron[p] = compute_slice_metrics(
            "pronunciation", p, [r for r in results if r.pronunciation == p]
        )

    by_conf: dict[str, SliceMetrics] = {}
    confusers = {r.confuser_family for r in results if r.confuser_family is not None}
    for c in sorted(confusers):
        by_conf[c] = compute_slice_metrics(
            "confuser_family", c, [r for r in results if r.confuser_family == c]
        )

    metrics = EvaluationMetrics(
        threshold=threshold,
        split=split_name,
        total_clips=total_clips,
        total_positive=len(pos_clips),
        total_negative=len(neg_clips),
        total_duration_sec=total_dur_sec,
        total_negative_hours=neg_hours,
        tp=tp,
        fn=fn,
        fp=fp,
        tn=tn,
        recall=recall,
        frr=frr,
        false_positive_rate=fpr,
        false_activations_per_hour=fa_per_hour,
        latency_p50_ms=lat_p50,
        latency_p90_ms=lat_p90,
        latency_p95_ms=lat_p95,
        latency_p99_ms=lat_p99,
        latency_mean_ms=lat_mean,
        by_speaker=by_speaker,
        by_distance=by_dist,
        by_noise=by_noise,
        by_pronunciation=by_pron,
        by_confuser_family=by_conf,
    )

    return metrics, results


def sweep_thresholds(
    engine_factory: WakeWordEngineFactory,
    clips: Sequence[CorpusClip],
    thresholds: Sequence[float],
    split_name: str = "calibration",
    audio_loader: AudioLoaderFn | None = None,
    base_dir: Path | None = None,
) -> list[EvaluationMetrics]:
    """Evaluate performance across a sweep of candidate operating thresholds."""
    sweep_results: list[EvaluationMetrics] = []
    for thresh in thresholds:
        engine = engine_factory(thresh)
        metrics, _ = evaluate_dataset(
            engine=engine,
            clips=clips,
            threshold=thresh,
            split_name=split_name,
            audio_loader=audio_loader,
            base_dir=base_dir,
        )
        sweep_results.append(metrics)
    return sweep_results


def select_calibrated_threshold(
    sweep_results: Sequence[EvaluationMetrics],
    max_fa_per_hour: float = GATE5C0_TARGET_MAX_FA_PER_HOUR,
    min_recall: float = GATE5C0_TARGET_QUIET_RECALL,
) -> CalibratedThreshold:
    """Select the optimal operating threshold from calibration sweep results.

    Honors min_recall whenever an operating point meets the requested recall.
    Does not treat missing negative duration as measured zero FA/hour.
    If no candidate meets both targets, applies an explicitly documented fallback
    and returns a CalibratedThreshold exposing status, targets_met, and reason.
    """
    if not sweep_results:
        raise ValueError("Cannot select threshold from empty sweep results.")

    # 1. Candidates with measured FA/hr meeting BOTH recall and FA/hr targets
    both_met = [
        r
        for r in sweep_results
        if r.false_activations_per_hour is not None
        and r.total_negative_hours > 0.0
        and r.false_activations_per_hour <= max_fa_per_hour
        and r.recall >= min_recall
    ]
    if both_met:
        # Pick candidate meeting both targets with lowest FA/hr (and highest recall if tied)
        best = min(both_met, key=lambda r: (r.false_activations_per_hour, -r.recall))
        return CalibratedThreshold(
            best.threshold,
            status="TARGETS_MET",
            targets_met=True,
            reason=(
                f"Operating point meets both recall target ({best.recall * 100:.1f}% >= "
                f"{min_recall * 100:.1f}%) and FA/hr target "
                f"({best.false_activations_per_hour:.3f} <= {max_fa_per_hour:.3f})."
            ),
        )

    # 2. Check if negative duration is unmeasured across all candidates
    all_unmeasured_fa = all(
        r.false_activations_per_hour is None or r.total_negative_hours <= 0.0
        for r in sweep_results
    )
    if all_unmeasured_fa:
        rec_candidates = [r for r in sweep_results if r.recall >= min_recall]
        if rec_candidates:
            best = max(rec_candidates, key=lambda r: r.recall)
        else:
            best = max(sweep_results, key=lambda r: r.recall)
        return CalibratedThreshold(
            best.threshold,
            status="FALLBACK_UNMEASURED_FA",
            targets_met=False,
            reason=(
                "Fallback: Negative audio duration is unmeasured (0 hours); FA/hr cannot be "
                f"verified. Selected threshold ({best.threshold}) based on recall "
                f"({best.recall * 100:.1f}%)."
            ),
        )

    # 3. Fallback A: Candidates meeting min_recall with measured FA/hr
    recall_met = [
        r
        for r in sweep_results
        if r.recall >= min_recall
        and r.false_activations_per_hour is not None
        and r.total_negative_hours > 0.0
    ]
    if recall_met:
        best = min(recall_met, key=lambda r: (r.false_activations_per_hour, -r.recall))
        return CalibratedThreshold(
            best.threshold,
            status="FALLBACK_RECALL_MET_FA_EXCEEDED",
            targets_met=False,
            reason=(
                f"Fallback: Honored recall target ({best.recall * 100:.1f}% >= "
                f"{min_recall * 100:.1f}%), selected lowest FA/hr "
                f"({best.false_activations_per_hour:.3f} > {max_fa_per_hour:.3f})."
            ),
        )

    # 4. Fallback B: Candidates meeting FA/hr target with measured FA/hr
    fa_met = [
        r
        for r in sweep_results
        if r.false_activations_per_hour is not None
        and r.total_negative_hours > 0.0
        and r.false_activations_per_hour <= max_fa_per_hour
    ]
    if fa_met:
        best = max(fa_met, key=lambda r: (r.recall, -r.false_activations_per_hour))
        return CalibratedThreshold(
            best.threshold,
            status="FALLBACK_FA_MET_RECALL_UNMET",
            targets_met=False,
            reason=(
                f"Fallback: Met FA/hr target ({best.false_activations_per_hour:.3f} <= "
                f"{max_fa_per_hour:.3f}), but recall unmet "
                f"({best.recall * 100:.1f}% < {min_recall * 100:.1f}%)."
            ),
        )

    # 5. Fallback C: Minimum combined error
    measured = [
        r
        for r in sweep_results
        if r.false_activations_per_hour is not None and r.total_negative_hours > 0.0
    ]
    pool = measured if measured else list(sweep_results)
    best = min(pool, key=lambda r: (r.frr + r.false_positive_rate))
    return CalibratedThreshold(
        best.threshold,
        status="FALLBACK_MIN_COMBINED_ERROR",
        targets_met=False,
        reason=(
            f"Fallback: Selected minimum combined error (FRR={best.frr * 100:.1f}%, "
            f"FPR={best.false_positive_rate * 100:.1f}%), neither target met."
        ),
    )


def write_json_report(
    path: Path | str,
    metrics: EvaluationMetrics,
    clip_results: Sequence[ClipEvaluationResult] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> None:
    """Export structured evaluation metrics and optional clip results to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    report_dict: dict[str, Any] = {
        "metadata": {
            "timestamp": time.time(),
            "split": metrics.split,
            "threshold": metrics.threshold,
            **(extra_metadata or {}),
        },
        "summary": metrics.to_dict(),
    }
    if clip_results is not None:
        report_dict["clips"] = [c.to_dict() for c in clip_results]

    dumped = json.dumps(report_dict, indent=2, ensure_ascii=False) + "\n"
    p.write_text(dumped, encoding="utf-8")


def write_csv_clip_results(
    path: Path | str,
    clip_results: Sequence[ClipEvaluationResult],
) -> None:
    """Export per-clip evaluation outcomes to CSV."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "clip_id",
        "split",
        "label",
        "is_positive",
        "detected",
        "score",
        "threshold",
        "latency_ms",
        "is_tp",
        "is_fn",
        "is_tn",
        "is_fp",
        "speaker_id",
        "distance",
        "noise_condition",
        "pronunciation",
        "confuser_family",
        "duration_sec",
        "file_path",
    ]

    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in clip_results:
            row = c.to_dict()
            writer.writerow({k: row.get(k) for k in fieldnames})


def write_calibration_sweep_json(
    path: Path | str,
    sweep_results: Sequence[EvaluationMetrics],
    selected_threshold: CalibratedThreshold | float,
    model_name: str = "openwakeword",
) -> None:
    """Export structured calibration sweep results to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    status_str = getattr(selected_threshold, "status", "CALIBRATED")
    targets_met = getattr(selected_threshold, "targets_met", True)
    reason_str = getattr(selected_threshold, "reason", "Selected via calibration sweep")

    out_data = {
        "metadata": {
            "stage": "calibration_sweep",
            "split": "calibration",
            "model_name": model_name,
            "sweep_thresholds": [m.threshold for m in sweep_results],
            "selected_threshold": float(selected_threshold),
            "selection_status": status_str,
            "targets_met": targets_met,
            "selection_reason": reason_str,
        },
        "sweep": [m.to_dict() for m in sweep_results],
    }
    p.write_text(json.dumps(out_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_calibration_sweep_csv(
    path: Path | str,
    sweep_results: Sequence[EvaluationMetrics],
    selected_threshold: CalibratedThreshold | float,
) -> None:
    """Export calibration sweep metrics across thresholds to CSV."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "threshold",
        "is_selected",
        "recall",
        "frr",
        "false_positive_rate",
        "false_activations_per_hour",
        "tp",
        "fn",
        "fp",
        "tn",
        "total_clips",
        "positive_clips",
        "negative_clips",
        "negative_hours",
        "latency_p50_ms",
        "latency_p95_ms",
    ]
    sel_val = float(selected_threshold)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in sweep_results:
            fa_str = (
                f"{m.false_activations_per_hour:.4f}"
                if m.false_activations_per_hour is not None
                else ""
            )
            lat50_str = f"{m.latency_p50_ms:.2f}" if m.latency_p50_ms is not None else ""
            lat95_str = f"{m.latency_p95_ms:.2f}" if m.latency_p95_ms is not None else ""
            writer.writerow({
                "threshold": m.threshold,
                "is_selected": math.isclose(m.threshold, sel_val, abs_tol=1e-5),
                "recall": f"{m.recall:.4f}",
                "frr": f"{m.frr:.4f}",
                "false_positive_rate": f"{m.false_positive_rate:.4f}",
                "false_activations_per_hour": fa_str,
                "tp": m.tp,
                "fn": m.fn,
                "fp": m.fp,
                "tn": m.tn,
                "total_clips": m.total_clips,
                "positive_clips": m.total_positive,
                "negative_clips": m.total_negative,
                "negative_hours": f"{m.total_negative_hours:.4f}",
                "latency_p50_ms": lat50_str,
                "latency_p95_ms": lat95_str,
            })


def generate_markdown_summary(
    metrics: EvaluationMetrics,
    title: str = "Heyino Wake Word Evaluation Report",
    model_name: str = "Candidate Engine",
    model_hash: str | None = None,
    acceptance_state: str = "PROVISIONAL",
) -> str:
    """Generate GitHub-flavored Markdown evaluation summary report."""
    is_data_pending = acceptance_state == "DATA_PENDING"
    is_provisional = acceptance_state == "PROVISIONAL"

    def format_status(passed: bool | None, unmeasured: bool = False) -> str:
        if is_data_pending:
            return "DATA_PENDING"
        if unmeasured or passed is None:
            return "NOT_MEASURED"
        if passed:
            return "PASS (PROVISIONAL)" if is_provisional else "PASS"
        return "FAIL / PROVISIONAL" if is_provisional else "FAIL"

    # 1. Recall and FRR
    if metrics.total_positive == 0:
        recall_val = "NOT_MEASURED (0 pos clips)"
        rec_pass = format_status(None, unmeasured=True)
        frr_val = "NOT_MEASURED (0 pos clips)"
        frr_pass = format_status(None, unmeasured=True)
    else:
        recall_val = f"{metrics.recall * 100.0:.2f}%"
        rec_pass = format_status(metrics.recall >= GATE5C0_TARGET_QUIET_RECALL)
        frr_val = f"{metrics.frr * 100.0:.2f}%"
        frr_pass = format_status(metrics.frr <= (1.0 - GATE5C0_TARGET_QUIET_RECALL))

    # 2. False Activations / Hour
    if (
        metrics.total_negative == 0
        or metrics.total_negative_hours <= 0.0
        or metrics.false_activations_per_hour is None
    ):
        fa_hr_str = "NOT_MEASURED (0 neg hrs)"
        fa_pass = format_status(None, unmeasured=True)
    else:
        fa_hr_str = f"{metrics.false_activations_per_hour:.2f} FA/hr"
        fa_pass = format_status(
            metrics.false_activations_per_hour <= GATE5C0_TARGET_MAX_FA_PER_HOUR
        )

    # 3. Detection Latency (P50 and P95)
    if metrics.latency_p50_ms is None:
        lat_p50_str = "NOT_MEASURED"
        lat_p50_pass = format_status(None, unmeasured=True)
    else:
        lat_p50_str = f"{metrics.latency_p50_ms:.1f} ms"
        lat_p50_pass = format_status(
            metrics.latency_p50_ms <= GATE5C0_TARGET_MEDIAN_LATENCY_MS
        )

    if metrics.latency_p95_ms is None:
        lat_p95_str = "NOT_MEASURED"
        lat_p95_pass = format_status(None, unmeasured=True)
    else:
        lat_p95_str = f"{metrics.latency_p95_ms:.1f} ms"
        lat_p95_pass = format_status(
            metrics.latency_p95_ms <= GATE5C0_TARGET_MEDIAN_LATENCY_MS
        )

    lines: list[str] = [
        f"# {title}",
        "",
        f"- **Model / Engine:** `{model_name}`",
        f"- **Model SHA-256:** `{model_hash or 'DATA_PENDING'}`",
        f"- **Split:** `{metrics.split}`",
        f"- **Operating Threshold:** `{metrics.threshold:.3f}`",
        f"- **Acceptance State:** `{acceptance_state}`",
        "",
        "## 1. Primary Metrics Overview",
        "",
        "| Metric | Measured Value | Gate 5C.0 Target | Status |",
        "|---|---|---|---|",
        f"| Recall (Detection Rate) | {recall_val} | ≥ 98.0% | {rec_pass} |",
        f"| False Rejection Rate (FRR) | {frr_val} | ≤ 2.0% | {frr_pass} |",
        f"| False Activations / Hour | {fa_hr_str} | ≤ 0.10 FA/hr | {fa_pass} |",
        f"| Median Detection Latency (P50) | {lat_p50_str} | ≤ 300 ms | {lat_p50_pass} |",
        f"| P95 Detection Latency | {lat_p95_str} | ≤ 300 ms | {lat_p95_pass} |",
        (
            f"| Total Clips Evaluated | {metrics.total_clips} "
            f"(Pos: {metrics.total_positive}, Neg: {metrics.total_negative}) | — | — |"
        ),
        f"| Negative Audio Duration | {metrics.total_negative_hours:.2f} hours | — | — |",
        "",
        "## 2. Granular Breakdown by Distance",
        "",
        "| Distance Bucket | Total Clips | Positive | TP | Recall | FRR |",
        "|---|---|---|---|---|---|",
    ]

    for d_val, s_met in sorted(metrics.by_distance.items()):
        rec_s = (
            f"{s_met.recall * 100.0:.1f}%"
            if s_met.positive_clips > 0
            else "NOT_MEASURED"
        )
        frr_s = (
            f"{s_met.frr * 100.0:.1f}%"
            if s_met.positive_clips > 0
            else "NOT_MEASURED"
        )
        lines.append(
            f"| `{d_val}` | {s_met.total_clips} | {s_met.positive_clips} | "
            f"{s_met.tp} | {rec_s} | {frr_s} |"
        )

    lines.extend([
        "",
        "## 3. Granular Breakdown by Acoustic Noise Condition",
        "",
        "| Noise Condition | Clips | Pos | Recall | Neg | FP | FA Rate |",
        "|---|---|---|---|---|---|---|",
    ])

    for n_val, s_met in sorted(metrics.by_noise.items()):
        rec_s = (
            f"{s_met.recall * 100.0:.1f}%"
            if s_met.positive_clips > 0
            else "NOT_MEASURED"
        )
        fa_s = (
            f"{s_met.false_alarm_rate * 100.0:.1f}%"
            if s_met.negative_clips > 0
            else "NOT_MEASURED"
        )
        lines.append(
            f"| `{n_val}` | {s_met.total_clips} | {s_met.positive_clips} | "
            f"{rec_s} | {s_met.negative_clips} | {s_met.fp} | "
            f"{fa_s} |"
        )

    lines.extend([
        "",
        "## 4. Granular Breakdown by Hard-Negative Confuser Family",
        "",
        "| Confuser Family | Total Clips | False Alarms (FP) | False Alarm Rate |",
        "|---|---|---|---|",
    ])

    for c_val, s_met in sorted(metrics.by_confuser_family.items()):
        fa_s = (
            f"{s_met.false_alarm_rate * 100.0:.1f}%"
            if s_met.total_clips > 0
            else "NOT_MEASURED"
        )
        lines.append(
            f"| `{c_val}` | {s_met.total_clips} | {s_met.fp} | {fa_s} |"
        )

    lines.extend([
        "",
        "## 5. Granular Breakdown by Pronunciation Variant",
        "",
        "| Pronunciation Variant | Total Clips | Detected (TP) | Recall |",
        "|---|---|---|---|",
    ])

    for p_val, s_met in sorted(metrics.by_pronunciation.items()):
        rec_s = (
            f"{s_met.recall * 100.0:.1f}%"
            if s_met.total_clips > 0
            else "NOT_MEASURED"
        )
        lines.append(
            f"| `{p_val}` | {s_met.total_clips} | {s_met.tp} | {rec_s} |"
        )

    lines.append("")
    return "\n".join(lines)


def run_two_stage_evaluation(
    manifest_path: Path | str,
    engine_factory: WakeWordEngineFactory,
    threshold_sweep: Sequence[float] = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
    output_dir: Path | str | None = None,
    audio_loader: AudioLoaderFn | None = None,
    base_dir: Path | None = None,
    model_name: str = "openwakeword",
) -> tuple[EvaluationMetrics, EvaluationMetrics]:
    """Execute rigorous two-stage evaluation: calibration sweep then held-out test.

    Enforces zero data leakage and separate calibration / held-out splits.
    Exports calibration sweep results and held-out evaluation reports.
    """
    clips = load_manifest(manifest_path)
    val_res = validate_manifest(clips, base_dir=base_dir)
    if not val_res.valid:
        raise ValueError(
            f"Corpus manifest validation failed with errors: {val_res.errors}"
        )

    calib_clips = [c for c in clips if c.split == "calibration"]
    held_out_clips = [c for c in clips if c.split == "held_out"]

    if not calib_clips:
        raise ValueError("No calibration clips found in manifest for threshold calibration.")
    if not held_out_clips:
        raise ValueError("No held_out clips found in manifest for final benchmark evaluation.")

    # Stage 1: Sweep thresholds on calibration set
    sweep_results = sweep_thresholds(
        engine_factory=engine_factory,
        clips=calib_clips,
        thresholds=threshold_sweep,
        split_name="calibration",
        audio_loader=audio_loader,
        base_dir=base_dir,
    )

    best_thresh = select_calibrated_threshold(sweep_results)
    best_calib_metrics = next(m for m in sweep_results if m.threshold == best_thresh)

    # Stage 2: Final evaluation on held-out set using calibrated threshold
    held_out_engine = engine_factory(best_thresh)
    held_out_metrics, held_out_clip_results = evaluate_dataset(
        engine=held_out_engine,
        clips=held_out_clips,
        threshold=best_thresh,
        split_name="held_out",
        audio_loader=audio_loader,
        base_dir=base_dir,
    )

    if output_dir is not None:
        out_p = Path(output_dir)
        # Export calibration sweep JSON & CSV
        write_calibration_sweep_json(
            out_p / f"{model_name}_calibration_sweep.json",
            sweep_results,
            best_thresh,
            model_name=model_name,
        )
        write_calibration_sweep_csv(
            out_p / f"{model_name}_calibration_sweep.csv",
            sweep_results,
            best_thresh,
        )

        status_str = getattr(best_thresh, "status", "CALIBRATED")
        targets_met = getattr(best_thresh, "targets_met", True)
        reason_str = getattr(best_thresh, "reason", "Selected via calibration sweep")

        # Export held-out metrics JSON, CSV, and Markdown report
        write_json_report(
            out_p / f"{model_name}_held_out_metrics.json",
            held_out_metrics,
            held_out_clip_results,
            extra_metadata={
                "stage": "held_out_evaluation",
                "split": "held_out",
                "model_name": model_name,
                "threshold_origin": "calibration_split_only",
                "calibrated_threshold": float(best_thresh),
                "calibration_selection_status": status_str,
                "calibration_targets_met": targets_met,
                "calibration_selection_reason": reason_str,
            },
        )
        write_csv_clip_results(
            out_p / f"{model_name}_held_out_clips.csv",
            held_out_clip_results,
        )
        md_text = generate_markdown_summary(
            held_out_metrics,
            title=f"Heyino Wake Word Held-Out Benchmark ({model_name})",
            model_name=model_name,
            acceptance_state="PROVISIONAL",
        )
        (out_p / f"{model_name}_held_out_report.md").write_text(md_text, encoding="utf-8")

    return best_calib_metrics, held_out_metrics


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for offline evaluation."""
    parser = argparse.ArgumentParser(
        description="Offline Heyino Wake Word Engine Evaluator and Calibrator"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to corpus manifest.json",
    )
    parser.add_argument(
        "--engine",
        choices=["openwakeword", "porcupine"],
        default="openwakeword",
        help="Wake engine adapter type",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=None,
        help="Path to engine model file (.onnx or .ppn)",
    )
    parser.add_argument(
        "--split",
        choices=["calibration", "held_out", "both"],
        default="both",
        help="Dataset split to evaluate",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        help="Candidate thresholds to sweep during calibration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/phase5/wake_eval"),
        help="Output directory for reports, CSVs, and JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for evaluate_wakeword."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.manifest.is_file():
        print(f"Error: Manifest file not found: {args.manifest}", file=sys.stderr)
        return 1

    # In production CLI runs, construct real engine factories based on --engine
    # If model file is absent, fail gracefully without fake numbers
    if args.model_path is None or not args.model_path.is_file():
        print(
            f"DATA_PENDING: Engine model path '{args.model_path}' does not exist. "
            f"Cannot run real evaluation without model asset.",
            file=sys.stderr,
        )
        return 1

    # Import engine classes conditionally
    from innobrain.wake.contracts import WakeEngineConfig

    if args.engine == "openwakeword":
        from innobrain.wake.openwakeword_engine import OpenWakeWordEngine

        def factory(thresh: float) -> WakeWordEngine:
            cfg = WakeEngineConfig(threshold=thresh, model_path=str(args.model_path))
            return OpenWakeWordEngine(config=cfg)
    else:
        from innobrain.wake.porcupine_engine import PorcupineWakeWordEngine

        def factory(thresh: float) -> WakeWordEngine:
            cfg = WakeEngineConfig(threshold=thresh, model_path=str(args.model_path))
            return PorcupineWakeWordEngine(config=cfg)

    try:
        calib_m, holdout_m = run_two_stage_evaluation(
            manifest_path=args.manifest,
            engine_factory=factory,
            threshold_sweep=args.thresholds,
            output_dir=args.output_dir,
            model_name=args.engine,
        )
        print(f"Calibration optimal threshold: {calib_m.threshold:.3f}")
        print(f"Held-out Recall: {holdout_m.recall * 100.0:.2f}%")
        print(f"Held-out FRR: {holdout_m.frr * 100.0:.2f}%")
        return 0
    except Exception as err:
        print(f"Evaluation failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

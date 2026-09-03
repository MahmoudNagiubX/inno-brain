from typing import Any

import numpy as np
import pytest

from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    WakeDetection,
    WakeEngineConfig,
    WakeEngineInitializationError,
    WakeEngineProcessingError,
)
from innobrain.wake.openwakeword_engine import OpenWakeWordEngine


class FakeOWWBackend:
    def __init__(
        self,
        scores: list[dict[str, float]] | None = None,
        raise_on_predict: Exception | None = None,
    ) -> None:
        self.scores = list(scores or [])
        self.raise_on_predict = raise_on_predict
        self.reset_called = False
        self.closed = False
        self.predict_calls: list[Any] = []

    def predict(self, chunk: Any) -> dict[str, float]:
        self.predict_calls.append(chunk)
        if self.raise_on_predict:
            raise self.raise_on_predict
        if self.scores:
            return self.scores.pop(0)
        return {CANONICAL_WAKE_LABEL: 0.0}

    def reset(self) -> None:
        self.reset_called = True

    def close(self) -> None:
        self.closed = True


def test_missing_vendor_package_raises_initialization_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure openwakeword cannot be imported
    import sys

    monkeypatch.setitem(sys.modules, "openwakeword", None)
    monkeypatch.setitem(sys.modules, "openwakeword.model", None)

    with pytest.raises(WakeEngineInitializationError, match="openwakeword"):
        OpenWakeWordEngine(backend=None)


def test_initialization_with_injected_backend() -> None:
    backend = FakeOWWBackend()
    engine = OpenWakeWordEngine(backend=backend)
    assert engine.sample_rate_hz == 16000
    assert engine.frame_length == 1280
    assert engine.health.ready is True
    assert engine.health.engine_name == "openwakeword"
    assert engine.health.degraded is False


def test_canonical_detection() -> None:
    backend = FakeOWWBackend(scores=[{"heyino": 0.85}])
    engine = OpenWakeWordEngine(
        config=WakeEngineConfig(threshold=0.6),
        backend=backend,
    )

    frame = b"\x00\x00" * 1280
    detection = engine.process(frame)

    assert detection is not None
    assert isinstance(detection, WakeDetection)
    assert detection.label == CANONICAL_WAKE_LABEL
    assert detection.detector == "openwakeword"
    assert detection.score == 0.85
    assert detection.detected_at_monotonic > 0

    assert len(backend.predict_calls) == 1
    call_arg = backend.predict_calls[0]
    assert isinstance(call_arg, np.ndarray)
    assert call_arg.dtype == np.int16
    assert call_arg.shape == (1280,)

    assert engine.health.detection_count == 1
    assert engine.health.last_detection_monotonic is not None
    assert engine.health.last_frame_monotonic is not None


def test_allowed_variant_maps_to_canonical_label() -> None:
    backend = FakeOWWBackend(scores=[{"hey_ino": 0.91}])
    engine = OpenWakeWordEngine(
        config=WakeEngineConfig(
            threshold=0.6,
            allowed_variants=("heyino", "hey_ino"),
        ),
        backend=backend,
    )

    frame = b"\x00\x00" * 1280
    detection = engine.process(frame)

    assert detection is not None
    assert detection.label == CANONICAL_WAKE_LABEL
    assert detection.score == 0.91


def test_confuser_and_background_suppression() -> None:
    backend = FakeOWWBackend(
        scores=[
            {"alexa": 0.99, "noise": 0.5},  # Confuser model
            {"heyino": 0.45},  # Below threshold
            {"unrelated_phrase": 0.95},
        ]
    )
    engine = OpenWakeWordEngine(
        config=WakeEngineConfig(threshold=0.6),
        backend=backend,
    )

    frame = b"\x00\x00" * 1280

    # 1. High score for confuser phrase
    assert engine.process(frame) is None
    # 2. Target phrase below threshold
    assert engine.process(frame) is None
    # 3. Unrelated phrase
    assert engine.process(frame) is None

    assert engine.health.detection_count == 0


def test_chunk_accumulation() -> None:
    # 20ms chunks = 320 samples = 640 bytes.
    # 4 chunks = 1280 samples = 2560 bytes = 1 full frame.
    backend = FakeOWWBackend(scores=[{"heyino": 0.82}])
    engine = OpenWakeWordEngine(
        config=WakeEngineConfig(threshold=0.5),
        backend=backend,
    )

    chunk_20ms = b"\x01\x00" * 320

    # Chunks 1, 2, 3 should buffer without calling predict
    assert engine.process(chunk_20ms) is None
    assert len(backend.predict_calls) == 0

    assert engine.process(chunk_20ms) is None
    assert len(backend.predict_calls) == 0

    assert engine.process(chunk_20ms) is None
    assert len(backend.predict_calls) == 0

    # Chunk 4 completes 1280 samples -> triggers prediction
    detection = engine.process(chunk_20ms)
    assert len(backend.predict_calls) == 1
    call_arg = backend.predict_calls[0]
    assert isinstance(call_arg, np.ndarray)
    assert call_arg.dtype == np.int16
    assert call_arg.shape == (1280,)
    assert detection is not None
    assert detection.label == CANONICAL_WAKE_LABEL
    assert detection.score == 0.82


def test_recoverable_backend_error_updates_health_and_raises() -> None:
    backend = FakeOWWBackend(raise_on_predict=RuntimeError("GPU/ONNX kernel failure"))
    engine = OpenWakeWordEngine(backend=backend)

    frame = b"\x00\x00" * 1280
    with pytest.raises(WakeEngineProcessingError, match="GPU/ONNX kernel failure"):
        engine.process(frame)

    assert engine.health.error_count == 1
    assert engine.health.degraded is True
    assert "GPU/ONNX kernel failure" in (engine.health.last_error or "")


def test_reset_and_close() -> None:
    backend = FakeOWWBackend()
    engine = OpenWakeWordEngine(backend=backend)

    # Accumulate partial chunk
    engine.process(b"\x00\x00" * 320)
    engine.reset()
    assert backend.reset_called is True

    engine.close()
    assert backend.closed is True
    assert engine.health.ready is False

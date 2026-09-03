import pytest

from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    WakeDetection,
    WakeEngineConfig,
    WakeEngineInitializationError,
    WakeEngineProcessingError,
)
from innobrain.wake.porcupine_engine import PorcupineWakeWordEngine


class FakePorcupineBackend:
    def __init__(
        self,
        results: list[int] | None = None,
        raise_on_process: Exception | None = None,
        frame_length: int = 512,
        sample_rate: int = 16000,
    ) -> None:
        self.results = list(results or [])
        self.raise_on_process = raise_on_process
        self.frame_length = frame_length
        self.sample_rate = sample_rate
        self.deleted = False
        self.reset_called = False
        self.process_calls: list[tuple[int, ...] | list[int] | bytes] = []

    def process(self, frame: tuple[int, ...] | list[int] | bytes) -> int:
        self.process_calls.append(frame)
        if self.raise_on_process:
            raise self.raise_on_process
        if self.results:
            return self.results.pop(0)
        return -1

    def delete(self) -> None:
        self.deleted = True

    def reset(self) -> None:
        self.reset_called = True


def test_missing_vendor_package_raises_initialization_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "pvporcupine", None)

    with pytest.raises(WakeEngineInitializationError, match="pvporcupine"):
        PorcupineWakeWordEngine(backend=None)


def test_initialization_with_injected_backend() -> None:
    backend = FakePorcupineBackend()
    engine = PorcupineWakeWordEngine(backend=backend)

    assert engine.sample_rate_hz == 16000
    assert engine.frame_length == 512
    assert engine.health.ready is True
    assert engine.health.engine_name == "porcupine"
    assert engine.health.degraded is False


def test_canonical_detection() -> None:
    # 0 = keyword index for canonical "heyino"
    backend = FakePorcupineBackend(results=[0])
    engine = PorcupineWakeWordEngine(
        config=WakeEngineConfig(),
        backend=backend,
    )

    frame = b"\x00\x00" * 512
    detection = engine.process(frame)

    assert detection is not None
    assert isinstance(detection, WakeDetection)
    assert detection.label == CANONICAL_WAKE_LABEL
    assert detection.detector == "porcupine"
    assert detection.score == 1.0
    assert detection.detected_at_monotonic > 0

    assert len(backend.process_calls) == 1
    call_arg = backend.process_calls[0]
    assert isinstance(call_arg, tuple)
    assert len(call_arg) == 512
    assert all(isinstance(val, int) for val in call_arg)

    assert engine.health.detection_count == 1
    assert engine.health.last_detection_monotonic is not None


def test_variant_index_maps_to_canonical_label() -> None:
    # index 1 = variant keyword "hey_ino"
    backend = FakePorcupineBackend(results=[1])
    engine = PorcupineWakeWordEngine(
        config=WakeEngineConfig(allowed_variants=("heyino", "hey_ino")),
        backend=backend,
    )

    frame = b"\x00\x00" * 512
    detection = engine.process(frame)

    assert detection is not None
    assert detection.label == CANONICAL_WAKE_LABEL


def test_no_detection_returns_none() -> None:
    backend = FakePorcupineBackend(results=[-1])
    engine = PorcupineWakeWordEngine(backend=backend)

    frame = b"\x00\x00" * 512
    assert engine.process(frame) is None
    assert engine.health.detection_count == 0


def test_chunk_accumulation() -> None:
    # 320 samples (640 bytes). 512 samples required (1024 bytes).
    # Chunk 1: 320 samples -> buffer (no process)
    # Chunk 2: 320 samples -> total 640 samples -> processes 512 samples, leaves 128 in buffer.
    backend = FakePorcupineBackend(results=[0])
    engine = PorcupineWakeWordEngine(backend=backend)

    chunk_320 = b"\x01\x00" * 320

    assert engine.process(chunk_320) is None
    assert len(backend.process_calls) == 0

    detection = engine.process(chunk_320)
    assert len(backend.process_calls) == 1
    assert detection is not None
    assert detection.label == CANONICAL_WAKE_LABEL


def test_recoverable_backend_error_updates_health_and_raises() -> None:
    backend = FakePorcupineBackend(raise_on_process=RuntimeError("Porcupine C library panic"))
    engine = PorcupineWakeWordEngine(backend=backend)

    frame = b"\x00\x00" * 512
    with pytest.raises(WakeEngineProcessingError, match="Porcupine C library panic"):
        engine.process(frame)

    assert engine.health.error_count == 1
    assert engine.health.degraded is True
    assert "Porcupine C library panic" in (engine.health.last_error or "")


def test_reset_and_close() -> None:
    backend = FakePorcupineBackend()
    engine = PorcupineWakeWordEngine(backend=backend)

    engine.process(b"\x00\x00" * 100)
    engine.reset()
    assert backend.reset_called is True

    engine.close()
    assert backend.deleted is True
    assert engine.health.ready is False


def test_porcupine_fallback_to_bytes() -> None:
    class BytesOnlyBackend:
        frame_length = 512

        def __init__(self) -> None:
            self.calls: list[bytes] = []

        def process(self, frame: object) -> int:
            if not isinstance(frame, (bytes, bytearray)):
                raise TypeError("Expected raw bytes")
            self.calls.append(bytes(frame))
            return 0

    backend = BytesOnlyBackend()
    engine = PorcupineWakeWordEngine(backend=backend)
    frame = b"\x01\x00" * 512
    det = engine.process(frame)
    assert det is not None
    assert len(backend.calls) == 1

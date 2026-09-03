import time
from typing import Any

import pytest

from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    WakeDetection,
    WakeEngineHealth,
    WakeEngineProcessingError,
)
from innobrain.wake.router import (
    WakeAudioRouter,
    WakeRouterHealth,
    WakeRouterMode,
    WakeRouterOutput,
)


class MockEngine:
    def __init__(
        self,
        detections: list[WakeDetection | None] | None = None,
        raise_error: Exception | None = None,
        raise_on_reset: Exception | None = None,
        frame_length: int = 1280,
    ) -> None:
        self._detections = list(detections or [])
        self._raise_error = raise_error
        self._raise_on_reset = raise_on_reset
        self._frame_length = frame_length
        self.process_calls: list[bytes] = []
        self.reset_called = False
        self.closed = False
        self._error_count = 0
        self._degraded = False
        self._last_error: str | None = None

    @property
    def sample_rate_hz(self) -> int:
        return 16000

    @property
    def frame_length(self) -> int:
        return self._frame_length

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(
            ready=not self.closed,
            engine_name="mock_engine",
            error_count=self._error_count,
            degraded=self._degraded,
            last_error=self._last_error,
        )

    def process(self, pcm16: bytes) -> WakeDetection | None:
        self.process_calls.append(pcm16)
        if self._raise_error:
            self._error_count += 1
            self._degraded = True
            self._last_error = str(self._raise_error)
            raise self._raise_error
        if self._detections:
            return self._detections.pop(0)
        return None

    def reset(self) -> None:
        self.reset_called = True
        if self._raise_on_reset:
            raise self._raise_on_reset

    def close(self) -> None:
        self.closed = True


def test_router_initial_state() -> None:
    engine = MockEngine()
    router = WakeAudioRouter(engine=engine, preroll_ms=1500)

    assert router.mode == WakeRouterMode.SLEEPING
    assert router.is_playback_active is False
    assert isinstance(router.health, WakeRouterHealth)
    assert router.health.ready is True
    assert router.health.mode == "sleeping"
    assert router.health.buffered_duration_ms == 0.0


def test_sleeping_mode_routes_to_engine_no_downstream_pcm() -> None:
    engine = MockEngine(detections=[None, None])
    router = WakeAudioRouter(engine=engine)

    chunk = b"\x01\x00" * 320  # 20ms
    out1 = router.route_pcm(chunk)

    assert out1.mode == WakeRouterMode.SLEEPING
    assert out1.detection is None
    assert out1.downstream_pcm == b""
    assert len(engine.process_calls) == 1
    assert router.health.total_frames_received == 1


def test_detection_preserves_same_breath_continuation() -> None:
    # 3 chunks of 20ms background noise, then detection on chunk 4
    pre_wake_noise = b"\xaa\xbb" * 320
    wake_continuation_chunk = b"\x05\x00" * 320
    now = time.monotonic()
    detection = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="mock_engine",
        detected_at_monotonic=now,
        score=0.95,
    )
    engine = MockEngine(detections=[None, None, None, detection])
    router = WakeAudioRouter(engine=engine, preroll_ms=1500)

    # First 3 chunks: background noise while sleeping produces no downstream PCM
    for _ in range(3):
        out_noise = router.route_pcm(pre_wake_noise)
        assert out_noise.downstream_pcm == b""

    # 4th chunk triggers detection
    out = router.route_pcm(wake_continuation_chunk)

    assert out.detection is not None
    assert out.detection.label == CANONICAL_WAKE_LABEL
    assert out.mode == WakeRouterMode.ENGAGED

    # Downstream PCM contains ONLY current detection/continuation frame, NOT pre-wake noise
    assert out.downstream_pcm == wake_continuation_chunk
    assert pre_wake_noise not in out.downstream_pcm

    # Diagnostic bounded ring history preserves pre-roll context
    assert pre_wake_noise in out.pre_roll_context_pcm
    assert pre_wake_noise in router.get_pre_roll_history()
    assert router.mode == WakeRouterMode.ENGAGED

    # Subsequent frame in engaged mode passes directly through
    subsequent_chunk = b"\x06\x00" * 320
    out_subsequent = router.route_pcm(subsequent_chunk)
    assert out_subsequent.downstream_pcm == subsequent_chunk


def test_engaged_mode_bypasses_engine_routes_directly_to_downstream() -> None:
    engine = MockEngine()
    router = WakeAudioRouter(engine=engine)
    router.set_mode(WakeRouterMode.ENGAGED)

    chunk = b"\x09\x00" * 320
    out = router.route_pcm(chunk)

    assert out.mode == WakeRouterMode.ENGAGED
    assert out.detection is None
    assert out.downstream_pcm == chunk
    # Wake engine was NOT called in ENGAGED mode
    assert len(engine.process_calls) == 0


def test_followup_window_bypasses_engine_routes_directly_to_downstream() -> None:
    engine = MockEngine()
    router = WakeAudioRouter(engine=engine)
    router.set_mode(WakeRouterMode.FOLLOWUP_WINDOW)

    chunk = b"\x07\x00" * 320
    out = router.route_pcm(chunk)

    assert out.mode == WakeRouterMode.FOLLOWUP_WINDOW
    assert out.detection is None
    assert out.downstream_pcm == chunk
    assert len(engine.process_calls) == 0


def test_cooldown_duplicate_suppression() -> None:
    now = time.monotonic()
    d1 = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="mock",
        detected_at_monotonic=now,
        score=0.9,
    )
    d2 = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="mock",
        detected_at_monotonic=now + 0.1,
        score=0.92,
    )
    engine = MockEngine(detections=[d1, d2])
    router = WakeAudioRouter(engine=engine, cooldown_seconds=1.5)

    chunk = b"\x01\x00" * 100
    out1 = router.route_pcm(chunk)
    assert out1.detection is not None

    # Reset back to SLEEPING to test cooldown window
    router.set_mode(WakeRouterMode.SLEEPING)

    # Immediately feed chunk with d2
    out2 = router.route_pcm(chunk)
    assert out2.detection is None  # Suppressed by cooldown
    assert out2.downstream_pcm == b""
    assert router.health.suppressed_detections_cooldown == 1


def test_self_playback_suppression() -> None:
    detection = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="mock",
        detected_at_monotonic=time.monotonic(),
        score=0.9,
    )
    engine = MockEngine(detections=[detection, detection])
    router = WakeAudioRouter(engine=engine)

    router.set_playback_active(True)
    assert router.is_playback_active is True

    chunk = b"\x02\x00" * 100
    out = router.route_pcm(chunk)
    # Detection suppressed because robot is speaking
    assert out.detection is None
    assert out.downstream_pcm == b""
    assert router.health.suppressed_detections_playback == 1

    # Playback finishes
    router.set_playback_active(False)
    out2 = router.route_pcm(chunk)
    assert out2.detection is not None
    assert out2.detection.label == CANONICAL_WAKE_LABEL


def test_confuser_suppression_at_router_boundary() -> None:
    confuser_detection = WakeDetection(
        label="alexa",  # Non-canonical confuser label
        detector="mock",
        detected_at_monotonic=time.monotonic(),
        score=0.99,
    )
    engine = MockEngine(detections=[confuser_detection])
    router = WakeAudioRouter(engine=engine)

    chunk = b"\x03\x00" * 100
    out = router.route_pcm(chunk)
    assert out.detection is None
    assert out.downstream_pcm == b""


def test_recoverable_engine_exception_does_not_crash_router() -> None:
    engine = MockEngine(raise_error=WakeEngineProcessingError("DSP buffer overflow"))
    router = WakeAudioRouter(engine=engine)

    chunk = b"\x04\x00" * 100
    # Should not raise; catches recoverable error, resets engine, records health
    out = router.route_pcm(chunk)

    assert out.detection is None
    assert out.downstream_pcm == b""
    assert router.health.degraded is True
    assert router.health.error_count == 1
    assert router.health.recovery_count == 1
    assert engine.reset_called is True
    assert router.mode == WakeRouterMode.SLEEPING
    assert "DSP buffer overflow" in (router.health.last_error or "")

    # Router stays alive and continues processing
    engine._raise_error = None
    out2 = router.route_pcm(chunk)
    assert out2.mode == WakeRouterMode.SLEEPING
    assert out2.detection is None


def test_recoverable_engine_exception_when_reset_itself_fails() -> None:
    engine = MockEngine(
        raise_error=WakeEngineProcessingError("Hardware fault"),
        raise_on_reset=RuntimeError("Reset bus timeout"),
    )
    router = WakeAudioRouter(engine=engine)

    chunk = b"\x04\x00" * 100
    # Even if reset raises, router catches it, remains visibly degraded, does not crash-loop
    out = router.route_pcm(chunk)

    assert out.detection is None
    assert out.downstream_pcm == b""
    assert router.health.degraded is True
    assert router.health.error_count == 1
    assert router.health.recovery_count == 0
    assert "Recovery reset failed" in (router.health.last_error or "")
    assert "Reset bus timeout" in (router.health.last_error or "")

    # Subsequent frames continue without unhandled exceptions
    out2 = router.route_pcm(chunk)
    assert out2.mode == WakeRouterMode.SLEEPING
    assert router.health.error_count == 2


def test_entering_sleeping_clears_buffered_engaged_audio() -> None:
    engine = MockEngine()
    router = WakeAudioRouter(engine=engine)

    # Transition to ENGAGED and stream session audio
    router.set_mode(WakeRouterMode.ENGAGED)
    router.route_pcm(b"\x07\x00" * 320)
    router.route_pcm(b"\x08\x00" * 320)

    assert router.health.buffered_duration_ms > 0
    assert len(router.get_pre_roll_history()) > 0

    # Entering SLEEPING must wipe buffered engaged audio and reset engine
    router.set_mode(WakeRouterMode.SLEEPING)

    assert router.mode == WakeRouterMode.SLEEPING
    assert router.health.buffered_duration_ms == 0.0
    assert router.get_pre_roll_history() == b""
    assert engine.reset_called is True


def test_reset_and_close() -> None:
    engine = MockEngine()
    router = WakeAudioRouter(engine=engine)

    router.route_pcm(b"\x01\x00" * 320)
    assert router.health.buffered_duration_ms > 0

    router.reset()
    assert router.health.buffered_duration_ms == 0.0
    assert engine.reset_called is True

    router.close()
    assert engine.closed is True
    assert router.health.ready is False


@pytest.mark.asyncio
async def test_async_route_stream_helper() -> None:
    engine = MockEngine()
    router = WakeAudioRouter(engine=engine)

    async def fake_pcm_stream() -> Any:
        yield b"\x01\x00" * 100
        yield b"\x02\x00" * 100

    results: list[WakeRouterOutput] = []
    async for output in router.route_stream(fake_pcm_stream()):
        results.append(output)

    assert len(results) == 2
    assert results[0].mode == WakeRouterMode.SLEEPING
    assert results[1].mode == WakeRouterMode.SLEEPING

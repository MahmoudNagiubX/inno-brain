
from innobrain.attention.contracts import (
    AddressivityVerdict,
    AttentionState,
    SessionCloseReason,
)
from innobrain.attention.controller import AttentionController
from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    WakeDetection,
    WakeEngineHealth,
)
from innobrain.wake.router import WakeAudioRouter, WakeRouterMode


class MockEngine:
    def __init__(self, detections: list[WakeDetection | None] | None = None) -> None:
        self._detections = list(detections or [])
        self.process_calls: list[bytes] = []
        self.reset_called = False
        self.closed = False

    @property
    def sample_rate_hz(self) -> int:
        return 16000

    @property
    def frame_length(self) -> int:
        return 1280

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(
            ready=not self.closed,
            engine_name="mock_integration_engine",
        )

    def process(self, pcm16: bytes) -> WakeDetection | None:
        self.process_calls.append(pcm16)
        if self._detections:
            return self._detections.pop(0)
        return None

    def reset(self) -> None:
        self.reset_called = True

    def close(self) -> None:
        self.closed = True


class StepClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.current = start

    def __call__(self) -> float:
        return self.current

    def advance(self, s: float) -> float:
        self.current += s
        return self.current


def test_wake_router_and_attention_multi_turn_lifecycle() -> None:
    clock = StepClock(1000.0)
    wake_detection = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="mock_detector",
        detected_at_monotonic=1000.0,
        score=0.98,
    )
    engine = MockEngine(detections=[None, wake_detection])
    router = WakeAudioRouter(engine=engine, auto_engage=False)
    controller = AttentionController(clock=clock, router=router)

    # 1. Initially sleeping
    assert controller.state == AttentionState.SLEEPING
    assert router.mode == WakeRouterMode.SLEEPING

    # 2. Feed quiet chunk while sleeping: downstream pcm is suppressed
    quiet_chunk = b"\x01\x00" * 320
    out1 = router.route_pcm(quiet_chunk)
    assert out1.downstream_pcm == b""
    assert controller.state == AttentionState.SLEEPING

    # 3. Feed wake chunk: router emits detection
    wake_chunk = b"\x05\x00" * 320
    out2 = router.route_pcm(wake_chunk)
    assert out2.detection is not None
    assert out2.detection.label == CANONICAL_WAKE_LABEL

    # Controller handles wake detection
    accepted = controller.on_wake_detected(
        detection=out2.detection,
        continuation_pcm=out2.downstream_pcm,
        same_breath_text="tell me the weather",
    )
    assert accepted is True
    assert controller.state == AttentionState.ENGAGED
    # Router mode synchronized to ENGAGED
    assert router.mode == WakeRouterMode.ENGAGED

    # 4. In ENGAGED mode, speech streams directly downstream without wake engine invocation
    subsequent_chunk = b"\x06\x00" * 320
    out3 = router.route_pcm(subsequent_chunk)
    assert out3.downstream_pcm == subsequent_chunk

    # 5. Assistant reply completes -> enter FOLLOWUP_WINDOW
    clock.advance(3.0)
    controller.on_reply_completed()
    assert controller.state == AttentionState.FOLLOWUP_WINDOW
    assert router.mode == WakeRouterMode.FOLLOWUP_WINDOW

    # In follow-up window, router continues passing downstream PCM
    out4 = router.route_pcm(subsequent_chunk)
    assert out4.downstream_pcm == subsequent_chunk

    # 6. Directed follow-up from user: "tamam"
    clock.advance(1.0)
    assert controller.on_utterance_start() is True
    decision = controller.on_utterance_end("tamam")
    assert decision is not None
    assert decision.is_directed is True
    assert decision.verdict == AddressivityVerdict.CONVERSATION_CONTINUITY
    # Transitions back to ENGAGED
    assert controller.state == AttentionState.ENGAGED
    assert router.mode == WakeRouterMode.ENGAGED

    # 7. Next assistant reply completes -> FOLLOWUP_WINDOW again
    clock.advance(2.0)
    controller.on_reply_completed()
    assert controller.state == AttentionState.FOLLOWUP_WINDOW
    assert router.mode == WakeRouterMode.FOLLOWUP_WINDOW

    # 8. User doesn't speak, follow-up window expires (4.5s)
    clock.advance(4.6)
    reason = controller.check_timeouts()
    assert reason == SessionCloseReason.FOLLOWUP_TIMEOUT
    assert controller.state == AttentionState.SLEEPING
    assert router.mode == WakeRouterMode.SLEEPING
    # Engine was reset upon entering SLEEPING
    assert engine.reset_called is True

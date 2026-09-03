
from innobrain.attention.contracts import AttentionPolicyConfig, AttentionState
from innobrain.attention.controller import AttentionController
from innobrain.wake.bridge import WakeAttentionBridge
from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineHealth,
    WakeWordEngine,
)
from innobrain.wake.router import WakeAudioRouter


class FakeEngine(WakeWordEngine):
    def __init__(self) -> None:
        self.trigger_on_next: WakeDetection | None = None
        self.reset_called = False
        self.close_called = False

    @property
    def sample_rate_hz(self) -> int:
        return SAMPLE_RATE_HZ

    @property
    def frame_length(self) -> int:
        return 1280

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(ready=True, engine_name="fake")

    def process(self, pcm16: bytes) -> WakeDetection | None:
        det = self.trigger_on_next
        self.trigger_on_next = None
        return det

    def reset(self) -> None:
        self.reset_called = True

    def close(self) -> None:
        self.close_called = True


def test_bridge_sleeping_pcm_is_suppressed_from_downstream() -> None:
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    chunk = b"\x01\x00" * 640
    # Sleeping chunk with no wake detection
    out = bridge.process_chunk(chunk)

    # Suppressed: downstream receives empty bytes
    assert out == b""
    assert bridge.state == AttentionState.SLEEPING
    assert bridge.mode == "sleeping"
    # Diagnostic history is kept in router ring buffer
    assert len(router.get_pre_roll_history()) > 0


def test_bridge_canonical_wake_enters_engaged_and_emits_only_current_chunk() -> None:
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    pre_chunk = b"\x01\x00" * 640
    bridge.process_chunk(pre_chunk)
    assert bridge.state == AttentionState.SLEEPING

    # Trigger canonical wake
    wake_chunk = b"\x02\x00" * 640
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="fake",
        detected_at_monotonic=100.0,
        score=0.95,
    )

    out = bridge.process_chunk(wake_chunk)

    # Mode transitioned to ENGAGED
    assert bridge.state == AttentionState.ENGAGED
    assert bridge.mode == "engaged"
    # Emits only the current wake chunk downstream, NOT pre_chunk
    assert out == wake_chunk
    # Same-breath handoff metadata available
    assert attention.handoff_metadata is not None
    assert attention.handoff_metadata.wake_detection.label == CANONICAL_WAKE_LABEL


def test_bridge_non_canonical_confuser_is_suppressed() -> None:
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    chunk = b"\x03\x00" * 640
    engine.trigger_on_next = WakeDetection(
        label="alexa",
        detector="fake",
        detected_at_monotonic=100.0,
        score=0.99,
    )

    out = bridge.process_chunk(chunk)

    assert out == b""
    assert bridge.state == AttentionState.SLEEPING
    assert bridge.mode == "sleeping"


def test_bridge_engaged_chunks_flow_downstream() -> None:
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    # Wake up
    wake_chunk = b"\x02\x00" * 640
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=1.0
    )
    bridge.process_chunk(wake_chunk)
    assert bridge.state == AttentionState.ENGAGED

    # Stream subsequent engaged audio
    speech_1 = b"\x04\x00" * 640
    speech_2 = b"\x05\x00" * 640
    assert bridge.process_chunk(speech_1) == speech_1
    assert bridge.process_chunk(speech_2) == speech_2


def test_bridge_followup_window_chunks_flow_downstream_and_timeout_returns_to_sleeping() -> None:
    mock_now = 100.0

    def clock() -> float:
        return mock_now

    policy = AttentionPolicyConfig(followup_window_ms=4500.0)
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(policy=policy, clock=clock, router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    # Wake up
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=mock_now
    )
    bridge.process_chunk(b"\x01\x00" * 640)
    assert bridge.state == AttentionState.ENGAGED

    # Reply completed -> FOLLOWUP_WINDOW
    mock_now += 2.0
    attention.on_reply_completed(now=mock_now)
    assert bridge.state == AttentionState.FOLLOWUP_WINDOW

    # Chunks during follow-up window flow downstream
    mock_now += 1.0
    followup_pcm = b"\x06\x00" * 640
    assert bridge.process_chunk(followup_pcm) == followup_pcm

    # Follow-up deadline passes without speech (e.g. 5 seconds after reply complete)
    mock_now += 4.0  # 5 seconds elapsed > 4.5s
    sleeping_pcm = b"\x07\x00" * 640
    out = bridge.process_chunk(sleeping_pcm)

    # Bridge detected timeout, closed session, and suppressed chunk
    assert out == b""
    assert bridge.state == AttentionState.SLEEPING
    assert bridge.mode == "sleeping"

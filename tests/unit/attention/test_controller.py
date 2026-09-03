
from innobrain.attention.contracts import (
    AddressivityVerdict,
    AttentionPolicyConfig,
    AttentionState,
    SameBreathHandoff,
    SessionCloseReason,
)
from innobrain.attention.controller import AttentionController
from innobrain.attention.presence import DefaultPresenceSignal, PresenceState
from innobrain.wake.contracts import CANONICAL_WAKE_LABEL, WakeDetection
from innobrain.wake.router import WakeRouterMode


class ManualClock:
    """Deterministic monotonic clock for attention tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self.time = initial_time

    def __call__(self) -> float:
        return self.time

    def advance(self, seconds: float) -> float:
        self.time += seconds
        return self.time


def make_wake_detection(
    label: str = CANONICAL_WAKE_LABEL,
    detected_at: float = 1000.0,
    score: float = 0.95,
) -> WakeDetection:
    return WakeDetection(
        label=label,
        detector="test_detector",
        detected_at_monotonic=detected_at,
        score=score,
    )


class MockRouter:
    """Mock router observing mode synchronization."""

    def __init__(self) -> None:
        self.mode: str = "sleeping"

    def set_mode(self, mode: str) -> None:
        self.mode = str(mode)


def test_initial_state_is_sleeping() -> None:
    clock = ManualClock()
    controller = AttentionController(clock=clock)

    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    assert controller.is_engaged is False
    assert controller.is_utterance_in_progress is False
    assert controller.handoff_metadata is None

    health = controller.health
    assert health.ready is True
    assert health.state == AttentionState.SLEEPING
    assert health.session_active is False
    assert health.total_sessions_started == 0
    assert health.total_sessions_closed == 0


def test_sleeping_speech_rejected_and_never_forwarded() -> None:
    clock = ManualClock()
    controller = AttentionController(clock=clock)

    # Ordinary speech while sleeping cannot start an utterance
    accepted_start = controller.on_utterance_start()
    assert accepted_start is False
    assert controller.is_utterance_in_progress is False

    # Utterance end while sleeping is ignored
    decision = controller.on_utterance_end("hello")
    assert decision is None
    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None


def test_wake_acceptance_starts_engaged_session() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    detection = make_wake_detection(detected_at=100.0)
    chunk = b"\x01\x00" * 160

    accepted = controller.on_wake_detected(
        detection=detection,
        continuation_pcm=chunk,
        same_breath_text="what time is it",
    )

    assert accepted is True
    assert controller.state == AttentionState.ENGAGED
    assert controller.is_engaged is True
    assert controller.session_id is not None
    assert len(controller.session_id) > 0

    # Same-breath handoff metadata captured
    handoff = controller.handoff_metadata
    assert isinstance(handoff, SameBreathHandoff)
    assert handoff.wake_detection == detection
    assert handoff.continuation_pcm == chunk
    assert handoff.command_text == "what time is it"
    assert handoff.session_id == controller.session_id

    # Health metrics reflect started session
    health = controller.health
    assert health.session_active is True
    assert health.total_sessions_started == 1
    assert health.last_wake_monotonic == 100.0


def test_non_canonical_wake_confuser_rejected() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    confuser = make_wake_detection(label="alexa", detected_at=100.0)
    accepted = controller.on_wake_detected(confuser)

    assert accepted is False
    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    assert controller.health.total_sessions_started == 0


def test_reply_completed_enters_followup_window() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    # Enter ENGAGED
    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    assert controller.state == AttentionState.ENGAGED

    clock.advance(5.0)  # At 105.0s, assistant finishes reply
    entered = controller.on_reply_completed()

    assert entered is True
    assert controller.state == AttentionState.FOLLOWUP_WINDOW
    assert controller.is_engaged is True
    assert controller.health.followup_window_remaining_ms == 4500.0


def test_reply_completed_idempotent_when_sleeping() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    entered = controller.on_reply_completed()
    assert entered is False
    assert controller.state == AttentionState.SLEEPING


def test_followup_window_directed_speech_accepted_and_reopens_engaged() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    clock.advance(2.0)
    controller.on_reply_completed()
    assert controller.state == AttentionState.FOLLOWUP_WINDOW

    clock.advance(1.5)  # 1500ms into 4500ms window
    assert controller.on_utterance_start() is True
    assert controller.is_utterance_in_progress is True

    # User gives directed confirmation
    decision = controller.on_utterance_end("tamam")
    assert decision is not None
    assert decision.is_directed is True
    assert decision.verdict == AddressivityVerdict.CONVERSATION_CONTINUITY
    assert controller.state == AttentionState.ENGAGED
    assert controller.is_utterance_in_progress is False
    assert controller.health.rejected_background_count == 0


def test_followup_window_ambiguous_speech_rejected_and_closes_on_limit() -> None:
    clock = ManualClock(100.0)
    policy = AttentionPolicyConfig(rejected_background_limit=1)
    controller = AttentionController(policy=policy, clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    clock.advance(2.0)
    controller.on_reply_completed()
    assert controller.state == AttentionState.FOLLOWUP_WINDOW

    clock.advance(1.0)
    assert controller.on_utterance_start() is True

    # Background speech: side conversation
    decision = controller.on_utterance_end("did you see the match yesterday")
    assert decision is not None
    assert decision.is_directed is False
    assert decision.verdict == AddressivityVerdict.BACKGROUND_AMBIGUOUS

    # Reached rejected-background limit 1 -> session closed!
    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    health = controller.health
    assert health.rejected_background_count == 1
    assert health.last_close_reason == SessionCloseReason.REJECTED_BACKGROUND
    assert health.total_sessions_closed == 1


def test_followup_window_timeout_closes_session() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    clock.advance(2.0)
    controller.on_reply_completed()  # Reply completed at 102.0s
    assert controller.state == AttentionState.FOLLOWUP_WINDOW

    # Advance past 4.5s default window
    clock.advance(4.6)

    close_reason = controller.check_timeouts()
    assert close_reason == SessionCloseReason.FOLLOWUP_TIMEOUT
    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    assert controller.health.last_close_reason == SessionCloseReason.FOLLOWUP_TIMEOUT


def test_followup_window_configurable_cap() -> None:
    # Cap is 8000ms; even if 10000ms requested, clamped to 8000ms
    policy = AttentionPolicyConfig(followup_window_ms=10000.0, followup_window_cap_ms=8000.0)
    clock = ManualClock(100.0)
    controller = AttentionController(policy=policy, clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    clock.advance(1.0)
    controller.on_reply_completed()

    # At 7.5s, window should still be active
    clock.advance(7.5)
    assert controller.check_timeouts() is None
    assert controller.state == AttentionState.FOLLOWUP_WINDOW

    # At 8.1s, cap of 8.0s has expired
    clock.advance(0.6)
    assert controller.check_timeouts() == SessionCloseReason.FOLLOWUP_TIMEOUT
    assert controller.state == AttentionState.SLEEPING


def test_direct_new_wake_in_followup_refreshes_engagement() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    initial_session_id = controller.session_id

    clock.advance(2.0)
    controller.on_reply_completed()
    assert controller.state == AttentionState.FOLLOWUP_WINDOW

    # A direct new Heyino wake reopens/refreshes engagement
    clock.advance(2.0)
    detection2 = make_wake_detection(detected_at=104.0)
    refreshed = controller.on_wake_detected(
        detection=detection2,
        same_breath_text="search python docs",
    )

    assert refreshed is True
    assert controller.state == AttentionState.ENGAGED
    assert controller.session_id == initial_session_id  # Maintains current session
    assert controller.handoff_metadata is not None
    assert controller.handoff_metadata.command_text == "search python docs"
    assert controller.health.last_wake_monotonic == 104.0


def test_do_not_close_mid_utterance_followup_timeout() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    clock.advance(2.0)
    controller.on_reply_completed()  # Followup starts at 102.0s
    assert controller.state == AttentionState.FOLLOWUP_WINDOW

    # User starts speaking at second 4.0 (before 4.5s deadline)
    clock.advance(4.0)
    assert controller.on_utterance_start() is True
    assert controller.is_utterance_in_progress is True

    # Monotonic clock ticks past 4.5s (e.g. at 5.5s) while user is STILL speaking
    clock.advance(1.5)
    timeout_result = controller.check_timeouts()

    # MUST NOT close mid-utterance!
    assert timeout_result is None
    assert controller.state == AttentionState.FOLLOWUP_WINDOW
    assert controller.is_utterance_in_progress is True

    # User finishes speaking a directed utterance
    decision = controller.on_utterance_end("yes please")
    assert decision is not None
    assert decision.is_directed is True
    # Directed utterance accepted, transitions back to ENGAGED
    assert controller.state == AttentionState.ENGAGED


def test_do_not_close_mid_utterance_max_session_cap() -> None:
    clock = ManualClock(100.0)
    policy = AttentionPolicyConfig(max_session_duration_seconds=120.0)
    controller = AttentionController(policy=policy, clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    assert controller.state == AttentionState.ENGAGED

    # Advance to 119.0s (1s before 120s limit)
    clock.advance(119.0)
    assert controller.on_utterance_start() is True
    assert controller.is_utterance_in_progress is True

    # Clock reaches 121.0s while utterance in progress
    clock.advance(2.0)
    assert controller.check_timeouts() is None
    assert controller.state == AttentionState.ENGAGED

    # Utterance ends
    controller.on_utterance_end("this was a long question")
    # Now max session cap is enforced
    assert controller.state == AttentionState.SLEEPING
    assert controller.health.last_close_reason == SessionCloseReason.MAX_SESSION_DURATION


def test_utterance_starting_after_followup_timeout_is_rejected() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    clock.advance(1.0)
    controller.on_reply_completed()

    # Time elapses past follow-up window (5.0s > 4.5s)
    clock.advance(5.0)

    # Attempting to start utterance after expiration is rejected and closes session
    accepted = controller.on_utterance_start()
    assert accepted is False
    assert controller.state == AttentionState.SLEEPING
    assert controller.health.last_close_reason == SessionCloseReason.FOLLOWUP_TIMEOUT


def test_max_session_cap_120_seconds_enforced() -> None:
    clock = ManualClock(100.0)
    policy = AttentionPolicyConfig(max_session_duration_seconds=120.0)
    controller = AttentionController(policy=policy, clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    assert controller.state == AttentionState.ENGAGED

    # Advance past 120.0s
    clock.advance(120.1)
    close_reason = controller.check_timeouts()

    assert close_reason == SessionCloseReason.MAX_SESSION_DURATION
    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    assert controller.health.last_close_reason == SessionCloseReason.MAX_SESSION_DURATION


def test_explicit_dismiss() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    assert controller.state == AttentionState.ENGAGED

    controller.dismiss()
    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    assert controller.health.last_close_reason == SessionCloseReason.EXPLICIT_DISMISS


def test_reset_clears_prior_session_data_without_leaks() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(
        make_wake_detection(detected_at=100.0),
        continuation_pcm=b"\x01\x00" * 100,
        same_breath_text="private info",
    )
    assert controller.session_id is not None
    assert controller.handoff_metadata is not None

    controller.reset()

    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None
    assert controller.handoff_metadata is None
    assert controller.is_utterance_in_progress is False

    health = controller.health
    assert health.state == AttentionState.SLEEPING
    assert health.session_id is None
    assert health.session_active is False
    assert health.session_duration_seconds == 0.0


def test_recovery_reset_tracks_watchdog_metrics() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    controller.recovery_reset(error="Audio pipeline deadlock detected")

    assert controller.state == AttentionState.SLEEPING
    assert controller.session_id is None

    health = controller.health
    assert health.degraded is True
    assert health.error_count == 1
    assert health.recovery_count == 1
    assert health.last_error == "Audio pipeline deadlock detected"
    assert health.last_close_reason == SessionCloseReason.ERROR

    # Reset clears degraded state
    controller.reset()
    assert controller.health.degraded is False
    assert controller.health.last_error is None


def test_safe_default_presence_signal_behavior() -> None:
    clock = ManualClock(100.0)
    controller = AttentionController(clock=clock)
    assert isinstance(controller.presence, DefaultPresenceSignal)
    assert controller.presence.get_presence_state() == PresenceState.UNKNOWN


def test_router_mode_synchronization_if_provided() -> None:
    clock = ManualClock(100.0)
    mock_router = MockRouter()
    controller = AttentionController(clock=clock, router=mock_router)

    assert mock_router.mode == "sleeping"

    controller.on_wake_detected(make_wake_detection(detected_at=100.0))
    assert mock_router.mode == WakeRouterMode.ENGAGED.value

    clock.advance(1.0)
    controller.on_reply_completed()
    assert mock_router.mode == WakeRouterMode.FOLLOWUP_WINDOW.value

    controller.dismiss()
    assert mock_router.mode == WakeRouterMode.SLEEPING.value

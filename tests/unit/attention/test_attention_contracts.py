import pytest

from innobrain.attention.contracts import (
    AddressivityDecision,
    AddressivityVerdict,
    AttentionHealth,
    AttentionPolicyConfig,
    AttentionState,
    SameBreathHandoff,
    SessionCloseReason,
)
from innobrain.wake.contracts import CANONICAL_WAKE_LABEL, WakeDetection


def test_attention_states_values() -> None:
    assert AttentionState.SLEEPING == "SLEEPING"
    assert AttentionState.ENGAGED == "ENGAGED"
    assert AttentionState.FOLLOWUP_WINDOW == "FOLLOWUP_WINDOW"


def test_session_close_reasons_values() -> None:
    assert SessionCloseReason.FOLLOWUP_TIMEOUT == "followup_timeout"
    assert SessionCloseReason.MAX_SESSION_DURATION == "max_session_duration"
    assert SessionCloseReason.REJECTED_BACKGROUND == "rejected_background"
    assert SessionCloseReason.EXPLICIT_DISMISS == "explicit_dismiss"
    assert SessionCloseReason.RESET == "reset"
    assert SessionCloseReason.ERROR == "error"


def test_attention_policy_defaults() -> None:
    policy = AttentionPolicyConfig()
    assert policy.followup_window_ms == 4500.0
    assert policy.followup_window_cap_ms == 8000.0
    assert policy.effective_followup_window_ms == 4500.0
    assert policy.effective_followup_window_seconds == 4.5
    assert policy.max_session_duration_seconds == 120.0
    assert policy.rejected_background_limit == 1
    assert policy.wake_cooldown_seconds == 1.5


def test_attention_policy_cap_enforcement() -> None:
    # If followup_window_ms exceeds cap, effective value is clamped to cap
    policy = AttentionPolicyConfig(followup_window_ms=10000.0, followup_window_cap_ms=8000.0)
    assert policy.effective_followup_window_ms == 8000.0
    assert policy.effective_followup_window_seconds == 8.0

    # Custom cap
    custom_policy = AttentionPolicyConfig(followup_window_ms=5000.0, followup_window_cap_ms=6000.0)
    assert custom_policy.effective_followup_window_ms == 5000.0


def test_attention_policy_validation() -> None:
    with pytest.raises(ValueError, match="followup_window_ms must be non-negative"):
        AttentionPolicyConfig(followup_window_ms=-1.0)

    with pytest.raises(ValueError, match="followup_window_cap_ms must be non-negative"):
        AttentionPolicyConfig(followup_window_cap_ms=-5.0)

    with pytest.raises(ValueError, match="max_session_duration_seconds must be positive"):
        AttentionPolicyConfig(max_session_duration_seconds=0.0)

    with pytest.raises(ValueError, match="rejected_background_limit must be >= 1"):
        AttentionPolicyConfig(rejected_background_limit=0)


def test_same_breath_handoff_immutability() -> None:
    detection = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="test_engine",
        detected_at_monotonic=100.0,
        score=0.95,
    )
    handoff = SameBreathHandoff(
        wake_detection=detection,
        continuation_pcm=b"\x01\x00" * 160,
        command_text="turn on the lights",
        detected_at_monotonic=100.0,
        session_id="session-123",
    )
    assert handoff.wake_detection.label == CANONICAL_WAKE_LABEL
    assert handoff.command_text == "turn on the lights"
    assert handoff.session_id == "session-123"

    with pytest.raises(AttributeError):
        handoff.session_id = "mutated"  # type: ignore[misc]


def test_addressivity_decision_immutability() -> None:
    decision = AddressivityDecision(
        verdict=AddressivityVerdict.DIRECTED_CUE,
        is_directed=True,
        confidence=0.9,
        reason="Matched directed cue: tell me",
        matched_cue="tell me",
        extracted_command="tell me a story",
    )
    assert decision.is_directed is True
    assert decision.matched_cue == "tell me"

    with pytest.raises(AttributeError):
        decision.is_directed = False  # type: ignore[misc]


def test_attention_health_fields() -> None:
    health = AttentionHealth(
        ready=True,
        state=AttentionState.SLEEPING,
        session_id=None,
        session_active=False,
        session_duration_seconds=0.0,
        last_transition_monotonic=10.0,
        last_wake_monotonic=None,
        last_reply_monotonic=None,
        rejected_background_count=0,
        total_sessions_started=0,
        total_sessions_closed=0,
        last_close_reason=None,
        followup_window_remaining_ms=None,
        is_utterance_in_progress=False,
        degraded=False,
        error_count=0,
        recovery_count=0,
        last_error=None,
    )
    assert health.ready is True
    assert health.state == AttentionState.SLEEPING
    assert health.session_active is False

    with pytest.raises(AttributeError):
        health.ready = False  # type: ignore[misc]

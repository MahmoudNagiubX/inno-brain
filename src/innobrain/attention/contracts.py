from dataclasses import dataclass
from enum import StrEnum

from innobrain.wake.contracts import WakeDetection


class AttentionState(StrEnum):
    """Orthogonal attention states separate from conversation state machine."""

    SLEEPING = "SLEEPING"
    ENGAGED = "ENGAGED"
    FOLLOWUP_WINDOW = "FOLLOWUP_WINDOW"


class SessionCloseReason(StrEnum):
    """Explicit reasons for closing an attention session."""

    FOLLOWUP_TIMEOUT = "followup_timeout"
    MAX_SESSION_DURATION = "max_session_duration"
    REJECTED_BACKGROUND = "rejected_background"
    EXPLICIT_DISMISS = "explicit_dismiss"
    RESET = "reset"
    ERROR = "error"


class AddressivityVerdict(StrEnum):
    """Classification of speaker addressivity."""

    EXPLICIT_WAKE = "explicit_wake"
    CONVERSATION_CONTINUITY = "conversation_continuity"
    DIRECTED_CUE = "directed_cue"
    BACKGROUND_AMBIGUOUS = "background_ambiguous"


@dataclass(frozen=True, slots=True)
class AddressivityDecision:
    """Decision output from evaluating speaker input."""

    verdict: AddressivityVerdict
    is_directed: bool
    confidence: float
    reason: str
    matched_cue: str | None = None
    extracted_command: str | None = None


@dataclass(frozen=True, slots=True)
class SameBreathHandoff:
    """Metadata captured when wake detection includes continuation audio or command context."""

    wake_detection: WakeDetection
    continuation_pcm: bytes = b""
    command_text: str | None = None
    detected_at_monotonic: float = 0.0
    session_id: str = ""


@dataclass(frozen=True, slots=True)
class AttentionTransition:
    """Record of an attention state transition."""

    at_monotonic: float
    from_state: AttentionState
    to_state: AttentionState
    reason: str
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class AttentionPolicyConfig:
    """Configuration policy for attention session timing, caps, and limits."""

    followup_window_ms: float = 4500.0
    followup_window_cap_ms: float = 8000.0
    max_session_duration_seconds: float = 120.0
    rejected_background_limit: int = 1
    wake_cooldown_seconds: float = 1.5

    def __post_init__(self) -> None:
        if self.followup_window_ms < 0:
            raise ValueError("followup_window_ms must be non-negative")
        if self.followup_window_cap_ms < 0:
            raise ValueError("followup_window_cap_ms must be non-negative")
        if self.max_session_duration_seconds <= 0:
            raise ValueError("max_session_duration_seconds must be positive")
        if self.rejected_background_limit < 1:
            raise ValueError("rejected_background_limit must be >= 1")

    @property
    def effective_followup_window_ms(self) -> float:
        """Configured follow-up window clamped by the upper cap."""
        return min(self.followup_window_ms, self.followup_window_cap_ms)

    @property
    def effective_followup_window_seconds(self) -> float:
        return self.effective_followup_window_ms / 1000.0


@dataclass(frozen=True, slots=True)
class AttentionHealth:
    """Observable attention health snapshot exposed to watchdogs and orchestrators."""

    ready: bool
    state: AttentionState
    session_id: str | None
    session_active: bool
    session_duration_seconds: float
    last_transition_monotonic: float
    last_wake_monotonic: float | None
    last_reply_monotonic: float | None
    rejected_background_count: int
    total_sessions_started: int
    total_sessions_closed: int
    last_close_reason: SessionCloseReason | None
    followup_window_remaining_ms: float | None
    is_utterance_in_progress: bool
    degraded: bool
    error_count: int
    recovery_count: int
    last_error: str | None

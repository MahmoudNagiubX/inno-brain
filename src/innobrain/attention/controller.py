import time
import uuid
from collections.abc import Callable
from typing import Any

from innobrain.attention.addressivity import AddressivityGate
from innobrain.attention.contracts import (
    AddressivityDecision,
    AttentionHealth,
    AttentionPolicyConfig,
    AttentionState,
    AttentionTransition,
    SameBreathHandoff,
    SessionCloseReason,
)
from innobrain.attention.presence import DefaultPresenceSignal, PresenceSignal
from innobrain.wake.contracts import CANONICAL_WAKE_LABEL, WakeDetection


class AttentionController:
    """Mode and session controller for the orthogonal local attention layer.

    Manages attention transitions between SLEEPING, ENGAGED, and FOLLOWUP_WINDOW.
    Operates without background threads, using event boundaries and an injected monotonic clock.
    Protects ongoing utterances from closing mid-speech while enforcing session caps and
    follow-up deadlines.
    """

    def __init__(
        self,
        policy: AttentionPolicyConfig | None = None,
        presence: PresenceSignal | None = None,
        gate: AddressivityGate | None = None,
        clock: Callable[[], float] = time.monotonic,
        router: Any | None = None,
    ) -> None:
        self._policy = policy or AttentionPolicyConfig()
        self._presence = presence or DefaultPresenceSignal()
        self._gate = gate or AddressivityGate()
        self._clock = clock
        self._router = router

        self._state = AttentionState.SLEEPING
        self._session_id: str | None = None
        self._session_start_monotonic: float | None = None
        self._last_transition_monotonic: float = self._clock()
        self._last_wake_monotonic: float | None = None
        self._last_reply_monotonic: float | None = None
        self._last_close_reason: SessionCloseReason | None = None

        self._is_utterance_in_progress = False
        self._rejected_background_count = 0
        self._total_sessions_started = 0
        self._total_sessions_closed = 0

        self._handoff_metadata: SameBreathHandoff | None = None
        self._transitions: list[AttentionTransition] = []

        self._ready = True
        self._degraded = False
        self._error_count = 0
        self._recovery_count = 0
        self._last_error: str | None = None

        # Synchronize router to initial mode if provided
        if self._router is not None:
            self._sync_router(self._state)

    @property
    def state(self) -> AttentionState:
        return self._state

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def is_engaged(self) -> bool:
        return self._state in (AttentionState.ENGAGED, AttentionState.FOLLOWUP_WINDOW)

    @property
    def is_utterance_in_progress(self) -> bool:
        return self._is_utterance_in_progress

    @property
    def handoff_metadata(self) -> SameBreathHandoff | None:
        return self._handoff_metadata

    @property
    def presence(self) -> PresenceSignal:
        return self._presence

    @property
    def health(self) -> AttentionHealth:
        """Watchdog-visible immutable health and metrics snapshot."""
        t = self._clock()
        session_active = self.is_engaged
        session_duration = 0.0
        if session_active and self._session_start_monotonic is not None:
            session_duration = max(0.0, t - self._session_start_monotonic)

        followup_remaining_ms = None
        if self._state == AttentionState.FOLLOWUP_WINDOW and self._last_reply_monotonic is not None:
            elapsed_ms = (t - self._last_reply_monotonic) * 1000.0
            followup_remaining_ms = max(0.0, self._policy.effective_followup_window_ms - elapsed_ms)

        return AttentionHealth(
            ready=self._ready,
            state=self._state,
            session_id=self._session_id,
            session_active=session_active,
            session_duration_seconds=session_duration,
            last_transition_monotonic=self._last_transition_monotonic,
            last_wake_monotonic=self._last_wake_monotonic,
            last_reply_monotonic=self._last_reply_monotonic,
            rejected_background_count=self._rejected_background_count,
            total_sessions_started=self._total_sessions_started,
            total_sessions_closed=self._total_sessions_closed,
            last_close_reason=self._last_close_reason,
            followup_window_remaining_ms=followup_remaining_ms,
            is_utterance_in_progress=self._is_utterance_in_progress,
            degraded=self._degraded,
            error_count=self._error_count,
            recovery_count=self._recovery_count,
            last_error=self._last_error,
        )

    def _sync_router(self, state: AttentionState) -> None:
        if self._router is not None:
            try:
                self._router.set_mode(state.value.lower())
            except Exception:
                pass

    def _transition_to(self, new_state: AttentionState, reason: str, now: float) -> None:
        if self._state == new_state:
            return
        old_state = self._state
        self._state = new_state
        self._last_transition_monotonic = now
        self._transitions.append(
            AttentionTransition(
                at_monotonic=now,
                from_state=old_state,
                to_state=new_state,
                reason=reason,
                session_id=self._session_id,
            )
        )
        self._sync_router(new_state)

    def on_wake_detected(
        self,
        detection: WakeDetection,
        continuation_pcm: bytes = b"",
        same_breath_text: str | None = None,
        now: float | None = None,
    ) -> bool:
        """Process a wake word detection event.

        Canonical 'heyino' wake enters ENGAGED and starts/refreshes a session.
        Non-canonical labels are rejected.
        """
        t = self._clock() if now is None else now
        if detection.label != CANONICAL_WAKE_LABEL:
            return False

        # Entering from SLEEPING starts a brand-new session
        if self._state == AttentionState.SLEEPING:
            self._session_id = uuid.uuid4().hex
            self._session_start_monotonic = t
            self._last_wake_monotonic = t
            self._rejected_background_count = 0
            self._total_sessions_started += 1
            self._handoff_metadata = SameBreathHandoff(
                wake_detection=detection,
                continuation_pcm=continuation_pcm,
                command_text=same_breath_text,
                detected_at_monotonic=detection.detected_at_monotonic or t,
                session_id=self._session_id,
            )
            self._transition_to(AttentionState.ENGAGED, reason="wake_word_detected", now=t)
            return True

        # In FOLLOWUP_WINDOW or ENGAGED, a direct new wake reopens/refreshes engagement
        self._last_wake_monotonic = t
        self._rejected_background_count = 0
        if continuation_pcm or same_breath_text:
            self._handoff_metadata = SameBreathHandoff(
                wake_detection=detection,
                continuation_pcm=continuation_pcm,
                command_text=same_breath_text,
                detected_at_monotonic=detection.detected_at_monotonic or t,
                session_id=self._session_id or "",
            )
        if self._state != AttentionState.ENGAGED:
            self._transition_to(AttentionState.ENGAGED, reason="wake_word_refresh", now=t)
        return True

    def on_reply_completed(self, now: float | None = None) -> bool:
        """Signal completion of an assistant reply.

        Transitions ENGAGED -> FOLLOWUP_WINDOW. Safe and idempotent if not ENGAGED.
        """
        t = self._clock() if now is None else now
        if self._state == AttentionState.ENGAGED:
            self._last_reply_monotonic = t
            self._rejected_background_count = 0
            self._transition_to(AttentionState.FOLLOWUP_WINDOW, reason="reply_completed", now=t)
            return True
        return False

    def on_utterance_start(self, now: float | None = None) -> bool:
        """Signal start of speaker speech.

        Rejects speech if SLEEPING or if follow-up window already expired.
        Guarantees that once speech starts, the session does not close mid-utterance.
        """
        t = self._clock() if now is None else now
        if self._state == AttentionState.SLEEPING:
            return False

        # If in follow-up window, verify deadline hasn't elapsed prior to speech start
        if self._state == AttentionState.FOLLOWUP_WINDOW:
            if self._last_reply_monotonic is not None:
                elapsed = t - self._last_reply_monotonic
                if elapsed >= self._policy.effective_followup_window_seconds:
                    self._close_session(SessionCloseReason.FOLLOWUP_TIMEOUT, now=t)
                    return False

        # Check if max session duration expired prior to speech start
        if self._session_start_monotonic is not None:
            elapsed = t - self._session_start_monotonic
            if elapsed >= self._policy.max_session_duration_seconds:
                self._close_session(SessionCloseReason.MAX_SESSION_DURATION, now=t)
                return False

        self._is_utterance_in_progress = True
        return True

    def on_utterance_end(
        self,
        text: str = "",
        now: float | None = None,
    ) -> AddressivityDecision | None:
        """Signal end of speaker speech and evaluate addressivity.

        Evaluates addressivity in FOLLOWUP_WINDOW; directed speech refreshes engagement,
        while ambiguous speech is counted and closes the session on limit.
        """
        t = self._clock() if now is None else now
        self._is_utterance_in_progress = False

        if self._state == AttentionState.SLEEPING:
            return None

        presence_state = self._presence.get_presence_state()

        if self._state == AttentionState.FOLLOWUP_WINDOW:
            decision = self._gate.evaluate(
                text=text,
                expecting_reply=True,
                presence=presence_state,
            )
            if decision.is_directed:
                # Directed follow-up accepted: reopens engagement
                self._rejected_background_count = 0
                self._transition_to(
                    AttentionState.ENGAGED,
                    reason=f"directed_followup:{decision.verdict.value}",
                    now=t,
                )
                return decision

            # Ambiguous / background speech rejected and counted
            self._rejected_background_count += 1
            if self._rejected_background_count >= self._policy.rejected_background_limit:
                self._close_session(SessionCloseReason.REJECTED_BACKGROUND, now=t)
            else:
                # If background speech didn't trip the limit, check if window expired during speech
                if self._last_reply_monotonic is not None:
                    elapsed = t - self._last_reply_monotonic
                    if elapsed >= self._policy.effective_followup_window_seconds:
                        self._close_session(SessionCloseReason.FOLLOWUP_TIMEOUT, now=t)
            return decision

        if self._state == AttentionState.ENGAGED:
            decision = self._gate.evaluate(
                text=text,
                expecting_reply=False,
                presence=presence_state,
            )
            if self._session_start_monotonic is not None:
                elapsed = t - self._session_start_monotonic
                if elapsed >= self._policy.max_session_duration_seconds:
                    self._close_session(SessionCloseReason.MAX_SESSION_DURATION, now=t)
            return decision

        return None

    def check_timeouts(self, now: float | None = None) -> SessionCloseReason | None:
        """Check follow-up and max session timers without background threads.

        Guarantees that active sessions do NOT close mid-utterance.
        """
        t = self._clock() if now is None else now
        if self._is_utterance_in_progress:
            return None

        # Check max session duration
        if self.is_engaged and self._session_start_monotonic is not None:
            elapsed = t - self._session_start_monotonic
            if elapsed >= self._policy.max_session_duration_seconds:
                self._close_session(SessionCloseReason.MAX_SESSION_DURATION, now=t)
                return SessionCloseReason.MAX_SESSION_DURATION

        # Check follow-up window expiration
        if self._state == AttentionState.FOLLOWUP_WINDOW and self._last_reply_monotonic is not None:
            elapsed = t - self._last_reply_monotonic
            if elapsed >= self._policy.effective_followup_window_seconds:
                self._close_session(SessionCloseReason.FOLLOWUP_TIMEOUT, now=t)
                return SessionCloseReason.FOLLOWUP_TIMEOUT

        return None

    def _close_session(self, reason: SessionCloseReason, now: float) -> None:
        if self._state == AttentionState.SLEEPING:
            return
        self._last_close_reason = reason
        self._total_sessions_closed += 1
        self._session_id = None
        self._session_start_monotonic = None
        self._handoff_metadata = None
        self._is_utterance_in_progress = False
        self._transition_to(
            AttentionState.SLEEPING,
            reason=f"session_closed:{reason.value}",
            now=now,
        )

    def dismiss(
        self,
        reason: SessionCloseReason = SessionCloseReason.EXPLICIT_DISMISS,
    ) -> None:
        """Explicitly dismiss attention session."""
        t = self._clock()
        self._close_session(reason=reason, now=t)

    def reset(self) -> None:
        """Watchdog recovery/reset method. Idempotent and clears prior session data."""
        t = self._clock()
        if self._state != AttentionState.SLEEPING:
            self._close_session(SessionCloseReason.RESET, now=t)
        self._handoff_metadata = None
        self._session_id = None
        self._session_start_monotonic = None
        self._rejected_background_count = 0
        self._is_utterance_in_progress = False
        self._degraded = False
        self._last_error = None
        self._ready = True

    def recovery_reset(self, error: str | None = None) -> None:
        """Recovery reset for failures, recording degraded status for watchdogs."""
        t = self._clock()
        if self._state != AttentionState.SLEEPING:
            self._close_session(SessionCloseReason.ERROR, now=t)
        self._error_count += 1
        self._recovery_count += 1
        self._last_error = error
        self._degraded = True
        self._handoff_metadata = None
        self._session_id = None
        self._session_start_monotonic = None
        self._rejected_background_count = 0
        self._is_utterance_in_progress = False
        self._ready = True

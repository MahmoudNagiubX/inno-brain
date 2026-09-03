from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from .state import ConversationState, ConversationStateMachine

ThinkingCancellationCallback = Callable[[], Awaitable[None]]


class CancelablePlayback(Protocol):
    async def cancel(self) -> None: ...


@dataclass(frozen=True, slots=True)
class InterruptionResult:
    interrupted: bool
    prior_state: ConversationState
    event_to_playback_stop_ms: float | None


class InterruptionController:
    def __init__(
        self,
        machine: ConversationStateMachine,
        playback: CancelablePlayback,
        thinking_cancel_callback: ThinkingCancellationCallback | None = None,
        response_cancel_callback: ThinkingCancellationCallback | None = None,
    ) -> None:
        self._machine = machine
        self._playback = playback
        self._response_cancel_callback = response_cancel_callback or thinking_cancel_callback

    async def handle_user_turn_started(self) -> InterruptionResult:
        prior_state = self._machine.state
        started_at = perf_counter()

        if prior_state is ConversationState.SPEAKING:
            self._machine.transition(ConversationState.INTERRUPTED, "user_barge_in")
            try:
                await self._playback.cancel()
                elapsed_ms = (perf_counter() - started_at) * 1000.0
                if self._response_cancel_callback is not None:
                    await self._response_cancel_callback()
                return InterruptionResult(True, prior_state, elapsed_ms)
            finally:
                if self._machine.state is not ConversationState.LISTENING:
                    self._machine.transition(
                        ConversationState.LISTENING,
                        "interruption_handled",
                    )

        if prior_state is ConversationState.THINKING:
            self._machine.transition(ConversationState.INTERRUPTED, "user_barge_in")
            try:
                if self._response_cancel_callback is not None:
                    await self._response_cancel_callback()
                return InterruptionResult(True, prior_state, None)
            finally:
                if self._machine.state is not ConversationState.LISTENING:
                    self._machine.transition(
                        ConversationState.LISTENING,
                        "interruption_handled",
                    )

        return InterruptionResult(False, prior_state, None)

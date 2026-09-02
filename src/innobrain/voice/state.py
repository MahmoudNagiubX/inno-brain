from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter


class ConversationState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True, slots=True)
class StateTransition:
    at_monotonic: float
    from_state: ConversationState
    to_state: ConversationState
    reason: str


class InvalidStateTransition(RuntimeError):
    pass


_ALLOWED: dict[ConversationState, set[ConversationState]] = {
    ConversationState.IDLE: {ConversationState.LISTENING},
    ConversationState.LISTENING: {ConversationState.IDLE, ConversationState.THINKING},
    ConversationState.THINKING: {
        ConversationState.IDLE,
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
    },
    ConversationState.SPEAKING: {
        ConversationState.IDLE,
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
    },
    ConversationState.INTERRUPTED: {ConversationState.IDLE, ConversationState.LISTENING},
}


class ConversationStateMachine:
    def __init__(self) -> None:
        self._state = ConversationState.IDLE
        self._history: list[StateTransition] = []

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def history(self) -> tuple[StateTransition, ...]:
        return tuple(self._history)

    def transition(self, to_state: ConversationState, reason: str) -> StateTransition:
        if to_state not in _ALLOWED[self._state]:
            raise InvalidStateTransition(
                f"Invalid transition {self._state.value} -> {to_state.value}: {reason}"
            )

        transition = StateTransition(
            at_monotonic=perf_counter(),
            from_state=self._state,
            to_state=to_state,
            reason=reason,
        )
        self._state = to_state
        self._history.append(transition)
        return transition

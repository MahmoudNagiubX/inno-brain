import pytest

from innobrain.voice.state import (
    ConversationState,
    ConversationStateMachine,
    InvalidStateTransition,
)


def test_normal_turn_state_cycle() -> None:
    machine = ConversationStateMachine()

    machine.transition(ConversationState.LISTENING, "runtime_started")
    machine.transition(ConversationState.THINKING, "user_turn_complete")
    machine.transition(ConversationState.SPEAKING, "response_playback_started")
    machine.transition(ConversationState.LISTENING, "response_playback_finished")

    assert machine.state is ConversationState.LISTENING
    assert [item.to_state for item in machine.history] == [
        ConversationState.LISTENING,
        ConversationState.THINKING,
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
    ]


def test_speaking_can_be_interrupted() -> None:
    machine = ConversationStateMachine()
    machine.transition(ConversationState.LISTENING, "runtime_started")
    machine.transition(ConversationState.THINKING, "user_turn_complete")
    machine.transition(ConversationState.SPEAKING, "response_started")
    machine.transition(ConversationState.INTERRUPTED, "user_barge_in")
    machine.transition(ConversationState.LISTENING, "interruption_handled")

    assert machine.state is ConversationState.LISTENING


def test_invalid_transition_is_rejected() -> None:
    machine = ConversationStateMachine()

    with pytest.raises(InvalidStateTransition):
        machine.transition(ConversationState.SPEAKING, "invalid")

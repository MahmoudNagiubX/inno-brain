import pytest

from innobrain.voice.interruption import InterruptionController
from innobrain.voice.state import ConversationState, ConversationStateMachine


class FakePlayback:
    def __init__(self) -> None:
        self.cancel_calls = 0

    async def cancel(self) -> None:
        self.cancel_calls += 1


def speaking_machine() -> ConversationStateMachine:
    machine = ConversationStateMachine()
    machine.transition(ConversationState.LISTENING, "runtime_started")
    machine.transition(ConversationState.THINKING, "user_turn_complete")
    machine.transition(ConversationState.SPEAKING, "response_started")
    return machine


@pytest.mark.asyncio
async def test_speaking_interruption_stops_playback_and_recovers() -> None:
    machine = speaking_machine()
    playback = FakePlayback()
    controller = InterruptionController(machine, playback)

    result = await controller.handle_user_turn_started()

    assert result.interrupted is True
    assert result.prior_state is ConversationState.SPEAKING
    assert result.event_to_playback_stop_ms is not None
    assert playback.cancel_calls == 1
    assert machine.state is ConversationState.LISTENING
    assert [item.to_state for item in machine.history[-2:]] == [
        ConversationState.INTERRUPTED,
        ConversationState.LISTENING,
    ]


@pytest.mark.asyncio
async def test_listening_speech_is_not_an_interruption() -> None:
    machine = ConversationStateMachine()
    machine.transition(ConversationState.LISTENING, "runtime_started")
    playback = FakePlayback()
    controller = InterruptionController(machine, playback)

    result = await controller.handle_user_turn_started()

    assert result.interrupted is False
    assert result.prior_state is ConversationState.LISTENING
    assert result.event_to_playback_stop_ms is None
    assert playback.cancel_calls == 0
    assert machine.state is ConversationState.LISTENING

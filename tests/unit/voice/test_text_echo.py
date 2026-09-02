import pytest

from innobrain.voice.state import ConversationState, ConversationStateMachine
from innobrain.voice.text_echo import echo_text_once


@pytest.mark.asyncio
async def test_echo_text_uses_one_normal_turn_state_cycle() -> None:
    machine = ConversationStateMachine()
    machine.transition(ConversationState.LISTENING, "runtime_started")

    result = await echo_text_once("الـsession الساعة كام؟", machine)

    assert result == "ECHO: الـsession الساعة كام؟"
    assert machine.state is ConversationState.LISTENING
    assert [item.to_state for item in machine.history] == [
        ConversationState.LISTENING,
        ConversationState.THINKING,
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
    ]

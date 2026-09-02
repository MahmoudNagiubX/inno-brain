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
async def test_speaking_interruption_stops_playback_before_cancelling_response() -> None:
    machine = speaking_machine()
    playback = FakePlayback()
    calls = []

    async def cancel_response() -> None:
        calls.append("response")

    original_cancel = playback.cancel

    async def cancel_playback() -> None:
        calls.append("playback")
        await original_cancel()

    playback.cancel = cancel_playback
    controller = InterruptionController(
        machine,
        playback,
        response_cancel_callback=cancel_response,
    )

    await controller.handle_user_turn_started()

    assert calls == ["playback", "response"]


@pytest.mark.asyncio
async def test_slow_remote_cancellation_cannot_delay_local_playback_stop() -> None:
    import asyncio

    machine = speaking_machine()
    playback = FakePlayback()
    remote_started = asyncio.Event()
    release_remote = asyncio.Event()
    calls = []

    async def cancel_response() -> None:
        calls.append("remote_started")
        remote_started.set()
        await release_remote.wait()
        calls.append("remote_finished")

    async def cancel_playback() -> None:
        calls.append("playback")
        await FakePlayback.cancel(playback)

    playback.cancel = cancel_playback
    controller = InterruptionController(
        machine,
        playback,
        response_cancel_callback=cancel_response,
    )

    task = asyncio.create_task(controller.handle_user_turn_started())
    await asyncio.wait_for(remote_started.wait(), timeout=0.1)

    assert calls[:2] == ["playback", "remote_started"]
    assert playback.cancel_calls == 1

    release_remote.set()
    await task


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

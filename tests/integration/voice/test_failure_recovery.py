import asyncio
from pathlib import Path

import pytest

from innobrain.config import load_all_configs
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import AnswerRoute, BrainResult
from innobrain.providers import AudioChunk, TranscriptEvent
from innobrain.telemetry.runtime_events import RuntimeFault
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.state import ConversationState
from innobrain.voice.turn_events import TurnEvent, TurnEventType

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class RecordingSink:
    def __init__(self):
        self.faults: list[RuntimeFault] = []

    def fault(self, fault: RuntimeFault) -> None:
        self.faults.append(fault)


class FakeTurnRuntime:
    def __init__(self):
        self.stop_calls = 0

    async def start(self):
        return None

    async def stop(self):
        self.stop_calls += 1


class FakeSTT:
    def __init__(self, *, final_error=None):
        self.final_error = final_error
        self.stop_calls = 0

    async def start(self):
        return None

    async def begin_turn(self, _turn_id):
        return None

    async def stream_audio(self, _pcm):
        return None

    async def partial_text(self):
        return None

    async def final_text(self, turn_id=None):
        if self.final_error:
            raise self.final_error
        return TranscriptEvent("سؤال", True, turn_id=turn_id)

    async def stop(self):
        self.stop_calls += 1


class FakeOrchestrator:
    def __init__(self):
        self.memory = SessionMemory()
        self.cancel_calls = 0
        self.commits = []

    async def answer(self, _text):
        return BrainResult("إجابة واضحة.", AnswerRoute.RAG_DEGRADED, (), None)

    async def cancel(self):
        self.cancel_calls += 1

    def commit_delivered(self, user_text, result):
        self.commits.append((user_text, result))


class FailingTTS:
    def __init__(self):
        self.cancel_calls = 0

    def stream(self, _text):
        async def chunks():
            yield AudioChunk(b"first", 16000)
            raise RuntimeError("synthesis failed")

        return chunks()

    async def cancel(self):
        self.cancel_calls += 1


class RecordingPlayback:
    def __init__(self):
        self.calls = []

    async def start(self, sample_rate_hz):
        self.calls.append(("start", sample_rate_hz))

    async def write(self, pcm):
        self.calls.append(("write", pcm))

    async def finish(self):
        self.calls.append(("finish",))

    async def cancel(self):
        self.calls.append(("cancel",))


class ExplodingPlayback(RecordingPlayback):
    def __init__(self, cancel_error=None):
        super().__init__()
        self.cancel_error = cancel_error or RuntimeError("speaker cleanup failed")

    async def cancel(self):
        await super().cancel()
        raise self.cancel_error


class ExplodingCancelOrchestrator(FakeOrchestrator):
    async def cancel(self):
        await super().cancel()
        raise RuntimeError("llm cancel failed")


class ExplodingCancelTTS(FailingTTS):
    async def cancel(self):
        await super().cancel()
        raise RuntimeError("tts cancel failed")


def build_runtime(*, stt=None, sink=None, orchestrator=None, tts=None, playback=None):
    orchestrator = orchestrator or FakeOrchestrator()
    tts = tts or FailingTTS()
    playback = playback or RecordingPlayback()
    turn_runtime = FakeTurnRuntime()
    runtime = VoiceBrainRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stt=stt or FakeSTT(),
        orchestrator=orchestrator,
        tts=tts,
        playback=playback,
        turn_runtime=turn_runtime,
        event_sink=sink or RecordingSink(),
    )
    return runtime, orchestrator, tts, playback, turn_runtime


@pytest.mark.asyncio
async def test_tts_failure_after_first_pcm_recovers_and_never_returns_stale_result():
    sink = RecordingSink()
    runtime, orchestrator, tts, playback, _ = build_runtime(sink=sink)
    runtime.last_result = BrainResult("قديم", AnswerRoute.EXACT, (), None)

    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is None
    assert runtime.last_result.text == "قديم"
    assert runtime.machine.state is ConversationState.LISTENING
    assert playback.calls[-1] == ("cancel",)
    assert tts.cancel_calls == 1
    assert orchestrator.cancel_calls == 1
    assert orchestrator.commits == []
    assert [(fault.stage, fault.turn_id) for fault in sink.faults] == [("tts", 1)]


@pytest.mark.asyncio
async def test_final_transcript_failure_is_observed_and_recovers_to_listening():
    sink = RecordingSink()
    runtime, _, _, playback, _ = build_runtime(
        stt=FakeSTT(final_error=RuntimeError("final failed")),
        sink=sink,
    )

    await runtime.handle_user_turn_started()
    await runtime._on_turn_event(
        TurnEvent.now(TurnEventType.USER_TURN_STOPPED, "test-smart-turn")
    )
    while runtime._turn_task is not None:
        await asyncio.sleep(0)

    assert runtime.machine.state is ConversationState.LISTENING
    assert playback.calls[-1] == ("cancel",)
    assert [(fault.stage, fault.turn_id) for fault in sink.faults] == [("stt_final", 1)]


@pytest.mark.asyncio
@pytest.mark.parametrize("active_state", [ConversationState.THINKING, ConversationState.SPEAKING])
async def test_shutdown_from_active_response_state_is_clean_and_idempotent(active_state):
    runtime, orchestrator, tts, playback, turn_runtime = build_runtime()
    runtime.machine.transition(ConversationState.LISTENING, "test")
    runtime.machine.transition(ConversationState.THINKING, "test")
    if active_state is ConversationState.SPEAKING:
        runtime.machine.transition(ConversationState.SPEAKING, "test")

    await runtime.stop()
    await runtime.stop()

    assert runtime.machine.state is ConversationState.IDLE
    assert playback.calls.count(("cancel",)) >= 1
    assert orchestrator.cancel_calls >= 1
    assert tts.cancel_calls >= 1
    assert turn_runtime.stop_calls == 1


@pytest.mark.asyncio
async def test_tts_failure_with_playback_cancel_exception_recovers_to_listening():
    sink = RecordingSink()
    playback = ExplodingPlayback()
    runtime, orchestrator, tts, _, _ = build_runtime(sink=sink, playback=playback)
    runtime.last_result = BrainResult("قديم", AnswerRoute.EXACT, (), None)

    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is None
    assert runtime.last_result.text == "قديم"
    assert runtime.machine.state is ConversationState.LISTENING
    assert orchestrator.commits == []
    assert playback.calls[-1] == ("cancel",)
    assert tts.cancel_calls == 1
    assert orchestrator.cancel_calls == 1
    assert [(fault.stage, fault.turn_id) for fault in sink.faults] == [
        ("tts", 1),
        ("tts.playback_cleanup", 1),
    ]


@pytest.mark.asyncio
async def test_tts_failure_with_provider_cancel_exception_recovers_to_listening():
    sink = RecordingSink()
    orchestrator = ExplodingCancelOrchestrator()
    tts = ExplodingCancelTTS()
    playback = RecordingPlayback()
    runtime, _, _, _, _ = build_runtime(
        sink=sink,
        orchestrator=orchestrator,
        tts=tts,
        playback=playback,
    )

    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is None
    assert runtime.machine.state is ConversationState.LISTENING
    assert orchestrator.commits == []
    assert playback.calls[-1] == ("cancel",)
    assert orchestrator.cancel_calls == 1
    assert tts.cancel_calls == 1
    fault_stages = [fault.stage for fault in sink.faults]
    assert fault_stages[0] == "tts"
    assert "tts.provider_cleanup" in fault_stages[1:]
    assert all(fault.turn_id == 1 for fault in sink.faults)


@pytest.mark.asyncio
async def test_tts_failure_with_playback_and_provider_cancel_exceptions():
    sink = RecordingSink()
    orchestrator = ExplodingCancelOrchestrator()
    tts = ExplodingCancelTTS()
    playback = ExplodingPlayback()
    runtime, _, _, _, _ = build_runtime(
        sink=sink,
        orchestrator=orchestrator,
        tts=tts,
        playback=playback,
    )

    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is None
    assert runtime.machine.state is ConversationState.LISTENING
    assert orchestrator.commits == []
    assert playback.calls[-1] == ("cancel",)
    assert orchestrator.cancel_calls == 1
    assert tts.cancel_calls == 1
    assert sink.faults[0].stage == "tts"
    cleanup_stages = [fault.stage for fault in sink.faults[1:]]
    assert "tts.playback_cleanup" in cleanup_stages
    assert "tts.provider_cleanup" in cleanup_stages

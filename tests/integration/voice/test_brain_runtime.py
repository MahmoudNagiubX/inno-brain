from pathlib import Path

import pytest

from innobrain.config import load_all_configs
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import AnswerRoute, BrainResult
from innobrain.providers import AudioChunk, TranscriptEvent
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.state import ConversationState

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class FakeStream:
    def start(self):
        return None

    def stop(self):
        return None

    async def chunks(self):
        if False:
            yield b""


class FakeSTT:
    name = "fake-stt"

    def __init__(self):
        self.begun = []
        self.finalized = []

    async def start(self):
        return None

    async def stop(self):
        return None

    async def stream_audio(self, pcm):
        return None

    async def begin_turn(self, turn_id):
        self.begun.append(turn_id)

    async def final_text(self, turn_id=None):
        self.finalized.append(turn_id)
        return TranscriptEvent("Future of AI", True, turn_id=turn_id)


class FakeOrchestrator:
    def __init__(self):
        self.memory = SessionMemory()
        self.committed = []

    async def answer(self, text):
        return BrainResult("رد واضح.", AnswerRoute.RAG_DEGRADED, ("chunk:1",), None)

    def commit_delivered(self, text, result):
        self.committed.append((text, result.text))
        self.memory.add_turn(text, result.text)


class FakeTTS:
    name = "fake-tts"

    async def cancel(self):
        return None

    def stream(self, text):
        async def chunks():
            yield AudioChunk(b"pcm", 16000, 1)

        return chunks()


class FakePlayback:
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


class CollectingSink:
    def __init__(self):
        self.events = []
        self.faults = []

    def emit(self, observation):
        self.events.append(observation)

    def fault(self, fault):
        self.faults.append(fault)


@pytest.mark.asyncio
async def test_voice_brain_runtime_completes_synthetic_turn_and_interruption():
    config = load_all_configs(REPOSITORY_ROOT).runtime
    machine = None
    orchestrator = FakeOrchestrator()
    playback = FakePlayback()
    stt = FakeSTT()
    runtime = VoiceBrainRuntime(
        config,
        stt=stt,
        orchestrator=orchestrator,
        tts=FakeTTS(),
        playback=playback,
        stream=FakeStream(),
        machine=machine,
    )
    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is not None
    assert runtime.machine.state is ConversationState.LISTENING


@pytest.mark.asyncio
async def test_missing_tts_keeps_text_result_available_without_committing_undelivered_voice():
    orchestrator = FakeOrchestrator()
    stt = FakeSTT()
    runtime = VoiceBrainRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stt=stt,
        orchestrator=orchestrator,
        tts=None,
        playback=FakePlayback(),
        stream=FakeStream(),
    )

    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is not None
    assert runtime.last_result is result
    assert orchestrator.committed == []
    assert runtime.machine.state is ConversationState.LISTENING


@pytest.mark.asyncio
async def test_synthetic_turn_emits_required_provider_route_state_and_timing_events():
    sink = CollectingSink()
    stt = FakeSTT()
    orchestrator = FakeOrchestrator()
    playback = FakePlayback()
    runtime = VoiceBrainRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stt=stt,
        orchestrator=orchestrator,
        tts=FakeTTS(),
        playback=playback,
        stream=FakeStream(),
        event_sink=sink,
    )

    await runtime.handle_user_turn_started()
    await runtime.handle_user_turn_stopped()

    by_name = {item.event: item for item in sink.events}
    assert {
        "turn_started",
        "speech_stop",
        "stt_final",
        "brain_complete",
        "tts_first_pcm",
        "playback_stop",
    }.issubset(by_name)
    assert by_name["stt_final"].transcript_final_received is True
    assert by_name["brain_complete"].answer_route == "rag_degraded"
    assert by_name["brain_complete"].evidence_count == 1
    assert by_name["turn_started"].stt_provider == "fake-stt"
    assert by_name["tts_first_pcm"].tts_provider == "fake-tts"
    assert all(item.turn_id == 1 for item in sink.events)
    assert all(item.conversation_state for item in sink.events)
    assert playback.calls == [("start", 16000), ("write", b"pcm"), ("finish",)]
    assert orchestrator.committed == [("Future of AI", "رد واضح.")]
    assert stt.begun == [1]
    assert stt.finalized == [1]

    runtime.machine.transition(ConversationState.THINKING, "test_thinking")
    interruption = await runtime.interruption.handle_user_turn_started()
    assert interruption.interrupted is True
    assert runtime.machine.state is ConversationState.LISTENING


@pytest.mark.asyncio
async def test_voice_runtime_owns_monotonic_turn_ids_and_stop_without_start_is_safe():
    config = load_all_configs(REPOSITORY_ROOT).runtime
    stt = FakeSTT()
    runtime = VoiceBrainRuntime(
        config,
        stt=stt,
        orchestrator=FakeOrchestrator(),
        tts=FakeTTS(),
        playback=FakePlayback(),
        stream=FakeStream(),
    )

    assert await runtime.handle_user_turn_stopped() is None
    await runtime.handle_user_turn_started()
    await runtime.handle_user_turn_stopped()
    await runtime.handle_user_turn_started()
    await runtime.handle_user_turn_stopped()

    assert stt.begun == [1, 2]
    assert stt.finalized == [1, 2]
    assert runtime.active_turn_id is None


@pytest.mark.asyncio
async def test_voice_runtime_rejects_stale_transcript_from_prior_turn():
    class StaleSTT(FakeSTT):
        async def final_text(self, turn_id=None):
            self.finalized.append(turn_id)
            return TranscriptEvent("قديم", True, turn_id=turn_id - 1)

    config = load_all_configs(REPOSITORY_ROOT).runtime
    orchestrator = FakeOrchestrator()
    runtime = VoiceBrainRuntime(
        config,
        stt=StaleSTT(),
        orchestrator=orchestrator,
        tts=FakeTTS(),
        playback=FakePlayback(),
        stream=FakeStream(),
    )

    await runtime.handle_user_turn_started()
    result = await runtime.handle_user_turn_stopped()

    assert result is None
    assert orchestrator.committed == []
    assert runtime.machine.state is ConversationState.LISTENING

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
    async def start(self):
        return None

    async def stop(self):
        return None

    async def stream_audio(self, pcm):
        return None

    async def final_text(self):
        return TranscriptEvent("Future of AI", True)


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


@pytest.mark.asyncio
async def test_voice_brain_runtime_completes_synthetic_turn_and_interruption():
    config = load_all_configs(REPOSITORY_ROOT).runtime
    machine = None
    orchestrator = FakeOrchestrator()
    playback = FakePlayback()
    runtime = VoiceBrainRuntime(
        config,
        stt=FakeSTT(),
        orchestrator=orchestrator,
        tts=FakeTTS(),
        playback=playback,
        stream=FakeStream(),
        machine=machine,
    )
    result = await runtime.handle_user_turn_stopped()

    assert result is not None
    assert runtime.machine.state is ConversationState.LISTENING
    assert playback.calls == [("start", 16000), ("write", b"pcm"), ("finish",)]
    assert orchestrator.committed == [("Future of AI", "رد واضح.")]

    runtime.machine.transition(ConversationState.THINKING, "test_thinking")
    interruption = await runtime.interruption.handle_user_turn_started()
    assert interruption.interrupted is True
    assert runtime.machine.state is ConversationState.LISTENING

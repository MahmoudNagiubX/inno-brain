import asyncio
from pathlib import Path
from time import perf_counter

import pytest

from innobrain.config import load_all_configs
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import AnswerRoute, BrainResult
from innobrain.providers import AudioChunk
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.state import ConversationState

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class NullStream:
    def start(self):
        return None

    def stop(self):
        return None

    async def chunks(self):
        if False:
            yield b""


class NullSTT:
    async def start(self):
        return None

    async def begin_turn(self, turn_id):
        return None

    async def stream_audio(self, pcm):
        return None

    async def partial_text(self):
        return None

    async def final_text(self, turn_id=None):
        raise AssertionError("not used")

    async def stop(self):
        return None


class SlowCancelable:
    def __init__(self, calls, name):
        self.calls = calls
        self.name = name

    async def cancel(self):
        self.calls.append(f"{self.name}_started")
        await asyncio.sleep(0.5)
        self.calls.append(f"{self.name}_finished")


class CancelableOrchestrator(SlowCancelable):
    def __init__(self, calls):
        super().__init__(calls, "llm")
        self.memory = SessionMemory()


class RecordingPlayback:
    def __init__(self, calls):
        self.calls = calls

    async def cancel(self):
        self.calls.append("playback")


class StreamingPlayback(RecordingPlayback):
    def __init__(self, calls):
        super().__init__(calls)
        self.first_write = asyncio.Event()
        self.cancelled = False

    async def start(self, sample_rate_hz):
        self.calls.append(("start", sample_rate_hz))

    async def write(self, pcm):
        if self.cancelled:
            raise AssertionError("PCM write occurred after playback cancellation")
        self.calls.append(("write", pcm))
        self.first_write.set()

    async def finish(self):
        self.calls.append("finish")

    async def cancel(self):
        self.cancelled = True
        await super().cancel()


class ResponseOrchestrator:
    def __init__(self):
        self.memory = SessionMemory()
        self.cancel_calls = 0

    async def answer(self, _text):
        return BrainResult("جملة أولى. جملة ثانية.", AnswerRoute.RAG_DEGRADED, (), None)

    async def cancel(self):
        self.cancel_calls += 1

    def commit_delivered(self, *_args):
        raise AssertionError("an interrupted response must not commit memory")


class PausingTTS:
    def __init__(self):
        self.release = asyncio.Event()
        self.cancel_calls = 0

    def stream(self, _text):
        async def chunks():
            yield AudioChunk(b"first", 16000)
            await self.release.wait()
            yield AudioChunk(b"late", 16000)

        return chunks()

    async def cancel(self):
        self.cancel_calls += 1
        self.release.set()


@pytest.mark.asyncio
async def test_barge_in_stops_playback_then_bounds_llm_and_tts_cancellation():
    calls = []
    runtime = VoiceBrainRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stt=NullSTT(),
        orchestrator=CancelableOrchestrator(calls),
        tts=SlowCancelable(calls, "tts"),
        playback=RecordingPlayback(calls),
        stream=NullStream(),
    )
    runtime.machine.transition(ConversationState.LISTENING, "test")
    runtime.machine.transition(ConversationState.THINKING, "test")
    runtime.machine.transition(ConversationState.SPEAKING, "test")

    started = perf_counter()
    result = await runtime.interruption.handle_user_turn_started()
    elapsed = perf_counter() - started

    assert result.interrupted is True
    assert calls[0] == "playback"
    assert set(calls[1:]) == {"llm_started", "tts_started"}
    assert elapsed < 0.45
    assert runtime.machine.state is ConversationState.LISTENING


@pytest.mark.asyncio
async def test_barge_in_prevents_pcm_write_after_playback_cancel() -> None:
    calls = []
    playback = StreamingPlayback(calls)
    orchestrator = ResponseOrchestrator()
    tts = PausingTTS()
    runtime = VoiceBrainRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stt=NullSTT(),
        orchestrator=orchestrator,
        tts=tts,
        playback=playback,
        stream=NullStream(),
    )
    runtime.machine.transition(ConversationState.LISTENING, "test")
    runtime.machine.transition(ConversationState.THINKING, "test")
    runtime._response_task = asyncio.create_task(runtime._respond("سؤال"))
    await asyncio.wait_for(playback.first_write.wait(), timeout=0.5)

    await runtime.interruption.handle_user_turn_started()

    assert ("write", b"late") not in calls
    assert calls.index("playback") > calls.index(("write", b"first"))
    assert orchestrator.cancel_calls == 1
    assert tts.cancel_calls == 1
    assert runtime.machine.state is ConversationState.LISTENING

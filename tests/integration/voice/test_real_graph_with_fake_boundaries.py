from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from innobrain.app import build_application
from innobrain.config import load_all_configs
from innobrain.conversation.knowledge_binding import ActiveKnowledgeBinding
from innobrain.conversation.orchestrator import AnswerRoute, GroundedOrchestrator
from innobrain.event.registry import InstalledEventRecord
from innobrain.event.runtime import open_runtime_context
from innobrain.knowledge.retrieval import HybridRetriever
from innobrain.knowledge.structured_resolver import StructuredResolver
from innobrain.providers import AudioChunk, TranscriptEvent
from innobrain.providers.registry import ProviderBundle
from innobrain.providers.stt_failover import FailoverSTTProvider
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.pipecat_runtime import RealtimeTurnRuntime
from innobrain.voice.state import ConversationState
from scripts.phase3.build_demo_db import build_demo_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class FakeSTTEdge:
    def __init__(self, name: str, transcripts: list[str], *, fail_final: bool = False) -> None:
        self.name = name
        self.transcripts = transcripts
        self.fail_final = fail_final
        self.audio = []
        self.turn_id = None
        self.cancelled = False

    async def start(self) -> None:
        return None

    async def begin_turn(self, turn_id: int) -> None:
        self.turn_id = turn_id

    async def stream_audio(self, pcm: bytes) -> None:
        self.audio.append(pcm)

    async def partial_text(self):
        return None

    async def final_text(self, turn_id: int | None = None) -> TranscriptEvent:
        if self.fail_final:
            self.fail_final = False
            raise RuntimeError("synthetic final failure")
        return TranscriptEvent(self.transcripts.pop(0), True, turn_id=turn_id)

    async def stop(self) -> None:
        return None


class FakeLLMEdge:
    name = "fake-groq-edge"

    def __init__(self) -> None:
        self.cancel_calls = 0

    def stream(self, messages, tools, context):
        async def chunks():
            yield "fallback"

        return chunks()

    async def cancel(self) -> None:
        self.cancel_calls += 1


class FakeTTSEdge:
    name = "fake-azure-edge"

    def __init__(self) -> None:
        self.cancel_calls = 0
        self.texts = []

    def stream(self, text: str) -> AsyncIterator[AudioChunk]:
        self.texts.append(text)

        async def chunks():
            yield AudioChunk(b"voice-pcm", 16000)

        return chunks()

    async def cancel(self) -> None:
        self.cancel_calls += 1


class FakeAudioEdge:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    async def chunks(self):
        if False:
            yield b""


class FakePlaybackEdge:
    def __init__(self) -> None:
        self.calls = []

    async def start(self, sample_rate_hz: int) -> None:
        self.calls.append(("start", sample_rate_hz))

    async def write(self, pcm: bytes) -> None:
        self.calls.append(("write", pcm))

    async def finish(self) -> None:
        self.calls.append(("finish",))

    async def cancel(self) -> None:
        self.calls.append(("cancel",))


def _event_context(tmp_path: Path):
    database_path = build_demo_db(
        REPOSITORY_ROOT / "fixtures" / "phase3" / "demo_event.yaml",
        tmp_path / "event.sqlite3",
    )
    record = InstalledEventRecord(
        "demo-2026",
        "1.0.0",
        "a" * 64,
        tmp_path,
        database_path,
        {"chunks": 1, "fts": 1, "vec": 1, "embedding_rows": 1},
    )
    return open_runtime_context(record)


def _build_graph(tmp_path: Path, primary: FakeSTTEdge, fallback: FakeSTTEdge):
    llm = FakeLLMEdge()
    tts = FakeTTSEdge()
    playback = FakePlaybackEdge()
    providers = ProviderBundle(FailoverSTTProvider(primary, fallback), llm, tts)
    app = build_application(
        config=load_all_configs(REPOSITORY_ROOT),
        provider_bundle=providers,
        event_context=_event_context(tmp_path),
        stream=FakeAudioEdge(),
        playback=playback,
    )
    return app, llm, tts, playback


@pytest.mark.asyncio
async def test_real_graph_delivers_two_turn_exact_follow_up_and_commits_memory(
    tmp_path: Path,
) -> None:
    primary = FakeSTTEdge(
        "speechmatics",
        [
            "Future of AI in Events "
            "\u0645\u064a\u0639\u0627\u062f\u0647\u0627 \u0627\u0645\u062a\u0649\u061f",
            "\u0648\u0641\u064a\u0646\u061f",
        ],
    )
    app, _llm, tts, playback = _build_graph(
        tmp_path,
        primary,
        FakeSTTEdge("deepgram", []),
    )
    try:
        assert isinstance(app.voice.turn_runtime, RealtimeTurnRuntime)
        assert isinstance(app.voice, VoiceBrainRuntime)
        assert isinstance(app.knowledge, ActiveKnowledgeBinding)
        snapshot = app.knowledge.snapshot()
        assert isinstance(snapshot.resolver, StructuredResolver)
        assert isinstance(snapshot.retriever, HybridRetriever)
        assert isinstance(app.orchestrator, GroundedOrchestrator)

        await app.providers.stt.start()
        await app.voice.handle_user_turn_started()
        await app.voice._on_audio_chunk(b"first-turn-pcm")
        first = await app.voice.handle_user_turn_stopped()
        await app.voice.handle_user_turn_started()
        await app.voice._on_audio_chunk(b"second-turn-pcm")
        second = await app.voice.handle_user_turn_stopped()

        assert primary.audio == [b"first-turn-pcm", b"second-turn-pcm"]
        assert first is not None and first.route is AnswerRoute.EXACT
        assert second is not None and second.route is AnswerRoute.EXACT
        assert "Main Stage" in second.text
        assert len(app.memory.recent_turns()) == 2
        assert len(tts.texts) == 2
        assert playback.calls.count(("finish",)) == 2
        assert app.voice.machine.state is ConversationState.LISTENING
    finally:
        await app.providers.stt.stop()
        app.event_context.close()


@pytest.mark.asyncio
async def test_real_graph_recovers_from_stt_failure_and_cancels_on_interruption(
    tmp_path: Path,
) -> None:
    primary = FakeSTTEdge("speechmatics", [], fail_final=True)
    fallback = FakeSTTEdge(
        "deepgram",
        [
            "Future of AI in Events "
            "\u0645\u064a\u0639\u0627\u062f\u0647\u0627 \u0627\u0645\u062a\u0649\u061f"
        ],
    )
    app, llm, tts, playback = _build_graph(tmp_path, primary, fallback)
    try:
        await app.providers.stt.start()
        await app.voice.handle_user_turn_started()
        await app.voice._on_audio_chunk(b"failed-turn-pcm")
        assert await app.voice.handle_user_turn_stopped() is None
        assert app.voice.machine.state is ConversationState.LISTENING

        await app.voice.handle_user_turn_started()
        await app.voice._on_audio_chunk(b"fallback-turn-pcm")
        assert await app.voice.handle_user_turn_stopped() is not None
        assert fallback.audio == [b"fallback-turn-pcm"]

        app.voice.machine.transition(ConversationState.THINKING, "synthetic")
        app.voice.machine.transition(ConversationState.SPEAKING, "synthetic")
        interrupted = await app.voice.interruption.handle_user_turn_started()
        assert interrupted.interrupted is True
        assert playback.calls[-1] == ("cancel",)
        assert llm.cancel_calls >= 1
        assert tts.cancel_calls >= 1
        assert app.voice.machine.state is ConversationState.LISTENING
    finally:
        await app.providers.stt.stop()
        app.event_context.close()

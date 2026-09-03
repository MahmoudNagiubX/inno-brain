from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from innobrain.app import InnoBrainApplication, build_application
from innobrain.config import load_all_configs
from innobrain.conversation.knowledge_binding import ActiveKnowledgeBinding
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import GroundedOrchestrator
from innobrain.event.activation import ActivationManager
from innobrain.event.builder import build_event_package
from innobrain.event.errors import EventActivationBusy
from innobrain.event.installer import install_event_package
from innobrain.event.registry import EventRegistry
from innobrain.event.validation import PackageVerificationPolicy
from innobrain.providers import AudioChunk, TranscriptEvent
from innobrain.providers.registry import ProviderBundle
from innobrain.providers.stt_failover import FailoverSTTProvider
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.state import ConversationState

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class TestTokenizer:
    def encode(self, text: str) -> SimpleNamespace:
        return SimpleNamespace(ids=text.split())


class TestEmbeddingProvider:
    async def embed_passage(self, text: str) -> list[float]:
        vector = np.zeros(384, dtype=np.float32)
        vector[len(text) % 384] = 1.0
        return vector.tolist()

    async def embed_query(self, text: str) -> list[float]:
        vector = np.zeros(384, dtype=np.float32)
        vector[len(text) % 384] = 1.0
        return vector.tolist()


class FakeSTTEdge:
    def __init__(self, name: str) -> None:
        self.name = name
        self.audio: list[bytes] = []
        self.turn_id: int | None = None

    async def start(self) -> None:
        return None

    async def begin_turn(self, turn_id: int) -> None:
        self.turn_id = turn_id

    async def stream_audio(self, pcm: bytes) -> None:
        self.audio.append(pcm)

    async def final_text(self, turn_id: int | None = None) -> TranscriptEvent:
        return TranscriptEvent("", True, turn_id=turn_id)

    async def stop(self) -> None:
        return None


class FakeLLMEdge:
    name = "fake-groq-edge"

    def __init__(self) -> None:
        self.cancel_calls = 0

    def stream(self, messages, tools, context):
        async def chunks():
            evidence_text = " ".join(item.content for item in context.evidence.evidence)
            yield f"grounded: {evidence_text}"

        return chunks()

    async def cancel(self) -> None:
        self.cancel_calls += 1


class FakeTTSEdge:
    name = "fake-azure-edge"

    def __init__(self) -> None:
        self.cancel_calls = 0
        self.texts: list[str] = []

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
        self.calls: list[tuple[object, ...]] = []

    async def start(self, sample_rate_hz: int) -> None:
        self.calls.append(("start", sample_rate_hz))

    async def write(self, pcm: bytes) -> None:
        self.calls.append(("write", pcm))

    async def finish(self) -> None:
        self.calls.append(("finish",))

    async def cancel(self) -> None:
        self.calls.append(("cancel",))


async def _build_and_install(fixture_name: str, tmp_path: Path, data_root: Path) -> None:
    package = tmp_path / f"{fixture_name}.innoevent"
    await build_event_package(
        REPOSITORY_ROOT / "fixtures" / "phase4" / fixture_name,
        package,
        embedding_provider=TestEmbeddingProvider(),
        tokenizer=TestTokenizer(),
    )
    installed = install_event_package(
        package,
        data_root,
        verification_policy=PackageVerificationPolicy(
            environment="development", allow_unsigned_development=True
        ),
    )
    installed.close()


@pytest.mark.asyncio
async def test_production_application_event_switch_and_quiescent_guard(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime_data"
    await _build_and_install("event_alpha", tmp_path, data_root)
    await _build_and_install("event_beta", tmp_path, data_root)

    registry = EventRegistry(data_root)
    alpha = registry.get("event-alpha")
    beta = registry.get("event-beta")

    initial_manager = ActivationManager(data_root, registry)
    initial_manager.activate("event-alpha", build_id=alpha.build_id)

    config = load_all_configs(REPOSITORY_ROOT)
    config = config.model_copy(
        update={
            "runtime": config.runtime.model_copy(
                update={
                    "events": config.runtime.events.model_copy(
                        update={"data_root": str(data_root)}
                    )
                }
            )
        }
    )

    primary = FakeSTTEdge("speechmatics")
    fallback = FakeSTTEdge("deepgram")
    providers = ProviderBundle(FailoverSTTProvider(primary, fallback), FakeLLMEdge(), FakeTTSEdge())
    embedding_provider = TestEmbeddingProvider()
    playback = FakePlaybackEdge()

    app = build_application(
        config=config,
        provider_bundle=providers,
        embedding_provider=embedding_provider,
        registry=registry,
        stream=FakeAudioEdge(),
        playback=playback,
    )

    assert isinstance(app, InnoBrainApplication)
    assert isinstance(app.voice, VoiceBrainRuntime)
    assert isinstance(app.knowledge, ActiveKnowledgeBinding)
    assert isinstance(app.memory, SessionMemory)
    assert isinstance(app.orchestrator, GroundedOrchestrator)

    # 1. Alpha starts and answers
    await app.start()
    assert app.voice.is_quiescent
    alpha_ans = await app.orchestrator.answer("ALPHA COMPASS")
    assert "ALPHA-COMPASS" in alpha_ans.text

    # 2. Beta-only facts are absent
    beta_absent = await app.orchestrator.answer("BETA LANTERN")
    assert "BETA-LANTERN" not in beta_absent.text

    # Record old context and populate memory
    old_context = app.event_context
    assert old_context.record.event_id == "event-alpha"
    assert app.knowledge.snapshot().event_id == "event-alpha"
    app.memory.add_turn("user", "remembered alpha", ["ALPHA-COMPASS"])
    assert len(app.memory.recent_turns()) == 1

    # 3. Activation while the runtime is non-quiescent raises EventActivationBusy
    app.voice.machine.transition(ConversationState.THINKING, "active_processing")
    assert not app.voice.is_quiescent
    with pytest.raises(EventActivationBusy, match="conversation runtime is busy"):
        app.activate_event("event-beta", build_id=beta.build_id)

    app.voice.machine.transition(ConversationState.LISTENING, "recovered")
    assert app.voice.is_quiescent

    # 4. app.activate_event(Beta) changes app.event_context, brain knowledge, and memory
    activated_record = app.activate_event("event-beta", build_id=beta.build_id)
    assert activated_record.event_id == "event-beta"
    assert app.event_context is not old_context
    assert app.event_context.record.event_id == "event-beta"
    assert app.knowledge.snapshot().event_id == "event-beta"
    assert app.memory.recent_turns() == ()

    # 5. Alpha facts are absent; Beta facts work
    alpha_absent = await app.orchestrator.answer("ALPHA COMPASS")
    assert "ALPHA-COMPASS" not in alpha_absent.text
    beta_ans = await app.orchestrator.answer("BETA LANTERN")
    assert "BETA-LANTERN" in beta_ans.text

    # 6. Rollback returns to Alpha
    rolled_back_record = app.rollback_event()
    assert rolled_back_record.event_id == "event-alpha"
    assert app.event_context.record.event_id == "event-alpha"
    assert app.knowledge.snapshot().event_id == "event-alpha"
    alpha_restored = await app.orchestrator.answer("ALPHA COMPASS")
    assert "ALPHA-COMPASS" in alpha_restored.text
    beta_absent_again = await app.orchestrator.answer("BETA LANTERN")
    assert "BETA-LANTERN" not in beta_absent_again.text

    # Stop closes context and marks inactive
    await app.stop()
    with pytest.raises(RuntimeError, match="no active event context"):
        _ = app.event_context

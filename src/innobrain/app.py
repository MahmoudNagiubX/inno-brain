from dataclasses import dataclass, field
from pathlib import Path

from innobrain.config.models import ProjectConfigs
from innobrain.conversation.knowledge_binding import ActiveKnowledgeBinding, KnowledgeSnapshot
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import GroundedOrchestrator
from innobrain.event.activation import ActivationManager
from innobrain.event.registry import EventRegistry
from innobrain.event.runtime import ActiveRuntimeContext, open_runtime_context
from innobrain.knowledge.e5_onnx import MultilingualE5OnnxProvider
from innobrain.providers.registry import ProviderBundle, build_provider_bundle
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.pcm_playback import PCMStreamPlaybackController

ActiveEventContext = ActiveRuntimeContext


@dataclass
class InnoBrainApplication:
    config: ProjectConfigs
    providers: ProviderBundle
    event_context: ActiveEventContext
    knowledge: ActiveKnowledgeBinding
    memory: SessionMemory
    orchestrator: GroundedOrchestrator
    playback: PCMStreamPlaybackController
    voice: VoiceBrainRuntime
    _started: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    async def start(self) -> None:
        if self._started:
            return
        self._closed = False
        try:
            await self.voice.start()
            self._started = True
        except BaseException:
            await self.voice.stop()
            self.event_context.close()
            self._closed = True
            raise

    async def stop(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self.voice.stop()
        finally:
            self.event_context.close()
            self._started = False


def _open_configured_event(config: ProjectConfigs) -> ActiveEventContext:
    data_root = Path(config.runtime.events.data_root)
    registry = EventRegistry(data_root)
    record = ActivationManager(data_root, registry).active()
    if record is None:
        raise RuntimeError("no active event is configured")
    embedding = MultilingualE5OnnxProvider(
        dimension=config.providers.embedding.dimension,
        max_tokens=config.providers.embedding.max_tokens,
        download_assets=False,
    )
    retrieval = config.providers.retrieval
    return open_runtime_context(
        record,
        embedding_provider=embedding,
        lexical_top_k=retrieval.lexical_top_k,
        dense_top_k=retrieval.dense_top_k,
        final_top_k=retrieval.final_top_k,
        rrf_k=retrieval.rrf_k,
    )


def build_application(
    *,
    config: ProjectConfigs,
    provider_bundle: ProviderBundle | None = None,
    event_context: ActiveEventContext | None = None,
    stream: object | None = None,
    playback: PCMStreamPlaybackController | None = None,
) -> InnoBrainApplication:
    context = event_context or _open_configured_event(config)
    try:
        providers = provider_bundle or build_provider_bundle(config)
        knowledge = ActiveKnowledgeBinding(
            KnowledgeSnapshot(
                event_id=context.record.event_id,
                event_version=context.record.event_version,
                resolver=context.resolver,
                retriever=context.retriever,
            )
        )
        memory = SessionMemory(
            max_turns=config.runtime.conversation.memory_max_turns,
            ttl_seconds=config.runtime.conversation.memory_ttl_seconds,
        )
        orchestrator = GroundedOrchestrator(
            memory=memory,
            llm_provider=providers.llm,
            knowledge=knowledge,
        )
        playback_controller = playback or PCMStreamPlaybackController()
        voice = VoiceBrainRuntime(
            config.runtime,
            stt=providers.stt,
            orchestrator=orchestrator,
            tts=providers.tts,
            playback=playback_controller,
            stream=stream,
        )
        return InnoBrainApplication(
            config=config,
            providers=providers,
            event_context=context,
            knowledge=knowledge,
            memory=memory,
            orchestrator=orchestrator,
            playback=playback_controller,
            voice=voice,
        )
    except BaseException:
        context.close()
        raise


__all__ = [
    "ActiveEventContext",
    "InnoBrainApplication",
    "build_application",
]

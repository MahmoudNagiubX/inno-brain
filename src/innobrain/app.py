from dataclasses import dataclass, field
from pathlib import Path

from innobrain.config.models import ProjectConfigs
from innobrain.conversation.knowledge_binding import ActiveKnowledgeBinding, KnowledgeSnapshot
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import GroundedOrchestrator
from innobrain.event.activation import ActivationManager
from innobrain.event.registry import EventRegistry, InstalledEventRecord
from innobrain.event.runtime import (
    ActiveRuntimeContext,
    RuntimeContextSwitcher,
    open_runtime_context,
)
from innobrain.knowledge.e5_onnx import MultilingualE5OnnxProvider
from innobrain.providers.registry import ProviderBundle, build_provider_bundle
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.pcm_playback import PCMStreamPlaybackController

ActiveEventContext = ActiveRuntimeContext


@dataclass
class InnoBrainApplication:
    config: ProjectConfigs
    providers: ProviderBundle
    context_switcher: RuntimeContextSwitcher
    activation_manager: ActivationManager
    knowledge: ActiveKnowledgeBinding
    memory: SessionMemory
    orchestrator: GroundedOrchestrator
    playback: PCMStreamPlaybackController
    voice: VoiceBrainRuntime
    _started: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def event_context(self) -> ActiveEventContext:
        context = self.context_switcher.current
        if context is None:
            raise RuntimeError("no active event context")
        return context

    def activate_event(
        self,
        event_id: str,
        event_version: str | None = None,
        build_id: str | None = None,
    ) -> InstalledEventRecord:
        return self.activation_manager.activate(
            event_id,
            event_version=event_version,
            build_id=build_id,
        )

    def rollback_event(self) -> InstalledEventRecord:
        return self.activation_manager.rollback()

    async def start(self) -> None:
        if self._started:
            return
        self._closed = False
        try:
            await self.voice.start()
            self._started = True
        except BaseException:
            await self.voice.stop()
            self.context_switcher.close()
            self._closed = True
            raise

    async def stop(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self.voice.stop()
        finally:
            self.context_switcher.close()
            self._started = False


def _open_configured_event(
    config: ProjectConfigs,
    *,
    registry: EventRegistry | None = None,
    embedding_provider: object | None = None,
) -> ActiveEventContext:
    data_root = Path(config.runtime.events.data_root)
    event_registry = registry or EventRegistry(data_root)
    record = ActivationManager(event_registry.data_root, event_registry).active()
    if record is None:
        raise RuntimeError("no active event is configured")
    embedding = (
        embedding_provider
        if embedding_provider is not None
        else MultilingualE5OnnxProvider(
            dimension=config.providers.embedding.dimension,
            max_tokens=config.providers.embedding.max_tokens,
            download_assets=False,
        )
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
    embedding_provider: object | None = None,
    registry: EventRegistry | None = None,
    stream: object | None = None,
    playback: PCMStreamPlaybackController | None = None,
) -> InnoBrainApplication:
    event_registry = registry or EventRegistry(Path(config.runtime.events.data_root))
    retrieval = config.providers.retrieval
    embedding = embedding_provider
    if embedding is None and event_context is not None:
        embedding = getattr(getattr(event_context, "retriever", None), "embedding_provider", None)
    if embedding is None and event_context is None:
        embedding = MultilingualE5OnnxProvider(
            dimension=config.providers.embedding.dimension,
            max_tokens=config.providers.embedding.max_tokens,
            download_assets=False,
        )

    context = event_context or _open_configured_event(
        config,
        registry=event_registry,
        embedding_provider=embedding,
    )
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
        context_switcher = RuntimeContextSwitcher(
            memory,
            embedding_provider=embedding,
            binding=knowledge,
            current=context,
            lexical_top_k=retrieval.lexical_top_k,
            dense_top_k=retrieval.dense_top_k,
            final_top_k=retrieval.final_top_k,
            rrf_k=retrieval.rrf_k,
        )
        activation_manager = ActivationManager(
            event_registry.data_root,
            event_registry,
            idle_guard=lambda: voice.is_quiescent,
            switch_hook=context_switcher.switch,
        )
        return InnoBrainApplication(
            config=config,
            providers=providers,
            context_switcher=context_switcher,
            activation_manager=activation_manager,
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

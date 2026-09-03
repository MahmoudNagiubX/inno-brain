import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from innobrain.attention.contracts import AttentionHealth, AttentionPolicyConfig
from innobrain.attention.controller import AttentionController
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
from innobrain.wake.bridge import WakeAttentionBridge
from innobrain.wake.contracts import WakeWordEngine
from innobrain.wake.factory import build_wake_router
from innobrain.wake.router import WakeAudioRouter, WakeRouterHealth

ActiveEventContext = ActiveRuntimeContext


@dataclass(frozen=True, slots=True)
class ApplicationHealth:
    """Watchdog-visible immutable health snapshot without secret values."""

    ready: bool
    degraded: bool
    started: bool
    quiescent: bool
    conversation_state: str
    active_event_id: str | None
    attention: dict[str, Any] | None
    wake: dict[str, Any] | None
    audio: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "degraded": self.degraded,
            "started": self.started,
            "quiescent": self.quiescent,
            "conversation_state": self.conversation_state,
            "active_event_id": self.active_event_id,
            "attention": self.attention,
            "wake": self.wake,
            "audio": self.audio,
        }


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
    attention: AttentionController | None = None
    wake_router: WakeAudioRouter | None = None
    wake_bridge: WakeAttentionBridge | None = None
    _started: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def event_context(self) -> ActiveEventContext:
        context = self.context_switcher.current
        if context is None:
            raise RuntimeError("no active event context")
        return context

    @property
    def wake_health(self) -> WakeRouterHealth | None:
        return self.wake_router.health if self.wake_router is not None else None

    @property
    def attention_health(self) -> AttentionHealth | None:
        return self.attention.health if self.attention is not None else None

    @property
    def health(self) -> ApplicationHealth:
        att_health = self.attention.health if self.attention is not None else None
        wake_health = self.wake_router.health if self.wake_router is not None else None
        turn_stream = getattr(self.voice.turn_runtime, "stream", None)
        audio_stats = getattr(turn_stream, "stats", None)

        active_ctx = self.context_switcher.current
        active_event_id = active_ctx.record.event_id if active_ctx is not None else None

        ready = (
            (att_health is None or att_health.ready)
            and (wake_health is None or wake_health.ready)
        )
        degraded = (
            (att_health is not None and att_health.degraded)
            or (wake_health is not None and wake_health.degraded)
        )

        return ApplicationHealth(
            ready=ready,
            degraded=degraded,
            started=self._started,
            quiescent=self.voice.is_quiescent,
            conversation_state=self.voice.machine.state.value,
            active_event_id=active_event_id,
            attention=dataclasses.asdict(att_health) if att_health is not None else None,
            wake=dataclasses.asdict(wake_health) if wake_health is not None else None,
            audio=dataclasses.asdict(audio_stats) if audio_stats is not None else None,
        )

    def activate_event(
        self,
        event_id: str,
        event_version: str | None = None,
        build_id: str | None = None,
    ) -> InstalledEventRecord:
        if self.attention is not None:
            self.attention.reset()
        if self.wake_router is not None:
            self.wake_router.reset()
        return self.activation_manager.activate(
            event_id,
            event_version=event_version,
            build_id=build_id,
        )

    def rollback_event(self) -> InstalledEventRecord:
        if self.attention is not None:
            self.attention.reset()
        if self.wake_router is not None:
            self.wake_router.reset()
        return self.activation_manager.rollback()

    async def start(self) -> None:
        if self._started:
            return
        self._closed = False
        try:
            await self.voice.start()
            self._started = True
        except BaseException:
            try:
                await self.voice.stop()
            finally:
                try:
                    if self.attention is not None:
                        self.attention.reset()
                finally:
                    try:
                        if self.wake_router is not None:
                            self.wake_router.close()
                    finally:
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
            if self.attention is not None:
                self.attention.reset()
            if self.wake_router is not None:
                self.wake_router.close()
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
    wake_engine: WakeWordEngine | None = None,
    wake_router: WakeAudioRouter | None = None,
    attention_controller: AttentionController | None = None,
    environment: Mapping[str, str] | None = None,
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
        router = wake_router or build_wake_router(
            config.runtime.wake_word,
            engine=wake_engine,
            environment=environment,
        )
        if attention_controller is not None:
            attention = attention_controller
            if getattr(attention, "_router", None) is None:
                attention._router = router
        else:
            att_cfg = config.runtime.attention
            policy = AttentionPolicyConfig(
                followup_window_ms=att_cfg.followup_window_ms,
                followup_window_cap_ms=att_cfg.followup_window_cap_ms,
                max_session_duration_seconds=att_cfg.max_session_duration_seconds,
                rejected_background_limit=att_cfg.rejected_background_limit,
                wake_cooldown_seconds=att_cfg.wake_cooldown_seconds,
            )
            attention = AttentionController(policy=policy, router=router)

        bridge = WakeAttentionBridge(router=router, attention=attention)

        voice = VoiceBrainRuntime(
            config.runtime,
            stt=providers.stt,
            orchestrator=orchestrator,
            tts=providers.tts,
            playback=playback_controller,
            stream=stream,
            audio_gate=bridge,
            attention=attention,
            wake_router=router,
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
            attention=attention,
            wake_router=router,
            wake_bridge=bridge,
        )
    except BaseException:
        context.close()
        raise


__all__ = [
    "ActiveEventContext",
    "ApplicationHealth",
    "InnoBrainApplication",
    "build_application",
]

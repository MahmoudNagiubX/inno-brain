import asyncio
import inspect

from innobrain.config import RuntimeConfig
from innobrain.providers import STTProvider, TTSProvider
from innobrain.telemetry.runtime_events import (
    LoggingRuntimeEventSink,
    RuntimeEventSink,
    RuntimeFault,
    RuntimeObservation,
)

from ..conversation.memory import SessionMemory
from ..conversation.orchestrator import BrainResult, GroundedOrchestrator
from ..conversation.sentence_chunker import SentenceChunker
from .interruption import InterruptionController
from .pcm_playback import PCMStreamPlaybackController
from .pipecat_runtime import RealtimeTurnRuntime
from .state import ConversationState, ConversationStateMachine
from .turn_events import TurnEvent, TurnEventType


class VoiceBrainRuntime:
    """Compose the Phase 2 capture/turn path with Phase 3 providers and brain."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        stt: STTProvider,
        orchestrator: GroundedOrchestrator,
        tts: TTSProvider,
        playback: PCMStreamPlaybackController,
        stream: object | None = None,
        machine: ConversationStateMachine | None = None,
        turn_runtime: RealtimeTurnRuntime | None = None,
        event_sink: RuntimeEventSink | None = None,
    ) -> None:
        self.config = config
        self.machine = machine or ConversationStateMachine()
        self.stt = stt
        self.orchestrator = orchestrator
        self.tts = tts
        self.playback = playback
        self.memory: SessionMemory = orchestrator.memory
        self.last_result: BrainResult | None = None
        self._response_task: asyncio.Task[BrainResult | None] | None = None
        self._turn_task: asyncio.Task[BrainResult | None] | None = None
        self._next_turn_id = 1
        self._active_turn_id: int | None = None
        self._started = False
        self._closed = False
        self._event_sink = event_sink or LoggingRuntimeEventSink()
        self.interruption = InterruptionController(
            self.machine,
            self.playback,
            response_cancel_callback=self.cancel_response,
        )
        self.turn_runtime = turn_runtime or RealtimeTurnRuntime(
            config,
            stream=stream,
            machine=self.machine,
            interruption=self.interruption,
            on_audio_chunk=self._on_audio_chunk,
            on_event=self._on_turn_event,
        )

    @property
    def active_turn_id(self) -> int | None:
        return self._active_turn_id

    async def start(self) -> None:
        if self._started:
            return
        self._closed = False
        await self.stt.start()
        await self.turn_runtime.start()
        self._started = True

    async def stop(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self.cancel_response()
            turn_task = self._turn_task
            if turn_task is not None and not turn_task.done():
                turn_task.cancel()
                await self._await_cancelled_task(turn_task)
            await self.turn_runtime.stop()
            await self.stt.stop()
            await self.playback.cancel()
        finally:
            self._active_turn_id = None
            self._started = False
            if self.machine.state is not ConversationState.IDLE:
                self.machine.transition(ConversationState.IDLE, "runtime_stopped")

    async def cancel_response(self) -> None:
        task = self._response_task
        cancellations = []
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            cancellations.append(self._await_cancelled_task(task))
        cancellations.extend(self._provider_cancellations())
        if cancellations:
            await asyncio.gather(*cancellations)

    def _provider_cancellations(self) -> list[object]:
        cancellations = []
        cancel_llm = getattr(self.orchestrator, "cancel", None)
        if cancel_llm is not None:
            cancellations.append(self._invoke_cancel(cancel_llm))
        cancel_tts = getattr(self.tts, "cancel", None)
        if cancel_tts is not None:
            cancellations.append(self._invoke_cancel(cancel_tts))
        return cancellations

    @staticmethod
    async def _await_cancelled_task(task: asyncio.Task[object]) -> None:
        try:
            await asyncio.wait_for(task, timeout=0.25)
        except (asyncio.CancelledError, TimeoutError):
            pass

    @staticmethod
    async def _invoke_cancel(callback: object) -> None:
        try:
            result = callback()  # type: ignore[operator]
            if inspect.isawaitable(result):
                await asyncio.wait_for(result, timeout=0.25)
        except (asyncio.CancelledError, TimeoutError):
            pass

    async def handle_user_turn_started(self) -> int:
        if self.machine.state is ConversationState.IDLE:
            self.machine.transition(ConversationState.LISTENING, "runtime_started")
        turn_id = self._next_turn_id
        self._next_turn_id += 1
        self._active_turn_id = turn_id
        try:
            await self.stt.begin_turn(turn_id)
        except Exception:
            self._active_turn_id = None
            raise
        self._emit("turn_started", turn_id=turn_id)
        return turn_id

    async def handle_user_turn_stopped(self) -> BrainResult | None:
        turn_id = self._active_turn_id
        if turn_id is None:
            return None
        self._active_turn_id = None
        if self.machine.state is not ConversationState.LISTENING:
            return None
        self._emit("speech_stop", turn_id=turn_id, timing_marker="speech_stop")
        try:
            transcript = await self.stt.final_text(turn_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_fault("stt_final", exc, turn_id)
            return None
        if transcript.turn_id is not None and transcript.turn_id != turn_id:
            return None
        self._emit(
            "stt_final",
            turn_id=turn_id,
            transcript_final_received=True,
            timing_marker="stt_final",
        )
        if not transcript.text.strip():
            return None
        self.machine.transition(ConversationState.THINKING, "user_turn_stopped")
        response_task = asyncio.create_task(self._respond(transcript.text, turn_id=turn_id))
        self._response_task = response_task
        try:
            return await response_task
        finally:
            if self._response_task is response_task:
                self._response_task = None

    async def _respond(self, user_text: str, *, turn_id: int | None = None) -> BrainResult | None:
        stage = "brain"
        try:
            result = await self.orchestrator.answer(user_text)
            self._emit(
                "brain_complete",
                turn_id=turn_id,
                answer_route=result.route.value,
                evidence_count=len(result.evidence_ids),
                llm_provider=result.provider,
                timing_marker="brain_complete",
            )
            chunker = SentenceChunker()
            sentences = chunker.feed(result.text) + chunker.flush()
            started_playback = False
            for sentence in sentences:
                stage = "tts"
                async for audio in self.tts.stream(sentence):
                    if not started_playback:
                        stage = "playback"
                        await self.playback.start(audio.sample_rate_hz)
                        started_playback = True
                        self.machine.transition(ConversationState.SPEAKING, "first_pcm")
                        self._emit(
                            "tts_first_pcm",
                            turn_id=turn_id,
                            timing_marker="tts_first_pcm",
                        )
                    stage = "playback"
                    await self.playback.write(audio.data)
                    stage = "tts"
            if not started_playback:
                self.machine.transition(ConversationState.LISTENING, "tts_unavailable")
                return result
            stage = "playback"
            await self.playback.finish()
            self._emit(
                "playback_stop",
                turn_id=turn_id,
                timing_marker="playback_stop",
            )
            self.orchestrator.commit_delivered(user_text, result)
            self.last_result = result
            self.machine.transition(ConversationState.LISTENING, "response_delivered")
            return result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._handle_fault(stage, exc, turn_id)
            return None

    async def _handle_fault(
        self,
        stage: str,
        exc: Exception,
        turn_id: int | None,
    ) -> None:
        fault = RuntimeFault(
            stage=stage,
            error_type=type(exc).__name__,
            message=str(exc),
            turn_id=turn_id,
        )
        try:
            self._event_sink.fault(fault)
        except Exception:
            pass
        await self.playback.cancel()
        cancellations = self._provider_cancellations()
        if cancellations:
            await asyncio.gather(*cancellations)
        if self.machine.state in {ConversationState.THINKING, ConversationState.SPEAKING}:
            self.machine.transition(ConversationState.LISTENING, "response_fault_recovered")

    async def _on_audio_chunk(self, pcm: bytes) -> None:
        await self.stt.stream_audio(pcm)

    async def _on_turn_event(self, event: TurnEvent) -> None:
        if event.event_type is TurnEventType.USER_TURN_STARTED:
            if event.barge_in:
                self._emit("barge_in", turn_id=self._active_turn_id, barge_in=True)
            await self.handle_user_turn_started()
            return
        if event.event_type is TurnEventType.USER_TURN_STOPPED:
            if self._turn_task is None or self._turn_task.done():
                task = asyncio.create_task(self.handle_user_turn_stopped())
                self._turn_task = task
                task.add_done_callback(self._observe_turn_task)

    def _observe_turn_task(self, task: asyncio.Task[BrainResult | None]) -> None:
        if self._turn_task is task:
            self._turn_task = None
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            try:
                self._event_sink.fault(
                    RuntimeFault(
                        stage="turn_background",
                        error_type=type(exc).__name__,
                        message=str(exc),
                        turn_id=self._active_turn_id,
                    )
                )
            except Exception:
                pass

    def _emit(self, event: str, **values: object) -> None:
        emit = getattr(self._event_sink, "emit", None)
        if emit is None:
            return
        event_id = None
        event_version = None
        knowledge = getattr(self.orchestrator, "knowledge", None)
        if knowledge is not None:
            snapshot = knowledge.snapshot()
            event_id = snapshot.event_id
            event_version = snapshot.event_version
        observation = RuntimeObservation(
            event=event,
            conversation_state=self.machine.state.value,
            stt_provider=getattr(self.stt, "name", type(self.stt).__name__),
            event_id=event_id,
            event_version=event_version,
            tts_provider=getattr(self.tts, "name", type(self.tts).__name__),
            **values,
        )
        try:
            emit(observation)
        except Exception:
            pass

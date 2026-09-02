import asyncio
import inspect

from innobrain.config import RuntimeConfig
from innobrain.providers import STTProvider, TTSProvider

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
        self._next_turn_id = 1
        self._active_turn_id: int | None = None
        self._started = False
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
        await self.stt.start()
        await self.turn_runtime.start()
        self._started = True

    async def stop(self) -> None:
        await self.cancel_response()
        await self.stt.stop()
        await self.turn_runtime.stop()
        self._started = False

    async def cancel_response(self) -> None:
        task = self._response_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        cancel_tts = getattr(self.tts, "cancel", None)
        if cancel_tts is not None:
            result = cancel_tts()
            if inspect.isawaitable(result):
                await result

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
        return turn_id

    async def handle_user_turn_stopped(self) -> BrainResult | None:
        turn_id = self._active_turn_id
        if turn_id is None:
            return None
        self._active_turn_id = None
        if self.machine.state is not ConversationState.LISTENING:
            return None
        transcript = await self.stt.final_text(turn_id)
        if transcript.turn_id is not None and transcript.turn_id != turn_id:
            return None
        if not transcript.text.strip():
            return None
        self.machine.transition(ConversationState.THINKING, "user_turn_stopped")
        self._response_task = asyncio.create_task(self._respond(transcript.text))
        try:
            return await self._response_task
        finally:
            self._response_task = None

    async def _respond(self, user_text: str) -> BrainResult | None:
        try:
            result = await self.orchestrator.answer(user_text)
            self.last_result = result
            chunker = SentenceChunker()
            sentences = chunker.feed(result.text) + chunker.flush()
            started_playback = False
            for sentence in sentences:
                async for audio in self.tts.stream(sentence):
                    if not started_playback:
                        await self.playback.start(audio.sample_rate_hz)
                        started_playback = True
                        self.machine.transition(ConversationState.SPEAKING, "first_pcm")
                    await self.playback.write(audio.data)
            if not started_playback:
                self.machine.transition(ConversationState.LISTENING, "tts_unavailable")
                return result
            await self.playback.finish()
            self.orchestrator.commit_delivered(user_text, result)
            self.machine.transition(ConversationState.LISTENING, "response_delivered")
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            if self.machine.state is ConversationState.THINKING:
                self.machine.transition(ConversationState.LISTENING, "tts_unavailable")
            return self.last_result

    async def _on_audio_chunk(self, pcm: bytes) -> None:
        await self.stt.stream_audio(pcm)

    async def _on_turn_event(self, event: TurnEvent) -> None:
        if event.event_type is TurnEventType.USER_TURN_STARTED:
            await self.handle_user_turn_started()
            return
        if event.event_type is TurnEventType.USER_TURN_STOPPED:
            if self._response_task is None or self._response_task.done():
                self._response_task = asyncio.create_task(self.handle_user_turn_stopped())

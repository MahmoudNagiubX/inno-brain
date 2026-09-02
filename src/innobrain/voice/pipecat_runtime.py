import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndFrame, InputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.turns.user_start import VADUserTurnStartStrategy
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_processor import UserTurnProcessor
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from innobrain.audio import SoundDevicePCMStream
from innobrain.config import RuntimeConfig

from .interruption import InterruptionController
from .playback import PlaybackController, SoundDevicePlaybackBackend
from .state import ConversationState, ConversationStateMachine
from .turn_events import TurnEvent, TurnEventType

TurnEventCallback = Callable[[TurnEvent], Awaitable[None] | None]


class RealtimeTurnRuntime:
    def __init__(
        self,
        config: RuntimeConfig,
        *,
        stream: Any | None = None,
        machine: ConversationStateMachine | None = None,
        interruption: InterruptionController | None = None,
        on_event: TurnEventCallback | None = None,
    ) -> None:
        self.config = config
        self.machine = machine or ConversationStateMachine()
        self.playback = PlaybackController(SoundDevicePlaybackBackend())
        self.interruption = interruption or InterruptionController(
            self.machine,
            self.playback,
        )
        self.stream = stream or SoundDevicePCMStream(
            sample_rate_hz=config.audio.target_sample_rate_hz,
            frame_ms=config.audio.frame_ms,
            device=config.audio.input_device,
            queue_max_chunks=config.realtime.audio_queue_max_chunks,
        )
        self.events: list[TurnEvent] = []
        self._on_event_callback = on_event
        self._runner: WorkerRunner | None = None
        self._ready_event: asyncio.Event | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self._feed_task: asyncio.Task[None] | None = None
        self._started = False
        self._cleaned = False

        vad_params = VADParams(
            confidence=config.realtime.vad.confidence,
            start_secs=config.realtime.vad.start_secs,
            stop_secs=config.realtime.vad.stop_secs,
            min_volume=config.realtime.vad.min_volume,
        )
        self.vad = SileroVADAnalyzer(
            sample_rate=config.audio.target_sample_rate_hz,
            params=vad_params,
        )
        self.smart_turn = LocalSmartTurnAnalyzerV3(
            cpu_count=config.realtime.smart_turn.cpu_count,
        )
        self.stop_strategy = TurnAnalyzerUserTurnStopStrategy(
            turn_analyzer=self.smart_turn,
            wait_for_transcript=config.realtime.smart_turn.wait_for_transcript,
        )
        self.user_turn_strategies = UserTurnStrategies(
            start=[VADUserTurnStartStrategy()],
            stop=[self.stop_strategy],
        )
        self.vad_processor = VADProcessor(vad_analyzer=self.vad)
        self.turn_processor = UserTurnProcessor(
            user_turn_strategies=self.user_turn_strategies,
            user_turn_stop_timeout=5.0,
        )
        self.pipeline = Pipeline([self.vad_processor, self.turn_processor])
        self.worker = PipelineWorker(
            self.pipeline,
            params=PipelineParams(
                audio_in_sample_rate=config.audio.target_sample_rate_hz,
                audio_out_sample_rate=config.audio.target_sample_rate_hz,
            ),
            processor_unusable_policy=ProcessorUnusablePolicy.END,
        )

        @self.turn_processor.event_handler("on_user_turn_started")
        async def on_user_turn_started(_processor: UserTurnProcessor, strategy: Any) -> None:
            await self._record_event(
                TurnEvent.now(
                    TurnEventType.USER_TURN_STARTED,
                    type(strategy).__name__,
                )
            )
            await self.interruption.handle_user_turn_started()

        @self.turn_processor.event_handler("on_user_turn_inference_triggered")
        async def on_user_turn_inference_triggered(
            _processor: UserTurnProcessor,
            strategy: Any,
        ) -> None:
            await self._record_event(
                TurnEvent.now(
                    TurnEventType.USER_TURN_INFERENCE_TRIGGERED,
                    type(strategy).__name__,
                )
            )

        @self.turn_processor.event_handler("on_user_turn_stopped")
        async def on_user_turn_stopped(_processor: UserTurnProcessor, strategy: Any) -> None:
            await self._record_event(
                TurnEvent.now(
                    TurnEventType.USER_TURN_STOPPED,
                    type(strategy).__name__,
                )
            )

    @property
    def vad_sample_rate_hz(self) -> int:
        return self.config.audio.target_sample_rate_hz

    @property
    def smart_turn_wait_for_transcript(self) -> bool:
        return self.config.realtime.smart_turn.wait_for_transcript

    @property
    def pipeline_processor_names(self) -> tuple[str, str]:
        return (type(self.vad_processor).__name__, type(self.turn_processor).__name__)

    async def start(self) -> None:
        if self._started:
            return

        if self.machine.state is ConversationState.IDLE:
            self.machine.transition(ConversationState.LISTENING, "runtime_started")

        self._runner = WorkerRunner(handle_sigint=False)
        self._ready_event = asyncio.Event()

        @self._runner.event_handler("on_ready")
        async def on_ready(_runner: WorkerRunner) -> None:
            assert self._ready_event is not None
            self._ready_event.set()

        await self._runner.add_workers(self.worker)
        self._runner_task = asyncio.create_task(self._runner.run())
        await asyncio.wait_for(self._ready_event.wait(), timeout=20.0)
        self.stream.start()
        self._feed_task = asyncio.create_task(self._feed_audio())
        self._started = True

    async def stop(self) -> None:
        if not self._started and self._runner_task is None:
            await self.cleanup()
            return

        self.stream.stop()
        try:
            if self._runner_task is not None and not self._runner_task.done():
                await self.worker.queue_frames([EndFrame()])
                await self._runner_task
        finally:
            await self._cancel_feed_task()
            await self.playback.cancel()
            await self.cleanup()
            self._started = False

    async def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        await self.vad.cleanup()
        await self.smart_turn.cleanup()

    async def _feed_audio(self) -> None:
        async for chunk in self.stream.chunks():
            frame = InputAudioRawFrame(
                audio=chunk,
                sample_rate=self.config.audio.target_sample_rate_hz,
                num_channels=1,
            )
            await self.worker.queue_frames([frame])

    async def _cancel_feed_task(self) -> None:
        task = self._feed_task
        self._feed_task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _record_event(self, event: TurnEvent) -> None:
        self.events.append(event)
        if self._on_event_callback is None:
            return
        result = self._on_event_callback(event)
        if result is not None:
            await result

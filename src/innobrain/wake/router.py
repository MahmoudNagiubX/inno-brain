import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum

from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    WakeDetection,
    WakeEngineError,
    WakeEngineHealth,
    WakeWordEngine,
)
from innobrain.wake.ring_buffer import PCMRingBuffer


class WakeRouterMode(StrEnum):
    """Routing modes representing attention and conversation engagement states."""

    SLEEPING = "sleeping"
    ENGAGED = "engaged"
    FOLLOWUP_WINDOW = "followup_window"


@dataclass(frozen=True, slots=True)
class WakeRouterOutput:
    """The result of routing one PCM chunk through the wake router."""

    mode: WakeRouterMode
    detection: WakeDetection | None = None
    downstream_pcm: bytes = b""
    pre_roll_context_pcm: bytes = b""


@dataclass(frozen=True, slots=True)
class WakeRouterHealth:
    """Observable router health including ring buffer duration and engine metrics."""

    ready: bool
    mode: str
    playback_active: bool
    buffered_duration_ms: float
    total_frames_received: int
    total_detections: int
    suppressed_detections_cooldown: int
    suppressed_detections_playback: int
    engine_health: WakeEngineHealth
    degraded: bool
    error_count: int
    recovery_count: int
    last_error: str | None


class WakeAudioRouter:
    """A mode-aware audio router fed by a single PCM microphone stream.

    In SLEEPING:
      - Accumulates audio into a bounded pre-roll ring buffer (~1500 ms) for diagnostics/context.
      - Feeds incoming frames to the local WakeWordEngine.
      - Suppresses detections during robot self-playback or cooldown.
      - Upon detection, downstream_pcm emits ONLY the current detection/continuation chunk
        (never historical pre-wake audio, avoiding background speech leakage to VAD/STT).
      - Catches recoverable engine errors, resets the engine, records recovery health,
        and keeps the router alive without crash-looping.

    In ENGAGED or FOLLOWUP_WINDOW:
      - Bypasses local wake detection (saving CPU and preventing false triggers).
      - Routes incoming PCM directly to downstream consumers (VAD / STT).
      - Keeps the rolling pre-roll buffer fresh.
      - Transitioning back to SLEEPING clears buffered engaged audio so stale session PCM
        cannot survive into a later wake.
    """

    def __init__(
        self,
        engine: WakeWordEngine,
        preroll_ms: int = 1500,
        cooldown_seconds: float = 1.5,
        auto_engage: bool = True,
    ) -> None:
        self._engine = engine
        self._cooldown_seconds = cooldown_seconds
        self._auto_engage = auto_engage

        self._mode = WakeRouterMode.SLEEPING
        self._playback_active = False
        self._ready = True

        self._ring_buffer = PCMRingBuffer(
            capacity_ms=preroll_ms,
            sample_rate_hz=engine.sample_rate_hz,
            bytes_per_sample=2,
        )

        self._last_detection_monotonic: float | None = None
        self._total_frames_received = 0
        self._total_detections = 0
        self._suppressed_detections_cooldown = 0
        self._suppressed_detections_playback = 0
        self._error_count = 0
        self._recovery_count = 0
        self._degraded = False
        self._last_error: str | None = None

    @property
    def mode(self) -> WakeRouterMode:
        return self._mode

    def set_mode(self, mode: WakeRouterMode | str) -> None:
        """Set the router mode (e.g. from attention controller).

        When entering SLEEPING from another mode, clear buffered engaged audio
        and reset engine state to avoid stale session audio leakage.
        """
        new_mode = WakeRouterMode(mode)
        if new_mode == WakeRouterMode.SLEEPING and self._mode != WakeRouterMode.SLEEPING:
            self._ring_buffer.clear()
            self._engine.reset()
        self._mode = new_mode

    @property
    def is_playback_active(self) -> bool:
        return self._playback_active

    def set_playback_active(self, active: bool) -> None:
        """Set self-playback state to suppress wake detection while robot speaks."""
        self._playback_active = active

    def get_pre_roll_history(self) -> bytes:
        """Return diagnostic bounded ring buffer history without treating as user content."""
        return self._ring_buffer.snapshot()

    @property
    def health(self) -> WakeRouterHealth:
        eng_health = self._engine.health
        is_degraded = self._degraded or eng_health.degraded
        return WakeRouterHealth(
            ready=self._ready and eng_health.ready,
            mode=self._mode.value,
            playback_active=self._playback_active,
            buffered_duration_ms=self._ring_buffer.duration_ms,
            total_frames_received=self._total_frames_received,
            total_detections=self._total_detections,
            suppressed_detections_cooldown=self._suppressed_detections_cooldown,
            suppressed_detections_playback=self._suppressed_detections_playback,
            engine_health=eng_health,
            degraded=is_degraded,
            error_count=self._error_count,
            recovery_count=self._recovery_count,
            last_error=self._last_error or eng_health.last_error,
        )

    def route_pcm(self, chunk: bytes) -> WakeRouterOutput:
        """Route a single PCM chunk according to the current mode."""
        if not chunk:
            return WakeRouterOutput(mode=self._mode)

        if len(chunk) % 2 != 0:
            raise ValueError("PCM data length must be a multiple of 2 bytes.")

        self._total_frames_received += 1

        # Engaged / Follow-up: bypass wake engine, stream directly to downstream
        if self._mode in (WakeRouterMode.ENGAGED, WakeRouterMode.FOLLOWUP_WINDOW):
            self._ring_buffer.write(chunk)
            return WakeRouterOutput(
                mode=self._mode,
                detection=None,
                downstream_pcm=chunk,
            )

        # Sleeping mode: buffer pre-roll and evaluate wake engine
        self._ring_buffer.write(chunk)

        if self._playback_active:
            self._suppressed_detections_playback += 1
            return WakeRouterOutput(mode=self._mode, detection=None, downstream_pcm=b"")

        detection: WakeDetection | None = None
        try:
            detection = self._engine.process(chunk)
        except WakeEngineError as err:
            self._error_count += 1
            self._degraded = True
            self._last_error = str(err)
            try:
                self._engine.reset()
                self._recovery_count += 1
            except Exception as reset_err:
                self._last_error = (
                    f"Engine error: {err}; Recovery reset failed: {reset_err}"
                )
            return WakeRouterOutput(mode=self._mode, detection=None, downstream_pcm=b"")

        if detection is None:
            return WakeRouterOutput(mode=self._mode, detection=None, downstream_pcm=b"")

        # Suppress non-canonical labels (confusers)
        if detection.label != CANONICAL_WAKE_LABEL:
            return WakeRouterOutput(mode=self._mode, detection=None, downstream_pcm=b"")

        # Cooldown / duplicate suppression
        now = time.monotonic()
        if (
            self._last_detection_monotonic is not None
            and (now - self._last_detection_monotonic) < self._cooldown_seconds
        ):
            self._suppressed_detections_cooldown += 1
            return WakeRouterOutput(mode=self._mode, detection=None, downstream_pcm=b"")

        # Canonical detection verified
        self._last_detection_monotonic = now
        self._total_detections += 1

        # Diagnostic bounded ring history (diagnostic only, never sent to VAD/STT)
        pre_roll_context = self._ring_buffer.snapshot()

        if self._auto_engage:
            self._mode = WakeRouterMode.ENGAGED

        # downstream_pcm receives only the current detection/continuation chunk
        return WakeRouterOutput(
            mode=self._mode,
            detection=detection,
            downstream_pcm=chunk,
            pre_roll_context_pcm=pre_roll_context,
        )

    async def route_stream(
        self,
        stream: AsyncIterator[bytes],
    ) -> AsyncIterator[WakeRouterOutput]:
        """Asynchronously route an incoming stream of PCM chunks."""
        async for chunk in stream:
            yield self.route_pcm(chunk)

    def reset(self) -> None:
        """Reset internal buffers, cooldown timer, and engine state."""
        self._ring_buffer.clear()
        self._engine.reset()
        self._mode = WakeRouterMode.SLEEPING
        self._playback_active = False
        self._last_detection_monotonic = None
        self._degraded = False
        self._last_error = None

    def close(self) -> None:
        """Close router and underlying engine."""
        self._ready = False
        self._ring_buffer.clear()
        self._engine.close()

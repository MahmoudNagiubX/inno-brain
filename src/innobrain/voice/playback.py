import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

import numpy as np
import sounddevice as sd


class PlaybackBackend(Protocol):
    async def play(self, samples: np.ndarray, sample_rate_hz: int) -> None:
        """Play samples until completion or until stop is requested."""

    async def stop(self) -> None:
        """Stop the active playback, if any."""


class SoundDevicePlaybackBackend:
    async def play(self, samples: np.ndarray, sample_rate_hz: int) -> None:
        sd.play(samples, samplerate=sample_rate_hz, blocking=False)
        await asyncio.to_thread(sd.wait)

    async def stop(self) -> None:
        sd.stop()


@dataclass(frozen=True, slots=True)
class PlaybackSnapshot:
    session_id: int
    started_at_monotonic: float


class PlaybackController:
    def __init__(self, backend: PlaybackBackend) -> None:
        self._backend = backend
        self._next_session_id = 0
        self._active_session_id: int | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def is_playing(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start_tone(
        self,
        frequency_hz: float,
        duration_secs: float,
        volume: float,
        sample_rate_hz: int,
    ) -> PlaybackSnapshot:
        await self.cancel()

        sample_count = int(duration_secs * sample_rate_hz)
        timeline = np.arange(sample_count, dtype=np.float32) / sample_rate_hz
        samples = (
            volume * np.sin(2.0 * np.pi * frequency_hz * timeline)
        ).astype(np.float32)

        self._next_session_id += 1
        session_id = self._next_session_id
        started_at = perf_counter()
        self._active_session_id = session_id
        self._task = asyncio.create_task(
            self._play_session(session_id, samples, sample_rate_hz)
        )
        return PlaybackSnapshot(
            session_id=session_id,
            started_at_monotonic=started_at,
        )

    async def cancel(self) -> None:
        task = self._task
        if task is None:
            return

        await self._backend.stop()
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        if self._task is task:
            self._task = None
            self._active_session_id = None

    async def _play_session(
        self,
        session_id: int,
        samples: np.ndarray,
        sample_rate_hz: int,
    ) -> None:
        try:
            await self._backend.play(samples, sample_rate_hz)
        finally:
            if self._active_session_id == session_id:
                self._task = None
                self._active_session_id = None

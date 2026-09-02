import asyncio
import inspect
from collections.abc import Callable
from typing import Any

import sounddevice as sd


class PCMStreamPlaybackController:
    """Interruptible PCM playback using an injected or sounddevice RawOutputStream."""

    def __init__(self, output_stream_factory: Callable[..., Any] | None = None) -> None:
        self._output_stream_factory = output_stream_factory or sd.RawOutputStream
        self._stream: Any | None = None

    @property
    def is_started(self) -> bool:
        return self._stream is not None

    async def start(self, sample_rate_hz: int = 16000) -> None:
        await self.cancel()
        self._stream = await asyncio.to_thread(
            self._output_stream_factory,
            samplerate=sample_rate_hz,
            channels=1,
            dtype="int16",
        )
        result = self._stream.start()
        if inspect.isawaitable(result):
            await result

    async def write(self, pcm: bytes) -> None:
        if self._stream is None:
            raise RuntimeError("PCM playback has not started")
        result = await asyncio.to_thread(self._stream.write, pcm)
        if inspect.isawaitable(result):
            await result

    async def cancel(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        abort = getattr(stream, "abort", None)
        if abort is not None:
            result = await asyncio.to_thread(abort)
            if inspect.isawaitable(result):
                await result
        close = getattr(stream, "close", None)
        if close is not None:
            result = await asyncio.to_thread(close)
            if inspect.isawaitable(result):
                await result

    async def finish(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        stop = getattr(stream, "stop", None)
        if stop is not None:
            result = await asyncio.to_thread(stop)
            if inspect.isawaitable(result):
                await result
        close = getattr(stream, "close", None)
        if close is not None:
            result = await asyncio.to_thread(close)
            if inspect.isawaitable(result):
                await result

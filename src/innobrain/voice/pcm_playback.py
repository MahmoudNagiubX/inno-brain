import asyncio
import inspect
from collections.abc import Callable
from typing import Any

import sounddevice as sd

from innobrain.audio.devices import resolve_audio_device
from innobrain.audio.models import AudioDevice, AudioDeviceDescriptor, AudioDeviceResolution


class PCMStreamPlaybackController:
    """Interruptible PCM playback using an injected or sounddevice RawOutputStream."""

    def __init__(
        self,
        output_stream_factory: Callable[..., Any] | None = None,
        device: (
            int | str | AudioDeviceDescriptor | AudioDeviceResolution | AudioDevice | None
        ) = None,
    ) -> None:
        self._output_stream_factory = output_stream_factory or sd.RawOutputStream
        self._device = device
        self._stream: Any | None = None

    @property
    def device(self) -> Any:
        return self._device

    @property
    def is_started(self) -> bool:
        return self._stream is not None

    async def start(self, sample_rate_hz: int = 16000) -> None:
        await self.cancel()
        resolved_device_index: int | None = None
        if self._device is not None:
            if isinstance(self._device, AudioDeviceResolution):
                resolved_device_index = self._device.device_index
            elif isinstance(self._device, AudioDevice):
                resolved_device_index = self._device.index
            elif isinstance(self._device, int):
                resolved_device_index = self._device
            else:
                resolution = resolve_audio_device(
                    self._device,
                    direction="playback",
                    sample_rate_hz=sample_rate_hz,
                    channels=1,
                    sample_format="int16",
                )
                resolved_device_index = resolution.device_index

        kwargs: dict[str, Any] = {
            "samplerate": sample_rate_hz,
            "channels": 1,
            "dtype": "int16",
        }
        if resolved_device_index is not None:
            kwargs["device"] = resolved_device_index

        self._stream = await asyncio.to_thread(
            self._output_stream_factory,
            **kwargs,
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

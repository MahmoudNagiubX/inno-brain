import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import sounddevice as sd

from .devices import get_default_device_indices, resolve_audio_device, validate_device_format
from .models import AudioDevice, AudioDeviceDescriptor, AudioDeviceResolution


@dataclass(frozen=True, slots=True)
class AudioStreamStats:
    received_chunks: int
    dropped_chunks: int
    selected_device_name: str | None = None
    selected_host_api: str | None = None


class SoundDevicePCMStream:
    def __init__(
        self,
        sample_rate_hz: int = 16000,
        frame_ms: int = 20,
        device: (
            int | str | AudioDeviceDescriptor | AudioDeviceResolution | AudioDevice | None
        ) = None,
        queue_max_chunks: int = 100,
        input_stream_factory: Callable[..., Any] | None = None,
    ) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        if queue_max_chunks <= 0:
            raise ValueError("queue_max_chunks must be positive")

        self.sample_rate_hz = sample_rate_hz
        self.frame_ms = frame_ms
        self.block_frames = round(sample_rate_hz * frame_ms / 1000)
        self.device = device
        self._input_stream_factory = input_stream_factory or sd.RawInputStream
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(
            maxsize=queue_max_chunks
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: Any = None
        self._accepting = False
        self._received_chunks = 0
        self._dropped_chunks = 0
        self._selected_device_name: str | None = None
        self._selected_host_api: str | None = None

    @property
    def stats(self) -> AudioStreamStats:
        return AudioStreamStats(
            received_chunks=self._received_chunks,
            dropped_chunks=self._dropped_chunks,
            selected_device_name=self._selected_device_name,
            selected_host_api=self._selected_host_api,
        )

    def start(self) -> None:
        if self._accepting:
            return

        self._loop = asyncio.get_running_loop()
        self._accepting = True
        self._selected_device_name = None
        self._selected_host_api = None
        try:
            resolved_index: int | None = None
            resolved_device: AudioDevice | AudioDeviceResolution | None = None
            if self.device is not None:
                if isinstance(self.device, AudioDeviceResolution):
                    resolved_index = self.device.device_index
                    resolved_device = self.device
                elif isinstance(self.device, AudioDevice):
                    resolved_index = self.device.index
                    resolved_device = self.device
                elif isinstance(self.device, int):
                    resolved_index = self.device
                else:
                    resolution = resolve_audio_device(
                        self.device,
                        direction="capture",
                        sample_rate_hz=self.sample_rate_hz,
                        channels=1,
                        sample_format="int16",
                    )
                    resolved_index = resolution.device_index
                    resolved_device = resolution
            else:
                default_in, _ = get_default_device_indices()
                if default_in is not None:
                    validate_device_format(
                        default_in,
                        direction="capture",
                        sample_rate_hz=self.sample_rate_hz,
                        channels=1,
                        sample_format="int16",
                    )
                    resolved_index = default_in

            if resolved_device is not None:
                self._selected_device_name = resolved_device.device_name if isinstance(
                    resolved_device, AudioDeviceResolution
                ) else resolved_device.name
                self._selected_host_api = (
                    resolved_device.host_api_name
                    if isinstance(resolved_device, AudioDeviceResolution)
                    else resolved_device.host_api_name
                )

            self._stream = self._input_stream_factory(
                samplerate=self.sample_rate_hz,
                blocksize=self.block_frames,
                device=resolved_index,
                channels=1,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self._accepting = False
            self._stream = None
            self._selected_device_name = None
            self._selected_host_api = None
            raise

    def stop(self) -> None:
        if not self._accepting and self._stream is None:
            self._enqueue_stop()
            return

        self._accepting = False
        stream = self._stream
        self._stream = None
        if stream is not None:
            stream.stop()
            stream.close()

        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._enqueue_stop)
        else:
            self._enqueue_stop()

    async def chunks(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk

    def enqueue_chunk(self, chunk: bytes) -> None:
        """Enqueue one copied PCM chunk on the event-loop side."""
        self._received_chunks += 1
        if self._queue.full():
            self._queue.get_nowait()
            self._dropped_chunks += 1
        self._queue.put_nowait(bytes(chunk))

    def _callback(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del frames, time_info, status
        loop = self._loop
        if not self._accepting or loop is None:
            return
        try:
            chunk = bytes(indata)
            loop.call_soon_threadsafe(self.enqueue_chunk, chunk)
        except RuntimeError:
            return

    def _enqueue_stop(self) -> None:
        if self._queue.full():
            self._queue.get_nowait()
            self._dropped_chunks += 1
        self._queue.put_nowait(None)

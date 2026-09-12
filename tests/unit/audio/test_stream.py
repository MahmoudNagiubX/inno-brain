import pytest

from innobrain.audio.models import (
    AudioDevice,
    AudioDeviceDescriptor,
    AudioDeviceResolution,
)
from innobrain.audio.stream import SoundDevicePCMStream


class FakeInputStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_enqueue_increments_received() -> None:
    stream = SoundDevicePCMStream(queue_max_chunks=2)

    stream.enqueue_chunk(b"one")

    assert stream.stats.received_chunks == 1
    assert stream.stats.dropped_chunks == 0
    assert await anext(stream.chunks()) == b"one"


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_chunk() -> None:
    stream = SoundDevicePCMStream(queue_max_chunks=2)

    stream.enqueue_chunk(b"one")
    stream.enqueue_chunk(b"two")
    stream.enqueue_chunk(b"three")

    assert stream.stats.received_chunks == 3
    assert stream.stats.dropped_chunks == 1
    assert [await anext(stream.chunks()), await anext(stream.chunks())] == [
        b"two",
        b"three",
    ]


@pytest.mark.asyncio
async def test_stop_sentinel_terminates_async_iterator() -> None:
    stream = SoundDevicePCMStream(queue_max_chunks=2)
    stream.stop()

    chunks = []
    async for chunk in stream.chunks():
        chunks.append(chunk)

    assert chunks == []


def test_sounddevice_callback_only_enqueues_raw_pcm_without_gate() -> None:
    class FakeLoop:
        def __init__(self) -> None:
            self.calls = []

        def call_soon_threadsafe(self, callback, chunk) -> None:
            self.calls.append((callback, chunk))

    stream = SoundDevicePCMStream()
    loop = FakeLoop()
    stream._loop = loop
    stream._accepting = True

    stream._callback(memoryview(b"\x01\x00"), 1, None, None)

    assert len(loop.calls) == 1
    assert loop.calls[0][1] == b"\x01\x00"


@pytest.mark.asyncio
async def test_sounddevice_pcm_stream_receives_resolved_input_device_and_passes_to_factory(
    monkeypatch,
) -> None:
    streams = []

    def factory(**kwargs):
        stream = FakeInputStream(**kwargs)
        streams.append(stream)
        return stream

    # 1. With integer index
    stream_idx = SoundDevicePCMStream(device=1, input_stream_factory=factory)
    stream_idx.start()
    assert streams[0].kwargs["device"] == 1
    stream_idx.stop()

    # 2. With AudioDeviceResolution
    dummy_dev = AudioDevice(2, "Anker PowerConf S330", 1, 0, 16000.0, "MME", 0)
    res = AudioDeviceResolution(
        device_index=2,
        device_name=dummy_dev.name,
        host_api_name="MME",
        direction="capture",
        sample_rate_hz=16000,
        channels=1,
        sample_format="int16",
        device=dummy_dev,
    )
    streams.clear()
    stream_res = SoundDevicePCMStream(device=res, input_stream_factory=factory)
    stream_res.start()
    assert streams[0].kwargs["device"] == 2
    stream_res.stop()

    # 3. With descriptor resolved at start time
    monkeypatch.setattr(
        "innobrain.audio.stream.resolve_audio_device",
        lambda *args, **kwargs: res,
    )
    streams.clear()
    desc = AudioDeviceDescriptor(name_pattern="S330", host_api="MME")
    stream_desc = SoundDevicePCMStream(device=desc, input_stream_factory=factory)
    stream_desc.start()
    assert streams[0].kwargs["device"] == 2
    assert stream_desc.stats.selected_device_name == "Anker PowerConf S330"
    assert stream_desc.stats.selected_host_api == "MME"
    stream_desc.stop()

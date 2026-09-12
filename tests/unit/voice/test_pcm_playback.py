import pytest

from innobrain.audio.models import (
    AudioDevice,
    AudioDeviceDescriptor,
    AudioDeviceResolution,
)
from innobrain.voice.pcm_playback import PCMStreamPlaybackController


class FakeOutputStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.writes = []
        self.aborted = False
        self.stopped = False
        self.closed = False

    def start(self):
        self.started = True

    def write(self, pcm):
        self.writes.append(pcm)

    def abort(self):
        self.aborted = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_pcm_playback_uses_raw_output_stream_and_can_cancel():
    streams = []

    def factory(**kwargs):
        stream = FakeOutputStream(**kwargs)
        streams.append(stream)
        return stream

    controller = PCMStreamPlaybackController(factory)
    await controller.start()
    await controller.write(b"pcm")
    await controller.cancel()

    assert streams[0].kwargs == {"samplerate": 16000, "channels": 1, "dtype": "int16"}
    assert streams[0].writes == [b"pcm"]
    assert streams[0].aborted is True
    assert streams[0].closed is True
    assert controller.is_started is False


@pytest.mark.asyncio
async def test_pcm_playback_passes_resolved_output_device_to_factory():
    streams = []

    def factory(**kwargs):
        stream = FakeOutputStream(**kwargs)
        streams.append(stream)
        return stream

    # 1. With integer index
    controller = PCMStreamPlaybackController(factory, device=5)
    await controller.start(sample_rate_hz=16000)
    await controller.cancel()

    assert streams[0].kwargs == {
        "samplerate": 16000,
        "channels": 1,
        "dtype": "int16",
        "device": 5,
    }

    # 2. With AudioDeviceResolution object
    dummy_dev = AudioDevice(5, "Speakers (Anker PowerConf S330)", 0, 2, 48000.0, "MME", 0)
    res = AudioDeviceResolution(
        device_index=5,
        device_name="Speakers (Anker PowerConf S330)",
        host_api_name="MME",
        direction="playback",
        sample_rate_hz=16000,
        channels=1,
        sample_format="int16",
        device=dummy_dev,
    )
    streams.clear()
    controller_res = PCMStreamPlaybackController(factory, device=res)
    await controller_res.start(sample_rate_hz=16000)
    await controller_res.cancel()

    assert streams[0].kwargs["device"] == 5


@pytest.mark.asyncio
async def test_pcm_playback_resolves_descriptor_when_passed_directly(monkeypatch):
    streams = []

    def factory(**kwargs):
        stream = FakeOutputStream(**kwargs)
        streams.append(stream)
        return stream

    dummy_dev = AudioDevice(7, "Speakers (Anker PowerConf S330)", 0, 2, 48000.0, "MME", 0)
    monkeypatch.setattr(
        "innobrain.voice.pcm_playback.resolve_audio_device",
        lambda *args, **kwargs: AudioDeviceResolution(
            device_index=7,
            device_name=dummy_dev.name,
            host_api_name="MME",
            direction="playback",
            sample_rate_hz=16000,
            channels=1,
            sample_format="int16",
            device=dummy_dev,
        ),
    )

    desc = AudioDeviceDescriptor(name_pattern="Anker PowerConf S330", host_api="MME")
    controller = PCMStreamPlaybackController(factory, device=desc)
    await controller.start()
    await controller.cancel()

    assert streams[0].kwargs["device"] == 7

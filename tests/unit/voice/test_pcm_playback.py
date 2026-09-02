import pytest

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

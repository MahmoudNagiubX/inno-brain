import asyncio

import pytest

from innobrain.voice.playback import PlaybackController


class FakePlaybackBackend:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.release = asyncio.Event()

    async def play(self, samples, sample_rate_hz: int) -> None:
        self.started += 1
        await self.release.wait()

    async def stop(self) -> None:
        self.stopped += 1
        self.release.set()


@pytest.mark.asyncio
async def test_new_playback_cancels_existing_session() -> None:
    backend = FakePlaybackBackend()
    controller = PlaybackController(backend=backend)

    first = await controller.start_tone(
        frequency_hz=440.0,
        duration_secs=5.0,
        volume=0.05,
        sample_rate_hz=16000,
    )
    await asyncio.sleep(0)

    second = await controller.start_tone(
        frequency_hz=500.0,
        duration_secs=5.0,
        volume=0.05,
        sample_rate_hz=16000,
    )
    await asyncio.sleep(0)

    assert first.session_id != second.session_id
    assert backend.stopped >= 1

    await controller.cancel()

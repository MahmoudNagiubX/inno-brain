import pytest

from innobrain.audio.stream import SoundDevicePCMStream


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

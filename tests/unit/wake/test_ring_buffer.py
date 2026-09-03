import pytest

from innobrain.wake.ring_buffer import PCMRingBuffer


def test_default_buffer_capacity() -> None:
    buf = PCMRingBuffer()
    assert buf.sample_rate_hz == 16000
    assert buf.bytes_per_sample == 2
    assert buf.capacity_ms == 1500
    # 1.5s * 16000 * 2 = 48000 bytes
    assert buf.capacity_bytes == 48000
    assert buf.capacity_samples == 24000
    assert len(buf) == 0
    assert buf.duration_ms == 0.0


def test_write_and_read_all() -> None:
    buf = PCMRingBuffer(capacity_ms=100)  # 100ms = 0.1 * 16000 * 2 = 3200 bytes
    data = b"\x01\x00" * 800  # 800 samples = 1600 bytes = 50ms
    buf.write(data)

    assert len(buf) == 1600
    assert buf.length_samples == 800
    assert buf.duration_ms == 50.0
    assert buf.read_all() == data


def test_bounded_overflow_drops_oldest() -> None:
    # 10ms = 160 samples = 320 bytes capacity
    buf = PCMRingBuffer(capacity_ms=10)
    assert buf.capacity_bytes == 320

    chunk1 = b"\x01\x00" * 160  # 320 bytes
    chunk2 = b"\x02\x00" * 80  # 160 bytes

    buf.write(chunk1)
    assert len(buf) == 320
    assert buf.read_all() == chunk1

    buf.write(chunk2)
    assert len(buf) == 320
    # Oldest 160 bytes dropped, so second half of chunk1 + chunk2
    expected = (b"\x01\x00" * 80) + chunk2
    assert buf.read_all() == expected


def test_read_last() -> None:
    buf = PCMRingBuffer(capacity_ms=1500)
    # Write 100ms = 3200 bytes: 50ms of 1s, 50ms of 2s
    part1 = b"\x01\x00" * 800
    part2 = b"\x02\x00" * 800
    buf.write(part1 + part2)

    # Read last 50ms
    last_50ms = buf.read_last(50)
    assert last_50ms == part2
    assert len(last_50ms) == 1600

    # Read last 200ms when only 100ms is available returns all 100ms
    assert buf.read_last(200) == part1 + part2


def test_snapshot_and_drain() -> None:
    buf = PCMRingBuffer(capacity_ms=500)
    data = b"\xaa\xbb" * 100
    buf.write(data)

    snapshot = buf.snapshot()
    assert snapshot == data
    assert len(buf) == len(data)

    drained = buf.drain()
    assert drained == data
    assert len(buf) == 0
    assert buf.duration_ms == 0.0


def test_clear() -> None:
    buf = PCMRingBuffer(capacity_ms=500)
    buf.write(b"\x10\x20" * 50)
    assert len(buf) > 0

    buf.clear()
    assert len(buf) == 0
    assert buf.read_all() == b""


def test_odd_byte_handling() -> None:
    buf = PCMRingBuffer(capacity_ms=100)
    with pytest.raises(ValueError, match="multiple of bytes_per_sample"):
        buf.write(b"\x01\x02\x03")

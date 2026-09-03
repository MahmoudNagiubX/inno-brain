import threading


class PCMRingBuffer:
    """A bounded FIFO ring buffer for 16-bit linear PCM audio.

    Maintains approximately 1.5 seconds (or configured capacity_ms) of audio
    pre-roll and continuation for same-breath command preservation.
    """

    def __init__(
        self,
        capacity_ms: int = 1500,
        sample_rate_hz: int = 16000,
        bytes_per_sample: int = 2,
    ) -> None:
        if capacity_ms <= 0:
            raise ValueError("capacity_ms must be positive")
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if bytes_per_sample <= 0:
            raise ValueError("bytes_per_sample must be positive")

        self._sample_rate_hz = sample_rate_hz
        self._bytes_per_sample = bytes_per_sample
        self._capacity_ms = capacity_ms
        self._capacity_bytes = int((sample_rate_hz * bytes_per_sample * capacity_ms) / 1000)
        # Ensure capacity_bytes is an exact multiple of bytes_per_sample
        self._capacity_bytes -= self._capacity_bytes % bytes_per_sample

        self._buffer = bytearray()
        self._lock = threading.Lock()

    @property
    def sample_rate_hz(self) -> int:
        return self._sample_rate_hz

    @property
    def bytes_per_sample(self) -> int:
        return self._bytes_per_sample

    @property
    def capacity_ms(self) -> int:
        return self._capacity_ms

    @property
    def capacity_bytes(self) -> int:
        return self._capacity_bytes

    @property
    def capacity_samples(self) -> int:
        return self._capacity_bytes // self._bytes_per_sample

    @property
    def length_samples(self) -> int:
        with self._lock:
            return len(self._buffer) // self._bytes_per_sample

    @property
    def duration_ms(self) -> float:
        with self._lock:
            bytes_per_sec = self._sample_rate_hz * self._bytes_per_sample
            return (len(self._buffer) / bytes_per_sec) * 1000.0

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    def write(self, data: bytes) -> None:
        """Append PCM bytes, dropping oldest bytes if capacity is exceeded."""
        if not data:
            return
        if len(data) % self._bytes_per_sample != 0:
            raise ValueError(
                f"Data length ({len(data)}) must be a multiple of bytes_per_sample "
                f"({self._bytes_per_sample})"
            )

        with self._lock:
            self._buffer.extend(data)
            overflow = len(self._buffer) - self._capacity_bytes
            if overflow > 0:
                del self._buffer[:overflow]

    def read_all(self) -> bytes:
        """Return a copy of all PCM bytes currently in the buffer."""
        with self._lock:
            return bytes(self._buffer)

    def read_last(self, duration_ms: int) -> bytes:
        """Return the most recent audio up to duration_ms."""
        if duration_ms <= 0:
            return b""
        with self._lock:
            bytes_per_sec = self._sample_rate_hz * self._bytes_per_sample
            req_bytes = int((bytes_per_sec * duration_ms) / 1000)
            req_bytes -= req_bytes % self._bytes_per_sample
            if req_bytes >= len(self._buffer):
                return bytes(self._buffer)
            return bytes(self._buffer[-req_bytes:])

    def snapshot(self) -> bytes:
        """Return a copy of all current bytes without clearing the buffer."""
        return self.read_all()

    def drain(self) -> bytes:
        """Return all current bytes and reset the buffer to empty."""
        with self._lock:
            data = bytes(self._buffer)
            self._buffer.clear()
            return data

    def clear(self) -> None:
        """Clear all buffered audio."""
        with self._lock:
            self._buffer.clear()

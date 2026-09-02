import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


def record_mono(
    duration_seconds: float,
    sample_rate_hz: int,
    device: int | str | None = None,
) -> np.ndarray:
    frames = int(duration_seconds * sample_rate_hz)

    audio = sd.rec(
        frames=frames,
        samplerate=sample_rate_hz,
        channels=1,
        dtype="int16",
        device=device,
        blocking=True,
    )

    return np.asarray(audio, dtype=np.int16).reshape(-1)


def play_mono(
    samples: np.ndarray,
    sample_rate_hz: int,
    device: int | str | None = None,
) -> None:
    sd.play(
        np.asarray(samples, dtype=np.int16),
        samplerate=sample_rate_hz,
        device=device,
        blocking=True,
    )


def write_pcm16_wav(
    path: Path,
    samples: np.ndarray,
    sample_rate_hz: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    mono = np.asarray(samples, dtype=np.int16).reshape(-1)

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(mono.tobytes())


def read_pcm16_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1:
            raise ValueError("Expected mono WAV")
        if wav.getsampwidth() != 2:
            raise ValueError("Expected 16-bit PCM WAV")

        sample_rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())

    return np.frombuffer(raw, dtype=np.int16).copy(), sample_rate

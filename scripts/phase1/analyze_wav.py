import argparse
import wave
from pathlib import Path

import numpy as np


def analyze(path: Path) -> dict[str, float | int]:
    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        frame_count = wav.getnframes()
        sample_width = wav.getsampwidth()
        raw = wav.readframes(frame_count)

    if sample_width != 2:
        raise ValueError("Expected 16-bit PCM WAV")

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    absolute = np.abs(samples)
    rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
    peak = float(np.max(absolute)) if samples.size else 0.0
    clipping_percentage = float(np.mean(absolute >= 32767) * 100) if samples.size else 0.0

    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "duration_seconds": frame_count / sample_rate if sample_rate else 0.0,
        "rms": rms,
        "peak": peak,
        "clipping_percentage": clipping_percentage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze PCM16 WAV metadata and amplitude.")
    parser.add_argument("wav", type=Path)
    args = parser.parse_args()

    result = analyze(args.wav)
    print(f"Sample rate: {result['sample_rate_hz']} Hz")
    print(f"Channels: {result['channels']}")
    print(f"Duration: {result['duration_seconds']:.3f} s")
    print(f"RMS: {result['rms']:.3f}")
    print(f"Peak: {result['peak']:.3f}")
    print(f"Clipping: {result['clipping_percentage']:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

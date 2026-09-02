import argparse
from pathlib import Path

from innobrain.audio import get_default_device_indices
from innobrain.audio.io import play_mono, read_pcm16_wav


def _parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Play a mono PCM16 WAV on the laptop output.")
    parser.add_argument("wav", type=Path)
    parser.add_argument("--device")
    args = parser.parse_args()

    device = _parse_device(args.device)
    _, default_output = get_default_device_indices()
    selected_output = (
        args.device if args.device is not None else f"OS default (index {default_output})"
    )
    samples, sample_rate = read_pcm16_wav(args.wav)
    print(f"Selected output: {selected_output}")
    play_mono(samples, sample_rate, device=device)
    print(f"Played: {args.wav.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

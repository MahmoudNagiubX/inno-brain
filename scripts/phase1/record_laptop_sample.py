import argparse
import time
from pathlib import Path

from innobrain.audio import get_default_device_indices
from innobrain.audio.io import record_mono, write_pcm16_wav


def _parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a mono PCM16 sample from the laptop.")
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device")
    args = parser.parse_args()

    device = _parse_device(args.device)
    default_input, default_output = get_default_device_indices()
    selected_input = (
        args.device if args.device is not None else f"OS default (index {default_input})"
    )
    print(f"Selected input: {selected_input}")
    print(f"OS default output index: {default_output}")

    for count in (3, 2, 1):
        print(f"{count}...", flush=True)
        time.sleep(1)

    samples = record_mono(args.seconds, args.sample_rate, device=device)
    write_pcm16_wav(args.output, samples, args.sample_rate)
    print(f"Saved: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

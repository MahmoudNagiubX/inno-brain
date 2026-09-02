from collections.abc import Iterable

import sounddevice as sd

from .models import AudioDevice


def normalize_devices(raw_devices: Iterable[dict[str, object]]) -> list[AudioDevice]:
    devices: list[AudioDevice] = []

    for index, raw in enumerate(raw_devices):
        devices.append(
            AudioDevice(
                index=index,
                name=str(raw["name"]),
                max_input_channels=int(raw["max_input_channels"]),
                max_output_channels=int(raw["max_output_channels"]),
                default_sample_rate=float(raw["default_samplerate"]),
            )
        )

    return devices


def list_audio_devices() -> list[AudioDevice]:
    return normalize_devices(sd.query_devices())


def get_default_device_indices() -> tuple[int | None, int | None]:
    default = sd.default.device

    try:
        raw_input_index = default[0]
        raw_output_index = default[1]
    except (IndexError, KeyError, TypeError):
        return None, None

    input_index = _normalize_device_index(raw_input_index)
    output_index = _normalize_device_index(raw_output_index)

    return input_index, output_index


def _normalize_device_index(value: object) -> int | None:
    if value is None:
        return None

    try:
        index = int(value)
    except (TypeError, ValueError):
        return None

    return index if index >= 0 else None

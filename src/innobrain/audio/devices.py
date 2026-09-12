import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal

import sounddevice as sd

from .models import (
    AudioDevice,
    AudioDeviceAmbiguityError,
    AudioDeviceCapabilityError,
    AudioDeviceDescriptor,
    AudioDeviceNotFoundError,
    AudioDeviceResolution,
    coerce_audio_device_descriptor,
)


def normalize_devices(
    raw_devices: Iterable[dict[str, object]],
    raw_hostapis: Sequence[dict[str, object]] | None = None,
) -> list[AudioDevice]:
    devices: list[AudioDevice] = []

    host_api_lookup: dict[int, str] = {}
    if raw_hostapis is not None:
        for idx, h in enumerate(raw_hostapis):
            if isinstance(h, dict) and "name" in h:
                host_api_lookup[idx] = str(h["name"])

    for index, raw in enumerate(raw_devices):
        host_api_idx: int | None = None
        if "hostapi" in raw and raw["hostapi"] is not None:
            try:
                host_api_idx = int(raw["hostapi"])  # type: ignore[arg-type]
            except (ValueError, TypeError):
                host_api_idx = None

        host_api_name: str | None = None
        if "host_api_name" in raw and raw["host_api_name"] is not None:
            host_api_name = str(raw["host_api_name"])
        elif host_api_idx is not None and host_api_idx in host_api_lookup:
            host_api_name = host_api_lookup[host_api_idx]

        devices.append(
            AudioDevice(
                index=index,
                name=str(raw["name"]),
                max_input_channels=int(raw["max_input_channels"]),  # type: ignore[arg-type]
                max_output_channels=int(raw["max_output_channels"]),  # type: ignore[arg-type]
                default_sample_rate=float(raw["default_samplerate"]),  # type: ignore[arg-type]
                host_api_name=host_api_name,
                host_api_index=host_api_idx,
            )
        )

    return devices


def list_host_apis() -> list[dict[str, object]]:
    try:
        raw = sd.query_hostapis()
        return list(raw) if isinstance(raw, (list, tuple)) else []
    except Exception:
        return []


def list_audio_devices() -> list[AudioDevice]:
    try:
        raw_hostapis = sd.query_hostapis()
    except Exception:
        raw_hostapis = ()
    return normalize_devices(sd.query_devices(), raw_hostapis=raw_hostapis)


def get_default_device_indices() -> tuple[int | None, int | None]:
    try:
        default = sd.default.device
    except Exception:
        return None, None

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
        index = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

    return index if index >= 0 else None


def validate_device_format(
    device_index: int,
    direction: Literal["capture", "playback"],
    *,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    sample_format: str = "int16",
    check_func: Callable[..., Any] | None = None,
    device_name: str | None = None,
    host_api_name: str | None = None,
) -> None:
    """Validate that the requested audio format is supported by the device before opening."""
    target_name = device_name or f"device #{device_index}"
    target_host_api = host_api_name or "unknown"
    try:
        if check_func is not None:
            check_func(
                device=device_index,
                samplerate=sample_rate_hz,
                channels=channels,
                dtype=sample_format,
            )
        elif direction == "capture":
            sd.check_input_settings(
                device=device_index,
                samplerate=sample_rate_hz,
                channels=channels,
                dtype=sample_format,
            )
        else:
            sd.check_output_settings(
                device=device_index,
                samplerate=sample_rate_hz,
                channels=channels,
                dtype=sample_format,
            )
    except Exception as exc:
        msg = (
            f"Audio device '{target_name}' (host API: '{target_host_api}') "
            f"does not support {direction} format "
            f"({sample_rate_hz} Hz, {channels} ch, '{sample_format}'): {exc}"
        )
        raise AudioDeviceCapabilityError(msg) from exc


def _matches_pattern(pattern: str, name: str) -> bool:
    p_lower = pattern.lower()
    n_lower = name.lower()
    if p_lower in n_lower:
        return True
    try:
        return bool(re.search(pattern, name, re.IGNORECASE))
    except re.error:
        return False


def _matches_host_api(target_api: str, device_api: str | None) -> bool:
    if device_api is None:
        return False
    t = target_api.strip().lower()
    d = device_api.strip().lower()
    return t == d or t in d or d in t


def resolve_audio_device(
    descriptor: AudioDeviceDescriptor | dict[str, Any] | str | int | None,
    direction: Literal["capture", "playback"],
    *,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    sample_format: str = "int16",
    preferred_host_api: str | None = None,
    devices: list[AudioDevice] | None = None,
    check_capability: bool = True,
    check_func: Callable[..., Any] | None = None,
    default_indices: tuple[int | None, int | None] | None = None,
) -> AudioDeviceResolution:
    """Resolve audio descriptor to active numeric index and AudioDeviceResolution.

    Validates format capability before returning and raises actionable errors
    on no-match or ambiguity.
    """
    all_devices = list_audio_devices() if devices is None else devices
    defaults = get_default_device_indices() if default_indices is None else default_indices

    # 1. Direct integer index
    if isinstance(descriptor, int):
        matching = [d for d in all_devices if d.index == descriptor]
        if not matching:
            raise AudioDeviceNotFoundError(
                f"Audio device index {descriptor} not found among enumerated devices"
            )
        candidate = matching[0]
        if check_capability:
            validate_device_format(
                candidate.index,
                direction,
                sample_rate_hz=sample_rate_hz,
                channels=channels,
                sample_format=sample_format,
                check_func=check_func,
                device_name=candidate.name,
                host_api_name=candidate.host_api_name,
            )
        return AudioDeviceResolution(
            device_index=candidate.index,
            device_name=candidate.name,
            host_api_name=candidate.host_api_name,
            direction=direction,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            sample_format=sample_format,
            device=candidate,
        )

    # 2. Coerce descriptor or None
    desc = coerce_audio_device_descriptor(
        descriptor,
        direction=direction,
        channels=channels,
        sample_rate_hz=sample_rate_hz,
        sample_format=sample_format,
    )

    # If descriptor is None or has no pattern, resolve to default device
    if desc is None or desc.name_pattern is None:
        def_idx = defaults[0] if direction == "capture" else defaults[1]
        if def_idx is None:
            raise AudioDeviceNotFoundError(
                f"No default audio {direction} device available on the system"
            )
        matching_default = [d for d in all_devices if d.index == def_idx]
        if not matching_default:
            raise AudioDeviceNotFoundError(
                f"Default audio {direction} device index {def_idx} not found in enumerated devices"
            )
        candidate = matching_default[0]
        target_rate = (desc.sample_rate_hz if desc else None) or sample_rate_hz
        target_channels = (desc.channels if desc else None) or channels
        target_format = (desc.sample_format if desc else None) or sample_format
        if check_capability:
            validate_device_format(
                candidate.index,
                direction,
                sample_rate_hz=target_rate,
                channels=target_channels,
                sample_format=target_format,
                check_func=check_func,
                device_name=candidate.name,
                host_api_name=candidate.host_api_name,
            )
        return AudioDeviceResolution(
            device_index=candidate.index,
            device_name=candidate.name,
            host_api_name=candidate.host_api_name,
            direction=direction,
            sample_rate_hz=target_rate,
            channels=target_channels,
            sample_format=target_format,
            device=candidate,
        )

    # 3. Pattern-based resolution
    target_rate = desc.sample_rate_hz or sample_rate_hz
    target_channels = desc.channels or channels
    target_format = desc.sample_format or sample_format
    target_host_api = desc.host_api or preferred_host_api
    target_pattern = desc.name_pattern

    # Direction and channel filtering
    if direction == "capture":
        direction_devices = [d for d in all_devices if d.can_capture]
    else:
        direction_devices = [d for d in all_devices if d.can_playback]

    # Name pattern filtering
    name_matched = [d for d in direction_devices if _matches_pattern(target_pattern, d.name)]
    if not name_matched:
        available = [f"'{d.name}' ({d.host_api_name or 'unknown API'})" for d in direction_devices]
        raise AudioDeviceNotFoundError(
            f"No matching audio {direction} device found for pattern '{target_pattern}'. "
            f"Available {direction} devices: [{', '.join(available)}]"
        )

    # Host API filtering if specified or preferred
    if target_host_api is not None:
        host_matched = [
            d for d in name_matched if _matches_host_api(target_host_api, d.host_api_name)
        ]
        if not host_matched:
            found_apis = sorted({d.host_api_name for d in name_matched if d.host_api_name})
            raise AudioDeviceNotFoundError(
                f"Audio {direction} device matching '{target_pattern}' was found, "
                f"but not on requested host API '{target_host_api}'. "
                f"Matching devices exist on host APIs: {found_apis}"
            )
        candidates = host_matched
    else:
        candidates = name_matched

    # Check for ambiguity
    if len(candidates) > 1:
        summaries = [f"'{d.name}' (host_api='{d.host_api_name}')" for d in candidates]
        raise AudioDeviceAmbiguityError(
            f"Ambiguous audio {direction} device for pattern '{target_pattern}': "
            f"{len(candidates)} matching devices found [{', '.join(summaries)}]. "
            "Specify 'host_api' in descriptor to resolve ambiguity."
        )

    candidate = candidates[0]
    if check_capability:
        validate_device_format(
            candidate.index,
            direction,
            sample_rate_hz=target_rate,
            channels=target_channels,
            sample_format=target_format,
            check_func=check_func,
            device_name=candidate.name,
            host_api_name=candidate.host_api_name,
        )

    return AudioDeviceResolution(
        device_index=candidate.index,
        device_name=candidate.name,
        host_api_name=candidate.host_api_name,
        direction=direction,
        sample_rate_hz=target_rate,
        channels=target_channels,
        sample_format=target_format,
        device=candidate,
    )


def resolve_audio_devices(
    audio_config: Any,
    *,
    devices: list[AudioDevice] | None = None,
    check_capability: bool = True,
    check_input_func: Callable[..., Any] | None = None,
    check_output_func: Callable[..., Any] | None = None,
    default_indices: tuple[int | None, int | None] | None = None,
) -> tuple[AudioDeviceResolution | None, AudioDeviceResolution | None]:
    """Coordinated resolution of both input and output audio descriptors.

    If input resolves to a specific host API and output does not explicitly specify one,
    the output resolution prefers the same host API family for full-duplex pairing (e.g. S330).
    """
    all_devices = list_audio_devices() if devices is None else devices
    defaults = get_default_device_indices() if default_indices is None else default_indices

    resolved_input: AudioDeviceResolution | None = None
    if audio_config.input_device is not None:
        resolved_input = resolve_audio_device(
            audio_config.input_device,
            direction="capture",
            sample_rate_hz=audio_config.target_sample_rate_hz,
            channels=audio_config.channels,
            devices=all_devices,
            check_capability=check_capability,
            check_func=check_input_func,
            default_indices=defaults,
        )

    preferred_host_api = resolved_input.host_api_name if resolved_input is not None else None

    resolved_output: AudioDeviceResolution | None = None
    if audio_config.output_device is not None:
        resolved_output = resolve_audio_device(
            audio_config.output_device,
            direction="playback",
            sample_rate_hz=audio_config.target_sample_rate_hz,
            channels=audio_config.channels,
            preferred_host_api=preferred_host_api,
            devices=all_devices,
            check_capability=check_capability,
            check_func=check_output_func,
            default_indices=defaults,
        )

    return resolved_input, resolved_output


def diagnose_audio_devices(
    audio_config: Any | None = None,
    *,
    devices: list[AudioDevice] | None = None,
    host_apis: Sequence[dict[str, object]] | None = None,
    default_indices: tuple[int | None, int | None] | None = None,
) -> dict[str, Any]:
    """Inspect audio subsystem offline and produce safe diagnostic data without secrets/indexes."""
    all_devices = list_audio_devices() if devices is None else devices
    all_host_apis = list_host_apis() if host_apis is None else list(host_apis)
    defaults = get_default_device_indices() if default_indices is None else default_indices

    host_api_names = [
        str(h["name"]) for h in all_host_apis if isinstance(h, dict) and "name" in h
    ]

    result: dict[str, Any] = {
        "enumerated": True,
        "device_count": len(all_devices),
        "host_apis": host_api_names,
        "default_input": defaults[0],
        "default_output": defaults[1],
        "input": None,
        "output": None,
        "full_duplex_host_api_match": None,
    }

    if audio_config is None:
        return result

    # Diagnostic inspection for input
    in_desc = getattr(audio_config, "input_device", None)
    target_rate = getattr(audio_config, "target_sample_rate_hz", 16000)
    target_channels = getattr(audio_config, "channels", 1)

    input_descriptor_raw = (
        in_desc.model_dump() if isinstance(in_desc, AudioDeviceDescriptor) else in_desc
    )
    input_diag: dict[str, Any] = {
        "configured": in_desc is not None,
        "descriptor": input_descriptor_raw,
        "matched": False,
        "device_name": None,
        "host_api": None,
        "capability_supported": False,
        "error": None,
    }
    try:
        res_in = resolve_audio_device(
            in_desc,
            direction="capture",
            sample_rate_hz=target_rate,
            channels=target_channels,
            devices=all_devices,
            check_capability=True,
            default_indices=defaults,
        )
        input_diag["matched"] = True
        input_diag["device_name"] = res_in.device_name
        input_diag["host_api"] = res_in.host_api_name
        input_diag["capability_supported"] = True
    except Exception as exc:
        input_diag["error"] = f"{type(exc).__name__}: {exc}"

    result["input"] = input_diag

    # Diagnostic inspection for output
    out_desc = getattr(audio_config, "output_device", None)
    pref_host = input_diag.get("host_api") if input_diag.get("matched") else None

    output_descriptor_raw = (
        out_desc.model_dump() if isinstance(out_desc, AudioDeviceDescriptor) else out_desc
    )
    output_diag: dict[str, Any] = {
        "configured": out_desc is not None,
        "descriptor": output_descriptor_raw,
        "matched": False,
        "device_name": None,
        "host_api": None,
        "capability_supported": False,
        "error": None,
    }
    try:
        res_out = resolve_audio_device(
            out_desc,
            direction="playback",
            sample_rate_hz=target_rate,
            channels=target_channels,
            preferred_host_api=pref_host,
            devices=all_devices,
            check_capability=True,
            default_indices=defaults,
        )
        output_diag["matched"] = True
        output_diag["device_name"] = res_out.device_name
        output_diag["host_api"] = res_out.host_api_name
        output_diag["capability_supported"] = True
    except Exception as exc:
        output_diag["error"] = f"{type(exc).__name__}: {exc}"

    result["output"] = output_diag

    if input_diag.get("matched") and output_diag.get("matched"):
        in_api = input_diag.get("host_api")
        out_api = output_diag.get("host_api")
        result["full_duplex_host_api_match"] = (in_api is not None) and (in_api == out_api)

    return result

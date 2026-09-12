from dataclasses import dataclass
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float
    host_api_name: str | None = None
    host_api_index: int | None = None

    @property
    def can_capture(self) -> bool:
        return self.max_input_channels > 0

    @property
    def can_playback(self) -> bool:
        return self.max_output_channels > 0


class AudioDeviceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name_pattern: str | None = Field(
        default=None,
        validation_alias=AliasChoices("name", "name_pattern", "pattern"),
        description="Device name substring or regex pattern",
    )
    host_api: str | None = Field(
        default=None,
        validation_alias=AliasChoices("host_api", "host_api_name", "hostapi"),
        description="Preferred Host API name, e.g. 'MME', 'Windows WASAPI', 'ALSA'",
    )
    direction: Literal["capture", "playback"] | None = Field(
        default=None,
        validation_alias=AliasChoices("direction", "mode"),
        description="Audio direction: capture (input) or playback (output)",
    )
    channels: int | None = Field(
        default=None,
        ge=1,
        le=32,
        description="Required number of channels",
    )
    sample_rate_hz: int | None = Field(
        default=None,
        ge=8000,
        le=192000,
        validation_alias=AliasChoices("sample_rate_hz", "samplerate", "sample_rate"),
        description="Requested sample rate in Hz",
    )
    sample_format: str = Field(
        default="int16",
        validation_alias=AliasChoices("sample_format", "dtype", "format"),
        description="PCM format, default int16",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_direction(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            raw_direction = data.pop("direction", None)
            if raw_direction is None:
                raw_direction = data.pop("mode", None)
            else:
                data.pop("mode", None)
            if raw_direction == "input":
                data["direction"] = "capture"
            elif raw_direction == "output":
                data["direction"] = "playback"
            elif raw_direction is not None:
                data["direction"] = raw_direction
        return data

    @property
    def name(self) -> str | None:
        return self.name_pattern


@dataclass(frozen=True, slots=True)
class AudioDeviceResolution:
    device_index: int
    device_name: str
    host_api_name: str | None
    direction: Literal["capture", "playback"]
    sample_rate_hz: int
    channels: int
    sample_format: str
    device: AudioDevice

    @property
    def index(self) -> int:
        return self.device_index


class AudioDeviceResolutionError(RuntimeError):
    """Base error for audio device resolution and capability validation."""


class AudioDeviceNotFoundError(AudioDeviceResolutionError):
    """Raised when no audio device matches the descriptor."""


class AudioDeviceAmbiguityError(AudioDeviceResolutionError):
    """Raised when multiple audio devices match the descriptor without disambiguation."""


class AudioDeviceCapabilityError(AudioDeviceResolutionError):
    """Raised when an audio device fails format capability validation."""


def coerce_audio_device_descriptor(
    value: AudioDeviceDescriptor | dict[str, Any] | str | None,
    *,
    direction: Literal["capture", "playback"] | None = None,
    channels: int | None = None,
    sample_rate_hz: int | None = None,
    sample_format: str = "int16",
) -> AudioDeviceDescriptor | None:
    """Coerce various descriptor representations into an AudioDeviceDescriptor."""
    if value is None:
        if direction is None and channels is None and sample_rate_hz is None:
            return None
        return AudioDeviceDescriptor(
            direction=direction,
            channels=channels,
            sample_rate_hz=sample_rate_hz,
            sample_format=sample_format,
        )

    if isinstance(value, AudioDeviceDescriptor):
        updates: dict[str, Any] = {}
        if value.direction is None and direction is not None:
            updates["direction"] = direction
        if value.channels is None and channels is not None:
            updates["channels"] = channels
        if value.sample_rate_hz is None and sample_rate_hz is not None:
            updates["sample_rate_hz"] = sample_rate_hz
        if updates:
            return value.model_copy(update=updates)
        return value

    if isinstance(value, str):
        return AudioDeviceDescriptor(
            name_pattern=value,
            direction=direction,
            channels=channels,
            sample_rate_hz=sample_rate_hz,
            sample_format=sample_format,
        )

    if isinstance(value, dict):
        d = dict(value)
        if direction is not None and "direction" not in d and "mode" not in d:
            d["direction"] = direction
        if channels is not None and "channels" not in d:
            d["channels"] = channels
        if (
            sample_rate_hz is not None
            and "sample_rate_hz" not in d
            and "samplerate" not in d
            and "sample_rate" not in d
        ):
            d["sample_rate_hz"] = sample_rate_hz
        if (
            sample_format
            and "sample_format" not in d
            and "dtype" not in d
            and "format" not in d
        ):
            d["sample_format"] = sample_format
        return AudioDeviceDescriptor.model_validate(d)

    return None

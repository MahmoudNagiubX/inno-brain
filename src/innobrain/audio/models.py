from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float

    @property
    def can_capture(self) -> bool:
        return self.max_input_channels > 0

    @property
    def can_playback(self) -> bool:
        return self.max_output_channels > 0

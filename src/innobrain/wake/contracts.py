from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

CANONICAL_WAKE_LABEL: str = "heyino"
SAMPLE_RATE_HZ: int = 16000


class WakeOperatingMode(StrEnum):
    """Wake subsystem operating mode."""

    WAKE_REQUIRED = "wake_required"
    DEVELOPMENT_BYPASS = "development_bypass"


class WakeStatus(StrEnum):
    """Safe, machine-readable status distinguishing wake and attention states."""

    READY = "ready"
    DATA_PENDING = "data_pending"
    BYPASSED = "bypassed"
    DEGRADED = "degraded"


class WakeEngineError(Exception):
    """Base exception for wake word engine failures."""


class WakeEngineInitializationError(WakeEngineError):
    """Raised when engine adapter cannot be initialized or loaded."""


class WakeEngineProcessingError(WakeEngineError):
    """Raised when an error occurs while processing an audio frame."""


@dataclass(frozen=True, slots=True)
class WakeDetection:
    """Represents a timestamped wake word detection event."""

    label: str
    detector: str
    detected_at_monotonic: float
    score: float | None = None


@dataclass(frozen=True, slots=True)
class WakeEngineHealth:
    """Observable health metrics exposed to watchdogs and orchestrators."""

    ready: bool
    engine_name: str
    model_name_or_path: str | None = None
    model_hash: str | None = None
    last_frame_monotonic: float | None = None
    last_detection_monotonic: float | None = None
    detection_count: int = 0
    error_count: int = 0
    restart_count: int = 0
    degraded: bool = False
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class WakeEngineConfig:
    """Vendor-neutral configuration for wake word engines."""

    enabled: bool = True
    engine_type: str = "openwakeword"
    model_path: str | None = None
    threshold: float = 0.5
    cooldown_seconds: float = 1.5
    allowed_variants: tuple[str, ...] = (CANONICAL_WAKE_LABEL,)
    sample_rate_hz: int = SAMPLE_RATE_HZ
    frame_length_samples: int | None = None
    access_key: str | None = None
    mode: str = WakeOperatingMode.WAKE_REQUIRED.value


@runtime_checkable
class WakeWordEngine(Protocol):
    """Vendor-neutral protocol for wake word engines."""

    @property
    def sample_rate_hz(self) -> int: ...

    @property
    def frame_length(self) -> int: ...

    @property
    def health(self) -> WakeEngineHealth: ...

    def process(self, pcm16: bytes) -> WakeDetection | None: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from innobrain.config.models import WakeWordRuntimeConfig
from innobrain.wake.contracts import (
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineConfig,
    WakeEngineHealth,
    WakeEngineInitializationError,
    WakeOperatingMode,
    WakeWordEngine,
)
from innobrain.wake.router import WakeAudioRouter


class DegradedWakeWordEngine:
    """Explicitly degraded fallback wake engine when model/dependencies are absent or disabled."""

    def __init__(
        self,
        engine_name: str,
        reason: str,
        model_name_or_path: str | None = None,
        sample_rate_hz: int = SAMPLE_RATE_HZ,
        frame_length: int = 1280,
    ) -> None:
        self._engine_name = engine_name
        self._reason = reason
        self._model_name_or_path = model_name_or_path
        self._sample_rate_hz = sample_rate_hz
        self._frame_length = frame_length

    @property
    def sample_rate_hz(self) -> int:
        return self._sample_rate_hz

    @property
    def frame_length(self) -> int:
        return self._frame_length

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(
            ready=False,
            engine_name=self._engine_name,
            model_name_or_path=self._model_name_or_path,
            degraded=True,
            last_error=self._reason,
        )

    def process(self, pcm16: bytes) -> WakeDetection | None:
        return None

    def reset(self) -> None:
        pass

    def close(self) -> None:
        pass


def build_wake_engine(
    config: WakeWordRuntimeConfig,
    *,
    environment: Mapping[str, str] | None = None,
    backend: Any = None,
) -> WakeWordEngine:
    """Construct a WakeWordEngine according to configuration.

    Supports:
    - Injected fake engine (when backend is WakeWordEngine).
    - Degraded/DATA_PENDING state when openWakeWord or Porcupine assets/dependencies are absent.
    - Explicitly degraded state for disabled wake configuration.
    Never creates fake production detections or claims model acceptance.
    """
    if not config.enabled:
        return DegradedWakeWordEngine(
            engine_name="disabled",
            reason="Wake word engine is disabled in configuration.",
        )

    engine_type = config.engine_type.lower()
    env = os.environ if environment is None else environment

    if engine_type == "openwakeword":
        candidate_meta = config.candidate_engines.get("openwakeword")
        model_path = config.model_path or (candidate_meta.model_path if candidate_meta else None)
        frame_length = candidate_meta.frame_length_samples if candidate_meta else 1280

        model_file = Path(model_path) if model_path else None
        if model_file is None or not model_file.is_file():
            return DegradedWakeWordEngine(
                engine_name="openwakeword",
                reason=f"DATA_PENDING: openWakeWord model asset '{model_path}' is not present.",
                model_name_or_path=model_path,
                frame_length=frame_length,
            )

        wake_cfg = WakeEngineConfig(
            enabled=True,
            engine_type="openwakeword",
            model_path=model_path,
            threshold=config.threshold,
            cooldown_seconds=config.cooldown_seconds,
            allowed_variants=(config.canonical_label,),
            frame_length_samples=frame_length,
            mode=config.operating_mode,
        )
        try:
            from innobrain.wake.openwakeword_engine import OpenWakeWordEngine

            return OpenWakeWordEngine(config=wake_cfg, backend=backend)
        except WakeEngineInitializationError as err:
            return DegradedWakeWordEngine(
                engine_name="openwakeword",
                reason=f"DATA_PENDING: {err}",
                model_name_or_path=model_path,
                frame_length=frame_length,
            )

    if engine_type == "porcupine":
        candidate_meta = config.candidate_engines.get("porcupine")
        model_path = config.model_path or (candidate_meta.model_path if candidate_meta else None)
        frame_length = candidate_meta.frame_length_samples if candidate_meta else 512
        access_key = env.get("PORCUPINE_ACCESS_KEY") or env.get("PICOVOICE_ACCESS_KEY")

        if not access_key:
            return DegradedWakeWordEngine(
                engine_name="porcupine",
                reason="DATA_PENDING: Missing PORCUPINE_ACCESS_KEY environment variable.",
                model_name_or_path=model_path,
                frame_length=frame_length,
            )

        model_file = Path(model_path) if model_path else None
        if model_file is None or not model_file.is_file():
            return DegradedWakeWordEngine(
                engine_name="porcupine",
                reason=f"DATA_PENDING: Porcupine keyword asset '{model_path}' is not present.",
                model_name_or_path=model_path,
                frame_length=frame_length,
            )

        wake_cfg = WakeEngineConfig(
            enabled=True,
            engine_type="porcupine",
            model_path=model_path,
            threshold=config.threshold,
            cooldown_seconds=config.cooldown_seconds,
            access_key=access_key,
            allowed_variants=(config.canonical_label,),
            frame_length_samples=frame_length,
            mode=config.operating_mode,
        )
        try:
            from innobrain.wake.porcupine_engine import PorcupineWakeWordEngine

            return PorcupineWakeWordEngine(config=wake_cfg, backend=backend)
        except WakeEngineInitializationError as err:
            return DegradedWakeWordEngine(
                engine_name="porcupine",
                reason=f"DATA_PENDING: {err}",
                model_name_or_path=model_path,
                frame_length=frame_length,
            )

    if engine_type == "fake":
        if backend is not None and isinstance(backend, WakeWordEngine):
            return backend
        raise ValueError("Fake wake engine requested but no WakeWordEngine backend provided.")

    return DegradedWakeWordEngine(
        engine_name=engine_type,
        reason=f"Unknown or unsupported wake engine type: '{engine_type}'.",
    )


def build_wake_router(
    config: WakeWordRuntimeConfig,
    *,
    engine: WakeWordEngine | None = None,
    environment: Mapping[str, str] | None = None,
    backend: Any = None,
) -> WakeAudioRouter:
    """Build a WakeAudioRouter fed by the configured or injected WakeWordEngine."""
    wake_engine = engine or build_wake_engine(config, environment=environment, backend=backend)
    return WakeAudioRouter(
        engine=wake_engine,
        preroll_ms=config.preroll_ms,
        cooldown_seconds=config.cooldown_seconds,
        operating_mode=WakeOperatingMode(config.operating_mode),
    )


__all__ = [
    "DegradedWakeWordEngine",
    "build_wake_engine",
    "build_wake_router",
]

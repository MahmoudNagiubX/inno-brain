import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np

from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineConfig,
    WakeEngineHealth,
    WakeEngineInitializationError,
    WakeEngineProcessingError,
)


class OpenWakeWordEngine:
    """WakeWordEngine adapter for openWakeWord models."""

    def __init__(
        self,
        config: WakeEngineConfig | None = None,
        backend: Any = None,
    ) -> None:
        self._config = config or WakeEngineConfig()
        self._sample_rate_hz = SAMPLE_RATE_HZ
        self._frame_length = self._config.frame_length_samples or 1280
        self._frame_bytes = self._frame_length * 2

        self._ready = True
        self._degraded = False
        self._last_frame_monotonic: float | None = None
        self._last_detection_monotonic: float | None = None
        self._detection_count = 0
        self._error_count = 0
        self._restart_count = 0
        self._last_error: str | None = None

        self._buffer = bytearray()
        self._model_hash: str | None = None

        if self._config.model_path:
            model_file = Path(self._config.model_path)
            if model_file.is_file():
                try:
                    self._model_hash = hashlib.sha256(model_file.read_bytes()).hexdigest()
                except OSError:
                    self._model_hash = None

        if backend is not None:
            self._backend = backend
        else:
            self._backend = self._init_real_backend()

    def _init_real_backend(self) -> Any:
        try:
            import openwakeword  # noqa: F401
            from openwakeword.model import Model
        except (ImportError, ModuleNotFoundError) as err:
            raise WakeEngineInitializationError(
                "openwakeword package is not installed. Install with builder/extra dependencies "
                "or inject a fake backend."
            ) from err

        model_path = self._config.model_path
        if not model_path:
            raise WakeEngineInitializationError("No model_path specified for OpenWakeWordEngine.")

        try:
            return Model(wakeword_models=[model_path])
        except Exception as err:
            raise WakeEngineInitializationError(
                f"Failed to load openWakeWord model from '{model_path}': {err}"
            ) from err

    @property
    def sample_rate_hz(self) -> int:
        return self._sample_rate_hz

    @property
    def frame_length(self) -> int:
        return self._frame_length

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(
            ready=self._ready,
            engine_name="openwakeword",
            model_name_or_path=self._config.model_path,
            model_hash=self._model_hash,
            last_frame_monotonic=self._last_frame_monotonic,
            last_detection_monotonic=self._last_detection_monotonic,
            detection_count=self._detection_count,
            error_count=self._error_count,
            restart_count=self._restart_count,
            degraded=self._degraded,
            last_error=self._last_error,
        )

    def process(self, pcm16: bytes) -> WakeDetection | None:
        """Feed PCM16 audio bytes and return detection if triggered."""
        if not self._ready:
            raise WakeEngineProcessingError("Engine has been closed.")
        if not pcm16:
            return None
        if len(pcm16) % 2 != 0:
            raise ValueError("PCM16 data length must be a multiple of 2 bytes.")

        self._last_frame_monotonic = time.monotonic()
        self._buffer.extend(pcm16)

        latest_detection: WakeDetection | None = None

        while len(self._buffer) >= self._frame_bytes:
            frame = bytes(self._buffer[: self._frame_bytes])
            del self._buffer[: self._frame_bytes]
            frame_array = np.frombuffer(frame, dtype=np.int16)

            try:
                if hasattr(self._backend, "predict"):
                    raw_scores = self._backend.predict(frame_array)
                elif callable(self._backend):
                    raw_scores = self._backend(frame_array)
                else:
                    raise WakeEngineProcessingError(
                        f"Backend {type(self._backend)} does not support predict()"
                    )
            except Exception as err:
                self._error_count += 1
                self._degraded = True
                self._last_error = str(err)
                raise WakeEngineProcessingError(f"openWakeWord inference failed: {err}") from err

            # Evaluate detection against canonical label and allowed variants
            if isinstance(raw_scores, dict):
                detection = self._evaluate_scores(raw_scores)
                if detection is not None:
                    latest_detection = detection

        return latest_detection

    def _evaluate_scores(self, scores: dict[str, float]) -> WakeDetection | None:
        best_score = -1.0
        allowed = set(self._config.allowed_variants) | {CANONICAL_WAKE_LABEL}

        for key, score in scores.items():
            if key in allowed and score > best_score:
                best_score = score

        if best_score >= self._config.threshold:
            now = time.monotonic()
            self._detection_count += 1
            self._last_detection_monotonic = now
            return WakeDetection(
                label=CANONICAL_WAKE_LABEL,
                detector="openwakeword",
                detected_at_monotonic=now,
                score=best_score,
            )
        return None

    def reset(self) -> None:
        """Reset internal buffers and engine state."""
        self._buffer.clear()
        self._restart_count += 1
        if hasattr(self._backend, "reset"):
            try:
                self._backend.reset()
            except Exception:
                pass

    def close(self) -> None:
        """Release engine backend and mark unready."""
        self._ready = False
        self._buffer.clear()
        if hasattr(self._backend, "close"):
            try:
                self._backend.close()
            except Exception:
                pass

import pytest

from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineConfig,
    WakeEngineError,
    WakeEngineHealth,
    WakeEngineInitializationError,
    WakeEngineProcessingError,
    WakeWordEngine,
)


def test_constants() -> None:
    assert CANONICAL_WAKE_LABEL == "heyino"
    assert SAMPLE_RATE_HZ == 16000


def test_wake_detection_immutable() -> None:
    detection = WakeDetection(
        label="heyino",
        detector="openwakeword",
        detected_at_monotonic=123.456,
        score=0.88,
    )
    assert detection.label == "heyino"
    assert detection.detector == "openwakeword"
    assert detection.detected_at_monotonic == 123.456
    assert detection.score == 0.88

    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        detection.score = 0.99  # type: ignore[misc]

    # Optional score defaults to None
    det_no_score = WakeDetection(
        label="heyino",
        detector="porcupine",
        detected_at_monotonic=100.0,
    )
    assert det_no_score.score is None


def test_wake_engine_health_defaults() -> None:
    health = WakeEngineHealth(
        ready=True,
        engine_name="test_engine",
    )
    assert health.ready is True
    assert health.engine_name == "test_engine"
    assert health.model_name_or_path is None
    assert health.model_hash is None
    assert health.last_frame_monotonic is None
    assert health.last_detection_monotonic is None
    assert health.detection_count == 0
    assert health.error_count == 0
    assert health.restart_count == 0
    assert health.degraded is False
    assert health.last_error is None


def test_wake_engine_config_defaults() -> None:
    config = WakeEngineConfig()
    assert config.enabled is True
    assert config.engine_type == "openwakeword"
    assert config.model_path is None
    assert config.threshold == 0.5
    assert config.cooldown_seconds == 1.5
    assert config.allowed_variants == ("heyino",)
    assert config.sample_rate_hz == 16000


def test_exceptions_hierarchy() -> None:
    assert issubclass(WakeEngineInitializationError, WakeEngineError)
    assert issubclass(WakeEngineProcessingError, WakeEngineError)
    assert issubclass(WakeEngineError, Exception)


def test_wake_word_engine_protocol() -> None:
    class DummyEngine:
        sample_rate_hz: int = 16000
        frame_length: int = 1280

        def process(self, pcm16: bytes) -> WakeDetection | None:
            return None

        def reset(self) -> None:
            pass

        def close(self) -> None:
            pass

        @property
        def health(self) -> WakeEngineHealth:
            return WakeEngineHealth(ready=True, engine_name="dummy")

    engine = DummyEngine()
    assert isinstance(engine, WakeWordEngine)

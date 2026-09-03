
from innobrain.config.models import WakeWordRuntimeConfig
from innobrain.wake.contracts import (
    WakeDetection,
    WakeEngineHealth,
)
from innobrain.wake.factory import (
    DegradedWakeWordEngine,
    build_wake_engine,
    build_wake_router,
)


class FakeWakeWordEngine:
    def __init__(self, sample_rate_hz: int = 16000, frame_length: int = 1280) -> None:
        self._sample_rate_hz = sample_rate_hz
        self._frame_length = frame_length
        self._ready = True
        self.processed_frames: list[bytes] = []

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
            engine_name="fake_engine",
        )

    def process(self, pcm16: bytes) -> WakeDetection | None:
        self.processed_frames.append(pcm16)
        return None

    def reset(self) -> None:
        pass

    def close(self) -> None:
        self._ready = False


def test_build_wake_engine_with_injected_fake() -> None:
    fake = FakeWakeWordEngine()
    cfg = WakeWordRuntimeConfig(engine_type="fake")
    engine = build_wake_engine(cfg, backend=fake)

    assert engine is fake
    assert engine.health.ready is True
    assert engine.health.engine_name == "fake_engine"


def test_build_wake_engine_disabled_is_explicitly_degraded() -> None:
    cfg = WakeWordRuntimeConfig(enabled=False)
    engine = build_wake_engine(cfg)

    assert isinstance(engine, DegradedWakeWordEngine)
    assert engine.health.ready is False
    assert engine.health.degraded is True
    assert engine.health.engine_name == "disabled"
    assert "disabled" in (engine.health.last_error or "").lower()
    # Processing never yields detections
    assert engine.process(b"\x00" * 2560) is None


def test_build_wake_engine_openwakeword_missing_model_fails_gracefully() -> None:
    cfg = WakeWordRuntimeConfig(
        engine_type="openwakeword",
        model_path="nonexistent/model.onnx",
    )
    engine = build_wake_engine(cfg)

    assert isinstance(engine, DegradedWakeWordEngine)
    assert engine.health.ready is False
    assert engine.health.degraded is True
    assert "DATA_PENDING" in (engine.health.last_error or "")
    # Never creates fake detections
    assert engine.process(b"\x00" * 2560) is None


def test_build_wake_engine_porcupine_missing_key_fails_gracefully() -> None:
    cfg = WakeWordRuntimeConfig(
        engine_type="porcupine",
        model_path="models/wake/heyino_porcupine.ppn",
    )
    engine = build_wake_engine(cfg, environment={})

    assert isinstance(engine, DegradedWakeWordEngine)
    assert engine.health.ready is False
    assert engine.health.degraded is True
    assert "DATA_PENDING" in (engine.health.last_error or "")
    assert "PORCUPINE_ACCESS_KEY" in (engine.health.last_error or "")


def test_build_wake_router_assembles_router_with_configured_settings() -> None:
    fake = FakeWakeWordEngine()
    cfg = WakeWordRuntimeConfig(
        preroll_ms=2000,
        cooldown_seconds=2.5,
        engine_type="fake",
    )
    router = build_wake_router(cfg, engine=fake)

    assert router.mode.value == "sleeping"
    assert router.health.ready is True
    assert router._cooldown_seconds == 2.5

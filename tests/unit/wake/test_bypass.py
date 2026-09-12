from pathlib import Path

import pytest

from innobrain.attention.controller import AttentionController
from innobrain.config.loader import load_all_configs
from innobrain.config.models import WakeWordRuntimeConfig
from innobrain.wake.bridge import WakeAttentionBridge
from innobrain.wake.contracts import (
    SAMPLE_RATE_HZ,
    WakeEngineHealth,
    WakeOperatingMode,
    WakeStatus,
    WakeWordEngine,
)
from innobrain.wake.factory import build_wake_router
from innobrain.wake.router import WakeAudioRouter

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class RecordingEngine(WakeWordEngine):
    def __init__(self, *, ready: bool = True, error: bool = False) -> None:
        self.ready = ready
        self.error = error
        self.process_calls: list[bytes] = []

    @property
    def sample_rate_hz(self) -> int:
        return SAMPLE_RATE_HZ

    @property
    def frame_length(self) -> int:
        return 1280

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(
            ready=self.ready,
            engine_name="recording",
            degraded=self.error,
            last_error="synthetic failure" if self.error else None,
        )

    def process(self, pcm16: bytes):
        self.process_calls.append(pcm16)
        return None

    def reset(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_development_bypass_forwards_pcm_without_calling_engine() -> None:
    engine = RecordingEngine(ready=False)
    router = WakeAudioRouter(engine, operating_mode=WakeOperatingMode.DEVELOPMENT_BYPASS)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router, attention)

    chunk = b"\x01\x00" * 320

    assert bridge.process_chunk(chunk) == chunk
    assert engine.process_calls == []
    assert router.health.status == WakeStatus.BYPASSED.value
    assert router.health.operating_mode == WakeOperatingMode.DEVELOPMENT_BYPASS.value
    assert router.health.ready is True
    assert router.health.engine_health.ready is False


def test_wake_required_sleeping_still_suppresses_pcm_and_calls_engine() -> None:
    engine = RecordingEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router, attention)

    chunk = b"\x02\x00" * 320

    assert bridge.process_chunk(chunk) == b""
    assert engine.process_calls == [chunk]
    assert router.health.status == WakeStatus.READY.value


def test_data_pending_and_degraded_statuses_are_distinct() -> None:
    pending = build_wake_router(WakeWordRuntimeConfig())
    assert pending.health.status == WakeStatus.DATA_PENDING.value

    degraded_engine = RecordingEngine(ready=False, error=True)
    degraded = WakeAudioRouter(degraded_engine)
    assert degraded.health.status == WakeStatus.DEGRADED.value


def test_runtime_yaml_explicitly_selects_development_bypass() -> None:
    config = load_all_configs(REPOSITORY_ROOT)
    assert config.runtime.environment == "development"
    assert config.runtime.wake_word.operating_mode == WakeOperatingMode.DEVELOPMENT_BYPASS.value


@pytest.mark.parametrize(
    "mode",
    [WakeOperatingMode.WAKE_REQUIRED, WakeOperatingMode.DEVELOPMENT_BYPASS],
)
def test_router_exposes_selected_operating_mode(mode: WakeOperatingMode) -> None:
    router = WakeAudioRouter(RecordingEngine(), operating_mode=mode)
    assert router.operating_mode == mode

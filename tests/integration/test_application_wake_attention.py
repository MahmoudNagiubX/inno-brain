import json
from pathlib import Path

import pytest

from innobrain.app import ApplicationHealth, InnoBrainApplication, build_application
from innobrain.attention.contracts import AttentionState
from innobrain.config.loader import load_all_configs
from innobrain.event.registry import InstalledEventRecord
from innobrain.event.runtime import open_runtime_context
from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.vector_store import VectorStore
from innobrain.providers.registry import ProviderBundle
from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineHealth,
    WakeWordEngine,
)


class FakeEngine(WakeWordEngine):
    def __init__(self) -> None:
        self.trigger_on_next: WakeDetection | None = None
        self.reset_called = False
        self.close_called = False

    @property
    def sample_rate_hz(self) -> int:
        return SAMPLE_RATE_HZ

    @property
    def frame_length(self) -> int:
        return 1280

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(ready=True, engine_name="fake_engine")

    def process(self, pcm16: bytes) -> WakeDetection | None:
        det = self.trigger_on_next
        self.trigger_on_next = None
        return det

    def reset(self) -> None:
        self.reset_called = True

    def close(self) -> None:
        self.close_called = True


class BoundaryProvider:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class BoundaryStream:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    async def chunks(self):
        if False:
            yield b""


class BoundaryPlayback:
    async def cancel(self) -> None:
        return None


def _context(tmp_path: Path):
    database_path = tmp_path / "event.sqlite3"
    conn = connect_event_db(database_path)
    initialize_schema(conn)
    VectorStore(conn)
    conn.close()
    record = InstalledEventRecord(
        "event",
        "1.0.0",
        "a" * 64,
        tmp_path,
        database_path,
        {"chunks": 0, "fts": 0, "vec": 0, "embedding_rows": 0},
    )
    return open_runtime_context(record)


def _wake_required_config():
    configs = load_all_configs(Path.cwd())
    configs.runtime = configs.runtime.model_copy(
        update={
            "wake_word": configs.runtime.wake_word.model_copy(
                update={"operating_mode": "wake_required"}
            )
        }
    )
    return configs


def test_build_application_with_injected_wake_engine(tmp_path: Path) -> None:
    context = _context(tmp_path)
    engine = FakeEngine()
    app = build_application(
        config=load_all_configs(Path.cwd()),
        provider_bundle=ProviderBundle(BoundaryProvider(), BoundaryProvider(), BoundaryProvider()),
        event_context=context,
        stream=BoundaryStream(),
        playback=BoundaryPlayback(),
        wake_engine=engine,
    )

    assert isinstance(app, InnoBrainApplication)
    assert app.attention is not None
    assert app.wake_router is not None
    assert app.wake_bridge is not None

    # Watchdog-visible health snapshot
    health = app.health
    assert isinstance(health, ApplicationHealth)
    assert health.ready is True
    assert health.degraded is False
    assert health.started is False
    assert health.quiescent is True
    assert health.attention is not None
    assert health.attention["state"] == "SLEEPING"
    assert health.wake is not None
    assert health.wake["engine_health"]["engine_name"] == "fake_engine"

    # JSON serializability
    as_dict = health.to_dict()
    serialized = json.dumps(as_dict)
    assert "fake_engine" in serialized

    app.event_context.close()


def test_build_application_degraded_when_wake_model_unconfigured(tmp_path: Path) -> None:
    context = _context(tmp_path)
    # Build without injecting fake engine (uses runtime.yaml defaults where models are not present)
    app = build_application(
        config=load_all_configs(Path.cwd()),
        provider_bundle=ProviderBundle(BoundaryProvider(), BoundaryProvider(), BoundaryProvider()),
        event_context=context,
        stream=BoundaryStream(),
        playback=BoundaryPlayback(),
    )

    assert isinstance(app, InnoBrainApplication)
    health = app.health
    # Intentional bypass is ready for core voice while the nested engine remains data pending.
    assert health.ready is True
    assert health.degraded is False
    assert "DATA_PENDING" in str(health.wake)
    assert health.wake["status"] == "bypassed"

    app.event_context.close()


@pytest.mark.asyncio
async def test_application_lifecycle_and_reset_on_failure(tmp_path: Path) -> None:
    context = _context(tmp_path)
    engine = FakeEngine()
    app = build_application(
        config=_wake_required_config(),
        provider_bundle=ProviderBundle(BoundaryProvider(), BoundaryProvider(), BoundaryProvider()),
        event_context=context,
        stream=BoundaryStream(),
        playback=BoundaryPlayback(),
        wake_engine=engine,
    )

    # Set engaged state to verify reset
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=1.0
    )
    app.wake_bridge.process_chunk(b"\x01\x00" * 640)
    assert app.attention.state == AttentionState.ENGAGED

    async def fail_start() -> None:
        raise RuntimeError("simulated startup crash")

    app.voice.start = fail_start
    with pytest.raises(RuntimeError, match="simulated startup crash"):
        await app.start()

    # Attention and router reset cleanly on failure
    assert app.attention.state == AttentionState.SLEEPING
    assert app.wake_router.mode.value == "sleeping"

    # Idempotent stop
    await app.stop()
    assert app.attention.state == AttentionState.SLEEPING
    assert engine.close_called is True

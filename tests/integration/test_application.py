from pathlib import Path

import pytest

from innobrain.app import InnoBrainApplication, build_application
from innobrain.config.loader import load_all_configs
from innobrain.event.registry import InstalledEventRecord
from innobrain.event.runtime import open_runtime_context
from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.vector_store import VectorStore
from innobrain.providers.registry import ProviderBundle


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


def test_factory_assembles_one_real_internal_application_graph(tmp_path: Path) -> None:
    context = _context(tmp_path)
    boundary = BoundaryProvider()
    app = build_application(
        config=load_all_configs(Path.cwd()),
        provider_bundle=ProviderBundle(boundary, boundary, boundary),
        event_context=context,
        stream=BoundaryStream(),
        playback=BoundaryPlayback(),
    )

    assert isinstance(app, InnoBrainApplication)
    assert app.orchestrator.knowledge is app.knowledge
    assert app.voice.orchestrator is app.orchestrator
    assert app.voice.turn_runtime.stream.__class__ is BoundaryStream
    app.event_context.close()


@pytest.mark.asyncio
async def test_startup_failure_rolls_back_and_stop_is_idempotent(tmp_path: Path) -> None:
    app = build_application(
        config=load_all_configs(Path.cwd()),
        provider_bundle=ProviderBundle(BoundaryProvider(), BoundaryProvider(), BoundaryProvider()),
        event_context=_context(tmp_path),
        stream=BoundaryStream(),
        playback=BoundaryPlayback(),
    )
    calls = []

    async def fail_start() -> None:
        raise RuntimeError("synthetic startup failure")

    async def stop() -> None:
        calls.append("stop")

    app.voice.start = fail_start
    app.voice.stop = stop

    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        await app.start()
    await app.stop()

    assert calls == ["stop"]

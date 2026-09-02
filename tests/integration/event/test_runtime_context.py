from pathlib import Path

from innobrain.conversation.memory import SessionMemory
from innobrain.event.registry import InstalledEventRecord
from innobrain.event.runtime import RuntimeContextSwitcher, open_runtime_context
from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.vector_store import VectorStore


def _record(tmp_path: Path, name: str) -> InstalledEventRecord:
    root = tmp_path / name
    root.mkdir()
    database_path = root / "event.sqlite3"
    conn = connect_event_db(database_path)
    initialize_schema(conn)
    VectorStore(conn)
    conn.close()
    return InstalledEventRecord(
        name,
        "1.0.0",
        (name[0] * 64),
        root,
        database_path,
        {"chunks": 0, "fts": 0, "vec": 0, "embedding_rows": 0},
    )


def test_context_is_read_only_and_contains_repository_vector_store_and_retriever(
    tmp_path: Path,
) -> None:
    context = open_runtime_context(_record(tmp_path, "alpha"))
    assert context.record.event_id == "alpha"
    assert context.repository.get_event_meta("alpha") is None
    assert context.vector_store.dimension == 384
    assert context.retriever.event_id == "alpha"
    context.close()


def test_switcher_resets_memory_and_closes_old_context(tmp_path: Path) -> None:
    memory = SessionMemory()
    memory.add_turn("alpha question", "alpha answer", ["alpha"])
    switcher = RuntimeContextSwitcher(memory)
    switcher.switch(_record(tmp_path, "alpha"))
    old = switcher.current
    switcher.switch(_record(tmp_path, "beta"))

    assert switcher.current is not old
    assert switcher.current.record.event_id == "beta"
    assert memory.recent_turns() == ()
    switcher.close()

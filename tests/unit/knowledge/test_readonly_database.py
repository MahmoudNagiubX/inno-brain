import sqlite3
from pathlib import Path

import pytest

from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.vector_store import VectorStore


def test_readonly_database_uses_sqlite_mode_ro_and_rejects_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "event.sqlite3"
    conn = connect_event_db(db_path)
    initialize_schema(conn)
    conn.execute("INSERT INTO schema_meta(key, value) VALUES ('probe', 'value')")
    conn.commit()
    conn.close()

    readonly = connect_event_db(db_path, readonly=True)
    try:
        assert (
            readonly.execute("SELECT value FROM schema_meta WHERE key = 'probe'").fetchone()[0]
            == "value"
        )
        with pytest.raises(sqlite3.OperationalError):
            readonly.execute("CREATE TABLE forbidden(value TEXT)")
    finally:
        readonly.close()


def test_readonly_connection_requires_a_real_database_file() -> None:
    with pytest.raises(ValueError):
        connect_event_db(":memory:", readonly=True)


def test_existing_vector_store_searches_without_creating_or_committing(tmp_path: Path) -> None:
    db_path = tmp_path / "event.sqlite3"
    conn = connect_event_db(db_path)
    initialize_schema(conn)
    VectorStore(conn, dimension=4).rebuild([(1, [1, 0, 0, 0])])
    conn.close()

    readonly = connect_event_db(db_path, readonly=True)
    try:
        store = VectorStore(readonly, dimension=4, create_if_missing=False)
        hits = store.search([1, 0, 0, 0], 1)
        assert hits[0].rowid == 1
    finally:
        readonly.close()

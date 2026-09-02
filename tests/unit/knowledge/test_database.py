import sqlite3

from innobrain.knowledge.database import connect_event_db, ensure_sqlite_features, initialize_schema


def test_event_database_enables_foreign_keys_and_required_tables() -> None:
    conn = connect_event_db(":memory:")
    initialize_schema(conn)

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    ensure_sqlite_features(conn)
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
        )
    }
    assert {"event_meta", "chunks", "chunks_fts", "vec_chunks"}.issubset(tables)
    assert conn.execute("SELECT vec_version()").fetchone()[0] == "v0.1.9"
    conn.close()


def test_database_foreign_keys_reject_orphan_rows() -> None:
    conn = connect_event_db(":memory:")
    initialize_schema(conn)

    try:
        conn.execute(
            "INSERT INTO locations(id, event_id, name, normalized_name) VALUES (?, ?, ?, ?)",
            ("orphan", "missing", "Orphan", "orphan"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("foreign key enforcement was not active")

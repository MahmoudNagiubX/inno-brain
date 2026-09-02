from datetime import datetime

from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.repository import EventRepository


def test_new_event_database_has_phase4_metadata_and_schema_version() -> None:
    conn = connect_event_db(":memory:")
    initialize_schema(conn)

    event_columns = {row["name"] for row in conn.execute("PRAGMA table_info(event_meta)")}
    document_columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    chunk_columns = {row["name"] for row in conn.execute("PRAGMA table_info(chunks)")}

    assert {"event_version", "client_id"}.issubset(event_columns)
    assert {
        "event_version",
        "client_id",
        "language",
        "authority_level",
        "valid_from",
        "valid_until",
    }.issubset(document_columns)
    assert {
        "event_version",
        "client_id",
        "language",
        "authority_level",
        "valid_from",
        "valid_until",
    }.issubset(chunk_columns)
    assert conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'database_schema_version'"
    ).fetchone()[0] == "2"


def test_lexical_search_excludes_invalid_time_content_when_reference_time_is_supplied() -> None:
    conn = connect_event_db(":memory:")
    initialize_schema(conn)
    conn.execute(
        "INSERT INTO event_meta("
        "id, title, event_date, venue_name, timezone, event_version, client_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("event", "Event", "2026-10-01", "Venue", "Africa/Cairo", "1.0.0", "client"),
    )
    conn.execute(
        "INSERT INTO documents("
        "id, event_id, source_type, title, source_ref, checksum, "
        "event_version, client_id, language, authority_level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "doc",
            "event",
            "markdown",
            "Guide",
            "guide.md",
            "checksum",
            "1.0.0",
            "client",
            "en",
            "official",
        ),
    )
    conn.executemany(
        "INSERT INTO chunks("
        "document_id, event_id, chunk_index, text, normalized_text, "
        "event_version, client_id, language, authority_level, valid_from, valid_until) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "doc",
                "event",
                0,
                "current schedule",
                "current schedule",
                "1.0.0",
                "client",
                "en",
                "official",
                "2026-09-01T00:00:00+02:00",
                "2026-12-01T00:00:00+02:00",
            ),
            (
                "doc",
                "event",
                1,
                "expired schedule",
                "expired schedule",
                "1.0.0",
                "client",
                "en",
                "official",
                "2026-01-01T00:00:00+02:00",
                "2026-02-01T00:00:00+02:00",
            ),
        ],
    )
    conn.commit()

    rows = EventRepository(conn).lexical_search(
        "event",
        "schedule",
        10,
        reference_time=datetime.fromisoformat("2026-10-01T12:00:00+02:00"),
    )

    assert [row["text"] for row in rows] == ["current schedule"]

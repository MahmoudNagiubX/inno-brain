from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.repository import EventRepository


def test_repository_uses_structured_joins_and_safe_fts_queries() -> None:
    conn = connect_event_db(":memory:")
    initialize_schema(conn)
    conn.execute(
        "INSERT INTO event_meta VALUES (?, ?, ?, ?, ?)",
        ("event", "Event", "2026-10-15", "Venue", "Africa/Cairo"),
    )
    conn.execute(
        "INSERT INTO locations VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("loc", "event", "Main Stage", "main stage", "Ground", "A", "stage"),
    )
    conn.execute(
        "INSERT INTO speakers VALUES (?, ?, ?, ?, ?)",
        ("spk", "event", "Sara Hassan", "sara hassan", "bio"),
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ses",
            "event",
            "Future AI",
            "future ai",
            "2026-10-15T11:00",
            "2026-10-15T12:00",
            "loc",
            "desc",
        ),
    )
    conn.execute("INSERT INTO session_speakers VALUES (?, ?)", ("ses", "spk"))
    conn.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
        ("doc", "event", "markdown", "Guide", "fixture://guide", "checksum"),
    )
    conn.execute(
        (
            "INSERT INTO chunks(document_id, event_id, chunk_index, text, normalized_text) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        ("doc", "event", 0, "Main Stage guide", "main stage guide"),
    )
    conn.commit()

    repository = EventRepository(conn)
    assert repository.get_event_meta("event")["venue_name"] == "Venue"
    assert repository.find_session_by_name("event", "future ai")[0]["id"] == "ses"
    assert repository.sessions_for_speaker("spk")[0]["id"] == "ses"
    assert repository.speakers_for_session("ses")[0]["id"] == "spk"
    assert repository.get_location("loc")["name"] == "Main Stage"
    assert repository.lexical_search("event", "main stage OR *", 5)[0]["id"] == 1

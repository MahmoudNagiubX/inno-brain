from pathlib import Path

from innobrain.knowledge.database import connect_event_db, load_sqlite_vec
from innobrain.knowledge.repository import EventRepository
from scripts.phase3.build_demo_db import build_demo_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_demo_fixture_builds_deterministic_structured_and_fts_content(tmp_path: Path) -> None:
    db_path = build_demo_db(
        REPOSITORY_ROOT / "fixtures" / "phase3" / "demo_event.yaml",
        tmp_path / "demo.sqlite3",
    )
    conn = connect_event_db(db_path)
    try:
        repository = EventRepository(conn)
        event = repository.get_event_meta("demo-2026")
        assert event["title"] == "InnoBrain Demo Event"
        assert (
            repository.find_session_by_name("demo-2026", "future of ai in events")[0]["id"]
            == "future-ai"
        )
        assert repository.lexical_search("demo-2026", "demos", 5)[0]["chunk_index"] == 1
        load_sqlite_vec(conn)
        assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
        assert (
            conn.execute("SELECT value FROM schema_meta WHERE key = 'fixture_id'").fetchone()[0]
            == "demo-2026"
        )
    finally:
        conn.close()

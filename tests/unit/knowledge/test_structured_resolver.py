from pathlib import Path

from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.structured_resolver import ExactIntent, StructuredResolver
from scripts.phase3.build_demo_db import build_demo_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_structured_resolver_returns_deterministic_exact_answers(tmp_path: Path) -> None:
    db_path = build_demo_db(
        REPOSITORY_ROOT / "fixtures" / "phase3" / "demo_event.yaml",
        tmp_path / "demo.sqlite3",
    )
    conn = connect_event_db(db_path)
    resolver = StructuredResolver(EventRepository(conn), event_id="demo-2026")

    time_answer = resolver.resolve("Future of AI in Events الساعة كام؟")
    booth_answer = resolver.resolve("بوث Innovatronics فين؟")
    speaker_answer = resolver.resolve("Sara Hassan بتتكلم فين؟")

    assert time_answer is not None and time_answer.intent is ExactIntent.SESSION_TIME
    assert "11:00" in time_answer.text
    assert booth_answer is not None and booth_answer.intent is ExactIntent.BOOTH_LOCATION
    assert "Expo A12" in booth_answer.text
    assert speaker_answer is not None and speaker_answer.intent is ExactIntent.SPEAKER_SESSIONS
    assert "Hall B" in speaker_answer.text
    conn.close()

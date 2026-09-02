from pathlib import Path

import pytest

from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import AnswerRoute, GroundedOrchestrator
from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.models import EvidencePack
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


class EmptyRetriever:
    async def retrieve(self, query):
        return EvidencePack(query, ())


class CountingLLM:
    name = "must-not-run"

    def __init__(self):
        self.calls = 0

    def stream(self, *_args, **_kwargs):
        self.calls += 1

        async def chunks():
            yield "wrong"

        return chunks()

    async def cancel(self):
        return None


@pytest.mark.asyncio
async def test_one_active_session_resolves_exact_follow_up_without_llm(tmp_path: Path) -> None:
    db_path = build_demo_db(
        REPOSITORY_ROOT / "fixtures" / "phase3" / "demo_event.yaml",
        tmp_path / "demo.sqlite3",
    )
    conn = connect_event_db(db_path)
    llm = CountingLLM()
    memory = SessionMemory()
    orchestrator = GroundedOrchestrator(
        StructuredResolver(EventRepository(conn), event_id="demo-2026"),
        EmptyRetriever(),
        memory=memory,
        llm_provider=llm,
    )

    first = await orchestrator.answer(
        "Future of AI in Events فين؟",
        delivery_confirmed=True,
    )
    second = await orchestrator.answer("طب الساعة كام؟")

    assert first.route is AnswerRoute.EXACT
    assert "future-ai" in first.entities
    assert "future-ai" in memory.active_entities()
    assert second.route is AnswerRoute.EXACT
    assert "11:00" in second.text
    assert llm.calls == 0
    conn.close()


def test_multiple_compatible_active_sessions_do_not_guess(tmp_path: Path) -> None:
    db_path = build_demo_db(
        REPOSITORY_ROOT / "fixtures" / "phase3" / "demo_event.yaml",
        tmp_path / "demo.sqlite3",
    )
    conn = connect_event_db(db_path)
    resolver = StructuredResolver(EventRepository(conn), event_id="demo-2026")

    answer = resolver.resolve(
        "طب الساعة كام؟",
        active_entities=("future-ai", "robot-workshop"),
    )

    assert answer is None
    conn.close()

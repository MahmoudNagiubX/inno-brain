from datetime import datetime
from pathlib import Path

import pytest

from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.retrieval import HybridRetriever
from innobrain.knowledge.vector_store import VectorHit
from scripts.phase3.build_demo_db import build_demo_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class BrokenEmbedding:
    async def embed_query(self, text: str):
        raise RuntimeError("model unavailable")


class FixedEmbedding:
    async def embed_query(self, text: str):
        return [0.0]


class FixedVectorStore:
    def __init__(self, rowids: list[int]) -> None:
        self.rowids = rowids

    def search(self, vector, limit: int):
        return [
            VectorHit(rowid=rowid, distance=float(index))
            for index, rowid in enumerate(self.rowids[:limit])
        ]


@pytest.mark.asyncio
async def test_hybrid_retrieval_degrades_to_fts_when_dense_is_unavailable(tmp_path: Path) -> None:
    db_path = build_demo_db(
        REPOSITORY_ROOT / "fixtures" / "phase3" / "demo_event.yaml",
        tmp_path / "demo.sqlite3",
    )
    conn = connect_event_db(db_path)
    retriever = HybridRetriever(
        EventRepository(conn),
        event_id="demo-2026",
        embedding_provider=BrokenEmbedding(),
        vector_store=object(),
    )

    result = await retriever.retrieve("Innovatronics Booth")

    assert result.evidence
    assert result.evidence[0].source.value == "lexical"
    assert "Innovatronics" in result.evidence[0].text
    conn.close()


@pytest.mark.asyncio
async def test_hybrid_retrieval_applies_one_clock_to_lexical_and_dense_results() -> None:
    conn = connect_event_db(":memory:")
    initialize_schema(conn)
    conn.execute(
        "INSERT INTO event_meta(id, title, event_date, venue_name, timezone) "
        "VALUES ('event', 'Event', '2026-10-01', 'Venue', 'Africa/Cairo')"
    )
    conn.execute(
        "INSERT INTO documents(id, event_id, source_type, title, source_ref, checksum) "
        "VALUES ('doc', 'event', 'markdown', 'Guide', 'guide.md', 'checksum')"
    )
    conn.executemany(
        "INSERT INTO chunks(document_id, event_id, chunk_index, text, normalized_text, "
        "valid_from, valid_until) VALUES ('doc', 'event', ?, ?, ?, ?, ?)",
        [
            (
                0,
                "expired lexical schedule",
                "expired lexical schedule",
                None,
                "2026-09-01T00:00:00+00:00",
            ),
            (
                1,
                "expired dense schedule",
                "expired dense schedule",
                None,
                "2026-09-01T00:00:00+00:00",
            ),
            (2, "future schedule", "future schedule", "2026-11-01T00:00:00+00:00", None),
            (
                3,
                "current schedule",
                "current schedule",
                "2026-09-01T00:00:00+00:00",
                "2026-11-01T00:00:00+00:00",
            ),
        ],
    )
    conn.commit()
    rows = conn.execute("SELECT id, chunk_index FROM chunks ORDER BY chunk_index").fetchall()
    ids = {row["chunk_index"]: row["id"] for row in rows}
    retriever = HybridRetriever(
        EventRepository(conn),
        event_id="event",
        embedding_provider=FixedEmbedding(),
        vector_store=FixedVectorStore([ids[1], ids[2], ids[3]]),
        clock=lambda: datetime.fromisoformat("2026-10-01T00:00:00+00:00"),
    )

    result = await retriever.retrieve("schedule")

    assert [item.text for item in result.evidence] == ["current schedule"]
    conn.close()

from pathlib import Path

import pytest

from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.retrieval import HybridRetriever
from scripts.phase3.build_demo_db import build_demo_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class BrokenEmbedding:
    async def embed_query(self, text: str):
        raise RuntimeError("model unavailable")


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

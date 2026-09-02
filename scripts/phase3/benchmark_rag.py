"""Benchmark the Phase 3 retrieval fixture and print the required metrics."""

import argparse
import asyncio
from pathlib import Path
from typing import Any

import yaml

from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.retrieval import HybridRetriever

if __package__:
    from .build_demo_db import DEFAULT_DB, DEFAULT_FIXTURE, build_demo_db
else:
    from build_demo_db import DEFAULT_DB, DEFAULT_FIXTURE, build_demo_db

DEFAULT_QUERIES = Path(__file__).parents[2] / "evals" / "rag" / "phase3_queries.yaml"


def recall_at_k(retrieved: list[int], gold: list[int], k: int = 5) -> float:
    return float(bool(set(retrieved[:k]).intersection(gold)))


def reciprocal_rank(retrieved: list[int], gold: list[int]) -> float:
    gold_set = set(gold)
    for index, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in gold_set:
            return 1.0 / index
    return 0.0


def _load_queries(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("RAG query fixture must be a list")
    return raw


async def _run_queries(
    retriever: HybridRetriever,
    queries: list[dict[str, Any]],
) -> tuple[float, float]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    for item in queries:
        result = await retriever.retrieve(item["query"])
        retrieved = [
            int(evidence.evidence_id.removeprefix("chunk:"))
            for evidence in result.evidence
        ]
        gold = [int(chunk_id) for chunk_id in item["gold_chunk_ids"]]
        recalls.append(recall_at_k(retrieved, gold))
        reciprocal_ranks.append(reciprocal_rank(retrieved, gold))
    return sum(recalls) / len(recalls), sum(reciprocal_ranks) / len(reciprocal_ranks)


def run_benchmark(
    *,
    db_path: Path = DEFAULT_DB,
    queries_path: Path = DEFAULT_QUERIES,
) -> tuple[int, float, float]:
    if not db_path.exists():
        build_demo_db(DEFAULT_FIXTURE, db_path)
    conn = connect_event_db(db_path)
    try:
        queries = _load_queries(queries_path)
        retriever = HybridRetriever(EventRepository(conn), event_id="demo-2026")
        recall, mrr = asyncio.run(_run_queries(retriever, queries))
        return len(queries), recall, mrr
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    args = parser.parse_args()
    count, recall, mrr = run_benchmark(db_path=args.db, queries_path=args.queries)
    print("HYBRID_ALGORITHM_TEST=PASS")
    print("REAL_E5_RETRIEVAL_TEST=NOT_RUN")
    print(f"QUERIES={count}")
    print(f"RECALL_AT_5={recall:.4f}")
    print(f"MRR={mrr:.4f}")
    if recall < 0.90 or mrr < 0.75:
        raise SystemExit("RAG thresholds failed")


if __name__ == "__main__":
    main()

"""Run a keyless typed Egyptian-Arabic conversation against the demo event."""

import argparse
import asyncio
import os
from pathlib import Path

from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import BrainResult, GroundedOrchestrator
from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.retrieval import HybridRetriever
from innobrain.knowledge.structured_resolver import StructuredResolver

if __package__:
    from .build_demo_db import DEFAULT_DB, DEFAULT_FIXTURE, build_demo_db
else:
    from build_demo_db import DEFAULT_DB, DEFAULT_FIXTURE, build_demo_db


def create_orchestrator(db_path: Path) -> tuple[GroundedOrchestrator, object]:
    conn = connect_event_db(db_path)
    repository = EventRepository(conn)
    retriever = HybridRetriever(repository, event_id="demo-2026")
    resolver = StructuredResolver(repository, event_id="demo-2026")
    llm = None
    if os.environ.get("GROQ_API_KEY"):
        from innobrain.providers.groq_llm import GroqLLMProvider

        llm = GroqLLMProvider()
    return (
        GroundedOrchestrator(
            resolver,
            retriever,
            memory=SessionMemory(max_turns=10, ttl_seconds=300),
            llm_provider=llm,
        ),
        conn,
    )


def answer_text(question: str, *, db_path: Path = DEFAULT_DB) -> BrainResult:
    if not db_path.exists():
        build_demo_db(DEFAULT_FIXTURE, db_path)
    orchestrator, conn = create_orchestrator(db_path)
    try:
        return asyncio.run(orchestrator.answer(question))
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not args.db.exists():
        build_demo_db(DEFAULT_FIXTURE, args.db)
    orchestrator, conn = create_orchestrator(args.db)
    try:
        print("Type an Egyptian-Arabic question; press Enter on an empty line to stop.")
        while True:
            question = input("> ").strip()
            if not question:
                break
            result = asyncio.run(orchestrator.answer(question))
            print(f"ROUTE={result.route.value}")
            print(f"EVIDENCE_IDS={','.join(result.evidence_ids) or '(none)'}")
            print(f"ANSWER={result.text}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

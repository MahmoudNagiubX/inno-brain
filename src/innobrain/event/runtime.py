import sqlite3
from dataclasses import dataclass

from innobrain.conversation.memory import SessionMemory
from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.retrieval import HybridRetriever
from innobrain.knowledge.vector_store import VectorStore

from .registry import InstalledEventRecord


@dataclass(slots=True)
class ActiveRuntimeContext:
    record: InstalledEventRecord
    connection: sqlite3.Connection
    repository: EventRepository
    vector_store: VectorStore
    retriever: HybridRetriever

    def close(self) -> None:
        self.connection.close()


def open_runtime_context(
    record: InstalledEventRecord,
    *,
    embedding_provider: object | None = None,
    lexical_top_k: int = 12,
    dense_top_k: int = 12,
    final_top_k: int = 5,
    rrf_k: int = 60,
) -> ActiveRuntimeContext:
    connection = connect_event_db(record.database_path, readonly=True)
    try:
        vector_store = VectorStore(connection, create_if_missing=False)
        repository = EventRepository(connection)
        retriever = HybridRetriever(
            repository,
            event_id=record.event_id,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            lexical_top_k=lexical_top_k,
            dense_top_k=dense_top_k,
            final_top_k=final_top_k,
            rrf_k=rrf_k,
        )
        return ActiveRuntimeContext(record, connection, repository, vector_store, retriever)
    except Exception:
        connection.close()
        raise


class RuntimeContextSwitcher:
    """Activation hook that opens new event state and resets visitor memory."""

    def __init__(self, memory: SessionMemory, *, embedding_provider: object | None = None) -> None:
        self.memory = memory
        self.embedding_provider = embedding_provider
        self.current: ActiveRuntimeContext | None = None

    def switch(self, record: InstalledEventRecord) -> None:
        new_context = open_runtime_context(
            record,
            embedding_provider=self.embedding_provider,
        )
        old_context = self.current
        self.current = new_context
        self.memory.reset()
        if old_context is not None:
            old_context.close()

    def close(self) -> None:
        if self.current is not None:
            self.current.close()
            self.current = None


__all__ = ["ActiveRuntimeContext", "RuntimeContextSwitcher", "open_runtime_context"]

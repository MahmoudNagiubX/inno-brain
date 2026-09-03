import sqlite3
from dataclasses import dataclass

from innobrain.conversation.knowledge_binding import ActiveKnowledgeBinding, KnowledgeSnapshot
from innobrain.conversation.memory import SessionMemory
from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.repository import EventRepository
from innobrain.knowledge.retrieval import HybridRetriever
from innobrain.knowledge.structured_resolver import StructuredResolver
from innobrain.knowledge.vector_store import VectorStore

from .registry import InstalledEventRecord


@dataclass(slots=True)
class ActiveRuntimeContext:
    record: InstalledEventRecord
    connection: sqlite3.Connection
    repository: EventRepository
    vector_store: VectorStore
    resolver: StructuredResolver
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
        resolver = StructuredResolver(repository, event_id=record.event_id)
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
        return ActiveRuntimeContext(
            record,
            connection,
            repository,
            vector_store,
            resolver,
            retriever,
        )
    except Exception:
        connection.close()
        raise


class RuntimeContextSwitcher:
    """Activation hook that opens new event state and resets visitor memory."""

    def __init__(
        self,
        memory: SessionMemory,
        *,
        embedding_provider: object | None = None,
        binding: ActiveKnowledgeBinding | None = None,
        current: ActiveRuntimeContext | None = None,
        lexical_top_k: int = 12,
        dense_top_k: int = 12,
        final_top_k: int = 5,
        rrf_k: int = 60,
    ) -> None:
        self.memory = memory
        self.embedding_provider = embedding_provider
        self.binding = binding
        self.current = current
        self.lexical_top_k = lexical_top_k
        self.dense_top_k = dense_top_k
        self.final_top_k = final_top_k
        self.rrf_k = rrf_k

    def switch(self, record: InstalledEventRecord) -> None:
        new_context = open_runtime_context(
            record,
            embedding_provider=self.embedding_provider,
            lexical_top_k=self.lexical_top_k,
            dense_top_k=self.dense_top_k,
            final_top_k=self.final_top_k,
            rrf_k=self.rrf_k,
        )
        snapshot = KnowledgeSnapshot(
            event_id=record.event_id,
            event_version=record.event_version,
            resolver=new_context.resolver,
            retriever=new_context.retriever,
        )
        old_context = self.current
        if self.binding is not None:
            self.binding.swap(snapshot)
        self.current = new_context
        self.memory.reset()
        if old_context is not None:
            old_context.close()

    def close(self) -> None:
        if self.current is not None:
            self.current.close()
            self.current = None


__all__ = ["ActiveRuntimeContext", "RuntimeContextSwitcher", "open_runtime_context"]

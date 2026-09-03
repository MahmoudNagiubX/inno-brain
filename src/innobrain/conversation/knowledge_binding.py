from dataclasses import dataclass
from threading import Lock

from innobrain.knowledge.retrieval import HybridRetriever
from innobrain.knowledge.structured_resolver import StructuredResolver


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    event_id: str
    event_version: str
    resolver: StructuredResolver
    retriever: HybridRetriever


class ActiveKnowledgeBinding:
    """A lock-protected pointer to one immutable event knowledge graph."""

    def __init__(self, initial: KnowledgeSnapshot) -> None:
        self._current = initial
        self._lock = Lock()

    def snapshot(self) -> KnowledgeSnapshot:
        with self._lock:
            return self._current

    def swap(self, snapshot: KnowledgeSnapshot) -> KnowledgeSnapshot:
        with self._lock:
            previous = self._current
            self._current = snapshot
            return previous


__all__ = ["ActiveKnowledgeBinding", "KnowledgeSnapshot"]

import json
from collections.abc import Sequence
from dataclasses import dataclass

from .models import Evidence, EvidencePack, EvidenceSource
from .normalize import normalize_arabic_retrieval
from .repository import EventRepository
from .vector_store import VectorStore


@dataclass(frozen=True, slots=True)
class RankedChunk:
    chunk_id: int | str
    score: float = 0.0


def reciprocal_rank_fusion(
    lexical: Sequence[RankedChunk],
    dense: Sequence[RankedChunk],
    *,
    k: int = 60,
    limit: int = 5,
) -> list[RankedChunk]:
    scores: dict[int | str, float] = {}
    for _source_name, ranked in (("lexical", lexical), ("dense", dense)):
        for rank, item in enumerate(ranked, start=1):
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], str(chunk_id)))[:limit]
    return [
        RankedChunk(chunk_id=chunk_id, score=scores[chunk_id])
        for chunk_id in ordered
    ]


class HybridRetriever:
    def __init__(
        self,
        repository: EventRepository,
        *,
        event_id: str,
        embedding_provider: object | None = None,
        vector_store: VectorStore | None = None,
        lexical_top_k: int = 12,
        dense_top_k: int = 12,
        final_top_k: int = 5,
        rrf_k: int = 60,
    ) -> None:
        self.repository = repository
        self.event_id = event_id
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.lexical_top_k = lexical_top_k
        self.dense_top_k = dense_top_k
        self.final_top_k = final_top_k
        self.rrf_k = rrf_k

    async def retrieve(self, query: str) -> EvidencePack:
        normalized_query = normalize_arabic_retrieval(query)
        lexical_rows = self.repository.lexical_search(
            self.event_id,
            normalized_query,
            self.lexical_top_k,
        )
        lexical = [RankedChunk(int(row["id"])) for row in lexical_rows]
        dense: list[RankedChunk] = []
        if self.embedding_provider is not None and self.vector_store is not None:
            try:
                vector = await self.embedding_provider.embed_query(normalized_query)
                dense = [
                    RankedChunk(hit.rowid)
                    for hit in self.vector_store.search(vector, self.dense_top_k)
                ]
            except Exception:
                dense = []

        fused = reciprocal_rank_fusion(
            lexical,
            dense,
            k=self.rrf_k,
            limit=self.final_top_k,
        )
        fused_ids = [int(item.chunk_id) for item in fused]
        rows = {row["id"]: row for row in self.repository.chunks_by_ids(fused_ids)}
        evidence: list[Evidence] = []
        lexical_ids = {item.chunk_id for item in lexical}
        dense_ids = {item.chunk_id for item in dense}
        for item in fused:
            row = rows.get(item.chunk_id)
            if row is None:
                continue
            source = (
                EvidenceSource.HYBRID
                if item.chunk_id in lexical_ids and item.chunk_id in dense_ids
                else EvidenceSource.DENSE
                if item.chunk_id in dense_ids
                else EvidenceSource.LEXICAL
            )
            metadata = json.loads(row["metadata_json"] or "{}")
            evidence.append(
                Evidence(
                    evidence_id=f"chunk:{row['id']}",
                    source=source,
                    text=row["text"],
                    score=item.score,
                    metadata={str(key): str(value) for key, value in metadata.items()},
                )
            )
        return EvidencePack(query=query, evidence=tuple(evidence))

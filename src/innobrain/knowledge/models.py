from dataclasses import dataclass
from enum import StrEnum


class EvidenceSource(StrEnum):
    STRUCTURED = "structured"
    LEXICAL = "lexical"
    DENSE = "dense"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    source: EvidenceSource
    text: str
    score: float
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class EvidencePack:
    query: str
    evidence: tuple[Evidence, ...]

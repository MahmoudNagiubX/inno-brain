import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .authoring import EventAuthoringBundle, SourceInventory, canonical_authoring_json

BUILDER_SCHEMA_VERSION = "1.0"
DEFAULT_E5_MODEL_ID = "intfloat/multilingual-e5-small"
DEFAULT_E5_REVISION = "614241f"
DEFAULT_E5_DIMENSION = 384
DEFAULT_CHUNK_MAX_TOKENS = 384


def compute_build_id(
    bundle: EventAuthoringBundle,
    inventory: SourceInventory,
    *,
    builder_schema_version: str = BUILDER_SCHEMA_VERSION,
    docling_version: str = "2.124.0",
    chunk_max_tokens: int = DEFAULT_CHUNK_MAX_TOKENS,
    embedding_model_id: str = DEFAULT_E5_MODEL_ID,
    embedding_revision: str = DEFAULT_E5_REVISION,
    embedding_dimension: int = DEFAULT_E5_DIMENSION,
) -> str:
    identity: dict[str, Any] = {
        "authoring": json.loads(canonical_authoring_json(bundle)),
        "sources": [
            {
                "path": source.relative_path,
                "sha256": source.sha256,
                "size_bytes": source.size_bytes,
            }
            for source in inventory.files
        ],
        "builder_schema_version": builder_schema_version,
        "docling_version": docling_version,
        "chunk_max_tokens": chunk_max_tokens,
        "embedding": {
            "model_id": embedding_model_id,
            "revision": embedding_revision,
            "dimension": embedding_dimension,
        },
    }
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_report(
    *,
    build_id: str,
    source_files: int,
    source_bytes: int,
    structured_counts: dict[str, int],
    parsed_documents: int,
    parse_warnings: Sequence[str] = (),
    parse_errors: Sequence[str] = (),
    chunk_count: int,
    token_counts: Sequence[int] = (),
    embedding_checks: dict[str, Any] | None = None,
    dependency_versions: dict[str, str] | None = None,
    durations_seconds: dict[str, float] | None = None,
) -> dict[str, Any]:
    tokens = list(token_counts)
    return {
        "schema_version": "1.0",
        "build_id": build_id,
        "sources": {"file_count": source_files, "total_bytes": source_bytes},
        "structured_counts": dict(sorted(structured_counts.items())),
        "parsing": {"document_count": parsed_documents, "errors": list(parse_errors)},
        "chunks": {
            "count": chunk_count,
            "token_count_min": min(tokens) if tokens else 0,
            "token_count_max": max(tokens) if tokens else 0,
            "token_count_total": sum(tokens),
        },
        "embeddings": embedding_checks or {},
        "dependencies": dependency_versions or {},
        "warnings": list(parse_warnings),
        "errors": list(parse_errors),
        "durations_seconds": durations_seconds or {},
    }


def write_build_report(path: Path | str, report: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "BUILDER_SCHEMA_VERSION",
    "DEFAULT_CHUNK_MAX_TOKENS",
    "DEFAULT_E5_DIMENSION",
    "DEFAULT_E5_MODEL_ID",
    "DEFAULT_E5_REVISION",
    "build_report",
    "compute_build_id",
    "write_build_report",
]

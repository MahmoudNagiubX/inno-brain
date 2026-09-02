import hashlib
import io
import json
import platform
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .archive import write_event_archive
from .authoring import (
    EventAuthoringBundle,
    SourceInventory,
    canonical_authoring_json,
    load_authoring_bundle,
)
from .chunking import CanonicalChunk, chunk_document
from .crypto import sign_manifest
from .embeddings import EmbeddingMatrix, build_embedding_matrix
from .errors import EventCompatibilityError, EventSchemaError
from .manifest import canonical_manifest_bytes
from .models import (
    BuilderSpec,
    ChunkingSpec,
    EmbeddingSpec,
    EventPackageManifest,
    ManifestFile,
)
from .parser import ParsedDocument, parse_document

BUILDER_SCHEMA_VERSION = "1.0"
DEFAULT_E5_MODEL_ID = "intfloat/multilingual-e5-small"
DEFAULT_E5_REVISION = "614241f"
DEFAULT_E5_DIMENSION = 384
DEFAULT_CHUNK_MAX_TOKENS = 384


@dataclass(frozen=True, slots=True)
class EventBuildResult:
    archive_path: Path
    manifest: EventPackageManifest
    report: dict[str, Any]
    parsed_documents: tuple[ParsedDocument, ...]
    chunks: tuple[CanonicalChunk, ...]
    embeddings: EmbeddingMatrix


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


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _chunks_jsonl(chunks: Sequence[CanonicalChunk]) -> bytes:
    lines = []
    for chunk in chunks:
        lines.append(
            _json_bytes(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "normalized_text": chunk.normalized_text,
                    "language": chunk.language,
                    "authority_level": chunk.authority_level,
                    "valid_from": chunk.valid_from,
                    "valid_until": chunk.valid_until,
                    "source_path": chunk.source_path,
                    "headings": list(chunk.headings),
                    "page_numbers": list(chunk.page_numbers),
                    "embedding_row": chunk.embedding_row,
                    "token_count": chunk.token_count,
                }
            ).decode("utf-8")
        )
    return "".join(lines).encode("utf-8")


def _npy_bytes(matrix: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.save(stream, np.asarray(matrix, dtype=np.dtype("<f4")), allow_pickle=False)
    return stream.getvalue()


def _load_private_key(value: Ed25519PrivateKey | Path | str) -> Ed25519PrivateKey:
    if isinstance(value, Ed25519PrivateKey):
        return value
    try:
        key = serialization.load_pem_private_key(Path(value).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise EventCompatibilityError(
            "production signing key is not a valid PEM Ed25519 key"
        ) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise EventCompatibilityError("production signing key must be Ed25519")
    return key


def _manifest_files(payloads: dict[str, bytes]) -> list[ManifestFile]:
    return [
        ManifestFile(
            path=path,
            sha256=hashlib.sha256(contents).hexdigest(),
            size_bytes=len(contents),
            role=(
                "structured"
                if path.startswith("structured/")
                else "document"
                if path.startswith("documents/")
                else "knowledge"
                if path.startswith("knowledge/")
                else "report"
                if path.startswith("reports/")
                else "metadata"
            ),
        )
        for path, contents in sorted(payloads.items())
    ]


async def build_event_package(
    source_root: Path | str,
    output_path: Path | str,
    *,
    embedding_provider: object,
    tokenizer: object | None = None,
    deployable: bool = False,
    signing_key: Ed25519PrivateKey | Path | str | None = None,
    key_id: str | None = None,
    docling_version: str = "2.124.0",
    cache_dir: Path | str | None = None,
    allow_plaintext_fallback: bool = True,
) -> EventBuildResult:
    """Build, sign when requested, and self-verify one self-contained event archive.

    The provider and tokenizer are injected deliberately: production callers must
    construct the real E5 provider from local assets, while automated tests can use
    an explicitly non-deployable provider without putting it in runtime code.
    """

    started = time.perf_counter()
    source_root = Path(source_root).resolve()
    output_path = Path(output_path).resolve()
    if deployable:
        from .embeddings import MultilingualE5OnnxProvider

        if not isinstance(embedding_provider, MultilingualE5OnnxProvider):
            raise EventCompatibilityError(
                "deployable packages require the real multilingual-E5 ONNX provider"
            )
        if tokenizer is None:
            raise EventCompatibilityError("deployable packages require the real E5 tokenizer")
        if signing_key is None or not key_id:
            raise EventCompatibilityError(
                "production builds require an Ed25519 signing key and key ID"
            )
    if tokenizer is None:
        raise EventCompatibilityError("event builds require an E5-compatible tokenizer")

    bundle, inventory = load_authoring_bundle(source_root)
    build_id = compute_build_id(
        bundle,
        inventory,
        docling_version=docling_version,
        chunk_max_tokens=DEFAULT_CHUNK_MAX_TOKENS,
    )
    parsed: list[ParsedDocument] = []
    chunks: list[CanonicalChunk] = []
    warnings: list[str] = []
    errors: list[str] = []
    for document in bundle.event.documents:
        try:
            parsed_document = parse_document(
                document,
                source_root,
                cache_dir=cache_dir,
                allow_plaintext_fallback=allow_plaintext_fallback and not deployable,
            )
            parsed.append(parsed_document)
            warnings.extend(parsed_document.warnings)
            chunks.extend(
                chunk_document(
                    parsed_document,
                    document,
                    tokenizer=tokenizer,
                    max_tokens=DEFAULT_CHUNK_MAX_TOKENS,
                )
            )
        except (EventSchemaError, ValueError) as exc:
            message = f"{document.id}: {exc}"
            if document.required or deployable:
                raise EventSchemaError(message) from exc
            errors.append(message)

    embedding_result = await build_embedding_matrix(
        [chunk.text for chunk in chunks],
        embedding_provider,
        deployable=deployable,
    )
    payloads: dict[str, bytes] = {}
    for structured_file in sorted((source_root / "structured").glob("*.yaml")):
        if structured_file.is_file():
            payloads[f"structured/{structured_file.name}"] = structured_file.read_bytes()
    for source in inventory.files:
        payloads[source.relative_path] = (source_root / Path(source.relative_path)).read_bytes()
    payloads["knowledge/chunks.jsonl"] = _chunks_jsonl(chunks)
    payloads["knowledge/embeddings.npy"] = _npy_bytes(embedding_result.values)
    payloads["knowledge/build_meta.json"] = _json_bytes(
        {
            "schema_version": "1.0",
            "build_id": build_id,
            "event_id": bundle.event.id,
            "event_version": bundle.event.version,
            "deployable": deployable,
            "embedding_model_id": DEFAULT_E5_MODEL_ID,
            "embedding_revision": DEFAULT_E5_REVISION,
            "embedding_dimension": DEFAULT_E5_DIMENSION,
            "chunk_max_tokens": DEFAULT_CHUNK_MAX_TOKENS,
            "builder_schema_version": BUILDER_SCHEMA_VERSION,
        }
    )
    report = build_report(
        build_id=build_id,
        source_files=len(inventory.files),
        source_bytes=sum(source.size_bytes for source in inventory.files),
        structured_counts={
            "locations": len(bundle.locations),
            "speakers": len(bundle.speakers),
            "sessions": len(bundle.sessions),
            "booths": len(bundle.booths),
            "aliases": len(bundle.aliases),
            "glossary": len(bundle.glossary),
        },
        parsed_documents=len(parsed),
        parse_warnings=warnings,
        parse_errors=errors,
        chunk_count=len(chunks),
        token_counts=[chunk.token_count for chunk in chunks],
        embedding_checks={
            "model_id": DEFAULT_E5_MODEL_ID,
            "revision": DEFAULT_E5_REVISION,
            "shape": list(embedding_result.values.shape),
            "dtype": embedding_result.values.dtype.str,
            "unit_normalized": True,
            "deployable": deployable,
        },
        dependency_versions={
            "python": platform.python_version(),
            "docling": docling_version,
            "sqlite_vec": "0.1.9",
        },
        durations_seconds={"build": round(time.perf_counter() - started, 6)},
    )
    payloads["reports/build_report.json"] = _json_bytes(report)

    manifest = EventPackageManifest(
        package_type="innobrain.event",
        package_schema_version="1.0",
        event_id=bundle.event.id,
        event_version=bundle.event.version,
        client_id=bundle.event.client_id,
        title=bundle.event.title,
        default_locale=bundle.event.default_locale,
        timezone=bundle.event.timezone,
        created_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        build_id=build_id,
        builder=BuilderSpec(name="innobrain-event-builder", version=BUILDER_SCHEMA_VERSION),
        deployable=deployable,
        runtime_compat={"python": ">=3.11,<3.15", "sqlite_vec": "0.1.9"},
        embedding=EmbeddingSpec(
            model_id=DEFAULT_E5_MODEL_ID,
            revision=DEFAULT_E5_REVISION,
            dimension=DEFAULT_E5_DIMENSION,
            dtype="<f4",
            max_input_tokens=512,
        ),
        chunking=ChunkingSpec(
            max_tokens=DEFAULT_CHUNK_MAX_TOKENS,
            merge_peers=True,
            tokenizer_model=DEFAULT_E5_MODEL_ID,
        ),
        structured_schema={"version": "1.0", "strict": True},
        files=_manifest_files(payloads),
    )
    signature_bytes: bytes | None = None
    if signing_key is not None:
        if not key_id:
            raise EventCompatibilityError("a key ID is required when signing a package")
        signature = sign_manifest(manifest, _load_private_key(signing_key), key_id=key_id)
        signature_bytes = _json_bytes(signature.model_dump(mode="json"))
    write_event_archive(
        output_path,
        manifest_bytes=canonical_manifest_bytes(manifest),
        signature_bytes=signature_bytes,
        payloads=payloads,
    )
    from .validation import PackageVerificationPolicy, verify_event_package

    verify_event_package(
        output_path,
        policy=PackageVerificationPolicy(
            environment="production" if deployable else "development",
            allow_unsigned_development=not deployable,
            trusted_keys=(
                {key_id: _load_private_key(signing_key).public_key()}
                if signing_key is not None and key_id
                else {}
            ),
        ),
    )
    return EventBuildResult(
        archive_path=output_path,
        manifest=manifest,
        report=report,
        parsed_documents=tuple(parsed),
        chunks=tuple(chunks),
        embeddings=embedding_result,
    )


__all__ = [
    "BUILDER_SCHEMA_VERSION",
    "DEFAULT_CHUNK_MAX_TOKENS",
    "DEFAULT_E5_DIMENSION",
    "DEFAULT_E5_MODEL_ID",
    "DEFAULT_E5_REVISION",
    "EventBuildResult",
    "build_report",
    "build_event_package",
    "compute_build_id",
    "write_build_report",
]

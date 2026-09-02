import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.normalize import normalize_arabic_retrieval
from innobrain.knowledge.vector_store import VectorStore

from .authoring import load_authoring_bundle
from .embeddings import load_embedding_matrix
from .errors import EventInstallError
from .validation import (
    PackageVerificationPolicy,
    VerifiedPackage,
    open_verified_event_package,
)


@dataclass(frozen=True, slots=True)
class InstalledEventPackage:
    manifest: object
    root: Path
    database_path: Path
    source_package: Path
    health: dict[str, int]
    readonly_connection: object

    def close(self) -> None:
        self.readonly_connection.close()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EventInstallError(f"invalid chunks JSONL at line {line_number}") from exc
        if not isinstance(value, dict):
            raise EventInstallError(f"chunk record at line {line_number} is not an object")
        records.append(value)
    return records


def _required_string(record: dict[str, object], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str):
        raise EventInstallError(f"chunk field {name!r} must be a string")
    return value


def _insert_knowledge(
    staging: Path,
    verified: VerifiedPackage,
) -> tuple[Path, dict[str, int]]:
    bundle, _ = load_authoring_bundle(staging)
    chunks = _read_jsonl(staging / "knowledge" / "chunks.jsonl")
    embeddings = load_embedding_matrix(
        staging / "knowledge" / "embeddings.npy", expected_rows=len(chunks)
    )
    database_path = staging / "event.sqlite3"
    conn = connect_event_db(database_path)
    try:
        initialize_schema(conn)
        event = bundle.event
        conn.execute(
            "INSERT INTO event_meta("
            "id, title, event_date, venue_name, timezone, event_version, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.id,
                event.title,
                event.start_date.isoformat(),
                event.venue,
                event.timezone,
                event.version,
                event.client_id,
            ),
        )
        conn.executemany(
            "INSERT INTO locations VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item.id,
                    event.id,
                    item.name,
                    normalize_arabic_retrieval(item.name),
                    item.level,
                    item.zone,
                    item.description,
                )
                for item in bundle.locations
            ],
        )
        conn.executemany(
            "INSERT INTO speakers VALUES (?, ?, ?, ?, ?)",
            [
                (item.id, event.id, item.name, normalize_arabic_retrieval(item.name), item.bio)
                for item in bundle.speakers
            ],
        )
        conn.executemany(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item.id,
                    event.id,
                    item.title,
                    normalize_arabic_retrieval(item.title),
                    item.starts_at.isoformat(),
                    item.ends_at.isoformat(),
                    item.location_id,
                    item.description,
                )
                for item in bundle.sessions
            ],
        )
        conn.executemany(
            "INSERT INTO session_speakers VALUES (?, ?)",
            [
                (session.id, speaker_id)
                for session in bundle.sessions
                for speaker_id in session.speaker_ids
            ],
        )
        conn.executemany(
            "INSERT INTO booths VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    item.id,
                    event.id,
                    item.name,
                    normalize_arabic_retrieval(item.name),
                    item.location_id,
                    item.description,
                )
                for item in bundle.booths
            ],
        )
    except Exception as exc:  # noqa: BLE001 - convert database failures to install errors.
        conn.close()
        raise EventInstallError(f"could not insert structured event data: {exc}") from exc

    # The schema has six columns after the primary identifiers; insert documents separately
    # so source metadata remains derived from the validated authoring bundle.
    document_entries = {
        entry.path: entry for entry in verified.manifest.files if entry.role == "document"
    }
    for document in bundle.event.documents:
        entry = document_entries.get(document.path)
        if entry is None:
            raise EventInstallError(
                f"document is absent from the package manifest: {document.path}"
            )
        conn.execute(
            """
            INSERT INTO documents(
                id, event_id, source_type, title, source_ref, checksum,
                event_version, client_id, language, authority_level, valid_from, valid_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.id,
                event.id,
                "local",
                document.title,
                document.path,
                entry.sha256,
                event.version,
                event.client_id,
                document.language,
                document.authority_level,
                document.valid_from.isoformat() if document.valid_from else None,
                document.valid_until.isoformat() if document.valid_until else None,
            ),
        )

    vector_rows: list[tuple[int, np.ndarray]] = []
    for row_id, chunk in enumerate(chunks, 1):
        document_id = _required_string(chunk, "document_id")
        if document_id not in {document.id for document in bundle.event.documents}:
            raise EventInstallError(f"chunk references unknown document: {document_id}")
        chunk_index = chunk.get("chunk_index")
        embedding_row = chunk.get("embedding_row")
        if not isinstance(chunk_index, int) or not isinstance(embedding_row, int):
            raise EventInstallError("chunk indexes must be integers")
        if embedding_row < 0 or embedding_row >= len(embeddings):
            raise EventInstallError("chunk embedding row is outside the embedding matrix")
        text = _required_string(chunk, "text")
        normalized_text = _required_string(chunk, "normalized_text")
        metadata = {
            key: chunk.get(key)
            for key in ("chunk_id", "source_path", "headings", "page_numbers", "token_count")
        }
        conn.execute(
            """
            INSERT INTO chunks(
                id, document_id, event_id, chunk_index, text, normalized_text, metadata_json,
                event_version, client_id, language, authority_level, valid_from, valid_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                document_id,
                bundle.event.id,
                chunk_index,
                text,
                normalized_text,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                bundle.event.version,
                bundle.event.client_id,
                _required_string(chunk, "language"),
                _required_string(chunk, "authority_level"),
                chunk.get("valid_from"),
                chunk.get("valid_until"),
            ),
        )
        vector_rows.append((row_id, embeddings[embedding_row]))
    conn.commit()
    VectorStore(conn, dimension=embeddings.shape[1]).rebuild(vector_rows)
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    readonly = connect_event_db(database_path, readonly=True)
    try:
        VectorStore(readonly, dimension=embeddings.shape[1], create_if_missing=False)
        health = {
            "chunks": readonly.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
            "fts": readonly.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0],
            "vec": readonly.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0],
            "embedding_rows": int(embeddings.shape[0]),
        }
        if len({health["chunks"], health["fts"], health["vec"], health["embedding_rows"]}) != 1:
            raise EventInstallError(f"installed knowledge health mismatch: {health}")
    except Exception:
        readonly.close()
        raise
    readonly.close()
    return database_path, health


def _installed_result(
    root: Path, manifest: object, health: dict[str, int]
) -> InstalledEventPackage:
    database_path = root / "event.sqlite3"
    return InstalledEventPackage(
        manifest=manifest,
        root=root,
        database_path=database_path,
        source_package=root / "source.innoevent",
        health=health,
        readonly_connection=connect_event_db(database_path, readonly=True),
    )


def install_event_package(
    archive_path: Path | str,
    data_root: Path | str,
    *,
    verification_policy: PackageVerificationPolicy | None = None,
) -> InstalledEventPackage:
    """Verify, compile and atomically install one event package on this target."""

    archive_path = Path(archive_path).resolve()
    data_root = Path(data_root).resolve()
    staging = data_root / "events" / ".staging" / uuid.uuid4().hex
    installed_root = data_root / "events" / "installed"
    policy = verification_policy or PackageVerificationPolicy(environment="production")
    try:
        with open_verified_event_package(archive_path, policy=policy) as verified_archive:
            verified_archive.extract_to(staging)
            verified_archive.copy_source_to(staging / "source.innoevent")
            verified = verified_archive.package_metadata()
        event_root = installed_root / verified.manifest.event_id / verified.manifest.event_version
        final_root = event_root / verified.manifest.build_id
        if final_root.exists():
            existing_manifest = final_root / "manifest.json"
            existing_text = (
                existing_manifest.read_text(encoding="utf-8")
                if existing_manifest.is_file()
                else ""
            )
            if verified.manifest.build_id not in existing_text:
                raise EventInstallError("an existing installed build conflicts with this package")
            shutil.rmtree(staging)
            report = json.loads((final_root / "install_report.json").read_text(encoding="utf-8"))
            return _installed_result(final_root, verified.manifest, report["health"])

        database_path, health = _insert_knowledge(staging, verified)
        (staging / "manifest.json").write_bytes(verified.manifest_bytes)
        if verified.signature is not None:
            signature_path = staging / "signature.json"
            signature_path.write_text(
                json.dumps(verified.signature.model_dump(mode="json"), sort_keys=True, indent=2)
                + "\n",
                encoding="utf-8",
            )
        (staging / "install_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "event_id": verified.manifest.event_id,
                    "event_version": verified.manifest.event_version,
                    "build_id": verified.manifest.build_id,
                    "health": health,
                    "database": database_path.name,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        event_root.mkdir(parents=True, exist_ok=True)
        os.replace(staging, final_root)
        return _installed_result(final_root, verified.manifest, health)
    except EventInstallError:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001 - installation exposes one stable error type.
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise EventInstallError(f"could not install event package: {exc}") from exc


__all__ = ["InstalledEventPackage", "install_event_package"]

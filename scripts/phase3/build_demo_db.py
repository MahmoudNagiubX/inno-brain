"""Build the deterministic Phase 3 demo event database without a vec index."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.normalize import normalize_arabic_retrieval

DEFAULT_FIXTURE = Path(__file__).parents[2] / "fixtures" / "phase3" / "demo_event.yaml"
DEFAULT_DB = Path(__file__).parents[2] / "artifacts" / "phase3" / "demo_event.sqlite3"


def _as_text(value: Any) -> str:
    return str(value)


def build_demo_db(fixture_path: Path = DEFAULT_FIXTURE, db_path: Path = DEFAULT_DB) -> Path:
    fixture = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(fixture, dict) or not isinstance(fixture.get("event"), dict):
        raise ValueError("demo fixture must contain an event mapping")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    for sidecar in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        if sidecar.exists():
            sidecar.unlink()

    conn = connect_event_db(db_path)
    try:
        initialize_schema(conn)
        event = fixture["event"]
        conn.execute(
            (
                "INSERT INTO event_meta(id, title, event_date, venue_name, timezone) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            (
                _as_text(event["id"]),
                _as_text(event["title"]),
                _as_text(event["date"]),
                _as_text(event["venue"]),
                _as_text(event["timezone"]),
            ),
        )

        for location in fixture.get("locations", []):
            conn.execute(
                """
                INSERT INTO locations
                    (id, event_id, name, normalized_name, level, zone, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location["id"],
                    event["id"],
                    location["name"],
                    normalize_arabic_retrieval(location["name"]),
                    location.get("level"),
                    location.get("zone"),
                    location.get("description", ""),
                ),
            )

        for speaker in fixture.get("speakers", []):
            conn.execute(
                """
                INSERT INTO speakers(id, event_id, name, normalized_name, bio)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    speaker["id"],
                    event["id"],
                    speaker["name"],
                    normalize_arabic_retrieval(speaker["name"]),
                    speaker.get("bio", ""),
                ),
            )

        for session in fixture.get("sessions", []):
            conn.execute(
                """
                INSERT INTO sessions
                    (id, event_id, title, normalized_title, starts_at, ends_at,
                     location_id, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"],
                    event["id"],
                    session["title"],
                    normalize_arabic_retrieval(session["title"]),
                    session["starts_at"],
                    session["ends_at"],
                    session["location_id"],
                    session.get("description", ""),
                ),
            )
            conn.executemany(
                "INSERT INTO session_speakers(session_id, speaker_id) VALUES (?, ?)",
                [(session["id"], speaker_id) for speaker_id in session.get("speakers", [])],
            )

        for booth in fixture.get("booths", []):
            conn.execute(
                """
                INSERT INTO booths(id, event_id, name, normalized_name, location_id, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    booth["id"],
                    event["id"],
                    booth["name"],
                    normalize_arabic_retrieval(booth["name"]),
                    booth["location_id"],
                    booth.get("description", ""),
                ),
            )

        for document in fixture.get("documents", []):
            document_text = _as_text(document.get("text", ""))
            checksum = hashlib.sha256(document_text.encode("utf-8")).hexdigest()
            conn.execute(
                """
                INSERT INTO documents(id, event_id, source_type, title, source_ref, checksum)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document["id"],
                    event["id"],
                    document["source_type"],
                    document["title"],
                    document["source_ref"],
                    checksum,
                ),
            )
            chunks = [line.strip() for line in document_text.splitlines() if line.strip()]
            for chunk_index, chunk_text in enumerate(chunks):
                metadata = json.dumps(
                    {"document_title": document["title"], "chunk_index": chunk_index},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                conn.execute(
                    """
                    INSERT INTO chunks
                        (id, document_id, event_id, chunk_index, text, normalized_text,
                         metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_index + 1,
                        document["id"],
                        event["id"],
                        chunk_index,
                        chunk_text,
                        normalize_arabic_retrieval(chunk_text),
                        metadata,
                    ),
                )
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES (?, ?)",
            ("fixture_id", _as_text(event["id"])),
        )
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES (?, ?)",
            ("builder_version", "phase3-task6-v1"),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(build_demo_db(args.fixture, args.db))


if __name__ == "__main__":
    main()

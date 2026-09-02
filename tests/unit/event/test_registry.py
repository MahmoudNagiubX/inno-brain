import json
from pathlib import Path

from innobrain.event.registry import EventRegistry, version_tuple


def _write_candidate(root: Path, *, event_id: str = "event-alpha") -> None:
    build_id = "a" * 64
    event_version = "1.2.3"
    candidate = root / "events" / "installed" / event_id / event_version / build_id
    candidate.mkdir(parents=True)
    manifest = {
        "package_type": "innobrain.event",
        "package_schema_version": "1.0",
        "event_id": event_id,
        "event_version": event_version,
        "client_id": "client",
        "title": "Event",
        "default_locale": "ar-EG",
        "timezone": "Africa/Cairo",
        "created_at_utc": "2026-01-01T00:00:00Z",
        "build_id": build_id,
        "builder": {"name": "builder", "version": "1.0"},
        "deployable": False,
        "runtime_compat": {},
        "embedding": {"model_id": "e5", "revision": "r", "dimension": 384},
        "chunking": {"max_tokens": 384},
        "structured_schema": {"version": "1.0"},
        "extensions": [],
        "files": [],
    }
    (candidate / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (candidate / "install_report.json").write_text(
        json.dumps(
            {
                "event_id": event_id,
                "event_version": event_version,
                "build_id": build_id,
                "health": {"chunks": 1, "fts": 1, "vec": 1, "embedding_rows": 1},
            }
        ),
        encoding="utf-8",
    )
    (candidate / "event.sqlite3").touch()


def test_registry_verifies_manifest_report_identity_and_health(tmp_path: Path) -> None:
    _write_candidate(tmp_path)
    registry = EventRegistry(tmp_path)
    records = registry.list()
    assert len(records) == 1
    assert records[0].event_id == "event-alpha"
    assert records[0].healthy is True
    assert registry.get("event-alpha").build_id == "a" * 64

    invalid = tmp_path / "events" / "installed" / "wrong-name" / "1.2.3" / ("b" * 64)
    invalid.mkdir(parents=True)
    (invalid / "manifest.json").write_text(
        (tmp_path / "events" / "installed" / "event-alpha" / "1.2.3" / ("a" * 64) / "manifest.json")
        .read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    assert len(registry.list()) == 1

    partial = tmp_path / "events" / "installed" / "partial" / "1.2.3" / ("c" * 64)
    partial.mkdir(parents=True)
    (partial / "manifest.json").write_text(
        (tmp_path / "events" / "installed" / "event-alpha" / "1.2.3" / ("a" * 64) / "manifest.json")
        .read_text(encoding="utf-8")
        .replace("event-alpha", "partial")
        .replace("a" * 64, "c" * 64),
        encoding="utf-8",
    )
    (partial / "install_report.json").write_text(
        json.dumps(
            {
                "event_id": "partial",
                "event_version": "1.2.3",
                "build_id": "c" * 64,
                "health": {"chunks": 1},
            }
        ),
        encoding="utf-8",
    )
    (partial / "event.sqlite3").touch()
    assert len(registry.list()) == 2
    assert registry.get("partial").healthy is False


def test_version_comparison_uses_integer_semver_components() -> None:
    assert version_tuple("10.2.3") > version_tuple("2.12.99")

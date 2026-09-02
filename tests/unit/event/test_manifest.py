import json

import pytest
from pydantic import ValidationError

from innobrain.event.manifest import canonical_manifest_bytes
from innobrain.event.models import EventPackageManifest


def _manifest(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "package_type": "innobrain.event",
        "package_schema_version": "1.0",
        "event_id": "event-alpha",
        "event_version": "1.2.3",
        "client_id": "client-alpha",
        "title": "Alpha Event",
        "default_locale": "ar-EG",
        "timezone": "Africa/Cairo",
        "created_at_utc": "2026-09-02T12:00:00Z",
        "build_id": "a" * 64,
        "builder": {"name": "innobrain", "version": "phase4"},
        "deployable": False,
        "runtime_compat": {"python": ">=3.11,<3.15"},
        "embedding": {
            "model_id": "intfloat/multilingual-e5-small",
            "revision": "614241f",
            "dimension": 384,
            "dtype": "<f4",
        },
        "chunking": {"max_tokens": 384, "merge_peers": True},
        "structured_schema": {"version": "1.0"},
        "extensions": [],
        "files": [
            {
                "path": "knowledge/chunks.jsonl",
                "sha256": "b" * 64,
                "size_bytes": 12,
                "role": "knowledge_chunks",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_manifest_requires_strict_package_identity_and_hashes() -> None:
    manifest = EventPackageManifest.model_validate(_manifest())

    assert manifest.package_type == "innobrain.event"
    assert manifest.files[0].path == "knowledge/chunks.jsonl"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("package_type", "other.package"),
        ("package_schema_version", "2.0"),
        ("event_version", "1.2"),
        ("build_id", "A" * 64),
        ("files", [{"path": "../escape", "sha256": "b" * 64, "size_bytes": 1, "role": "x"}]),
    ],
)
def test_manifest_rejects_invalid_identity_or_path(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        EventPackageManifest.model_validate(_manifest(**{field: value}))


def test_manifest_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EventPackageManifest.model_validate(_manifest(unexpected=True))


def test_canonical_manifest_bytes_are_stable_and_newline_terminated() -> None:
    first = EventPackageManifest.model_validate(_manifest())
    reordered = dict(reversed(list(_manifest().items())))
    second = EventPackageManifest.model_validate(reordered)

    expected = (
        json.dumps(
            first.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    assert canonical_manifest_bytes(first) == expected
    assert canonical_manifest_bytes(first) == canonical_manifest_bytes(second)

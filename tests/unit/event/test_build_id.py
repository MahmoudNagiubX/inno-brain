import json
from pathlib import Path

from innobrain.event.authoring import load_authoring_bundle
from innobrain.event.builder import (
    build_report,
    compute_build_id,
    write_build_report,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_build_id_is_stable_and_excludes_wall_clock_time(tmp_path: Path) -> None:
    source_root = tmp_path / "event"
    fixture_root = REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha"
    import shutil

    shutil.copytree(fixture_root, source_root)
    bundle, inventory = load_authoring_bundle(source_root)

    first = compute_build_id(bundle, inventory, docling_version="2.124.0")
    second = compute_build_id(bundle, inventory, docling_version="2.124.0")

    assert first == second
    assert len(first) == 64
    assert first.islower()


def test_build_id_changes_when_a_source_byte_changes(tmp_path: Path) -> None:
    source_root = tmp_path / "event"
    fixture_root = REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha"
    import shutil

    shutil.copytree(fixture_root, source_root)
    bundle, inventory = load_authoring_bundle(source_root)
    first = compute_build_id(bundle, inventory)
    (source_root / "documents" / "guide.md").write_text(
        (source_root / "documents" / "guide.md").read_text(encoding="utf-8") + "\nchanged",
        encoding="utf-8",
    )
    _, changed_inventory = load_authoring_bundle(source_root)

    assert first != compute_build_id(bundle, changed_inventory)


def test_build_report_contains_required_sections_and_is_json(tmp_path: Path) -> None:
    report = build_report(
        build_id="a" * 64,
        source_files=2,
        source_bytes=12,
        structured_counts={"locations": 1, "sessions": 2},
        parsed_documents=2,
        parse_warnings=["fallback"],
        chunk_count=3,
        token_counts=[10, 20, 30],
        embedding_checks={"shape": [3, 384], "deployable": False},
        dependency_versions={"python": "3.14"},
        durations_seconds={"total": 0.1},
    )
    path = write_build_report(tmp_path / "build_report.json", report)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["build_id"] == "a" * 64
    assert loaded["sources"]["file_count"] == 2
    assert loaded["chunks"]["count"] == 3
    assert loaded["warnings"] == ["fallback"]

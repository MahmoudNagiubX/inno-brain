from pathlib import Path

import pytest

from innobrain.event.activation import ActivationManager
from innobrain.event.errors import EventActivationBusy, EventActivationError
from innobrain.event.registry import InstalledEventRecord
from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.vector_store import VectorStore


class FakeRegistry:
    def __init__(self, records: list[InstalledEventRecord]) -> None:
        self.records = {
            (item.event_id, item.event_version, item.build_id): item for item in records
        }

    def get(self, event_id: str, *, event_version: str | None = None, build_id: str | None = None):
        matches = [
            item
            for item in self.records.values()
            if item.event_id == event_id
            and (event_version is None or item.event_version == event_version)
            and (build_id is None or item.build_id == build_id)
        ]
        if not matches:
            raise EventActivationError("missing test event")
        return sorted(matches, key=lambda item: item.version)[-1]


def _record(tmp_path: Path, event_id: str, version: str, build_char: str, *, healthy: bool = True):
    root = tmp_path / event_id / version / (build_char * 64)
    root.mkdir(parents=True)
    db_path = root / "event.sqlite3"
    conn = connect_event_db(db_path)
    initialize_schema(conn)
    VectorStore(conn)
    conn.close()
    counts = {"chunks": 1, "fts": 1, "vec": 1, "embedding_rows": 1}
    if not healthy:
        counts["vec"] = 0
    return InstalledEventRecord(event_id, version, build_char * 64, root, db_path, counts)


def test_activation_is_atomic_busy_safe_and_rejects_normal_downgrade(tmp_path: Path) -> None:
    alpha_v1 = _record(tmp_path, "alpha", "1.0.0", "a")
    alpha_v2 = _record(tmp_path, "alpha", "2.0.0", "b")
    broken = _record(tmp_path, "broken", "1.0.0", "c", healthy=False)
    manager = ActivationManager(
        tmp_path,
        FakeRegistry([alpha_v1, alpha_v2, broken]),
        idle_guard=lambda: True,
    )
    manager.activate("alpha", event_version="2.0.0", build_id=alpha_v2.build_id)
    pointer_before = manager.pointer_path.read_bytes()

    with pytest.raises(EventActivationError, match="downgrade"):
        manager.activate("alpha", event_version="1.0.0", build_id=alpha_v1.build_id)
    with pytest.raises(EventActivationError, match="healthy"):
        manager.activate("broken", event_version="1.0.0", build_id=broken.build_id)
    assert manager.pointer_path.read_bytes() == pointer_before

    busy = ActivationManager(
        tmp_path / "busy",
        FakeRegistry([alpha_v1]),
        idle_guard=lambda: False,
    )
    with pytest.raises(EventActivationBusy):
        busy.activate("alpha", event_version="1.0.0", build_id=alpha_v1.build_id)


def test_activation_hook_runs_only_after_candidate_database_validation(tmp_path: Path) -> None:
    alpha = _record(tmp_path, "alpha", "1.0.0", "a")
    events: list[str] = []
    manager = ActivationManager(
        tmp_path,
        FakeRegistry([alpha]),
        idle_guard=lambda: True,
        switch_hook=lambda record: events.append(record.event_id),
    )
    manager.activate("alpha", event_version="1.0.0", build_id=alpha.build_id)
    assert events == ["alpha"]
    assert manager.active().build_id == alpha.build_id
    assert manager.history_path.read_text(encoding="utf-8").count("alpha") == 1

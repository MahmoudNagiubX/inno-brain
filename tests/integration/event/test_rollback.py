from pathlib import Path

from innobrain.event.activation import ActivationManager
from innobrain.event.registry import InstalledEventRecord
from innobrain.knowledge.database import connect_event_db, initialize_schema
from innobrain.knowledge.vector_store import VectorStore


class Registry:
    def __init__(self, records):
        self.records = records

    def get(self, event_id, *, event_version=None, build_id=None):
        return next(
            item
            for item in self.records
            if item.event_id == event_id
            and (event_version is None or item.event_version == event_version)
            and (build_id is None or item.build_id == build_id)
        )


def _record(tmp_path: Path, event_id: str, version: str, char: str) -> InstalledEventRecord:
    root = tmp_path / event_id / version / (char * 64)
    root.mkdir(parents=True)
    db_path = root / "event.sqlite3"
    conn = connect_event_db(db_path)
    initialize_schema(conn)
    VectorStore(conn)
    conn.close()
    return InstalledEventRecord(
        event_id, version, char * 64, root, db_path,
        {"chunks": 1, "fts": 1, "vec": 1, "embedding_rows": 1},
    )


def test_explicit_rollback_reactivates_previous_healthy_build_and_logs_action(
    tmp_path: Path,
) -> None:
    alpha = _record(tmp_path, "alpha", "1.0.0", "a")
    beta = _record(tmp_path, "beta", "1.0.0", "b")
    manager = ActivationManager(tmp_path, Registry([alpha, beta]), idle_guard=lambda: True)
    manager.activate("alpha", event_version="1.0.0", build_id=alpha.build_id)
    manager.activate("beta", event_version="1.0.0", build_id=beta.build_id)

    restored = manager.rollback()

    assert restored.event_id == "alpha"
    assert manager.active().event_id == "alpha"
    assert '"action": "rollback"' in manager.history_path.read_text(encoding="utf-8")

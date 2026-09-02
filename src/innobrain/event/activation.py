import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from innobrain.knowledge.database import connect_event_db
from innobrain.knowledge.vector_store import VectorStore

from .errors import EventActivationBusy, EventActivationError
from .registry import EventRegistry, InstalledEventRecord


class IdleGuard(Protocol):
    def __call__(self) -> bool: ...


ActivationHook = Callable[[InstalledEventRecord], None]


class ActivationManager:
    def __init__(
        self,
        data_root: Path | str,
        registry: EventRegistry,
        *,
        idle_guard: IdleGuard | None = None,
        switch_hook: ActivationHook | None = None,
    ) -> None:
        self.data_root = Path(data_root).resolve()
        self.registry = registry
        self.idle_guard = idle_guard or (lambda: True)
        self.switch_hook = switch_hook
        self.state_root = self.data_root / "events"
        self.pointer_path = self.state_root / "active_event.json"
        self.history_path = self.state_root / "activation_history.jsonl"

    def active(self) -> InstalledEventRecord | None:
        if not self.pointer_path.is_file():
            return None
        try:
            pointer = json.loads(self.pointer_path.read_text(encoding="utf-8"))
            return self.registry.get(
                pointer["event_id"],
                event_version=pointer["event_version"],
                build_id=pointer["build_id"],
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EventActivationError("active event pointer is invalid") from exc

    def _candidate(
        self,
        event_id: str,
        *,
        event_version: str | None,
        build_id: str | None,
    ) -> InstalledEventRecord:
        try:
            candidate = self.registry.get(
                event_id, event_version=event_version, build_id=build_id
            )
        except Exception as exc:  # noqa: BLE001 - registry implementations expose one lookup boundary.
            if isinstance(exc, EventActivationError):
                raise
            raise EventActivationError("installed event candidate was not found") from exc
        if not candidate.healthy:
            raise EventActivationError("event candidate is not healthy")
        try:
            conn = connect_event_db(candidate.database_path, readonly=True)
            VectorStore(conn, create_if_missing=False)
            conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
            conn.close()
        except Exception as exc:  # noqa: BLE001 - candidate validation is one stable gate.
            raise EventActivationError(
                "event candidate database failed read-only validation"
            ) from exc
        return candidate

    def _append_history(self, record: InstalledEventRecord, action: str) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "action": action,
            "event_id": record.event_id,
            "event_version": record.event_version,
            "build_id": record.build_id,
        }
        with self.history_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _write_pointer(self, record: InstalledEventRecord) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        temporary = self.pointer_path.with_name("active_event.json.tmp")
        payload = {
            "event_id": record.event_id,
            "event_version": record.event_version,
            "build_id": record.build_id,
        }
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.pointer_path)

    def _activate(
        self,
        candidate: InstalledEventRecord,
        *,
        action: str,
        allow_downgrade: bool,
    ) -> InstalledEventRecord:
        current = self.active()
        if (
            current is not None
            and current.event_id == candidate.event_id
            and candidate.version < current.version
            and not allow_downgrade
        ):
            raise EventActivationError("normal activation cannot perform an event downgrade")
        if self.switch_hook is not None:
            self.switch_hook(candidate)
        self._write_pointer(candidate)
        self._append_history(candidate, action)
        return candidate

    def activate(
        self,
        event_id: str,
        *,
        event_version: str | None = None,
        build_id: str | None = None,
    ) -> InstalledEventRecord:
        if not self.idle_guard():
            raise EventActivationBusy("conversation runtime is busy")
        candidate = self._candidate(
            event_id, event_version=event_version, build_id=build_id
        )
        return self._activate(candidate, action="activation", allow_downgrade=False)

    def rollback(self) -> InstalledEventRecord:
        if not self.idle_guard():
            raise EventActivationBusy("conversation runtime is busy")
        current = self.active()
        if current is None:
            raise EventActivationError("there is no active event to roll back")
        if not self.history_path.is_file():
            raise EventActivationError("no previous activation is available for rollback")
        entries = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        for entry in reversed(entries):
            if (
                entry.get("event_id") == current.event_id
                and entry.get("event_version") == current.event_version
                and entry.get("build_id") == current.build_id
            ):
                continue
            try:
                candidate = self._candidate(
                    entry["event_id"],
                    event_version=entry["event_version"],
                    build_id=entry["build_id"],
                )
            except (EventActivationError, KeyError):
                continue
            return self._activate(candidate, action="rollback", allow_downgrade=True)
        raise EventActivationError("no previous healthy event is available for rollback")


__all__ = ["ActivationHook", "ActivationManager", "IdleGuard"]

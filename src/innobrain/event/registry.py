import json
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import EventInstallError
from .models import EventPackageManifest

_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def version_tuple(version: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"invalid event version: {version}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class InstalledEventRecord:
    event_id: str
    event_version: str
    build_id: str
    root: Path
    database_path: Path
    health: dict[str, int]

    @property
    def version(self) -> tuple[int, int, int]:
        return version_tuple(self.event_version)

    @property
    def healthy(self) -> bool:
        return (
            self.database_path.is_file()
            and bool(self.health)
            and len(set(self.health.values())) == 1
        )


class EventRegistry:
    def __init__(self, data_root: Path | str) -> None:
        self.data_root = Path(data_root).resolve()
        self.installed_root = self.data_root / "events" / "installed"

    def _candidate(self, root: Path) -> InstalledEventRecord | None:
        manifest_path = root / "manifest.json"
        report_path = root / "install_report.json"
        try:
            manifest = EventPackageManifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            health = report["health"]
            if not isinstance(health, dict) or not all(
                isinstance(key, str) and isinstance(value, int) for key, value in health.items()
            ):
                raise ValueError("health report is not a string/integer mapping")
            expected_parts = (manifest.event_id, manifest.event_version, manifest.build_id)
            if tuple(root.relative_to(self.installed_root).parts) != expected_parts:
                raise ValueError("installed directory does not match manifest identity")
            if (
                report.get("event_id") != manifest.event_id
                or report.get("event_version") != manifest.event_version
                or report.get("build_id") != manifest.build_id
            ):
                raise ValueError("install report identity does not match manifest")
            return InstalledEventRecord(
                event_id=manifest.event_id,
                event_version=manifest.event_version,
                build_id=manifest.build_id,
                root=root,
                database_path=root / "event.sqlite3",
                health=health,
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def discover(self) -> list[InstalledEventRecord]:
        if not self.installed_root.is_dir():
            return []
        records: list[InstalledEventRecord] = []
        for candidate in self.installed_root.glob("*/*/*"):
            if not candidate.is_dir():
                continue
            record = self._candidate(candidate)
            if record is not None:
                records.append(record)
        return sorted(records, key=lambda item: (item.event_id, item.version, item.build_id))

    def list(self, event_id: str | None = None) -> list[InstalledEventRecord]:
        records = self.discover()
        return [record for record in records if event_id is None or record.event_id == event_id]

    def get(
        self,
        event_id: str,
        *,
        event_version: str | None = None,
        build_id: str | None = None,
    ) -> InstalledEventRecord:
        matches = [
            record
            for record in self.list(event_id)
            if (event_version is None or record.event_version == event_version)
            and (build_id is None or record.build_id == build_id)
        ]
        if not matches:
            raise EventInstallError("installed event build was not found")
        return matches[-1]


__all__ = ["EventRegistry", "InstalledEventRecord", "version_tuple"]

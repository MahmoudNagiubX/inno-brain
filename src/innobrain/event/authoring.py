import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

AuthorityLevel = Literal["official", "approved", "reference", "marketing"]
EntityType = Literal["event", "location", "speaker", "session", "booth"]


class AuthoringModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventSource(AuthoringModel):
    id: str
    version: str
    client_id: str
    title: str
    start_date: date
    end_date: date
    venue: str
    timezone: str
    default_locale: str
    documents: list["DocumentSource"] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_event_window(self) -> "EventSource":
        if self.start_date >= self.end_date:
            raise ValueError("event start_date must precede end_date")
        return self


class LocationSource(AuthoringModel):
    id: str
    name: str
    level: str | None = None
    zone: str | None = None
    description: str = ""


class SpeakerSource(AuthoringModel):
    id: str
    name: str
    bio: str = ""


class SessionSource(AuthoringModel):
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    location_id: str
    speaker_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("speaker_ids", "speakers"),
    )
    description: str = ""

    @model_validator(mode="after")
    def validate_time_bounds(self) -> "SessionSource":
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise ValueError("session starts_at must be timezone-aware")
        if self.ends_at.tzinfo is None or self.ends_at.utcoffset() is None:
            raise ValueError("session ends_at must be timezone-aware")
        if self.starts_at >= self.ends_at:
            raise ValueError("session starts_at must precede ends_at")
        return self


class BoothSource(AuthoringModel):
    id: str
    name: str
    location_id: str
    description: str = ""


class AliasSource(AuthoringModel):
    alias: str
    entity_type: EntityType
    entity_id: str


class GlossaryTerm(AuthoringModel):
    term: str
    definition: str
    language: str = "ar-EG"


def _validate_relative_source_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or len(path.parts) == 0
        or any(part in {"", ".", ".."} for part in path.parts)
        or (len(value) >= 2 and value[1] == ":")
    ):
        raise ValueError("document path must be a relative local POSIX path")
    return value


class DocumentSource(AuthoringModel):
    id: str
    path: str
    title: str
    language: str
    authority_level: AuthorityLevel
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    required: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_relative_source_path(value)

    @model_validator(mode="after")
    def validate_validity_window(self) -> "DocumentSource":
        for field_name, value in (
            ("valid_from", self.valid_from),
            ("valid_until", self.valid_until),
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"document {field_name} must be timezone-aware")
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_from >= self.valid_until:
                raise ValueError("document valid_from must precede valid_until")
        return self


class EventAuthoringBundle(AuthoringModel):
    event: EventSource
    locations: list[LocationSource] = Field(default_factory=list)
    speakers: list[SpeakerSource] = Field(default_factory=list)
    sessions: list[SessionSource] = Field(default_factory=list)
    booths: list[BoothSource] = Field(default_factory=list)
    aliases: list[AliasSource] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    source_root: Path | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_references_and_collisions(self) -> "EventAuthoringBundle":
        collections = {
            "location": self.locations,
            "speaker": self.speakers,
            "session": self.sessions,
            "booth": self.booths,
        }
        all_ids: dict[str, str] = {self.event.id: "event"}
        for entity_type, entities in collections.items():
            for entity in entities:
                if entity.id in all_ids:
                    raise ValueError(f"duplicate entity id: {entity.id}")
                all_ids[entity.id] = entity_type

        location_ids = {item.id for item in self.locations}
        speaker_ids = {item.id for item in self.speakers}
        for session in self.sessions:
            if session.location_id not in location_ids:
                raise ValueError(f"session references missing location: {session.location_id}")
            missing_speakers = set(session.speaker_ids) - speaker_ids
            if missing_speakers:
                raise ValueError(f"session references missing speakers: {sorted(missing_speakers)}")
            self._validate_event_window(session.starts_at, session.ends_at, "session")
        for booth in self.booths:
            if booth.location_id not in location_ids:
                raise ValueError(f"booth references missing location: {booth.location_id}")

        aliases_seen: set[str] = set()
        for alias in self.aliases:
            normalized = alias.alias.casefold().strip()
            if not normalized or normalized in aliases_seen:
                raise ValueError(f"duplicate alias: {alias.alias}")
            aliases_seen.add(normalized)
            expected_type = "event" if alias.entity_type == "event" else alias.entity_type
            if all_ids.get(alias.entity_id) != expected_type:
                raise ValueError(f"alias references missing {alias.entity_type}: {alias.entity_id}")

        for index, first in enumerate(self.sessions):
            for second in self.sessions[index + 1 :]:
                if self._overlaps(first.starts_at, first.ends_at, second.starts_at, second.ends_at):
                    if first.location_id == second.location_id:
                        raise ValueError(f"location sessions overlap: {first.id}, {second.id}")
                    if set(first.speaker_ids) & set(second.speaker_ids):
                        raise ValueError(f"speaker sessions overlap: {first.id}, {second.id}")

        self._validate_source_files()
        return self

    def _validate_source_files(self) -> None:
        if self.source_root is None:
            return
        root = self.source_root.resolve()
        for document in self.event.documents:
            candidate = (root / Path(document.path)).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"document path escapes source root: {document.path}") from exc
            if not candidate.is_file():
                raise ValueError(f"document source does not exist: {document.path}")

    def _validate_event_window(self, starts_at: datetime, ends_at: datetime, label: str) -> None:
        if starts_at.date() < self.event.start_date or ends_at.date() > self.event.end_date:
            raise ValueError(f"{label} is outside the event date window")

    @staticmethod
    def _overlaps(
        first_start: datetime,
        first_end: datetime,
        second_start: datetime,
        second_end: datetime,
    ) -> bool:
        return first_start < second_end and second_start < first_end


@dataclass(frozen=True, slots=True)
class SourceFile:
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SourceInventory:
    files: tuple[SourceFile, ...]


def _read_yaml(path: Path) -> object:
    if not path.is_file():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _collection_payload(value: object, key: str, path: Path) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and set(value) == {key} and isinstance(value[key], list):
        return value[key]
    raise ValueError(f"{path} must contain a list or only a {key} list")


def _load_collection(
    root: Path,
    filename: str,
    key: str,
    model_type: type[BaseModel],
) -> list[BaseModel]:
    path = root / "structured" / filename
    return [
        model_type.model_validate(item)
        for item in _collection_payload(_read_yaml(path), key, path)
    ]


def build_source_inventory(root: Path, bundle: EventAuthoringBundle) -> SourceInventory:
    files: list[SourceFile] = []
    for document in bundle.event.documents:
        source = (root / document.path).resolve()
        contents = source.read_bytes()
        files.append(
            SourceFile(
                relative_path=source.relative_to(root.resolve()).as_posix(),
                sha256=hashlib.sha256(contents).hexdigest(),
                size_bytes=len(contents),
            )
        )
    return SourceInventory(files=tuple(sorted(files, key=lambda item: item.relative_path)))


def load_authoring_bundle(root: Path | str) -> tuple[EventAuthoringBundle, SourceInventory]:
    root = Path(root).resolve()
    structured = root / "structured"
    event = EventSource.model_validate(_read_yaml(structured / "event.yaml"))
    bundle = EventAuthoringBundle(
        event=event,
        locations=_load_collection(root, "locations.yaml", "locations", LocationSource),
        speakers=_load_collection(root, "speakers.yaml", "speakers", SpeakerSource),
        sessions=_load_collection(root, "sessions.yaml", "sessions", SessionSource),
        booths=_load_collection(root, "booths.yaml", "booths", BoothSource),
        aliases=_load_collection(root, "aliases.yaml", "aliases", AliasSource),
        glossary=_load_collection(root, "glossary.yaml", "glossary", GlossaryTerm),
        source_root=root,
    )
    return bundle, build_source_inventory(root, bundle)


def canonical_authoring_json(bundle: EventAuthoringBundle) -> bytes:
    payload = bundle.model_dump(mode="json", exclude={"source_root"})
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


__all__ = [
    "AliasSource",
    "AuthorityLevel",
    "BoothSource",
    "DocumentSource",
    "EventAuthoringBundle",
    "EventSource",
    "GlossaryTerm",
    "LocationSource",
    "SessionSource",
    "SourceFile",
    "SourceInventory",
    "SpeakerSource",
    "build_source_inventory",
    "canonical_authoring_json",
    "load_authoring_bundle",
]

import re
import unicodedata
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

_SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
_HEX64_PATTERN = r"^[0-9a-f]{64}$"
_SCHEMA_PATTERN = r"^1\.[0-9]+$"


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManifestFile(EventModel):
    path: StrictStr
    sha256: StrictStr = Field(pattern=_HEX64_PATTERN)
    size_bytes: StrictInt = Field(ge=0)
    role: StrictStr

    @field_validator("path")
    @classmethod
    def validate_archive_path(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFC", value)
        if normalized != value:
            raise ValueError("archive paths must use Unicode NFC")
        if not value or value.startswith(("/", "\\")) or "\\" in value:
            raise ValueError("archive paths must be relative POSIX paths")
        if re.match(r"^[A-Za-z]:", value):
            raise ValueError("archive paths must not contain a drive prefix")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("archive paths contain an invalid component")
        return value


class EmbeddingSpec(EventModel):
    model_id: StrictStr
    revision: StrictStr
    dimension: StrictInt = Field(gt=0)
    dtype: StrictStr = "<f4"
    max_input_tokens: StrictInt = Field(default=512, gt=0)


class ChunkingSpec(EventModel):
    max_tokens: StrictInt = Field(gt=0)
    merge_peers: StrictBool = True
    tokenizer_model: StrictStr = "intfloat/multilingual-e5-small"


class BuilderSpec(EventModel):
    name: StrictStr
    version: StrictStr


class ExtensionSpec(EventModel):
    namespace: StrictStr
    schema_version: StrictStr
    paths: list[StrictStr] = Field(default_factory=list)

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, values: list[str]) -> list[str]:
        return [ManifestFile.validate_archive_path(value) for value in values]


class EventPackageManifest(EventModel):
    package_type: StrictStr = Field(pattern=r"^innobrain\.event$")
    package_schema_version: StrictStr = Field(pattern=_SCHEMA_PATTERN)
    event_id: StrictStr
    event_version: StrictStr = Field(pattern=_SEMVER_PATTERN)
    client_id: StrictStr
    title: StrictStr
    default_locale: StrictStr
    timezone: StrictStr
    created_at_utc: StrictStr
    build_id: StrictStr = Field(pattern=_HEX64_PATTERN)
    builder: BuilderSpec
    deployable: StrictBool
    runtime_compat: dict[str, Any]
    embedding: EmbeddingSpec
    chunking: ChunkingSpec
    structured_schema: dict[str, Any] | StrictStr
    extensions: list[ExtensionSpec] = Field(default_factory=list)
    files: list[ManifestFile]

    @model_validator(mode="after")
    def validate_file_set(self) -> "EventPackageManifest":
        paths = [entry.path for entry in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("manifest file paths must be unique")
        return self


__all__ = [
    "BuilderSpec",
    "ChunkingSpec",
    "EmbeddingSpec",
    "EventPackageManifest",
    "EventModel",
    "ExtensionSpec",
    "ManifestFile",
]

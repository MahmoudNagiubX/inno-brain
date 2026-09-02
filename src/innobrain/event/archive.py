import re
import stat
import unicodedata
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import EventIntegrityError


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_archive_bytes: int = 536_870_912
    max_file_count: int = 2000
    max_uncompressed_bytes: int = 1_073_741_824
    max_single_file_bytes: int = 268_435_456


def _normalized_member_name(name: str) -> str:
    normalized = unicodedata.normalize("NFC", name)
    if normalized != name:
        raise EventIntegrityError(f"archive path is not Unicode NFC: {name!r}")
    if not name or "\x00" in name or "\\" in name:
        raise EventIntegrityError(f"archive path is not a relative POSIX path: {name!r}")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise EventIntegrityError(f"archive path is absolute: {name!r}")
    raw_parts = name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise EventIntegrityError(f"archive path contains unsafe components: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise EventIntegrityError(f"archive path contains unsafe components: {name!r}")
    if name.endswith("/"):
        raise EventIntegrityError(f"archive directories are not allowed: {name!r}")
    return normalized


def _validate_info(info: zipfile.ZipInfo) -> str:
    name = _normalized_member_name(info.filename)
    mode = (info.external_attr >> 16) & 0o170000
    if stat.S_ISLNK(mode):
        raise EventIntegrityError(f"symlink archive member rejected: {name}")
    if info.flag_bits & 0x1:
        raise EventIntegrityError(f"encrypted archive member rejected: {name}")
    if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise EventIntegrityError(f"unsupported archive compression: {name}")
    return name


def validate_archive_structure(
    archive_path: Path | str,
    *,
    limits: ArchiveLimits | None = None,
    declared_paths: Iterable[str] | None = None,
) -> list[zipfile.ZipInfo]:
    limits = limits or ArchiveLimits()
    archive_path = Path(archive_path)
    try:
        archive_bytes = archive_path.stat().st_size
    except OSError as exc:
        raise EventIntegrityError(f"cannot stat event archive: {archive_path}") from exc
    if archive_bytes > limits.max_archive_bytes:
        raise EventIntegrityError("event archive exceeds the archive-size quota")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_file_count:
                raise EventIntegrityError("event archive exceeds the file-count quota")
            names: list[str] = []
            collision_keys: set[str] = set()
            total_uncompressed = 0
            for info in infos:
                name = _validate_info(info)
                collision_key = unicodedata.normalize("NFC", name).casefold()
                if collision_key in collision_keys:
                    raise EventIntegrityError(f"archive path collision: {name}")
                collision_keys.add(collision_key)
                names.append(name)
                if info.file_size > limits.max_single_file_bytes:
                    raise EventIntegrityError(f"archive member exceeds single-file quota: {name}")
                total_uncompressed += info.file_size
            if total_uncompressed > limits.max_uncompressed_bytes:
                raise EventIntegrityError("event archive exceeds total-uncompressed quota")
            if declared_paths is not None:
                declared = {_normalized_member_name(path) for path in declared_paths}
                if set(names) != declared:
                    missing = sorted(declared - set(names))
                    extra = sorted(set(names) - declared)
                    raise EventIntegrityError(
                        "archive members do not match declaration; "
                        f"missing={missing}, extra={extra}"
                    )
            return infos
    except EventIntegrityError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise EventIntegrityError(f"invalid event archive: {archive_path}") from exc


def extract_validated_archive(
    archive_path: Path | str,
    destination: Path | str,
    *,
    limits: ArchiveLimits | None = None,
    declared_paths: Iterable[str] | None = None,
) -> list[Path]:
    infos = validate_archive_structure(
        archive_path,
        limits=limits,
        declared_paths=declared_paths,
    )
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise EventIntegrityError("archive extraction destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in infos:
                relative = Path(*PurePosixPath(info.filename).parts)
                target = (destination / relative).resolve()
                root = destination.resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise EventIntegrityError(
                        f"archive member escapes staging: {info.filename}"
                    ) from exc
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info, "r") as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > info.file_size:
                            raise EventIntegrityError(
                                f"archive member grew while extracting: {info.filename}"
                            )
                        output.write(chunk)
                if written != info.file_size:
                    raise EventIntegrityError(f"archive member size changed: {info.filename}")
                extracted.append(target)
    except EventIntegrityError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as exc:
        raise EventIntegrityError(
            f"could not safely extract event archive: {archive_path}"
        ) from exc
    return extracted


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    info.extra = b""
    info.comment = b""
    return info


def write_event_archive(
    output_path: Path | str,
    *,
    manifest_bytes: bytes,
    signature_bytes: bytes | None,
    payloads: Mapping[str, bytes],
) -> Path:
    output_path = Path(output_path)
    names = set()
    for name in payloads:
        normalized = _normalized_member_name(name)
        if normalized in {"manifest.json", "signature.json"}:
            raise EventIntegrityError("reserved archive member supplied as payload")
        collision_key = normalized.casefold()
        if collision_key in names:
            raise EventIntegrityError(f"payload path collision: {name}")
        names.add(collision_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(
            output_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            archive.writestr(_zip_info("manifest.json"), manifest_bytes)
            if signature_bytes is not None:
                archive.writestr(_zip_info("signature.json"), signature_bytes)
            for name in sorted(payloads):
                archive.writestr(_zip_info(name), payloads[name])
    except (OSError, ValueError, TypeError) as exc:
        raise EventIntegrityError(f"could not write event archive: {output_path}") from exc
    validate_archive_structure(output_path)
    return output_path


__all__ = [
    "ArchiveLimits",
    "extract_validated_archive",
    "validate_archive_structure",
    "write_event_archive",
]

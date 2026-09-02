import hashlib
import json
import os
import shutil
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal, Self

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ValidationError

from .archive import (
    ArchiveLimits,
    extract_open_verified_archive,
    validate_open_archive_structure,
)
from .crypto import SignatureMetadata, verify_manifest_signature
from .errors import (
    EventCompatibilityError,
    EventIntegrityError,
    EventPackageError,
    EventSchemaError,
    EventSignatureError,
)
from .models import EventPackageManifest


@dataclass(frozen=True, slots=True)
class PackageVerificationPolicy:
    environment: Literal["development", "test", "production"] = "development"
    require_signature_in_production: bool = True
    allow_unsigned_development: bool = False
    trusted_keys: Mapping[str, Ed25519PublicKey] | None = None
    limits: ArchiveLimits = ArchiveLimits()


@dataclass(frozen=True, slots=True)
class VerifiedPackage:
    archive_path: Path
    manifest: EventPackageManifest
    manifest_bytes: bytes
    signature: SignatureMetadata | None
    member_names: tuple[str, ...]


@dataclass(slots=True)
class VerifiedArchive:
    source_path: Path
    manifest: EventPackageManifest
    manifest_bytes: bytes
    signature: SignatureMetadata | None
    member_names: tuple[str, ...]
    file_handle: BinaryIO
    zip_file: zipfile.ZipFile
    info_by_name: Mapping[str, zipfile.ZipInfo]
    authenticated_members: Mapping[str, tuple[int, str]]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self.zip_file.close()
        self.file_handle.close()

    def extract_to(self, destination: Path | str) -> list[Path]:
        return extract_open_verified_archive(
            self.zip_file,
            self.info_by_name.values(),
            destination,
            authenticated_members=self.authenticated_members,
        )

    def copy_source_to(self, destination: Path | str) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        position = self.file_handle.tell()
        try:
            self.file_handle.seek(0)
            with destination.open("xb") as output:
                shutil.copyfileobj(self.file_handle, output, length=1024 * 1024)
        finally:
            self.file_handle.seek(position)
        return destination

    def package_metadata(self) -> VerifiedPackage:
        return VerifiedPackage(
            archive_path=self.source_path,
            manifest=self.manifest,
            manifest_bytes=self.manifest_bytes,
            signature=self.signature,
            member_names=self.member_names,
        )


def _parse_manifest(manifest_bytes: bytes) -> EventPackageManifest:
    try:
        payload = json.loads(manifest_bytes.decode("utf-8"))
        return EventPackageManifest.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise EventSchemaError("manifest.json is not a valid strict event manifest") from exc


def _parse_signature(signature_bytes: bytes) -> SignatureMetadata:
    try:
        payload = json.loads(signature_bytes.decode("utf-8"))
        return SignatureMetadata.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise EventSignatureError("signature.json is not valid signature metadata") from exc


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    try:
        with archive.open(info, "r") as stream:
            return stream.read()
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise EventIntegrityError(f"could not read archive member: {info.filename}") from exc


def open_verified_event_package(
    archive_path: Path | str,
    *,
    policy: PackageVerificationPolicy | None = None,
) -> VerifiedArchive:
    policy = policy or PackageVerificationPolicy()
    archive_path = Path(archive_path)
    file_handle: BinaryIO | None = None
    archive: zipfile.ZipFile | None = None
    ownership_transferred = False
    try:
        file_handle = archive_path.open("rb")
        archive = zipfile.ZipFile(file_handle)
        infos = validate_open_archive_structure(
            archive,
            archive_bytes=os.fstat(file_handle.fileno()).st_size,
            limits=policy.limits,
        )
        info_by_name = {info.filename: info for info in infos}
        if "manifest.json" not in info_by_name:
            raise EventSchemaError("event archive must contain manifest.json")

        manifest_bytes = _read_member(archive, info_by_name["manifest.json"])
        manifest = _parse_manifest(manifest_bytes)
        major = manifest.package_schema_version.split(".", 1)[0]
        if major != "1":
            raise EventCompatibilityError(
                f"unsupported event package schema major version: {major}"
            )

        signature: SignatureMetadata | None = None
        signature_bytes: bytes | None = None
        signature_info = info_by_name.get("signature.json")
        if signature_info is not None:
            signature_bytes = _read_member(archive, signature_info)
            signature = _parse_signature(signature_bytes)

        trusted_keys = policy.trusted_keys or {}
        if signature is None:
            if policy.environment == "production" and policy.require_signature_in_production:
                raise EventSignatureError("production event package must be signed")
            if not (
                policy.environment != "production" and policy.allow_unsigned_development
            ):
                raise EventSignatureError("unsigned event package is not allowed by policy")
        else:
            verify_manifest_signature(manifest, signature, trusted_keys)

        if policy.environment == "production" and not manifest.deployable:
            raise EventCompatibilityError("production runtime requires deployable=true")

        declared_payloads = {entry.path for entry in manifest.files}
        expected_members = {"manifest.json", *declared_payloads}
        if signature is not None:
            expected_members.add("signature.json")
        actual_members = set(info_by_name)
        if actual_members != expected_members:
            raise EventIntegrityError(
                "archive members do not match manifest declaration; "
                f"missing={sorted(expected_members - actual_members)}, "
                f"extra={sorted(actual_members - expected_members)}"
            )

        authenticated_members: dict[str, tuple[int, str]] = {
            "manifest.json": (len(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest())
        }
        if signature_bytes is not None:
            authenticated_members["signature.json"] = (
                len(signature_bytes),
                hashlib.sha256(signature_bytes).hexdigest(),
            )
        for entry in manifest.files:
            info = info_by_name[entry.path]
            digest = hashlib.sha256()
            size = 0
            with archive.open(info, "r") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            if size != entry.size_bytes:
                raise EventIntegrityError(f"payload size mismatch: {entry.path}")
            if digest.hexdigest() != entry.sha256:
                raise EventIntegrityError(f"payload SHA-256 mismatch: {entry.path}")
            authenticated_members[entry.path] = (entry.size_bytes, entry.sha256)

        verified = VerifiedArchive(
            source_path=archive_path,
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            signature=signature,
            member_names=tuple(info_by_name),
            file_handle=file_handle,
            zip_file=archive,
            info_by_name=info_by_name,
            authenticated_members=authenticated_members,
        )
        ownership_transferred = True
        return verified
    except EventPackageError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise EventIntegrityError(f"could not verify event package: {archive_path}") from exc
    finally:
        if archive is not None and not ownership_transferred:
            archive.close()
        if file_handle is not None and not ownership_transferred:
            file_handle.close()


def verify_event_package(
    archive_path: Path | str,
    *,
    policy: PackageVerificationPolicy | None = None,
    extract_to: Path | str | None = None,
) -> VerifiedPackage:
    with open_verified_event_package(archive_path, policy=policy) as verified:
        if extract_to is not None:
            verified.extract_to(extract_to)
        return verified.package_metadata()

verify_package = verify_event_package


__all__ = [
    "PackageVerificationPolicy",
    "VerifiedArchive",
    "VerifiedPackage",
    "open_verified_event_package",
    "verify_event_package",
    "verify_package",
]

import hashlib
import json
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ValidationError

from .archive import ArchiveLimits, extract_validated_archive, validate_archive_structure
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


def verify_event_package(
    archive_path: Path | str,
    *,
    policy: PackageVerificationPolicy | None = None,
    extract_to: Path | str | None = None,
) -> VerifiedPackage:
    policy = policy or PackageVerificationPolicy()
    archive_path = Path(archive_path)

    # 1. Validate the container and quotas before reading any package data.
    infos = validate_archive_structure(archive_path, limits=policy.limits)
    info_by_name = {info.filename: info for info in infos}
    if "manifest.json" not in info_by_name:
        raise EventSchemaError("event archive must contain manifest.json")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            # 2. Read the exact signed manifest bytes; do not reserialize before verification.
            manifest_bytes = _read_member(archive, info_by_name["manifest.json"])
            # 3. Strictly parse the manifest.
            manifest = _parse_manifest(manifest_bytes)
            # 4. Accept only package schema major version 1.
            major = manifest.package_schema_version.split(".", 1)[0]
            if major != "1":
                raise EventCompatibilityError(
                    f"unsupported event package schema major version: {major}"
                )

            signature: SignatureMetadata | None = None
            signature_info = info_by_name.get("signature.json")
            if signature_info is not None:
                signature = _parse_signature(_read_member(archive, signature_info))

            # 5-6. Production requires a trusted signature; development may opt in to unsigned.
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

            # 7. The archive must contain exactly the manifest, optional signature and payloads.
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

            # 8-9. Stream every declared payload and compare both digest and size.
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

            # 10. Extraction is performed only after every check above succeeds.
            if extract_to is not None:
                extract_validated_archive(
                    archive_path,
                    extract_to,
                    limits=policy.limits,
                    declared_paths=actual_members,
                )
    except EventPackageError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise EventIntegrityError(f"could not verify event package: {archive_path}") from exc

    return VerifiedPackage(
        archive_path=archive_path,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        signature=signature,
        member_names=tuple(info_by_name),
    )


verify_package = verify_event_package


__all__ = [
    "PackageVerificationPolicy",
    "VerifiedPackage",
    "verify_event_package",
    "verify_package",
]

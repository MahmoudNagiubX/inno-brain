import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from innobrain.event.archive import write_event_archive
from innobrain.event.crypto import sign_manifest
from innobrain.event.errors import (
    EventCompatibilityError,
    EventIntegrityError,
    EventSignatureError,
)
from innobrain.event.manifest import canonical_manifest_bytes
from innobrain.event.models import EventPackageManifest
from innobrain.event.validation import PackageVerificationPolicy, verify_event_package
from tests.unit.event.test_manifest import _manifest


def _build_package(
    path: Path,
    *,
    signed: bool = False,
    deployable: bool = False,
    private_key: Ed25519PrivateKey | None = None,
    payload: bytes = b"alpha knowledge",
) -> tuple[Path, Ed25519PrivateKey | None]:
    import hashlib

    manifest = EventPackageManifest.model_validate(
        _manifest(
            deployable=deployable,
            files=[
                {
                    "path": "knowledge/chunks.jsonl",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "role": "knowledge_chunks",
                }
            ],
        )
    )
    key = private_key or (Ed25519PrivateKey.generate() if signed else None)
    signature_bytes = None
    if key is not None:
        signature = sign_manifest(manifest, key, key_id="test-key")
        signature_bytes = (
            json.dumps(
                signature.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            )
            + "\n"
        ).encode("utf-8")
    write_event_archive(
        path,
        manifest_bytes=canonical_manifest_bytes(manifest),
        signature_bytes=signature_bytes,
        payloads={"knowledge/chunks.jsonl": payload},
    )
    return path, key


def _development_policy(*, keys: dict[str, object] | None = None) -> PackageVerificationPolicy:
    return PackageVerificationPolicy(
        environment="development",
        allow_unsigned_development=True,
        trusted_keys=keys or {},
    )


def test_unsigned_development_package_is_accepted_only_when_explicitly_enabled(
    tmp_path: Path,
) -> None:
    package, _ = _build_package(tmp_path / "unsigned.innoevent")

    verified = verify_event_package(package, policy=_development_policy())

    assert verified.manifest.event_id == "event-alpha"
    assert verified.signature is None


def test_unsigned_production_package_is_rejected(tmp_path: Path) -> None:
    package, _ = _build_package(tmp_path / "unsigned.innoevent", deployable=True)
    policy = PackageVerificationPolicy(environment="production", trusted_keys={})

    with pytest.raises(EventSignatureError):
        verify_event_package(package, policy=policy)


def test_non_deployable_production_package_is_rejected(tmp_path: Path) -> None:
    package, key = _build_package(tmp_path / "test.innoevent", signed=True, deployable=False)
    policy = PackageVerificationPolicy(
        environment="production",
        trusted_keys={"test-key": key.public_key()},
    )

    with pytest.raises(EventCompatibilityError):
        verify_event_package(package, policy=policy)


def test_signed_package_requires_a_trusted_key(tmp_path: Path) -> None:
    package, key = _build_package(tmp_path / "signed.innoevent", signed=True)

    with pytest.raises(EventSignatureError):
        verify_event_package(package, policy=_development_policy())

    verified = verify_event_package(
        package,
        policy=_development_policy(keys={"test-key": key.public_key()}),
    )
    assert verified.signature is not None


def test_payload_tampering_is_rejected_before_extraction(tmp_path: Path) -> None:
    package, _ = _build_package(tmp_path / "tampered.innoevent")
    tampered = tmp_path / "tampered-extract"
    with __import__("zipfile").ZipFile(package) as source, __import__("zipfile").ZipFile(
        package.with_name("rewritten.innoevent"), "w"
    ) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "knowledge/chunks.jsonl":
                data = b"tampered knowledge"
            target.writestr(info, data)
    package.with_name("rewritten.innoevent").replace(package)

    with pytest.raises(EventIntegrityError):
        verify_event_package(package, policy=_development_policy(), extract_to=tampered)
    assert not tampered.exists()


def test_manifest_and_signature_tampering_are_rejected(tmp_path: Path) -> None:
    package, key = _build_package(tmp_path / "signed.innoevent", signed=True)
    policy = _development_policy(keys={"test-key": key.public_key()})

    manifest_tampered = tmp_path / "manifest-tampered.innoevent"
    with __import__("zipfile").ZipFile(package) as source, __import__("zipfile").ZipFile(
        manifest_tampered, "w"
    ) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "manifest.json":
                data = data.replace(b"Alpha Event", b"Altered Event")
            target.writestr(info, data)
    with pytest.raises((EventIntegrityError, EventSignatureError)):
        verify_event_package(manifest_tampered, policy=policy)

    signature_tampered = tmp_path / "signature-tampered.innoevent"
    with __import__("zipfile").ZipFile(package) as source, __import__("zipfile").ZipFile(
        signature_tampered, "w"
    ) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "signature.json":
                metadata = json.loads(data)
                decoded = bytearray(base64.b64decode(metadata["signature_base64"]))
                decoded[0] ^= 1
                metadata["signature_base64"] = base64.b64encode(decoded).decode("ascii")
                data = (json.dumps(metadata) + "\n").encode("utf-8")
            target.writestr(info, data)
    with pytest.raises(EventSignatureError):
        verify_event_package(signature_tampered, policy=policy)

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from innobrain.event.crypto import SignatureMetadata, sign_manifest, verify_manifest_signature
from innobrain.event.errors import EventSignatureError
from innobrain.event.models import EventPackageManifest
from tests.unit.event.test_manifest import _manifest


def test_valid_ed25519_manifest_signature_verifies() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    manifest = EventPackageManifest.model_validate(_manifest())

    signature = sign_manifest(manifest, private_key, key_id="test-key")

    assert signature.algorithm == "Ed25519"
    assert verify_manifest_signature(manifest, signature, {"test-key": public_key}) is None


def test_changed_manifest_fails_signature_verification() -> None:
    private_key = Ed25519PrivateKey.generate()
    manifest = EventPackageManifest.model_validate(_manifest())
    signature = sign_manifest(manifest, private_key, key_id="test-key")
    changed = EventPackageManifest.model_validate(_manifest(build_id="c" * 64))

    with pytest.raises(EventSignatureError):
        verify_manifest_signature(changed, signature, {"test-key": private_key.public_key()})


def test_wrong_key_fails_signature_verification() -> None:
    private_key = Ed25519PrivateKey.generate()
    wrong_key = Ed25519PrivateKey.generate()
    manifest = EventPackageManifest.model_validate(_manifest())
    signature = sign_manifest(manifest, private_key, key_id="test-key")

    with pytest.raises(EventSignatureError):
        verify_manifest_signature(manifest, signature, {"test-key": wrong_key.public_key()})


def test_unknown_key_id_fails_signature_verification() -> None:
    private_key = Ed25519PrivateKey.generate()
    manifest = EventPackageManifest.model_validate(_manifest())
    signature = sign_manifest(manifest, private_key, key_id="missing-key")

    with pytest.raises(EventSignatureError):
        verify_manifest_signature(manifest, signature, {"other-key": private_key.public_key()})


def test_signature_metadata_is_strict() -> None:
    with pytest.raises(ValidationError):
        SignatureMetadata(
            algorithm="RSA",
            key_id="test-key",
            signature_base64="abc",
        )

import base64
from collections.abc import Mapping
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import StrictStr

from .errors import EventSignatureError
from .manifest import canonical_manifest_bytes
from .models import EventModel, EventPackageManifest


class SignatureMetadata(EventModel):
    algorithm: Literal["Ed25519"]
    key_id: StrictStr
    signature_base64: StrictStr


def sign_manifest(
    manifest: EventPackageManifest,
    private_key: Ed25519PrivateKey,
    *,
    key_id: str,
) -> SignatureMetadata:
    signature = private_key.sign(canonical_manifest_bytes(manifest))
    return SignatureMetadata(
        algorithm="Ed25519",
        key_id=key_id,
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


def verify_manifest_signature(
    manifest: EventPackageManifest,
    signature: SignatureMetadata,
    trusted_keys: Mapping[str, Ed25519PublicKey],
) -> None:
    if signature.algorithm != "Ed25519":
        raise EventSignatureError(f"unsupported signature algorithm: {signature.algorithm}")
    public_key = trusted_keys.get(signature.key_id)
    if public_key is None:
        raise EventSignatureError(f"untrusted event signing key: {signature.key_id}")
    try:
        signature_bytes = base64.b64decode(signature.signature_base64, validate=True)
    except (ValueError, TypeError) as exc:
        raise EventSignatureError("signature is not valid base64") from exc
    if len(signature_bytes) != 64:
        raise EventSignatureError("Ed25519 signatures must contain 64 bytes")
    try:
        public_key.verify(signature_bytes, canonical_manifest_bytes(manifest))
    except InvalidSignature as exc:
        raise EventSignatureError("event manifest signature verification failed") from exc


__all__ = ["SignatureMetadata", "sign_manifest", "verify_manifest_signature"]

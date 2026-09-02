import json

from .models import EventPackageManifest


def canonical_manifest_bytes(manifest: EventPackageManifest) -> bytes:
    payload = manifest.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


__all__ = ["canonical_manifest_bytes"]

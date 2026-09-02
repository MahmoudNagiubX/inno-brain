import io
import zipfile
from pathlib import Path

from innobrain.event import archive as archive_module
from innobrain.event.validation import (
    PackageVerificationPolicy,
    open_verified_event_package,
)
from tests.unit.event.test_package_verifier import _build_package


def test_extraction_uses_the_same_authenticated_open_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package, key = _build_package(
        tmp_path / "event.innoevent",
        signed=True,
        payload=b"authenticated-a",
    )
    replacement, _ = _build_package(
        tmp_path / "replacement.innoevent",
        signed=True,
        private_key=key,
        payload=b"unauthenticated-b",
    )
    policy = PackageVerificationPolicy(
        environment="development",
        trusted_keys={"test-key": key.public_key()},
    )

    with open_verified_event_package(package, policy=policy) as verified:
        real_zip_file = archive_module.zipfile.ZipFile

        def redirect_path_reopen(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and Path(file) == package:
                return real_zip_file(replacement, *args, **kwargs)
            return real_zip_file(file, *args, **kwargs)

        monkeypatch.setattr(archive_module.zipfile, "ZipFile", redirect_path_reopen)
        destination = tmp_path / "extracted"
        verified.extract_to(destination)

    assert (destination / "knowledge" / "chunks.jsonl").read_bytes() == b"authenticated-a"


def test_extraction_rehashes_authenticated_payload_while_writing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package, key = _build_package(
        tmp_path / "event.innoevent",
        signed=True,
        payload=b"authenticated-a",
    )
    policy = PackageVerificationPolicy(
        environment="development",
        trusted_keys={"test-key": key.public_key()},
    )

    with open_verified_event_package(package, policy=policy) as verified:
        real_open = verified.zip_file.open

        def tampered_open(member, *args, **kwargs):
            name = member.filename if isinstance(member, zipfile.ZipInfo) else member
            if name == "knowledge/chunks.jsonl":
                return io.BytesIO(b"tampered-data!!")
            return real_open(member, *args, **kwargs)

        monkeypatch.setattr(verified.zip_file, "open", tampered_open)

        destination = tmp_path / "extracted"
        try:
            verified.extract_to(destination)
        except Exception as exc:
            assert "sha-256" in str(exc).lower()
        else:
            raise AssertionError("extraction accepted payload metadata changed after verification")

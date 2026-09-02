import stat
import zipfile
from pathlib import Path

import pytest

from innobrain.event.archive import (
    ArchiveLimits,
    _normalized_member_name,
    extract_validated_archive,
    validate_archive_structure,
    write_event_archive,
)
from innobrain.event.errors import EventIntegrityError


def _zip_with_members(path: Path, members: list[tuple[str, bytes, int | None]]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data, compression in members:
            info = zipfile.ZipInfo(name)
            info.compress_type = compression if compression is not None else zipfile.ZIP_STORED
            archive.writestr(info, data)
    return path


def _mark_zip_encrypted(path: Path) -> None:
    data = bytearray(path.read_bytes())
    local = b"PK\x03\x04"
    central = b"PK\x01\x02"
    offset = 0
    while (local_index := data.find(local, offset)) >= 0:
        data[local_index + 6] |= 0x01
        offset = local_index + 4
    offset = 0
    while (central_index := data.find(central, offset)) >= 0:
        data[central_index + 8] |= 0x01
        offset = central_index + 4
    path.write_bytes(data)


@pytest.mark.parametrize(
    "name",
    [
        "../escape.txt",
        "/absolute.txt",
        "\\absolute.txt",
        "C:/drive.txt",
        "folder/./file.txt",
    ],
)
def test_archive_rejects_unsafe_paths(tmp_path: Path, name: str) -> None:
    archive = _zip_with_members(tmp_path / "unsafe.zip", [(name, b"x", None)])

    with pytest.raises(EventIntegrityError):
        validate_archive_structure(archive)


def test_archive_rejects_symlink_entry(tmp_path: Path) -> None:
    archive_path = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("payload.txt")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(info, b"target")

    with pytest.raises(EventIntegrityError):
        validate_archive_structure(archive_path)


def test_member_normalizer_rejects_backslash_paths() -> None:
    with pytest.raises(EventIntegrityError):
        _normalized_member_name("folder\\file.txt")


def test_archive_rejects_duplicate_and_case_unicode_collisions(tmp_path: Path) -> None:
    duplicate = _zip_with_members(
        tmp_path / "duplicate.zip",
        [("payload.txt", b"one", None), ("payload.txt", b"two", None)],
    )
    collision = _zip_with_members(
        tmp_path / "collision.zip",
        [("Guide.txt", b"one", None), ("guide.TXT", b"two", None)],
    )
    unicode_collision = _zip_with_members(
        tmp_path / "unicode.zip",
        [("cafe\u0301.txt", b"one", None), ("caf\u00e9.txt", b"two", None)],
    )

    for archive in (duplicate, collision, unicode_collision):
        with pytest.raises(EventIntegrityError):
            validate_archive_structure(archive)


def test_archive_rejects_encrypted_and_undeclared_entries(tmp_path: Path) -> None:
    archive = _zip_with_members(tmp_path / "payload.zip", [("payload.txt", b"x", None)])
    _mark_zip_encrypted(archive)

    with pytest.raises(EventIntegrityError):
        validate_archive_structure(archive)

    clean_archive = _zip_with_members(
        tmp_path / "undeclared.zip", [("payload.txt", b"x", None), ("extra.txt", b"y", None)]
    )
    with pytest.raises(EventIntegrityError):
        validate_archive_structure(clean_archive, declared_paths={"payload.txt"})


def test_archive_rejects_unsupported_compression_and_quotas(tmp_path: Path) -> None:
    unsupported = _zip_with_members(
        tmp_path / "unsupported.zip", [("payload.txt", b"x", zipfile.ZIP_BZIP2)]
    )
    with pytest.raises(EventIntegrityError):
        validate_archive_structure(unsupported)

    oversized = _zip_with_members(tmp_path / "oversized.zip", [("payload.txt", b"12345", None)])
    limits = ArchiveLimits(max_single_file_bytes=4)
    with pytest.raises(EventIntegrityError):
        validate_archive_structure(oversized, limits=limits)


def test_validated_extraction_stays_below_staging(tmp_path: Path) -> None:
    source = _zip_with_members(tmp_path / "valid.zip", [("folder/payload.txt", b"safe", None)])
    target = tmp_path / "staging"

    extract_validated_archive(source, target)

    assert (target / "folder" / "payload.txt").read_bytes() == b"safe"
    assert not (tmp_path / "payload.txt").exists()


def test_writer_uses_deterministic_members_and_order(tmp_path: Path) -> None:
    first = tmp_path / "first.innoevent"
    second = tmp_path / "second.innoevent"
    payloads = {"z-last.txt": b"z", "a-first.txt": b"a"}
    write_event_archive(
        first,
        manifest_bytes=b"manifest\n",
        signature_bytes=b"signature\n",
        payloads=payloads,
    )
    write_event_archive(
        second,
        manifest_bytes=b"manifest\n",
        signature_bytes=b"signature\n",
        payloads=payloads,
    )

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == [
            "manifest.json",
            "signature.json",
            "a-first.txt",
            "z-last.txt",
        ]
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())

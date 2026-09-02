from pathlib import Path

from innobrain.event.archive import write_event_archive


def test_archive_output_is_independent_of_payload_mapping_order(tmp_path: Path) -> None:
    first = tmp_path / "first.innoevent"
    second = tmp_path / "second.innoevent"
    write_event_archive(
        first,
        manifest_bytes=b"manifest\n",
        signature_bytes=None,
        payloads={"b/data": b"b", "a/data": b"a"},
    )
    write_event_archive(
        second,
        manifest_bytes=b"manifest\n",
        signature_bytes=None,
        payloads={"a/data": b"a", "b/data": b"b"},
    )

    assert first.read_bytes() == second.read_bytes()

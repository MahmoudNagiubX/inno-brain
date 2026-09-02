from pathlib import Path

import pytest

from innobrain.event.distribution import EventDistributionError, fetch_event_package


class Response:
    def __init__(self, body: bytes, url: str, content_length: str | None = None) -> None:
        self.body = body
        self.url = url
        self.headers = {"Content-Length": content_length} if content_length else {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self) -> str:
        return self.url

    def read(self, size: int) -> bytes:
        value, self.body = self.body[:size], self.body[size:]
        return value


class Opener:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.request = None

    def open(self, request, timeout: int):
        self.request = request
        return self.response


def test_fetcher_is_disabled_and_validates_https_allowlist(tmp_path: Path) -> None:
    with pytest.raises(EventDistributionError, match="disabled"):
        fetch_event_package(
            "https://packages.example.test/alpha.innoevent",
            tmp_path / "chosen-name.innoevent",
        )
    with pytest.raises(EventDistributionError, match="HTTPS"):
        fetch_event_package(
            "http://packages.example.test/alpha.innoevent",
            tmp_path / "chosen-name.innoevent",
            allow_remote_package_fetch=True,
            allowed_remote_hosts={"packages.example.test"},
        )
    with pytest.raises(EventDistributionError, match="allowlisted"):
        fetch_event_package(
            "https://other.example.test/alpha.innoevent",
            tmp_path / "chosen-name.innoevent",
            allow_remote_package_fetch=True,
            allowed_remote_hosts={"packages.example.test"},
        )


def test_fetcher_streams_to_explicit_destination_and_checks_final_redirect_host(
    tmp_path: Path,
) -> None:
    opener = Opener(Response(b"package-bytes", "https://cdn.example.test/opaque.innoevent"))
    destination = fetch_event_package(
        "https://packages.example.test/alpha.innoevent",
        tmp_path / "chosen-name.innoevent",
        allow_remote_package_fetch=True,
        allowed_remote_hosts={"packages.example.test", "cdn.example.test"},
        opener=opener,
    )
    assert destination.name == "chosen-name.innoevent"
    assert destination.read_bytes() == b"package-bytes"
    assert opener.request.full_url == "https://packages.example.test/alpha.innoevent"

    hostile = Opener(Response(b"bytes", "https://evil.example.test/alpha.innoevent"))
    with pytest.raises(EventDistributionError, match="allowlisted"):
        fetch_event_package(
            "https://packages.example.test/alpha.innoevent",
            tmp_path / "other.innoevent",
            allow_remote_package_fetch=True,
            allowed_remote_hosts={"packages.example.test"},
            opener=hostile,
        )


def test_fetcher_enforces_quota_with_and_without_content_length(tmp_path: Path) -> None:
    with pytest.raises(EventDistributionError, match="quota"):
        fetch_event_package(
            "https://packages.example.test/alpha.innoevent",
            tmp_path / "too-large.innoevent",
            allow_remote_package_fetch=True,
            allowed_remote_hosts={"packages.example.test"},
            opener=Opener(Response(b"12345", "https://packages.example.test/a.innoevent", "5")),
            max_bytes=4,
        )
    with pytest.raises(EventDistributionError, match="quota"):
        fetch_event_package(
            "https://packages.example.test/alpha.innoevent",
            tmp_path / "too-large-stream.innoevent",
            allow_remote_package_fetch=True,
            allowed_remote_hosts={"packages.example.test"},
            opener=Opener(Response(b"12345", "https://packages.example.test/a.innoevent")),
            max_bytes=4,
        )

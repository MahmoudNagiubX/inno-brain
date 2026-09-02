import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import EventDistributionError

MAX_REMOTE_PACKAGE_BYTES = 512 * 1024 * 1024


def _validate_url(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if parsed.scheme != "https":
        raise EventDistributionError("event package distribution requires HTTPS")
    if not host or host not in {item.casefold() for item in allowed_hosts}:
        raise EventDistributionError("event package host is not allowlisted")
    if parsed.username is not None or parsed.password is not None:
        raise EventDistributionError("event package URLs must not contain credentials")
    if not parsed.path.casefold().endswith(".innoevent"):
        raise EventDistributionError("distribution accepts complete .innoevent artifacts only")
    return host


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_event_package(
    url: str,
    destination: Path | str,
    *,
    allow_remote_package_fetch: bool = False,
    allowed_remote_hosts: set[str] | list[str] | tuple[str, ...] = (),
    opener: object | None = None,
    max_bytes: int = MAX_REMOTE_PACKAGE_BYTES,
) -> Path:
    """Fetch one allowlisted package; caller must verify its signature afterward."""

    if not allow_remote_package_fetch:
        raise EventDistributionError("remote event package fetching is disabled")
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    allowed = {host.casefold() for host in allowed_remote_hosts}
    _validate_url(url, allowed)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    active_opener = opener or build_opener(_AllowlistedRedirectHandler(allowed))
    request = Request(url, headers={"Accept": "application/octet-stream"})
    temporary_path: Path | None = None
    try:
        response = active_opener.open(request, timeout=30)
        with response:
            final_url = response.geturl()
            _validate_url(final_url, allowed)
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    if int(content_length) > max_bytes:
                        raise EventDistributionError("remote package exceeds download quota")
                except ValueError as exc:
                    raise EventDistributionError(
                        "remote package has invalid Content-Length"
                    ) from exc
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".innoevent-",
                suffix=".part",
                dir=destination.parent,
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                received = 0
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > max_bytes:
                        raise EventDistributionError("remote package exceeds download quota")
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        return destination
    except EventDistributionError:
        raise
    except Exception as exc:  # noqa: BLE001 - downloader exposes one stable error boundary.
        raise EventDistributionError(f"could not fetch event package: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


__all__ = ["EventDistributionError", "MAX_REMOTE_PACKAGE_BYTES", "fetch_event_package"]

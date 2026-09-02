"""Command-line entrypoint for Phase 4 event package operations.

The script intentionally keeps all Docling imports inside the build path.  A
normal runtime can therefore validate and install packages without the builder
dependency or its PyTorch transitive dependencies.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path


def _builder_setup_message() -> str:
    return (
        "Builder dependency is missing. Create the isolated builder environment with:\n"
        "py -3.14 -m venv .venv-event-builder\n"
        ".venv-event-builder\\Scripts\\python.exe -m pip install -e \".[event-builder]\""
    )


def _build(args: argparse.Namespace) -> int:
    if importlib.util.find_spec("docling") is None:
        print(_builder_setup_message(), file=sys.stderr)
        return 2
    if not args.model_path or not args.tokenizer_path:
        print(
            "build requires --model-path and --tokenizer-path for local E5 assets",
            file=sys.stderr,
        )
        return 2

    from innobrain.event.builder import build_event_package
    from innobrain.knowledge.e5_onnx import MultilingualE5OnnxProvider

    provider = MultilingualE5OnnxProvider(
        model_path=Path(args.model_path),
        tokenizer_path=Path(args.tokenizer_path),
    )
    result = asyncio.run(
        build_event_package(
            args.source,
            args.output,
            embedding_provider=provider,
            tokenizer=provider.tokenizer,
            deployable=args.profile == "production",
            signing_key=args.signing_key,
            key_id=args.key_id,
            cache_dir=args.cache_dir,
            allow_plaintext_fallback=args.profile != "production",
        )
    )
    print(f"built {result.archive_path} build_id={result.manifest.build_id}")
    return 0


def _policy(args: argparse.Namespace):
    from innobrain.event.validation import PackageVerificationPolicy

    production = args.profile == "production"
    return PackageVerificationPolicy(
        environment="production" if production else "development",
        allow_unsigned_development=bool(getattr(args, "allow_unsigned_development", False)),
    )


def _validate(args: argparse.Namespace) -> int:
    from innobrain.event.validation import verify_event_package

    verified = verify_event_package(args.package, policy=_policy(args))
    print(
        f"valid event_id={verified.manifest.event_id} "
        f"version={verified.manifest.event_version} build_id={verified.manifest.build_id}"
    )
    return 0


def _install(args: argparse.Namespace) -> int:
    from innobrain.event.installer import install_event_package

    installed = install_event_package(
        args.package,
        args.data_root,
        verification_policy=_policy(args),
    )
    try:
        print(
            f"installed event_id={installed.manifest.event_id} "
            f"build_id={installed.manifest.build_id} health={installed.health}"
        )
    finally:
        installed.close()
    return 0


def _list(args: argparse.Namespace) -> int:
    from innobrain.event.registry import EventRegistry

    for record in EventRegistry(args.data_root).list(args.event_id):
        print(
            f"{record.event_id} {record.event_version} {record.build_id} "
            f"healthy={record.healthy}"
        )
    return 0


def _status(args: argparse.Namespace) -> int:
    from innobrain.event.activation import ActivationManager
    from innobrain.event.registry import EventRegistry

    record = ActivationManager(args.data_root, EventRegistry(args.data_root)).active()
    print(
        "none"
        if record is None
        else f"{record.event_id} {record.event_version} {record.build_id}"
    )
    return 0


def _activate(args: argparse.Namespace) -> int:
    from innobrain.event.activation import ActivationManager
    from innobrain.event.registry import EventRegistry

    record = ActivationManager(args.data_root, EventRegistry(args.data_root)).activate(
        args.event_id,
        event_version=args.event_version,
        build_id=args.build_id,
    )
    print(f"active {record.event_id} {record.event_version} {record.build_id}")
    return 0


def _rollback(args: argparse.Namespace) -> int:
    from innobrain.event.activation import ActivationManager
    from innobrain.event.registry import EventRegistry

    record = ActivationManager(args.data_root, EventRegistry(args.data_root)).rollback()
    print(f"rolled back {record.event_id} {record.event_version} {record.build_id}")
    return 0


def _fetch(args: argparse.Namespace) -> int:
    from innobrain.event.distribution import fetch_event_package

    destination = fetch_event_package(
        args.url,
        args.destination,
        allow_remote_package_fetch=args.allow_remote_package_fetch,
        allowed_remote_hosts=set(args.allowed_host),
    )
    print(f"fetched {destination}")
    return 0


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-root", type=Path, default=Path("runtime_data"))


def _add_verification_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", choices=("development", "production"), default="development")
    parser.add_argument("--allow-unsigned-development", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eventctl", description="InnoBrain event package operations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build a self-contained .innoevent archive")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--profile", choices=("development", "production"), default="development")
    build.add_argument("--model-path", type=Path)
    build.add_argument("--tokenizer-path", type=Path)
    build.add_argument("--cache-dir", type=Path)
    build.add_argument("--signing-key", type=Path)
    build.add_argument("--key-id")
    build.set_defaults(handler=_build)
    validate = subparsers.add_parser("validate", help="verify an event package")
    validate.add_argument("package", type=Path)
    _add_verification_args(validate)
    validate.set_defaults(handler=_validate)
    install = subparsers.add_parser("install", help="install an event package")
    install.add_argument("package", type=Path)
    _add_runtime_args(install)
    _add_verification_args(install)
    install.set_defaults(handler=_install)
    listing = subparsers.add_parser("list", help="list installed event builds")
    _add_runtime_args(listing)
    listing.add_argument("--event-id")
    listing.set_defaults(handler=_list)
    status = subparsers.add_parser("status", help="show the active event")
    _add_runtime_args(status)
    status.set_defaults(handler=_status)
    activate = subparsers.add_parser("activate", help="activate an installed event")
    activate.add_argument("event_id")
    activate.add_argument("--event-version")
    activate.add_argument("--build-id")
    _add_runtime_args(activate)
    activate.set_defaults(handler=_activate)
    rollback = subparsers.add_parser("rollback", help="explicitly roll back activation")
    _add_runtime_args(rollback)
    rollback.set_defaults(handler=_rollback)
    fetch = subparsers.add_parser("fetch", help="fetch one allowlisted .innoevent artifact")
    fetch.add_argument("url")
    fetch.add_argument("--destination", type=Path, required=True)
    fetch.add_argument("--allow-remote-package-fetch", action="store_true")
    fetch.add_argument("--allowed-host", action="append", default=[])
    fetch.set_defaults(handler=_fetch)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

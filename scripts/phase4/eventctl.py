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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

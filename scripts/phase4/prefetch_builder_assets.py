"""Prefetch bounded builder assets without polluting the normal runtime venv."""

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from innobrain.knowledge.embedding_assets import E5Assets, download_e5_assets

E5_RETRY_DELAYS_SECONDS = (2, 5)


def prefetch_e5(
    cache_dir: Path,
    *,
    downloader: Callable[..., E5Assets] = download_e5_assets,
    sleeper: Callable[[float], None] = time.sleep,
) -> E5Assets:
    errors: list[str] = []
    for attempt in range(3):
        try:
            assets = downloader(cache_dir=cache_dir)
            print(f"E5 model path: {assets.model_path}")
            print(f"E5 tokenizer path: {assets.tokenizer_path}")
            return assets
        except Exception as exc:  # noqa: BLE001 - asset errors are reported and bounded.
            errors.append(f"attempt {attempt + 1}: {type(exc).__name__}: {exc}")
            print(errors[-1])
            if attempt < len(E5_RETRY_DELAYS_SECONDS):
                sleeper(E5_RETRY_DELAYS_SECONDS[attempt])
    raise RuntimeError("real E5 asset prefetch failed after three attempts: " + " | ".join(errors))


def prefetch_docling_models() -> bool:
    try:
        from docling.utils.model_downloader import download_models
    except ImportError:
        print("Docling public model downloader unavailable.")
        print("Supported fallback command: docling-tools models download")
        return False
    download_models()
    print("Docling model assets prefetched using the public downloader.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".builder-cache"),
        help="builder-only cache directory",
    )
    parser.add_argument(
        "--skip-docling",
        action="store_true",
        help="prefetch E5 only",
    )
    args = parser.parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"Builder cache path: {args.cache_dir.resolve()}")
    try:
        prefetch_e5(args.cache_dir.resolve())
    except RuntimeError as exc:
        print(f"E5 prefetch deferred: {exc}")
        return 1
    if not args.skip_docling:
        try:
            prefetch_docling_models()
        except Exception as exc:  # noqa: BLE001 - CLI reports builder-only failures.
            print(f"Docling prefetch deferred: {type(exc).__name__}: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

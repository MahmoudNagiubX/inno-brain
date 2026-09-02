"""Locate or explicitly download the pinned multilingual-E5-small ONNX assets."""

from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import hf_hub_download

MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f"
REQUIRED_FILES = (
    "onnx/model.onnx",
    "onnx/tokenizer.json",
)


@dataclass(frozen=True, slots=True)
class E5Assets:
    model_path: Path
    tokenizer_path: Path


def resolve_e5_assets(
    *,
    cache_dir: Path | None = None,
    download: bool = False,
) -> E5Assets:
    """Resolve cached assets; network access happens only when ``download`` is true."""

    paths = tuple(
        Path(
            hf_hub_download(
                repo_id=MODEL_ID,
                filename=filename,
                revision=MODEL_REVISION,
                cache_dir=str(cache_dir) if cache_dir else None,
                local_files_only=not download,
            )
        )
        for filename in REQUIRED_FILES
    )
    return E5Assets(model_path=paths[0], tokenizer_path=paths[1])


def download_e5_assets(*, cache_dir: Path | None = None) -> E5Assets:
    return resolve_e5_assets(cache_dir=cache_dir, download=True)

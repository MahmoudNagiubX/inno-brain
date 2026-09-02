from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from innobrain.knowledge.e5_onnx import MultilingualE5OnnxProvider

EMBEDDING_DIMENSION = 384
EMBEDDING_DTYPE = np.dtype("<f4")


@dataclass(frozen=True, slots=True)
class EmbeddingMatrix:
    values: np.ndarray
    deployable: bool


def validate_embedding_matrix(
    matrix: np.ndarray,
    *,
    expected_rows: int | None = None,
    dimension: int = EMBEDDING_DIMENSION,
) -> None:
    if not isinstance(matrix, np.ndarray) or matrix.ndim != 2:
        raise ValueError("embedding matrix must be a two-dimensional NumPy array")
    if matrix.shape[1] != dimension:
        raise ValueError(f"embedding matrix must have dimension {dimension}")
    if expected_rows is not None and matrix.shape[0] != expected_rows:
        raise ValueError(f"embedding matrix must contain {expected_rows} rows")
    if matrix.dtype.kind != "f" or matrix.dtype.itemsize != 4:
        raise ValueError("embedding matrix must use float32 values")
    if not np.isfinite(matrix).all():
        raise ValueError("embedding matrix contains non-finite values")
    if matrix.shape[0] and not np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-3):
        raise ValueError("embedding matrix rows must be approximately unit normalized")


async def build_embedding_matrix(
    texts: Sequence[str],
    provider: object,
    *,
    deployable: bool,
    dimension: int = EMBEDDING_DIMENSION,
) -> EmbeddingMatrix:
    if deployable and not isinstance(provider, MultilingualE5OnnxProvider):
        raise ValueError("deployable packages require the real multilingual-E5 ONNX provider")
    values: list[Sequence[float]] = []
    if not hasattr(provider, "embed_passage"):
        raise ValueError("embedding provider must expose embed_passage()")
    embed_passage = provider.embed_passage
    for text in texts:
        values.append(await embed_passage(text))
    matrix = np.asarray(values, dtype=EMBEDDING_DTYPE)
    if not values:
        matrix = np.empty((0, dimension), dtype=EMBEDDING_DTYPE)
    validate_embedding_matrix(matrix, expected_rows=len(texts), dimension=dimension)
    return EmbeddingMatrix(values=matrix, deployable=deployable)


def save_embedding_matrix(path: Path | str, matrix: np.ndarray) -> Path:
    validate_embedding_matrix(matrix)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, np.asarray(matrix, dtype=EMBEDDING_DTYPE), allow_pickle=False)
    return path


def load_embedding_matrix(
    path: Path | str,
    *,
    expected_rows: int | None = None,
    dimension: int = EMBEDDING_DIMENSION,
) -> np.ndarray:
    matrix = np.load(Path(path), allow_pickle=False)
    validate_embedding_matrix(matrix, expected_rows=expected_rows, dimension=dimension)
    return matrix


__all__ = [
    "EMBEDDING_DIMENSION",
    "EMBEDDING_DTYPE",
    "EmbeddingMatrix",
    "build_embedding_matrix",
    "load_embedding_matrix",
    "save_embedding_matrix",
    "validate_embedding_matrix",
]

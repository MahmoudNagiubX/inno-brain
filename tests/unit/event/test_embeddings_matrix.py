from pathlib import Path

import numpy as np
import pytest

from innobrain.event.embeddings import (
    build_embedding_matrix,
    load_embedding_matrix,
    save_embedding_matrix,
    validate_embedding_matrix,
)


class _DeterministicTestProvider:
    async def embed_passage(self, text: str) -> list[float]:
        vector = np.zeros(384, dtype=np.float32)
        vector[hash(text) % 384] = 1.0
        return vector.tolist()


def test_test_embedding_matrix_is_portable_but_not_deployable() -> None:
    matrix = __import__("asyncio").run(
        build_embedding_matrix(
            ["alpha", "beta"],
            _DeterministicTestProvider(),
            deployable=False,
        )
    )

    assert matrix.deployable is False
    assert matrix.values.shape == (2, 384)
    assert matrix.values.dtype == np.dtype("<f4")
    validate_embedding_matrix(matrix.values, expected_rows=2)


def test_production_matrix_rejects_non_real_e5_provider() -> None:
    with pytest.raises(ValueError, match="real multilingual-E5"):
        __import__("asyncio").run(
            build_embedding_matrix(
                ["alpha"],
                _DeterministicTestProvider(),
                deployable=True,
            )
        )


def test_matrix_save_and_load_disallow_pickle(tmp_path: Path) -> None:
    matrix = np.zeros((1, 384), dtype="<f4")
    matrix[0, 0] = 1.0
    path = tmp_path / "embeddings.npy"

    save_embedding_matrix(path, matrix)
    loaded = load_embedding_matrix(path, expected_rows=1)

    assert loaded.dtype == np.dtype("<f4")
    assert np.array_equal(loaded, matrix)


@pytest.mark.parametrize(
    "matrix",
    [
        np.zeros((1, 383), dtype="<f4"),
        np.full((1, 384), np.nan, dtype="<f4"),
        np.full((1, 384), 2.0, dtype="<f4"),
    ],
)
def test_embedding_validation_rejects_bad_shape_values_or_norm(matrix: np.ndarray) -> None:
    with pytest.raises(ValueError):
        validate_embedding_matrix(matrix, expected_rows=1)

import numpy as np

from innobrain.knowledge.e5_onnx import mean_pool


def test_mean_pool_ignores_padding_tokens() -> None:
    hidden = np.asarray(
        [[[1.0, 2.0], [3.0, 4.0], [100.0, 200.0]]],
        dtype=np.float32,
    )
    mask = np.asarray([[1, 1, 0]], dtype=np.int64)

    np.testing.assert_allclose(mean_pool(hidden, mask), [[2.0, 3.0]])

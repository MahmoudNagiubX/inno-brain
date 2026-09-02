import os

import pytest

from innobrain.knowledge.e5_onnx import MultilingualE5OnnxProvider
from innobrain.knowledge.embedding_assets import download_e5_assets


@pytest.mark.asyncio
async def test_real_e5_embedding_is_optional() -> None:
    if os.environ.get("INNOBRAIN_RUN_MODEL_TESTS") != "1":
        pytest.skip("set INNOBRAIN_RUN_MODEL_TESTS=1 to run the real E5 model test")
    try:
        assets = download_e5_assets()
        provider = MultilingualE5OnnxProvider(assets)
    except Exception as exc:  # pragma: no cover - depends on external cache/network
        pytest.skip(f"E5 assets unavailable: {exc}")

    vector = await provider.embed_query("ميعاد جلسة الذكاء الاصطناعي؟")
    assert len(vector) == 384

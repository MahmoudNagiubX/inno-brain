from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from innobrain.event.builder import build_event_package
from innobrain.event.errors import EventCompatibilityError
from innobrain.event.validation import PackageVerificationPolicy, verify_event_package

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class TestTokenizer:
    def encode(self, text: str) -> SimpleNamespace:
        return SimpleNamespace(ids=text.split())


class TestEmbeddingProvider:
    async def embed_passage(self, text: str) -> list[float]:
        vector = np.zeros(384, dtype=np.float32)
        vector[hash(text) % 384] = 1.0
        return vector.tolist()


@pytest.mark.asyncio
async def test_builds_self_contained_unsigned_development_package(tmp_path: Path) -> None:
    output = tmp_path / "alpha.innoevent"
    result = await build_event_package(
        REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha",
        output,
        embedding_provider=TestEmbeddingProvider(),
        tokenizer=TestTokenizer(),
        deployable=False,
    )

    assert result.archive_path == output
    assert result.manifest.event_id == "event-alpha"
    assert result.manifest.deployable is False
    assert result.report["chunks"]["count"] == len(result.chunks)
    verified = verify_event_package(
        output,
        policy=PackageVerificationPolicy(
            environment="development", allow_unsigned_development=True
        ),
    )
    assert "knowledge/chunks.jsonl" in verified.member_names
    assert "knowledge/embeddings.npy" in verified.member_names


@pytest.mark.asyncio
async def test_production_build_rejects_test_embeddings_before_archive(tmp_path: Path) -> None:
    with pytest.raises(EventCompatibilityError, match="real multilingual-E5"):
        await build_event_package(
            REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha",
            tmp_path / "alpha.innoevent",
            embedding_provider=TestEmbeddingProvider(),
            tokenizer=TestTokenizer(),
            deployable=True,
        )

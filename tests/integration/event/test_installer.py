import sqlite3
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from innobrain.event.builder import build_event_package
from innobrain.event.installer import install_event_package
from innobrain.event.validation import PackageVerificationPolicy

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class TestTokenizer:
    def encode(self, text: str) -> SimpleNamespace:
        return SimpleNamespace(ids=text.split())


class TestEmbeddingProvider:
    async def embed_passage(self, text: str) -> list[float]:
        vector = np.zeros(384, dtype=np.float32)
        vector[len(text) % 384] = 1.0
        return vector.tolist()


@pytest.mark.asyncio
async def test_installs_target_local_knowledge_database_and_health_checks_read_only(
    tmp_path: Path,
) -> None:
    package = tmp_path / "alpha.innoevent"
    await build_event_package(
        REPOSITORY_ROOT / "fixtures" / "phase4" / "event_alpha",
        package,
        embedding_provider=TestEmbeddingProvider(),
        tokenizer=TestTokenizer(),
    )

    installed = install_event_package(
        package,
        tmp_path / "runtime_data",
        verification_policy=PackageVerificationPolicy(
            environment="development", allow_unsigned_development=True
        ),
    )

    assert installed.manifest.event_id == "event-alpha"
    assert installed.health["chunks"] == installed.health["fts"]
    assert installed.health["chunks"] == installed.health["vec"]
    assert installed.health["chunks"] == installed.health["embedding_rows"]
    assert installed.database_path.name == "event.sqlite3"
    assert installed.source_package.name == "source.innoevent"
    assert installed.root.is_dir()
    assert installed.source_package.read_bytes() == package.read_bytes()

    with pytest.raises(sqlite3.OperationalError):
        installed.readonly_connection.execute("DELETE FROM chunks")
    installed.readonly_connection.close()

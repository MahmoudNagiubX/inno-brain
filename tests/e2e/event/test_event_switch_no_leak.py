from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from innobrain.conversation.memory import SessionMemory
from innobrain.event.activation import ActivationManager
from innobrain.event.builder import build_event_package
from innobrain.event.installer import install_event_package
from innobrain.event.registry import EventRegistry
from innobrain.event.runtime import RuntimeContextSwitcher
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


async def _build_and_install(fixture_name: str, tmp_path: Path, data_root: Path):
    package = tmp_path / f"{fixture_name}.innoevent"
    await build_event_package(
        REPOSITORY_ROOT / "fixtures" / "phase4" / fixture_name,
        package,
        embedding_provider=TestEmbeddingProvider(),
        tokenizer=TestTokenizer(),
    )
    installed = install_event_package(
        package,
        data_root,
        verification_policy=PackageVerificationPolicy(
            environment="development", allow_unsigned_development=True
        ),
    )
    installed.close()


def _texts(context, query: str) -> list[str]:
    return [
        row["text"]
        for row in context.repository.lexical_search(context.record.event_id, query, 5)
    ]


@pytest.mark.asyncio
async def test_switching_events_has_no_old_data_and_resets_session_memory(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime_data"
    await _build_and_install("event_alpha", tmp_path, data_root)
    await _build_and_install("event_beta", tmp_path, data_root)
    registry = EventRegistry(data_root)
    alpha = registry.get("event-alpha")
    beta = registry.get("event-beta")
    memory = SessionMemory()
    switcher = RuntimeContextSwitcher(memory)
    manager = ActivationManager(
        data_root,
        registry,
        idle_guard=lambda: True,
        switch_hook=switcher.switch,
    )

    manager.activate("event-alpha", build_id=alpha.build_id)
    memory.add_turn("alpha", "remembered alpha", ["ALPHA-COMPASS"])
    assert any("ALPHA-COMPASS" in text for text in _texts(switcher.current, "ALPHA COMPASS"))
    assert not any("BETA-LANTERN" in text for text in _texts(switcher.current, "BETA LANTERN"))

    manager.activate("event-beta", build_id=beta.build_id)
    assert memory.recent_turns() == ()
    assert any("BETA-LANTERN" in text for text in _texts(switcher.current, "BETA LANTERN"))
    assert not any("ALPHA-COMPASS" in text for text in _texts(switcher.current, "ALPHA COMPASS"))

    manager.rollback()
    assert switcher.current.record.event_id == "event-alpha"
    assert any("ALPHA-COMPASS" in text for text in _texts(switcher.current, "ALPHA COMPASS"))
    assert not any("BETA-LANTERN" in text for text in _texts(switcher.current, "BETA LANTERN"))
    switcher.close()

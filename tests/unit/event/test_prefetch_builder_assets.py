from pathlib import Path

import pytest

from innobrain.knowledge.embedding_assets import E5Assets
from scripts.phase4.prefetch_builder_assets import prefetch_e5


def test_e5_prefetch_succeeds_on_first_attempt(tmp_path: Path) -> None:
    calls: list[Path] = []

    def downloader(*, cache_dir: Path) -> E5Assets:
        calls.append(cache_dir)
        return E5Assets(cache_dir / "model.onnx", cache_dir / "tokenizer.json")

    sleeps: list[float] = []
    result = prefetch_e5(tmp_path, downloader=downloader, sleeper=sleeps.append)

    assert result.model_path.name == "model.onnx"
    assert calls == [tmp_path]
    assert sleeps == []


def test_e5_prefetch_retries_at_most_three_times_with_bounded_delays(tmp_path: Path) -> None:
    attempts = 0
    sleeps: list[float] = []

    def downloader(*, cache_dir: Path) -> E5Assets:
        nonlocal attempts
        attempts += 1
        raise OSError("offline")

    with pytest.raises(RuntimeError, match="three attempts"):
        prefetch_e5(tmp_path, downloader=downloader, sleeper=sleeps.append)

    assert attempts == 3
    assert sleeps == [2, 5]

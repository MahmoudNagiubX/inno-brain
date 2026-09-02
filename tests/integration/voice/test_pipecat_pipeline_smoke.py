import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from innobrain.config import load_all_configs
from innobrain.voice.pipecat_runtime import RealtimeTurnRuntime

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class SyntheticSilenceStream:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    async def chunks(self) -> AsyncIterator[bytes]:
        for _ in range(50):
            await asyncio.sleep(0)
            yield b"\x00" * 640


@pytest.mark.asyncio
async def test_pipeline_accepts_one_second_synthetic_silence() -> None:
    stream = SyntheticSilenceStream()
    runtime = RealtimeTurnRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stream=stream,
    )

    await runtime.start()
    await asyncio.sleep(0.2)
    await runtime.stop()

    assert stream.started is True
    assert stream.stopped is True

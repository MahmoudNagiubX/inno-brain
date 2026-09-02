from pathlib import Path

import pytest

from innobrain.config import load_all_configs
from innobrain.voice.pipecat_runtime import RealtimeTurnRuntime

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_builder_uses_laptop_realtime_turn_configuration() -> None:
    runtime = RealtimeTurnRuntime(load_all_configs(REPOSITORY_ROOT).runtime)

    assert runtime.vad_sample_rate_hz == 16000
    assert runtime.smart_turn_wait_for_transcript is False
    assert runtime.pipeline_processor_names == ("VADProcessor", "UserTurnProcessor")


@pytest.mark.asyncio
async def test_runtime_events_are_exposed_without_provider_modules() -> None:
    runtime = RealtimeTurnRuntime(load_all_configs(REPOSITORY_ROOT).runtime)

    assert runtime.events == []
    assert "innobrain.providers.stt" not in __import__("sys").modules
    assert "innobrain.providers.llm" not in __import__("sys").modules
    assert "innobrain.providers.tts" not in __import__("sys").modules
    await runtime.cleanup()

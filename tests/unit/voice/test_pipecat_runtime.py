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


@pytest.mark.asyncio
async def test_feed_audio_queues_vad_frame_before_stt_observer() -> None:
    class OneChunkStream:
        def start(self):
            return None

        def stop(self):
            return None

        async def chunks(self):
            yield b"pcm"

    order: list[str] = []

    async def observe(_pcm: bytes) -> None:
        order.append("stt-observer")

    runtime = RealtimeTurnRuntime(
        load_all_configs(REPOSITORY_ROOT).runtime,
        stream=OneChunkStream(),
        on_audio_chunk=observe,
    )

    async def queue_frames(_frames) -> None:
        order.append("vad-frame")

    runtime.worker.queue_frames = queue_frames
    await runtime._feed_audio()

    assert order == ["vad-frame", "stt-observer"]
    await runtime.cleanup()

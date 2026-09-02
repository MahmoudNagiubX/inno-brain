import asyncio
from pathlib import Path

import numpy as np
import pytest

from innobrain.config import load_all_configs
from innobrain.voice.interruption import InterruptionController
from innobrain.voice.pipecat_runtime import RealtimeTurnRuntime
from innobrain.voice.playback import PlaybackController
from innobrain.voice.state import ConversationState, ConversationStateMachine
from scripts.phase2.barge_in_demo import run_programmatic_barge_in_trial

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class RecordingPlaybackBackend:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.stop_calls = 0
        self._release = asyncio.Event()

    async def play(self, samples: np.ndarray, sample_rate_hz: int) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await self._release.wait()
        finally:
            self.active -= 1

    async def stop(self) -> None:
        self.stop_calls += 1
        self._release.set()


@pytest.mark.asyncio
async def test_programmatic_barge_in_cancels_one_playback_and_records_result(
    tmp_path: Path,
) -> None:
    config = load_all_configs(REPOSITORY_ROOT).runtime
    backend = RecordingPlaybackBackend()
    playback = PlaybackController(backend)

    machine = ConversationStateMachine()
    interruption = InterruptionController(machine, playback)
    runtime = RealtimeTurnRuntime(
        config,
        machine=machine,
        interruption=interruption,
    )

    try:
        result = await run_programmatic_barge_in_trial(
            runtime,
            playback,
            interruption,
            results_path=tmp_path / "barge_in_results.jsonl",
            trial_id="automated-1",
        )
    finally:
        await playback.cancel()
        await runtime.cleanup()

    assert result["interrupted"] is True
    assert result["final_state"] == ConversationState.LISTENING.value
    assert result["playback_active"] is False
    assert backend.stop_calls == 1
    assert backend.max_active == 1
    assert (tmp_path / "barge_in_results.jsonl").read_text(encoding="utf-8").count("\n") == 1

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import sounddevice as sd

from innobrain.audio import get_default_device_indices
from innobrain.config import load_all_configs
from innobrain.voice.interruption import InterruptionController, InterruptionResult
from innobrain.voice.pipecat_runtime import RealtimeTurnRuntime
from innobrain.voice.playback import (
    PlaybackController,
    SoundDevicePlaybackBackend,
)
from innobrain.voice.state import ConversationState, ConversationStateMachine
from innobrain.voice.turn_events import TurnEvent

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = REPOSITORY_ROOT / "artifacts" / "phase2" / "barge_in_results.jsonl"


def print_default_microphone() -> None:
    input_index, _ = get_default_device_indices()
    if input_index is None:
        print("DEFAULT_MICROPHONE index=default name=unresolved", flush=True)
        return
    device = sd.query_devices(input_index)
    print(
        f"DEFAULT_MICROPHONE index={input_index} name={device['name']}",
        flush=True,
    )


def print_turn_event(event: TurnEvent) -> None:
    print(
        f"{event.event_type.value} strategy={event.strategy_name} "
        f"at_monotonic={event.at_monotonic:.6f}",
        flush=True,
    )


def result_record(
    *,
    trial_id: str,
    trigger_source: str,
    result: InterruptionResult,
    machine: ConversationStateMachine,
    playback: PlaybackController,
) -> dict[str, Any]:
    return {
        "trial_id": trial_id,
        "trigger_source": trigger_source,
        "interrupted": result.interrupted,
        "prior_state": result.prior_state.value,
        "final_state": machine.state.value,
        "playback_active": playback.is_playing,
        "event_to_playback_stop_ms": result.event_to_playback_stop_ms,
        "latency_kind": "software_event_to_cancel_debug_only",
        "acceptance_status": "DEFERRED_NOT_RUN",
    }


def append_result(results_path: Path, record: dict[str, Any]) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


async def run_programmatic_barge_in_trial(
    runtime: RealtimeTurnRuntime,
    playback: PlaybackController,
    interruption: InterruptionController,
    *,
    results_path: Path,
    trial_id: str,
) -> dict[str, Any]:
    """Run the cancellation path without a microphone or human speech."""
    machine = runtime.machine
    if machine.state is ConversationState.IDLE:
        machine.transition(ConversationState.LISTENING, "runtime_started")
    if machine.state is not ConversationState.LISTENING:
        raise RuntimeError(f"Expected LISTENING before trial, got {machine.state.value}")

    machine.transition(ConversationState.THINKING, "user_turn_complete")
    machine.transition(ConversationState.SPEAKING, "response_started")
    if playback.is_playing:
        raise RuntimeError("Refusing to start an overlapping placeholder tone")

    realtime = runtime.config.realtime
    await playback.start_tone(
        frequency_hz=realtime.mock_response_tone_hz,
        duration_secs=realtime.mock_response_duration_secs,
        volume=realtime.mock_response_volume,
        sample_rate_hz=runtime.config.audio.target_sample_rate_hz,
    )
    await asyncio.sleep(0)
    result = await interruption.handle_user_turn_started()
    record = result_record(
        trial_id=trial_id,
        trigger_source="synthetic_programmatic_user_turn_start",
        result=result,
        machine=machine,
        playback=playback,
    )
    append_result(results_path, record)
    return record


class RecordingInterruptionController(InterruptionController):
    def __init__(
        self,
        machine: ConversationStateMachine,
        playback: PlaybackController,
        results_path: Path,
    ) -> None:
        super().__init__(machine, playback)
        self._machine = machine
        self._playback = playback
        self._results_path = results_path
        self._trial_id = "unassigned"
        self._trigger_source = "runtime_user_turn_started"

    def prepare_trial(self, trial_id: str) -> None:
        self._trial_id = trial_id
        self._trigger_source = "runtime_user_turn_started"

    async def handle_user_turn_started(self) -> InterruptionResult:
        result = await super().handle_user_turn_started()
        append_result(
            self._results_path,
            result_record(
                trial_id=self._trial_id,
                trigger_source=self._trigger_source,
                result=result,
                machine=self._machine,
                playback=self._playback,
            ),
        )
        return result


class SilentPlaybackBackend:
    """Test-only backend used by --synthetic so no laptop output is opened."""

    def __init__(self) -> None:
        self._release = asyncio.Event()

    async def play(self, _samples: Any, _sample_rate_hz: int) -> None:
        await self._release.wait()

    async def stop(self) -> None:
        self._release.set()


async def run_synthetic_mode(config: Any, results_path: Path) -> dict[str, Any]:
    machine = ConversationStateMachine()
    playback = PlaybackController(SilentPlaybackBackend())
    interruption = InterruptionController(machine, playback)
    runtime = RealtimeTurnRuntime(
        config,
        machine=machine,
        interruption=interruption,
    )
    try:
        return await run_programmatic_barge_in_trial(
            runtime,
            playback,
            interruption,
            results_path=results_path,
            trial_id="synthetic-1",
        )
    finally:
        await playback.cancel()
        await runtime.cleanup()


async def run_live_mode(config: Any, results_path: Path) -> None:
    machine = ConversationStateMachine()
    playback = PlaybackController(SoundDevicePlaybackBackend())
    interruption = RecordingInterruptionController(machine, playback, results_path)
    runtime = RealtimeTurnRuntime(
        config,
        machine=machine,
        interruption=interruption,
        on_event=print_turn_event,
    )
    await runtime.start()
    print("LIVE_MIC_STARTED", flush=True)
    print("Type 'tone' to explicitly start the placeholder tone, then speak.", flush=True)
    print("Type 'reset' to stop the tone and return to listening; type 'quit' to stop.", flush=True)
    trial_number = 0
    try:
        while True:
            command = await asyncio.to_thread(input, "barge-in command [tone/reset/quit]: ")
            command = command.strip().lower()
            if command in {"quit", "q"}:
                return
            if command == "reset":
                await playback.cancel()
                if machine.state is ConversationState.SPEAKING:
                    machine.transition(ConversationState.LISTENING, "placeholder_reset")
                print(f"STATE={machine.state.value}", flush=True)
                continue
            if command != "tone":
                print("Use tone, reset, or quit.", flush=True)
                continue
            if playback.is_playing:
                print("TONE_ALREADY_ACTIVE", flush=True)
                continue
            if machine.state is not ConversationState.LISTENING:
                print(f"TONE_NOT_STARTED state={machine.state.value}", flush=True)
                continue

            trial_number += 1
            interruption.prepare_trial(f"live-{trial_number}")
            machine.transition(ConversationState.THINKING, "user_turn_complete")
            machine.transition(ConversationState.SPEAKING, "response_started")
            realtime = config.realtime
            await playback.start_tone(
                frequency_hz=realtime.mock_response_tone_hz,
                duration_secs=realtime.mock_response_duration_secs,
                volume=realtime.mock_response_volume,
                sample_rate_hz=config.audio.target_sample_rate_hz,
            )
            print("PLACEHOLDER_TONE_STARTED", flush=True)
    finally:
        await playback.cancel()
        await runtime.stop()


async def main(synthetic: bool, results_path: Path) -> int:
    config = load_all_configs(REPOSITORY_ROOT).runtime
    if synthetic:
        record = await run_synthetic_mode(config, results_path)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        return 0

    print_default_microphone()
    await run_live_mode(config, results_path)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 placeholder-tone barge-in harness")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="exercise software cancellation without opening laptop microphone/output",
    )
    parser.add_argument(
        "--results-path",
        type=Path,
        default=RESULTS_PATH,
        help="JSONL result path (ignored by Git in the default location)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        raise SystemExit(asyncio.run(main(arguments.synthetic, arguments.results_path)))
    except KeyboardInterrupt:
        print()

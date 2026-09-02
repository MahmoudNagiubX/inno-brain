import asyncio
import json
from pathlib import Path

import sounddevice as sd

from innobrain.audio import get_default_device_indices
from innobrain.config import load_all_configs
from innobrain.voice.pipecat_runtime import RealtimeTurnRuntime
from innobrain.voice.turn_events import TurnEvent

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVENTS_PATH = REPOSITORY_ROOT / "artifacts" / "phase2" / "turn_events.jsonl"


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


def record_event(event: TurnEvent) -> None:
    record = {
        "event_type": event.event_type.value,
        "at_monotonic": event.at_monotonic,
        "strategy_name": event.strategy_name,
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(
        f"{event.event_type.value} strategy={event.strategy_name} "
        f"at_monotonic={event.at_monotonic:.6f}",
        flush=True,
    )


async def main() -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.write_text("", encoding="utf-8")
    config = load_all_configs(REPOSITORY_ROOT).runtime
    print_default_microphone()
    runtime = RealtimeTurnRuntime(config, on_event=record_event)
    await runtime.start()
    print("LIVE_MIC_STARTED", flush=True)
    print("Stay intentionally silent for 10 seconds for Test A.", flush=True)
    try:
        while True:
            await asyncio.sleep(1.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await runtime.stop()
        starts = sum(
            event.event_type.value == "USER_TURN_STARTED" for event in runtime.events
        )
        stops = sum(
            event.event_type.value == "USER_TURN_STOPPED" for event in runtime.events
        )
        print(f"USER_TURN_STARTED count = {starts}", flush=True)
        print(f"USER_TURN_STOPPED count = {stops}", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

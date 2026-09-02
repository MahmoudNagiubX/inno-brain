import asyncio
import threading

import pytest

from innobrain.providers.errors import ProviderTimeout
from innobrain.providers.transcript_buffer import TurnTranscriptBuffer


@pytest.mark.asyncio
async def test_aggregates_final_segments_and_suppresses_duplicates_from_worker_thread() -> None:
    buffer = TurnTranscriptBuffer(asyncio.get_running_loop())
    buffer.begin_turn(11)

    def publish() -> None:
        buffer.push_from_callback(turn_id=11, text="أهلاً", is_final=True)
        buffer.push_from_callback(turn_id=11, text="أهلاً", is_final=True)
        buffer.push_from_callback(turn_id=11, text="بيك", is_final=True)
        buffer.complete_from_callback(turn_id=11)

    worker = threading.Thread(target=publish)
    worker.start()
    worker.join()

    final = await buffer.finalize(11, timeout_seconds=0.5)

    assert final.text == "أهلاً بيك"
    assert final.is_final is True
    assert final.turn_id == 11


@pytest.mark.asyncio
async def test_rejects_late_old_turn_and_does_not_leak_between_turns() -> None:
    buffer = TurnTranscriptBuffer(asyncio.get_running_loop())
    buffer.begin_turn(1)
    buffer.push_from_callback(turn_id=1, text="قديم", is_final=True)
    buffer.close_turn(1)
    buffer.begin_turn(2)
    buffer.push_from_callback(turn_id=1, text="متأخر", is_final=True)
    buffer.push_from_callback(turn_id=2, text="جديد", is_final=True)
    buffer.complete_from_callback(turn_id=2)

    final = await buffer.finalize(2, timeout_seconds=0.5)

    assert final.text == "جديد"
    assert final.turn_id == 2


@pytest.mark.asyncio
async def test_finalize_times_out_without_definitive_turn_completion() -> None:
    buffer = TurnTranscriptBuffer(asyncio.get_running_loop())
    buffer.begin_turn(3)
    buffer.push_from_callback(turn_id=3, text="جزء", is_final=True)

    with pytest.raises(ProviderTimeout, match="turn 3"):
        await buffer.finalize(3, timeout_seconds=0.01)


@pytest.mark.asyncio
async def test_partial_is_scoped_to_active_turn() -> None:
    buffer = TurnTranscriptBuffer(asyncio.get_running_loop())
    buffer.begin_turn(4)
    buffer.push_from_callback(turn_id=4, text="مسودة", is_final=False)
    await asyncio.sleep(0)

    assert buffer.partial_text(4).text == "مسودة"

    buffer.close_turn(4)
    assert buffer.partial_text(4) is None

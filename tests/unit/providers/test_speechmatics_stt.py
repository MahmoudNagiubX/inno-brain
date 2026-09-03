import asyncio
import threading

import pytest
from speechmatics.voice import AgentServerMessageType, SegmentMessage, TurnStartEndResetMessage
from speechmatics.voice._models import MessageTimeMetadata, SegmentMessageSegment

from innobrain.providers.errors import ProviderTimeout
from innobrain.providers.speechmatics_stt import SpeechmaticsSTTProvider


def _make_segment_message(text: str, is_partial: bool = False) -> SegmentMessage:
    seg = SegmentMessageSegment(
        speaker_id="S1",
        is_active=True,
        timestamp="0.0",
        language="ar",
        text=text,
        annotation=[],
        metadata=MessageTimeMetadata(start_time=0.0, end_time=1.0),
    )
    msg_type = (
        AgentServerMessageType.ADD_PARTIAL_SEGMENT
        if is_partial
        else AgentServerMessageType.ADD_SEGMENT
    )
    return SegmentMessage(
        message=msg_type,
        segments=[seg],
        metadata=MessageTimeMetadata(start_time=0.0, end_time=1.0),
    )


def _make_eot_message(turn_id: int) -> TurnStartEndResetMessage:
    return TurnStartEndResetMessage(
        message=AgentServerMessageType.END_OF_TURN,
        turn_id=turn_id,
        metadata=MessageTimeMetadata(start_time=0.0, end_time=1.0),
    )


class FakeSpeechmaticsClient:
    def __init__(self):
        self.callbacks = {}
        self.audio = []
        self.connected = False
        self.finalized = False
        self.provider_turn_id = 0

    def on(self, event, callback):
        self.callbacks[getattr(event, "value", event)] = callback

    async def connect(self):
        self.connected = True

    async def send_audio(self, pcm):
        self.audio.append(pcm)

    async def finalize(self, end_of_turn=False):
        self.finalized = end_of_turn
        segment_callback = self.callbacks.get("AddSegment")
        if segment_callback is not None:
            segment_callback(_make_segment_message("أهلاً"))
            segment_callback(_make_segment_message("بيك"))
        end_callback = self.callbacks.get("EndOfTurn")
        if end_callback is not None:
            end_callback(_make_eot_message(self.provider_turn_id))
            self.provider_turn_id += 1

    async def disconnect(self):
        self.connected = False


@pytest.mark.asyncio
async def test_speechmatics_uses_ar_external_endpointing_and_injected_pcm_client():
    client = FakeSpeechmaticsClient()
    provider = SpeechmaticsSTTProvider(client=client)

    await provider.start()
    await provider.begin_turn(1)
    await provider.stream_audio(b"pcm")
    partial_callback = client.callbacks["AddPartialSegment"]
    partial_callback(
        _make_segment_message("أهلاً", is_partial=True)
    )
    partial = await provider.partial_text()
    final = await provider.final_text(1)
    await provider.stop()

    assert provider.config.language == "ar"
    assert provider.config.end_of_utterance_mode.value == "external"
    assert provider.config.sample_rate == 16000
    assert partial is not None
    assert partial.text == "أهلاً"
    assert partial.turn_id == 1
    assert final.text == "أهلاً بيك"
    assert final.turn_id == 1
    assert final.is_final is True
    assert final.language == "ar-EG"
    assert client.audio == [b"pcm"]
    assert client.finalized is True


@pytest.mark.asyncio
async def test_speechmatics_multi_turn_maps_provider_ids_0_1_2_to_application_turns():
    client = FakeSpeechmaticsClient()
    client.finalize = lambda end_of_turn=False: None
    provider = SpeechmaticsSTTProvider(client=client, final_timeout_seconds=0.2)
    await provider.start()
    segment_cb = client.callbacks["AddSegment"]
    end_cb = client.callbacks["EndOfTurn"]

    # Turn 1: application turn 1, provider turn 0
    await provider.begin_turn(1)
    segment_cb(_make_segment_message("turn-0"))
    end_cb(_make_eot_message(0))
    res1 = await provider.final_text(1)
    assert res1.turn_id == 1
    assert res1.text == "turn-0"

    # Turn 2: application turn 2, provider turn 1
    await provider.begin_turn(2)
    segment_cb(_make_segment_message("turn-1"))
    end_cb(_make_eot_message(1))
    res2 = await provider.final_text(2)
    assert res2.turn_id == 2
    assert res2.text == "turn-1"

    # Turn 3: application turn 3, provider turn 2
    await provider.begin_turn(3)
    segment_cb(_make_segment_message("turn-2"))
    end_cb(_make_eot_message(2))
    res3 = await provider.final_text(3)
    assert res3.turn_id == 3
    assert res3.text == "turn-2"

    await provider.stop()


@pytest.mark.asyncio
async def test_speechmatics_stale_prior_end_of_turn_cannot_complete_current_application_turn():
    client = FakeSpeechmaticsClient()
    client.finalize = lambda end_of_turn=False: None
    provider = SpeechmaticsSTTProvider(client=client, final_timeout_seconds=0.05)
    await provider.start()
    segment_cb = client.callbacks["AddSegment"]
    end_cb = client.callbacks["EndOfTurn"]

    # Turn 1
    await provider.begin_turn(1)
    segment_cb(_make_segment_message("turn-0"))
    end_cb(_make_eot_message(0))
    await provider.final_text(1)

    # Turn 2: active provider turn should be 1
    await provider.begin_turn(2)
    segment_cb(_make_segment_message("turn-1"))

    # Stale END_OF_TURN with provider ID 0 arrives
    end_cb(_make_eot_message(0))

    # Stale ID 0 must not complete turn 2; final_text without matching EOT times out
    with pytest.raises(ProviderTimeout, match="Speechmatics"):
        await provider.final_text(2)

    await provider.stop()


@pytest.mark.asyncio
async def test_speechmatics_segments_without_active_turn_are_ignored():
    client = FakeSpeechmaticsClient()
    client.finalize = lambda end_of_turn=False: None
    provider = SpeechmaticsSTTProvider(client=client, final_timeout_seconds=0.2)
    await provider.start()
    segment_cb = client.callbacks["AddSegment"]
    partial_cb = client.callbacks["AddPartialSegment"]
    end_cb = client.callbacks["EndOfTurn"]

    # Send segments before any turn has started
    segment_cb(_make_segment_message("stray final before turn"))
    partial_cb(_make_segment_message("stray partial before turn", is_partial=True))

    # Begin turn 1
    await provider.begin_turn(1)
    assert await provider.partial_text() is None

    segment_cb(_make_segment_message("valid-turn-1"))
    end_cb(_make_eot_message(0))
    res1 = await provider.final_text(1)
    assert res1.text == "valid-turn-1"
    assert res1.turn_id == 1

    # Send segments after turn 1 has closed, before turn 2 starts
    segment_cb(_make_segment_message("stray final between turns"))
    partial_cb(_make_segment_message("stray partial between turns", is_partial=True))

    # Begin turn 2
    await provider.begin_turn(2)
    assert await provider.partial_text() is None

    segment_cb(_make_segment_message("valid-turn-2"))
    end_cb(_make_eot_message(1))
    res2 = await provider.final_text(2)
    assert res2.text == "valid-turn-2"
    assert res2.turn_id == 2

    await provider.stop()


@pytest.mark.asyncio
async def test_speechmatics_stop_start_resets_provider_session_mapping():
    client = FakeSpeechmaticsClient()
    client.finalize = lambda end_of_turn=False: None
    provider = SpeechmaticsSTTProvider(client=client, final_timeout_seconds=0.2)
    await provider.start()
    segment_cb = client.callbacks["AddSegment"]
    end_cb = client.callbacks["EndOfTurn"]

    # Turn 1: provider ID 0
    await provider.begin_turn(1)
    segment_cb(_make_segment_message("first-turn"))
    end_cb(_make_eot_message(0))
    res1 = await provider.final_text(1)
    assert res1.text == "first-turn"
    assert res1.turn_id == 1

    # Stop and restart provider
    await provider.stop()
    await provider.start()
    segment_cb = client.callbacks["AddSegment"]
    end_cb = client.callbacks["EndOfTurn"]

    # Next turn: application turn is 2, but provider ID starts again at 0!
    await provider.begin_turn(2)
    segment_cb(_make_segment_message("restart-turn"))
    end_cb(_make_eot_message(0))  # Provider ID 0 must be accepted
    res2 = await provider.final_text(2)
    assert res2.text == "restart-turn"
    assert res2.turn_id == 2

    await provider.stop()


@pytest.mark.asyncio
async def test_speechmatics_rejects_late_old_turn_callback_from_worker_thread():
    client = FakeSpeechmaticsClient()
    client.finalize = lambda end_of_turn=False: None
    provider = SpeechmaticsSTTProvider(client=client, final_timeout_seconds=0.2)
    await provider.start()
    segment_callback = client.callbacks["AddSegment"]
    end_callback = client.callbacks["EndOfTurn"]

    await provider.begin_turn(1)
    segment_callback(_make_segment_message("قديم"))
    end_callback(_make_eot_message(0))
    first = await provider.final_text(1)
    assert first.text == "قديم"
    assert first.turn_id == 1

    await provider.begin_turn(2)

    worker = threading.Thread(
        target=lambda: (
            end_callback(_make_eot_message(0)),  # stale prior turn END_OF_TURN
            segment_callback(_make_segment_message("جديد")),
            end_callback(_make_eot_message(1)),  # matching turn 2 END_OF_TURN
        )
    )
    worker.start()
    worker.join()

    final = await provider.final_text(2)

    assert final.text == "جديد"
    assert final.turn_id == 2
    await provider.stop()


@pytest.mark.asyncio
async def test_speechmatics_finalize_timeout_is_typed_and_stop_clears_turn():
    client = FakeSpeechmaticsClient()
    client.finalize = lambda end_of_turn=False: None
    provider = SpeechmaticsSTTProvider(client=client, final_timeout_seconds=0.01)
    await provider.start()
    await provider.begin_turn(9)

    with pytest.raises(ProviderTimeout, match="Speechmatics"):
        await provider.final_text(9)

    await provider.stop()
    assert provider.active_turn_id is None


@pytest.mark.asyncio
async def test_speechmatics_callback_does_not_mutate_asyncio_state_on_worker_thread():
    client = FakeSpeechmaticsClient()
    provider = SpeechmaticsSTTProvider(client=client)
    await provider.start()
    await provider.begin_turn(5)
    partial_callback = client.callbacks["AddPartialSegment"]

    worker = threading.Thread(
        target=lambda: partial_callback(_make_segment_message("مسودة", is_partial=True))
    )
    worker.start()
    worker.join()
    await asyncio.sleep(0)

    partial = await provider.partial_text()
    assert partial is not None
    assert partial.text == "مسودة"
    assert partial.turn_id == 5
    await provider.stop()

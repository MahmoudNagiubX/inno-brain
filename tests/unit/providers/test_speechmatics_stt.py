import asyncio
import threading

import pytest

from innobrain.providers.errors import ProviderTimeout
from innobrain.providers.speechmatics_stt import SpeechmaticsSTTProvider


class FakeSpeechmaticsClient:
    def __init__(self):
        self.callbacks = {}
        self.audio = []
        self.connected = False
        self.finalized = False

    def on(self, event, callback):
        self.callbacks[event] = callback

    async def connect(self):
        self.connected = True

    async def send_audio(self, pcm):
        self.audio.append(pcm)

    async def finalize(self, end_of_turn=False):
        self.finalized = end_of_turn
        segment_callback = next(
            callback
            for event, callback in self.callbacks.items()
            if getattr(event, "value", event) == "AddSegment"
        )
        segment_callback({"segments": [{"text": "أهلاً"}], "turn_id": 1})
        segment_callback({"segments": [{"text": "بيك"}], "turn_id": 1})
        end_callback = next(
            callback
            for event, callback in self.callbacks.items()
            if getattr(event, "value", event) == "EndOfTurn"
        )
        end_callback({"turn_id": 1})

    async def disconnect(self):
        self.connected = False


@pytest.mark.asyncio
async def test_speechmatics_uses_ar_external_endpointing_and_injected_pcm_client():
    client = FakeSpeechmaticsClient()
    provider = SpeechmaticsSTTProvider(client=client)

    await provider.start()
    await provider.begin_turn(1)
    await provider.stream_audio(b"pcm")
    partial_callback = next(
        callback
        for event, callback in client.callbacks.items()
        if getattr(event, "value", event) == "AddPartialSegment"
    )
    partial_callback(
        {"segments": [{"text": "أهلاً"}]}
    )
    partial = await provider.partial_text()
    final = await provider.final_text(1)
    await provider.stop()

    assert provider.config.language == "ar"
    assert provider.config.end_of_utterance_mode.value == "external"
    assert provider.config.sample_rate == 16000
    assert partial.text == "أهلاً"
    assert partial.turn_id == 1
    assert final.text == "أهلاً بيك"
    assert final.turn_id == 1
    assert final.is_final is True
    assert final.language == "ar-EG"
    assert client.audio == [b"pcm"]
    assert client.finalized is True


@pytest.mark.asyncio
async def test_speechmatics_rejects_late_old_turn_callback_from_worker_thread():
    client = FakeSpeechmaticsClient()
    provider = SpeechmaticsSTTProvider(client=client)
    await provider.start()
    await provider.begin_turn(1)
    await provider.begin_turn(2)
    segment_callback = next(
        callback
        for event, callback in client.callbacks.items()
        if getattr(event, "value", event) == "AddSegment"
    )
    end_callback = next(
        callback
        for event, callback in client.callbacks.items()
        if getattr(event, "value", event) == "EndOfTurn"
    )

    worker = threading.Thread(
        target=lambda: (
            segment_callback({"segments": [{"text": "قديم"}], "turn_id": 1}),
            segment_callback({"segments": [{"text": "جديد"}], "turn_id": 2}),
            end_callback({"turn_id": 2}),
        )
    )
    worker.start()
    worker.join()
    client.finalize = lambda end_of_turn=False: None

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
    partial_callback = next(
        callback
        for event, callback in client.callbacks.items()
        if getattr(event, "value", event) == "AddPartialSegment"
    )

    worker = threading.Thread(
        target=lambda: partial_callback({"segments": [{"text": "مسودة"}], "turn_id": 5})
    )
    worker.start()
    worker.join()
    await asyncio.sleep(0)

    assert (await provider.partial_text()).turn_id == 5
    await provider.stop()

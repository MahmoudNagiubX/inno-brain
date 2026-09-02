import pytest

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
        callback = next(
            callback
            for event, callback in self.callbacks.items()
            if getattr(event, "value", event) == "AddSegment"
        )
        callback({"segments": [{"text": "أهلاً بيك"}]})

    async def disconnect(self):
        self.connected = False


@pytest.mark.asyncio
async def test_speechmatics_uses_ar_external_endpointing_and_injected_pcm_client():
    client = FakeSpeechmaticsClient()
    provider = SpeechmaticsSTTProvider(client=client)

    await provider.start()
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
    final = await provider.final_text()
    await provider.stop()

    assert provider.config.language == "ar"
    assert provider.config.end_of_utterance_mode.value == "external"
    assert provider.config.sample_rate == 16000
    assert partial.text == "أهلاً"
    assert final.is_final is True
    assert final.language == "ar-EG"
    assert client.audio == [b"pcm"]
    assert client.finalized is True

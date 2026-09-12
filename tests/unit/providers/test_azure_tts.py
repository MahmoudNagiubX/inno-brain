from types import SimpleNamespace

import pytest

from innobrain.providers.azure_tts import AzureTTSProvider


class FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback

    def disconnect(self, callback):
        if self.callback == callback:
            self.callback = None


class FakeFuture:
    def __init__(self, signal):
        self.signal = signal

    def get(self):
        self.signal.callback(SimpleNamespace(result=SimpleNamespace(audio_data=b"pcm")))
        return SimpleNamespace(reason="completed")


class FakeSynthesizer:
    def __init__(self):
        self.synthesizing = FakeSignal()
        self.calls = []

    def speak_text_async(self, text):
        self.calls.append(text)
        return FakeFuture(self.synthesizing)

    def stop_speaking_async(self):
        return FakeFuture(self.synthesizing)


@pytest.mark.asyncio
async def test_azure_tts_configures_male_egyptian_raw_pcm_and_streams_chunks():
    synthesizer = FakeSynthesizer()
    provider = AzureTTSProvider(synthesizer=synthesizer)

    chunks = [chunk async for chunk in provider.stream("أهلاً بيك")]

    assert provider.speech_config.speech_synthesis_voice_name == "ar-EG-ShakirNeural"
    assert provider.speech_config.speech_synthesis_language == "ar-EG"
    assert chunks[0].data == b"pcm"
    assert chunks[0].sample_rate_hz == 16000
    assert chunks[0].channels == 1
    assert synthesizer.calls == ["أهلاً بيك"]


@pytest.mark.asyncio
async def test_azure_tts_selects_configured_english_voice_per_response():
    synthesizer = FakeSynthesizer()
    provider = AzureTTSProvider(
        synthesizer=synthesizer,
        english_locale="en-US",
        english_voice="en-US-JennyNeural",
    )

    chunks = [chunk async for chunk in provider.stream("Where is the stage?", language="en")]

    assert chunks[0].data == b"pcm"
    assert provider.speech_config.speech_synthesis_voice_name == "en-US-JennyNeural"
    assert provider.speech_config.speech_synthesis_language == "en-US"

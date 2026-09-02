import pytest

from innobrain.providers.deepgram_stt import DeepgramSTTProvider


class FakeDeepgramConnection:
    def __init__(self, **options):
        self.options = options
        self.callbacks = {}
        self.audio = []
        self.finalized = False

    def on(self, event, callback):
        self.callbacks[event] = callback

    def send_media(self, pcm):
        self.audio.append(pcm)

    def send_finalize(self):
        self.finalized = True
        callback = next(iter(self.callbacks.values()))
        callback(
            {
                "type": "Results",
                "is_final": True,
                "channel": {"alternatives": [{"transcript": "أهلاً بيك"}]},
            }
        )

    def send_close_stream(self):
        return None


@pytest.mark.asyncio
async def test_deepgram_configures_nova3_arabic_raw_pcm_and_keeps_finalize_explicit():
    holder = {}

    def factory(**options):
        holder["connection"] = FakeDeepgramConnection(**options)
        return holder["connection"]

    provider = DeepgramSTTProvider(connection_factory=factory)
    await provider.start()
    await provider.stream_audio(b"pcm")
    final = await provider.final_text()
    await provider.stop()

    options = holder["connection"].options
    assert options["model"] == "nova-3"
    assert options["language"] == "ar-EG"
    assert options["encoding"] == "linear16"
    assert options["sample_rate"] == 16000
    assert options["channels"] == 1
    assert options["interim_results"] == "true"
    assert options["keyterm"]
    assert holder["connection"].finalized is True
    assert final.language == "ar-EG"

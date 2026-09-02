import asyncio
import threading

import pytest

from innobrain.providers.deepgram_stt import DeepgramSTTProvider
from innobrain.providers.errors import ProviderTimeout


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
                "speech_final": False,
                "channel": {"alternatives": [{"transcript": "أهلاً"}]},
                "turn_id": 1,
            }
        )
        callback(
            {
                "type": "Results",
                "is_final": True,
                "speech_final": True,
                "channel": {"alternatives": [{"transcript": "بيك"}]},
                "turn_id": 1,
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
    await provider.begin_turn(1)
    await provider.stream_audio(b"pcm")
    final = await provider.final_text(1)
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
    assert final.text == "أهلاً بيك"
    assert final.turn_id == 1
    assert final.language == "ar-EG"


@pytest.mark.asyncio
async def test_deepgram_send_media_does_not_block_asyncio_loop():
    connection = FakeDeepgramConnection()
    release = threading.Event()
    send_finished = threading.Event()

    def blocking_send(pcm):
        release.wait(timeout=0.2)
        connection.audio.append(pcm)
        send_finished.set()

    connection.send_media = blocking_send
    provider = DeepgramSTTProvider(connection_factory=lambda **_: connection)
    await provider.start()
    await provider.begin_turn(2)
    heartbeat_ran_before_send_finished = False

    async def heartbeat():
        nonlocal heartbeat_ran_before_send_finished
        await asyncio.sleep(0.01)
        heartbeat_ran_before_send_finished = not send_finished.is_set()
        release.set()

    await asyncio.gather(provider.stream_audio(b"pcm"), heartbeat())

    assert heartbeat_ran_before_send_finished is True
    assert connection.audio == [b"pcm"]
    await provider.stop()


@pytest.mark.asyncio
async def test_deepgram_rejects_stale_turn_callbacks_from_worker_thread():
    connection = FakeDeepgramConnection()
    connection.send_finalize = lambda: None
    provider = DeepgramSTTProvider(connection_factory=lambda **_: connection)
    await provider.start()
    await provider.begin_turn(7)
    await provider.begin_turn(8)
    callback = next(iter(connection.callbacks.values()))

    worker = threading.Thread(
        target=lambda: (
            callback(
                {
                    "type": "Results",
                    "is_final": True,
                    "speech_final": True,
                    "turn_id": 7,
                    "channel": {"alternatives": [{"transcript": "قديم"}]},
                }
            ),
            callback(
                {
                    "type": "Results",
                    "is_final": True,
                    "speech_final": True,
                    "turn_id": 8,
                    "channel": {"alternatives": [{"transcript": "جديد"}]},
                }
            ),
        )
    )
    worker.start()
    worker.join()

    final = await provider.final_text(8)

    assert final.text == "جديد"
    assert final.turn_id == 8
    await provider.stop()


@pytest.mark.asyncio
async def test_deepgram_finalize_timeout_is_typed_and_stop_clears_turn():
    connection = FakeDeepgramConnection()
    connection.send_finalize = lambda: None
    provider = DeepgramSTTProvider(
        connection_factory=lambda **_: connection,
        final_timeout_seconds=0.01,
    )
    await provider.start()
    await provider.begin_turn(9)

    with pytest.raises(ProviderTimeout, match="Deepgram"):
        await provider.final_text(9)

    await provider.stop()
    assert provider.active_turn_id is None

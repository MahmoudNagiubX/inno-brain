import asyncio
import inspect
import os
from collections.abc import AsyncIterator

import azure.cognitiveservices.speech as speechsdk

from .contracts import AudioChunk, TTSProvider
from .errors import MissingProviderCredential, ProviderUnavailable

_END = object()


class AzureTTSProvider(TTSProvider):
    name = "azure"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        region: str | None = None,
        synthesizer: object | None = None,
        sample_rate_hz: int = 16000,
    ) -> None:
        self.api_key = api_key or os.environ.get("AZURE_SPEECH_KEY")
        self.region = region or os.environ.get("AZURE_SPEECH_REGION")
        if synthesizer is None and (not self.api_key or not self.region):
            raise MissingProviderCredential(
                "AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are required"
            )
        self.sample_rate_hz = sample_rate_hz
        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.api_key or "injected-test-key",
            region=self.region or "injected-test-region",
        )
        self.speech_config.speech_synthesis_voice_name = "ar-EG-ShakirNeural"
        self.speech_config.speech_synthesis_language = "ar-EG"
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
        )
        self.synthesizer = synthesizer or speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=None,
        )
        self._active_task: asyncio.Task[object] | None = None
        self._active_queue: asyncio.Queue[object] | None = None

    def stream(self, text: str) -> AsyncIterator[AudioChunk]:
        return self._stream(text)

    async def _stream(self, text: str) -> AsyncIterator[AudioChunk]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[object] = asyncio.Queue()
        self._active_queue = queue

        def on_synthesizing(event: object) -> None:
            result = getattr(event, "result", event)
            data = getattr(result, "audio_data", None)
            if data:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    AudioChunk(data=bytes(data), sample_rate_hz=self.sample_rate_hz, channels=1),
                )

        handles = self._connect_callbacks(on_synthesizing)

        async def synthesize() -> None:
            try:
                future = self.synthesizer.speak_text_async(text)
                await asyncio.to_thread(self._get_future_result, future)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _END)

        self._active_task = asyncio.create_task(synthesize())
        try:
            while True:
                item = await queue.get()
                if item is _END:
                    break
                if isinstance(item, Exception):
                    raise ProviderUnavailable("Azure speech synthesis failed") from item
                yield item  # type: ignore[misc]
            await self._active_task
        finally:
            self._disconnect_callbacks(handles, on_synthesizing)
            self._active_task = None
            self._active_queue = None

    @staticmethod
    def _get_future_result(future: object) -> object:
        get = getattr(future, "get", None)
        if get is None:
            return future
        return get()

    def _connect_callbacks(self, callback: object) -> list[object]:
        signal = getattr(self.synthesizer, "synthesizing", None)
        if signal is None:
            return []
        connect = getattr(signal, "connect", None)
        if connect is not None:
            connect(callback)
        return [signal]

    @staticmethod
    def _disconnect_callbacks(handles: list[object], callback: object) -> None:
        for signal in handles:
            disconnect = getattr(signal, "disconnect", None)
            if disconnect is not None:
                disconnect(callback)

    async def cancel(self) -> None:
        stop = getattr(self.synthesizer, "stop_speaking_async", None)
        if stop is not None:
            future = stop()
            if inspect.isawaitable(future):
                await future
            else:
                await asyncio.to_thread(self._get_future_result, future)
        if self._active_queue is not None:
            self._active_queue.put_nowait(_END)

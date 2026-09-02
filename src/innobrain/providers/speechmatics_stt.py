import asyncio
import inspect
import os
from collections.abc import Callable, Iterable, Mapping

from speechmatics.voice import (
    AdditionalVocabEntry,
    AgentServerMessageType,
    AudioEncoding,
    EndOfUtteranceMode,
    VoiceAgentClient,
    VoiceAgentConfig,
)

from .contracts import STTProvider, TranscriptEvent
from .errors import MissingProviderCredential, ProviderTimeout

EVENT_GLOSSARY = (
    "InnoBrain",
    "Innovatronics",
    "Main Stage",
    "Expo A12",
    "Future of AI in Events",
    "Build an Interactive Robot",
)


def _message_text(message: object) -> str:
    if isinstance(message, Mapping):
        direct = message.get("text")
        if isinstance(direct, str):
            return direct
        for key in ("segments", "results", "alternatives"):
            value = message.get(key)
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
                texts = [_message_text(item) for item in value]
                result = " ".join(text for text in texts if text)
                if result:
                    return result
        return ""
    if isinstance(message, str):
        return message
    dump = getattr(message, "model_dump", None)
    if callable(dump):
        return _message_text(dump())
    return ""


class SpeechmaticsSTTProvider(STTProvider):
    name = "speechmatics"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: object | None = None,
        client_factory: Callable[..., object] | None = None,
        glossary: Iterable[str] = EVENT_GLOSSARY,
        final_timeout_seconds: float = 3.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("SPEECHMATICS_API_KEY")
        if client is None and not self._api_key:
            raise MissingProviderCredential("SPEECHMATICS_API_KEY is not configured")
        vocab = [AdditionalVocabEntry(content=item) for item in glossary]
        self.config = VoiceAgentConfig(
            language="ar",
            end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL,
            additional_vocab=vocab,
            sample_rate=16000,
            audio_encoding=AudioEncoding.PCM_S16LE,
            chunk_size=160,
        )
        if client is not None:
            self.client = client
        else:
            factory = client_factory or VoiceAgentClient
            self.client = factory(api_key=self._api_key, config=self.config)
        self.final_timeout_seconds = final_timeout_seconds
        self._partial: TranscriptEvent | None = None
        self._final_queue: asyncio.Queue[TranscriptEvent] = asyncio.Queue()

    async def start(self) -> None:
        self._register(AgentServerMessageType.ADD_PARTIAL_SEGMENT, self._on_partial)
        self._register(AgentServerMessageType.ADD_SEGMENT, self._on_final)
        result = self.client.connect()
        if inspect.isawaitable(result):
            await result

    async def stream_audio(self, pcm: bytes) -> None:
        result = self.client.send_audio(pcm)
        if inspect.isawaitable(result):
            await result

    async def partial_text(self) -> TranscriptEvent | None:
        return self._partial

    async def final_text(self) -> TranscriptEvent:
        try:
            result = self.client.finalize(end_of_turn=True)
        except TypeError:
            result = self.client.finalize(True)
        if inspect.isawaitable(result):
            await result
        try:
            return await asyncio.wait_for(self._final_queue.get(), self.final_timeout_seconds)
        except TimeoutError as exc:
            raise ProviderTimeout("Speechmatics did not return a final segment") from exc

    async def stop(self) -> None:
        disconnect = getattr(self.client, "disconnect", None) or getattr(self.client, "close", None)
        if disconnect is not None:
            result = disconnect()
            if inspect.isawaitable(result):
                await result

    def _register(self, event: AgentServerMessageType, callback: Callable[[object], None]) -> None:
        try:
            self.client.on(event, callback)
        except (TypeError, ValueError):
            self.client.on(event.value, callback)

    def _on_partial(self, message: object) -> None:
        text = _message_text(message)
        if text:
            self._partial = TranscriptEvent(text=text, is_final=False, language="ar-EG")

    def _on_final(self, message: object) -> None:
        text = _message_text(message)
        if text:
            self._final_queue.put_nowait(
                TranscriptEvent(text=text, is_final=True, language="ar-EG")
            )

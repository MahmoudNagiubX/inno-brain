import asyncio
import inspect
import os
from collections.abc import Callable, Iterable, Mapping

from deepgram import DeepgramClient
from deepgram.core.events import EventType

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


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _transcript(message: object) -> tuple[str, bool]:
    message_type = _field(message, "type", "")
    if message_type not in ("", "Results"):
        return "", False
    channel = _field(message, "channel")
    alternatives = _field(channel, "alternatives", [])
    if not alternatives:
        return "", False
    transcript = _field(alternatives[0], "transcript", "")
    return str(transcript or ""), bool(_field(message, "is_final", False))


class DeepgramSTTProvider(STTProvider):
    name = "deepgram"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: object | None = None,
        connection_factory: Callable[..., object] | None = None,
        glossary: Iterable[str] = EVENT_GLOSSARY,
        final_timeout_seconds: float = 3.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if client is None and connection_factory is None and not self._api_key:
            raise MissingProviderCredential("DEEPGRAM_API_KEY is not configured")
        self.client = client
        self.connection_factory = connection_factory
        self.keyterms = tuple(glossary)
        self.final_timeout_seconds = final_timeout_seconds
        self.options = {
            "model": "nova-3",
            "language": "ar-EG",
            "encoding": "linear16",
            "sample_rate": 16000,
            "channels": 1,
            "interim_results": "true",
            "keyterm": list(self.keyterms),
            "smart_format": "true",
            "vad_events": "false",
        }
        self.connection: object | None = None
        self._context_manager: object | None = None
        self._listener_task: asyncio.Task[object] | None = None
        self._partial: TranscriptEvent | None = None
        self._final_queue: asyncio.Queue[TranscriptEvent] = asyncio.Queue()

    async def start(self) -> None:
        if self.connection is None:
            if self.connection_factory is not None:
                try:
                    connection = self.connection_factory(**self.options)
                except TypeError:
                    connection = self.connection_factory(self.options)
            else:
                if self.client is None:
                    self.client = DeepgramClient(api_key=self._api_key)
                connection = self.client.listen.v1.connect(**self.options)
            if inspect.isawaitable(connection):
                connection = await connection
            self._context_manager = connection if hasattr(connection, "__enter__") else None
            if self._context_manager is not None:
                connection = self._context_manager.__enter__()
            self.connection = connection
        self._register(EventType.MESSAGE, self._on_message)
        start_listening = getattr(self.connection, "start_listening", None)
        if start_listening is not None:
            self._listener_task = asyncio.create_task(asyncio.to_thread(start_listening))

    async def stream_audio(self, pcm: bytes) -> None:
        if self.connection is None:
            raise RuntimeError("Deepgram provider has not started")
        result = self.connection.send_media(pcm)
        if inspect.isawaitable(result):
            await result

    async def partial_text(self) -> TranscriptEvent | None:
        return self._partial

    async def final_text(self) -> TranscriptEvent:
        if self.connection is None:
            raise RuntimeError("Deepgram provider has not started")
        finalize = getattr(self.connection, "send_finalize", None)
        if finalize is not None:
            result = finalize()
            if inspect.isawaitable(result):
                await result
        try:
            return await asyncio.wait_for(self._final_queue.get(), self.final_timeout_seconds)
        except TimeoutError as exc:
            raise ProviderTimeout("Deepgram did not return a final transcript") from exc

    async def stop(self) -> None:
        if self.connection is not None:
            close_stream = getattr(self.connection, "send_close_stream", None)
            if close_stream is not None:
                result = close_stream()
                if inspect.isawaitable(result):
                    await result
        if self._listener_task is not None:
            try:
                await asyncio.wait_for(self._listener_task, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                self._listener_task.cancel()
        if self._context_manager is not None:
            self._context_manager.__exit__(None, None, None)
        self.connection = None
        self._context_manager = None
        self._listener_task = None

    def _register(self, event: EventType, callback: Callable[[object], None]) -> None:
        if self.connection is None:
            return
        try:
            self.connection.on(event, callback)
        except (TypeError, ValueError):
            self.connection.on(event.value, callback)

    def _on_message(self, message: object) -> None:
        text, is_final = _transcript(message)
        if not text:
            return
        if is_final:
            self._final_queue.put_nowait(
                TranscriptEvent(text=text, is_final=True, language="ar-EG")
            )
        else:
            self._partial = TranscriptEvent(text=text, is_final=False, language="ar-EG")

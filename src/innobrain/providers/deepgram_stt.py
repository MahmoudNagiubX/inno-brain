import asyncio
import inspect
import os
from collections.abc import Callable, Iterable, Mapping

from deepgram import DeepgramClient
from deepgram.core.events import EventType

from .contracts import STTProvider, TranscriptEvent
from .errors import MissingProviderCredential, ProviderTimeout
from .transcript_buffer import TurnTranscriptBuffer

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


def _transcript(message: object) -> tuple[str, bool, bool, int | None, str | None]:
    message_type = _field(message, "type", "")
    if message_type not in ("", "Results"):
        return "", False, False, None, None
    channel = _field(message, "channel")
    alternatives = _field(channel, "alternatives", [])
    if not alternatives:
        text = ""
        language = None
    else:
        alternative = alternatives[0]
        text = str(_field(alternative, "transcript", "") or "")
        language = _field(alternative, "language")
        language = language if isinstance(language, str) else None
    message_language = _field(message, "language")
    if isinstance(message_language, str):
        language = message_language
    turn_id = _field(message, "turn_id")
    if not isinstance(turn_id, int):
        turn_id = None
    return (
        text,
        bool(_field(message, "is_final", False)),
        bool(_field(message, "speech_final", False)),
        turn_id,
        language,
    )


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
        model: str = "nova-3",
        language: str = "multi",
    ) -> None:
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if client is None and connection_factory is None and not self._api_key:
            raise MissingProviderCredential("DEEPGRAM_API_KEY is not configured")
        self.client = client
        self.connection_factory = connection_factory
        self.keyterms = tuple(glossary)
        self.final_timeout_seconds = final_timeout_seconds
        self.model = model
        self.language = language
        self.options = {
            "model": model,
            "language": language,
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
        self._buffer: TurnTranscriptBuffer | None = None
        self._active_turn_id: int | None = None

    @property
    def active_turn_id(self) -> int | None:
        return self._active_turn_id

    async def start(self) -> None:
        self._buffer = TurnTranscriptBuffer(
            asyncio.get_running_loop(),
            default_language=self.language,
        )
        if self.connection is None:
            def create_connection() -> object:
                if self.connection_factory is not None:
                    try:
                        return self.connection_factory(**self.options)
                    except TypeError:
                        return self.connection_factory(self.options)
                if self.client is None:
                    self.client = DeepgramClient(api_key=self._api_key)
                return self.client.listen.v1.connect(**self.options)

            connection = await asyncio.to_thread(create_connection)
            if inspect.isawaitable(connection):
                connection = await connection
            self._context_manager = connection if hasattr(connection, "__enter__") else None
            if self._context_manager is not None:
                connection = await asyncio.to_thread(self._context_manager.__enter__)
            self.connection = connection
        self._register(EventType.MESSAGE, self._on_message)
        start_listening = getattr(self.connection, "start_listening", None)
        if start_listening is not None:
            self._listener_task = asyncio.create_task(asyncio.to_thread(start_listening))

    async def begin_turn(self, turn_id: int) -> None:
        if self._buffer is None or self.connection is None:
            raise RuntimeError("Deepgram provider has not started")
        self._active_turn_id = turn_id
        self._buffer.begin_turn(turn_id)

    async def stream_audio(self, pcm: bytes) -> None:
        if self.connection is None:
            raise RuntimeError("Deepgram provider has not started")
        result = await asyncio.to_thread(self.connection.send_media, pcm)
        if inspect.isawaitable(result):
            await result

    async def partial_text(self) -> TranscriptEvent | None:
        if self._buffer is None or self._active_turn_id is None:
            return None
        await asyncio.sleep(0)
        return self._buffer.partial_text(self._active_turn_id)

    async def final_text(self, turn_id: int | None = None) -> TranscriptEvent:
        selected_turn_id = self._active_turn_id if turn_id is None else turn_id
        if self.connection is None or self._buffer is None or selected_turn_id is None:
            raise RuntimeError("Deepgram provider has not started")
        finalize = getattr(self.connection, "send_finalize", None)
        if finalize is not None:
            result = await asyncio.to_thread(finalize)
            if inspect.isawaitable(result):
                await result
        try:
            return await self._buffer.finalize(
                selected_turn_id,
                timeout_seconds=self.final_timeout_seconds,
            )
        except ProviderTimeout as exc:
            raise ProviderTimeout("Deepgram did not return a final transcript") from exc
        finally:
            self._buffer.close_turn(selected_turn_id)
            if self._active_turn_id == selected_turn_id:
                self._active_turn_id = None

    async def stop(self) -> None:
        if self._buffer is not None and self._active_turn_id is not None:
            self._buffer.close_turn(self._active_turn_id)
        self._active_turn_id = None
        if self.connection is not None:
            close_stream = getattr(self.connection, "send_close_stream", None)
            if close_stream is not None:
                result = await asyncio.to_thread(close_stream)
                if inspect.isawaitable(result):
                    await result
        if self._listener_task is not None:
            try:
                await asyncio.wait_for(self._listener_task, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                self._listener_task.cancel()
        if self._context_manager is not None:
            await asyncio.to_thread(self._context_manager.__exit__, None, None, None)
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
        text, is_final, is_terminal, message_turn_id, language = _transcript(message)
        turn_id = message_turn_id or self._active_turn_id
        if turn_id is None or self._buffer is None:
            return
        if text:
            self._buffer.push_from_callback(
                turn_id=turn_id,
                text=text,
                is_final=is_final,
                language=language,
            )
        if is_terminal:
            self._buffer.complete_from_callback(turn_id=turn_id)

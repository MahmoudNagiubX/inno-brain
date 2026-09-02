from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    text: str
    is_final: bool
    language: str = "ar-EG"


@dataclass(frozen=True, slots=True)
class AudioChunk:
    data: bytes
    sample_rate_hz: int
    channels: int = 1


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@runtime_checkable
class STTProvider(Protocol):
    async def start(self) -> None: ...

    async def stream_audio(self, pcm: bytes) -> None: ...

    async def partial_text(self) -> TranscriptEvent | None: ...

    async def final_text(self) -> TranscriptEvent: ...

    async def stop(self) -> None: ...


@runtime_checkable
class LLMProvider(Protocol):
    def stream(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[object],
        context: object,
    ) -> AsyncIterator[str]: ...

    async def cancel(self) -> None: ...


@runtime_checkable
class TTSProvider(Protocol):
    def stream(self, text: str) -> AsyncIterator[AudioChunk]: ...

    async def cancel(self) -> None: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> Sequence[float]: ...

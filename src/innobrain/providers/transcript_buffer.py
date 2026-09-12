import asyncio

from .contracts import TranscriptEvent
from .errors import ProviderTimeout


class TurnTranscriptBuffer:
    """Collect SDK callback transcripts without sharing asyncio state across threads."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        default_language: str = "unknown",
    ) -> None:
        self._loop = loop
        self._default_language = self._normalize_language(default_language)
        self._active_turn_id: int | None = None
        self._final_segments: list[str] = []
        self._final_seen: set[str] = set()
        self._partial: TranscriptEvent | None = None
        self._completed: asyncio.Event | None = None
        self._language = self._default_language

    @property
    def active_turn_id(self) -> int | None:
        return self._active_turn_id

    def begin_turn(self, turn_id: int) -> None:
        if turn_id < 0:
            raise ValueError("turn_id must be non-negative")
        self._active_turn_id = turn_id
        self._final_segments = []
        self._final_seen = set()
        self._partial = None
        self._completed = asyncio.Event()
        self._language = self._default_language

    def push_from_callback(
        self,
        *,
        turn_id: int,
        text: str,
        is_final: bool,
        language: str | None = None,
    ) -> None:
        self._loop.call_soon_threadsafe(
            self._accept_event,
            turn_id,
            text,
            is_final,
            language,
        )

    def complete_from_callback(self, *, turn_id: int) -> None:
        self._loop.call_soon_threadsafe(self._complete_turn, turn_id)

    def partial_text(self, turn_id: int) -> TranscriptEvent | None:
        if turn_id != self._active_turn_id:
            return None
        return self._partial

    async def finalize(self, turn_id: int, *, timeout_seconds: float) -> TranscriptEvent:
        if turn_id != self._active_turn_id or self._completed is None:
            raise ProviderTimeout(f"transcript turn {turn_id} is not active")
        try:
            await asyncio.wait_for(self._completed.wait(), timeout_seconds)
        except TimeoutError as exc:
            raise ProviderTimeout(
                f"transcript turn {turn_id} did not complete before timeout"
            ) from exc
        return TranscriptEvent(
            text=" ".join(self._final_segments).strip(),
            is_final=True,
            language=self._language,
            turn_id=turn_id,
        )

    def close_turn(self, turn_id: int) -> None:
        if turn_id != self._active_turn_id:
            return
        self._active_turn_id = None
        self._final_segments = []
        self._final_seen = set()
        self._partial = None
        self._completed = None
        self._language = self._default_language

    def _accept_event(
        self,
        turn_id: int,
        text: str,
        is_final: bool,
        language: str | None,
    ) -> None:
        if turn_id != self._active_turn_id:
            return
        normalized = " ".join(text.split())
        if not normalized:
            return
        detected_language = self._normalize_language(language)
        if detected_language != "unknown":
            self._language = detected_language
        event = TranscriptEvent(
            text=normalized,
            is_final=is_final,
            language=self._language,
            turn_id=turn_id,
        )
        if not is_final:
            self._partial = event
            return
        if normalized not in self._final_seen:
            self._final_seen.add(normalized)
            self._final_segments.append(normalized)

    def _complete_turn(self, turn_id: int) -> None:
        if turn_id == self._active_turn_id and self._completed is not None:
            self._completed.set()

    @staticmethod
    def _normalize_language(value: str | None) -> str:
        if not value:
            return "unknown"
        normalized = value.strip().lower().replace("_", "-")
        if normalized in {"mixed", "multi", "multilingual"}:
            return "mixed"
        if normalized.startswith("ar"):
            return "ar-EG"
        if normalized.startswith("en"):
            return "en"
        return "unknown"


__all__ = ["TurnTranscriptBuffer"]

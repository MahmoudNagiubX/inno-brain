import asyncio

from .contracts import TranscriptEvent
from .errors import ProviderTimeout


class TurnTranscriptBuffer:
    """Collect SDK callback transcripts without sharing asyncio state across threads."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._active_turn_id: int | None = None
        self._final_segments: list[str] = []
        self._final_seen: set[str] = set()
        self._partial: TranscriptEvent | None = None
        self._completed: asyncio.Event | None = None

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

    def push_from_callback(self, *, turn_id: int, text: str, is_final: bool) -> None:
        self._loop.call_soon_threadsafe(self._accept_event, turn_id, text, is_final)

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
            language="ar-EG",
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

    def _accept_event(self, turn_id: int, text: str, is_final: bool) -> None:
        if turn_id != self._active_turn_id:
            return
        normalized = " ".join(text.split())
        if not normalized:
            return
        event = TranscriptEvent(
            text=normalized,
            is_final=is_final,
            language="ar-EG",
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


__all__ = ["TurnTranscriptBuffer"]

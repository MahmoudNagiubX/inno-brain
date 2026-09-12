import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryTurn:
    user_text: str
    assistant_text: str
    entities: tuple[str, ...]
    committed_at_monotonic: float


class SessionMemory:
    """Bounded in-memory context; it never serializes provider credentials or turns."""

    def __init__(
        self,
        *,
        max_turns: int = 10,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be positive")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._turns: list[MemoryTurn] = []
        self._language_style = "ar-EG"

    def add_turn(
        self,
        user_text: str,
        assistant_text: str,
        entities: Iterable[str] = (),
        *,
        committed: bool = True,
        committed_at_monotonic: float | None = None,
    ) -> bool:
        """Commit a fully delivered response; return false for an interrupted draft."""

        if not committed:
            return False
        timestamp = self._clock() if committed_at_monotonic is None else committed_at_monotonic
        self.expire_if_idle(now=timestamp)
        unique_entities = tuple(dict.fromkeys(str(entity) for entity in entities))
        self._turns.append(
            MemoryTurn(
                user_text=user_text,
                assistant_text=assistant_text,
                entities=unique_entities,
                committed_at_monotonic=timestamp,
            )
        )
        del self._turns[:-self.max_turns]
        return True

    def recent_turns(
        self,
        limit: int | None = None,
        *,
        now: float | None = None,
    ) -> tuple[MemoryTurn, ...]:
        self.expire_if_idle(now=now)
        if limit is None:
            return tuple(self._turns)
        if limit < 1:
            return ()
        return tuple(self._turns[-limit:])

    def active_entities(self, *, now: float | None = None) -> tuple[str, ...]:
        entities: list[str] = []
        for turn in self.recent_turns(now=now):
            for entity in turn.entities:
                if entity not in entities:
                    entities.append(entity)
        return tuple(entities)

    def set_language_style(self, language_style: str) -> None:
        self._language_style = language_style

    @property
    def language_style(self) -> str:
        return self._language_style

    def reset(self) -> None:
        self._turns.clear()
        self._language_style = "ar-EG"

    def expire_if_idle(self, *, now: float | None = None) -> bool:
        if not self._turns:
            return False
        current = self._clock() if now is None else now
        if current - self._turns[-1].committed_at_monotonic > self.ttl_seconds:
            self.reset()
            return True
        return False

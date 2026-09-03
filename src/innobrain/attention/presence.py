from enum import StrEnum
from typing import Protocol, runtime_checkable


class PresenceState(StrEnum):
    """Observable physical or visual presence states."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@runtime_checkable
class PresenceSignal(Protocol):
    """Protocol for sensing user physical or visual presence without hardware dependencies."""

    def get_presence_state(self) -> PresenceState | None:
        """Return the current observed presence state, or None if unknown."""
        ...


class DefaultPresenceSignal:
    """Safe default presence implementation returning UNKNOWN / None without hardware calls."""

    def __init__(
        self,
        default_state: PresenceState | None = PresenceState.UNKNOWN,
    ) -> None:
        self._state = default_state

    def get_presence_state(self) -> PresenceState | None:
        return self._state

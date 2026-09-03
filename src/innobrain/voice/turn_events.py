from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter


class TurnEventType(StrEnum):
    USER_TURN_STARTED = "USER_TURN_STARTED"
    USER_TURN_INFERENCE_TRIGGERED = "USER_TURN_INFERENCE_TRIGGERED"
    USER_TURN_STOPPED = "USER_TURN_STOPPED"


@dataclass(frozen=True, slots=True)
class TurnEvent:
    event_type: TurnEventType
    at_monotonic: float
    strategy_name: str
    barge_in: bool = False

    @classmethod
    def now(
        cls,
        event_type: TurnEventType,
        strategy_name: str,
        *,
        barge_in: bool = False,
    ) -> "TurnEvent":
        return cls(
            event_type=event_type,
            at_monotonic=perf_counter(),
            strategy_name=strategy_name,
            barge_in=barge_in,
        )

import json
import logging
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RuntimeFault:
    stage: str
    error_type: str
    message: str
    turn_id: int | None


class RuntimeEventSink(Protocol):
    def fault(self, fault: RuntimeFault) -> None: ...


class LoggingRuntimeEventSink:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("innobrain.runtime")

    def fault(self, fault: RuntimeFault) -> None:
        payload = {"event": "runtime_fault", **asdict(fault)}
        self._logger.error(json.dumps(payload, ensure_ascii=False, sort_keys=True))


__all__ = ["LoggingRuntimeEventSink", "RuntimeEventSink", "RuntimeFault"]

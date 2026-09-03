import json
import logging
from dataclasses import asdict, dataclass
from time import monotonic
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RuntimeFault:
    stage: str
    error_type: str
    message: str
    turn_id: int | None


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    event: str
    turn_id: int | None = None
    conversation_state: str | None = None
    stt_provider: str | None = None
    transcript_final_received: bool | None = None
    event_id: str | None = None
    event_version: str | None = None
    answer_route: str | None = None
    evidence_count: int | None = None
    llm_provider: str | None = None
    tts_provider: str | None = None
    barge_in: bool | None = None
    fault_stage: str | None = None
    timing_marker: str | None = None
    at_monotonic: float | None = None


class RuntimeEventSink(Protocol):
    def fault(self, fault: RuntimeFault) -> None: ...

    def emit(self, observation: RuntimeObservation) -> None: ...


class LoggingRuntimeEventSink:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("innobrain.runtime")

    def fault(self, fault: RuntimeFault) -> None:
        payload = {
            "event": "runtime_fault",
            "stage": fault.stage,
            "error_type": fault.error_type,
            "turn_id": fault.turn_id,
        }
        self._logger.error(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def emit(self, observation: RuntimeObservation) -> None:
        values = asdict(observation)
        if values["at_monotonic"] is None:
            values["at_monotonic"] = monotonic()
        payload = {key: value for key, value in values.items() if value is not None}
        self._logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))


__all__ = [
    "LoggingRuntimeEventSink",
    "RuntimeEventSink",
    "RuntimeFault",
    "RuntimeObservation",
]

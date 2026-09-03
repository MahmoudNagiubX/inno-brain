import json
import logging

from innobrain.telemetry.runtime_events import LoggingRuntimeEventSink, RuntimeFault


def test_runtime_fault_is_structured_and_logging_sink_omits_transcript(caplog) -> None:
    fault = RuntimeFault(
        stage="tts",
        error_type="RuntimeError",
        message="synthesis failed",
        turn_id=4,
    )
    sink = LoggingRuntimeEventSink(logging.getLogger("innobrain.test.runtime"))

    with caplog.at_level(logging.ERROR, logger="innobrain.test.runtime"):
        sink.fault(fault)

    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "error_type": "RuntimeError",
        "event": "runtime_fault",
        "stage": "tts",
        "turn_id": 4,
    }
    assert "transcript" not in payload

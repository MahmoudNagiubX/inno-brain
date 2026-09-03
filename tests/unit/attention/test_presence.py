from innobrain.attention.presence import (
    DefaultPresenceSignal,
    PresenceSignal,
    PresenceState,
)


def test_presence_states() -> None:
    assert PresenceState.PRESENT == "present"
    assert PresenceState.ABSENT == "absent"
    assert PresenceState.UNKNOWN == "unknown"


def test_default_presence_signal() -> None:
    signal = DefaultPresenceSignal()
    assert isinstance(signal, PresenceSignal)
    assert signal.get_presence_state() == PresenceState.UNKNOWN


def test_default_presence_signal_custom_or_none() -> None:
    signal_none = DefaultPresenceSignal(default_state=None)
    assert signal_none.get_presence_state() is None

    signal_present = DefaultPresenceSignal(default_state=PresenceState.PRESENT)
    assert signal_present.get_presence_state() == PresenceState.PRESENT


def test_custom_presence_signal_conformance() -> None:
    class MockPresenceSensor:
        def __init__(self, state: PresenceState) -> None:
            self.state = state

        def get_presence_state(self) -> PresenceState | None:
            return self.state

    sensor = MockPresenceSensor(PresenceState.PRESENT)
    assert isinstance(sensor, PresenceSignal)
    assert sensor.get_presence_state() == PresenceState.PRESENT

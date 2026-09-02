from types import SimpleNamespace

from innobrain.audio import AudioDevice, get_default_device_indices, normalize_devices


def test_normalize_devices_exposes_capture_and_playback_capabilities() -> None:
    devices = normalize_devices(
        [
            {
                "name": "Laptop microphone",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48000,
            },
            {
                "name": "Laptop speakers",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            },
        ]
    )

    assert devices == [
        AudioDevice(0, "Laptop microphone", 2, 0, 48000.0),
        AudioDevice(1, "Laptop speakers", 0, 2, 44100.0),
    ]
    assert devices[0].can_capture is True
    assert devices[0].can_playback is False
    assert devices[1].can_capture is False
    assert devices[1].can_playback is True


def test_default_device_indices_normalize_missing_defaults(monkeypatch) -> None:
    from innobrain.audio import devices

    monkeypatch.setattr(devices.sd, "default", SimpleNamespace(device=(-1, 4)))

    assert get_default_device_indices() == (None, 4)

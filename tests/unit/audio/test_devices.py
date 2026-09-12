from types import SimpleNamespace

import pytest

from innobrain.audio import (
    AudioDevice,
    AudioDeviceAmbiguityError,
    AudioDeviceCapabilityError,
    AudioDeviceDescriptor,
    AudioDeviceNotFoundError,
    diagnose_audio_devices,
    get_default_device_indices,
    normalize_devices,
    resolve_audio_device,
    resolve_audio_devices,
)
from innobrain.config.models import AudioRuntimeConfig


def _s330_test_devices() -> list[AudioDevice]:
    """Synthetic inventory reproducing duplicate S330 names across multiple Windows host APIs."""
    raw_devices = [
        {
            "name": "Microsoft Sound Mapper - Input",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
            "host_api_name": "MME",
        },
        {
            "name": "Anker PowerConf S330 (2- USB Audio)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 16000.0,
            "host_api_name": "MME",
        },
        {
            "name": "Microphone Array (Realtek Audio)",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "host_api_name": "MME",
        },
        {
            "name": "Microsoft Sound Mapper - Output",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 44100.0,
            "host_api_name": "MME",
        },
        {
            "name": "Speakers (Realtek Audio)",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
            "host_api_name": "MME",
        },
        {
            "name": "Speakers (Anker PowerConf S330)",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
            "host_api_name": "MME",
        },
        {
            "name": "Anker PowerConf S330 (2- USB Audio)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "host_api_name": "Windows DirectSound",
        },
        {
            "name": "Speakers (Anker PowerConf S330)",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
            "host_api_name": "Windows DirectSound",
        },
        {
            "name": "Anker PowerConf S330 (2- USB Audio)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "host_api_name": "Windows WASAPI",
        },
        {
            "name": "Speakers (Anker PowerConf S330)",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
            "host_api_name": "Windows WASAPI",
        },
        {
            "name": "Anker PowerConf S330 (2- USB Audio)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "host_api_name": "Windows WDM-KS",
        },
        {
            "name": "Speakers (Anker PowerConf S330)",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
            "host_api_name": "Windows WDM-KS",
        },
    ]
    return normalize_devices(raw_devices)


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


def test_duplicate_s330_names_resolves_deterministically_with_host_api() -> None:
    devices = _s330_test_devices()
    noop_check = lambda **kwargs: None  # noqa: E731

    # Resolve S330 on MME
    desc_mme = AudioDeviceDescriptor(
        name_pattern="Anker PowerConf S330",
        host_api="MME",
        direction="capture",
    )
    res_mme = resolve_audio_device(
        desc_mme,
        direction="capture",
        devices=devices,
        check_func=noop_check,
    )
    assert res_mme.device_index == 1
    assert res_mme.host_api_name == "MME"

    # Resolve S330 on WASAPI
    desc_wasapi = AudioDeviceDescriptor(
        name_pattern="Anker PowerConf S330",
        host_api="Windows WASAPI",
        direction="capture",
    )
    res_wasapi = resolve_audio_device(
        desc_wasapi,
        direction="capture",
        devices=devices,
        check_func=noop_check,
    )
    assert res_wasapi.device_index == 8
    assert res_wasapi.host_api_name == "Windows WASAPI"


def test_duplicate_s330_names_without_host_api_raises_ambiguity_error() -> None:
    devices = _s330_test_devices()
    desc_ambiguous = AudioDeviceDescriptor(
        name_pattern="Anker PowerConf S330",
        direction="capture",
    )

    with pytest.raises(AudioDeviceAmbiguityError) as exc_info:
        resolve_audio_device(
            desc_ambiguous,
            direction="capture",
            devices=devices,
            check_capability=False,
        )

    err_msg = str(exc_info.value)
    assert "Ambiguous audio capture device" in err_msg
    assert "MME" in err_msg
    assert "Windows DirectSound" in err_msg
    assert "Specify 'host_api' in descriptor" in err_msg


def test_changing_numeric_indexes_preserves_selection_without_hardcoded_indexes() -> None:
    noop_check = lambda **kwargs: None  # noqa: E731
    desc = AudioDeviceDescriptor(name_pattern="Anker PowerConf S330", host_api="MME")

    # Run 1: Devices enumerated at indices 1 (capture) and 5 (playback)
    devices_run1 = _s330_test_devices()
    res1_in = resolve_audio_device(
        desc, direction="capture", devices=devices_run1, check_func=noop_check
    )
    res1_out = resolve_audio_device(
        desc, direction="playback", devices=devices_run1, check_func=noop_check
    )
    assert res1_in.device_index == 1
    assert res1_out.device_index == 5

    # Run 2: OS renumbers indices, shifting all devices by +10
    devices_run2 = [
        AudioDevice(
            index=d.index + 10,
            name=d.name,
            max_input_channels=d.max_input_channels,
            max_output_channels=d.max_output_channels,
            default_sample_rate=d.default_sample_rate,
            host_api_name=d.host_api_name,
            host_api_index=d.host_api_index,
        )
        for d in devices_run1
    ]

    res2_in = resolve_audio_device(
        desc, direction="capture", devices=devices_run2, check_func=noop_check
    )
    res2_out = resolve_audio_device(
        desc, direction="playback", devices=devices_run2, check_func=noop_check
    )
    assert res2_in.device_index == 11
    assert res2_out.device_index == 15
    # No index was hardcoded; both resolved purely through name and host_api properties
    assert res2_in.host_api_name == "MME"
    assert res2_out.host_api_name == "MME"


def test_capability_check_pass_and_fail() -> None:
    devices = _s330_test_devices()
    desc = AudioDeviceDescriptor(name_pattern="Anker PowerConf S330", host_api="MME")

    # Pass capability check
    recorded_calls = []

    def passing_check(**kwargs):
        recorded_calls.append(kwargs)

    res = resolve_audio_device(
        desc,
        direction="capture",
        sample_rate_hz=16000,
        channels=1,
        sample_format="int16",
        devices=devices,
        check_func=passing_check,
    )
    assert res.device_index == 1
    assert recorded_calls == [
        {"device": 1, "samplerate": 16000, "channels": 1, "dtype": "int16"}
    ]

    # Fail capability check (e.g. unsupported sample rate or format)
    def failing_check(**kwargs):
        raise RuntimeError("Invalid sample rate: 16000 not supported by driver")

    with pytest.raises(AudioDeviceCapabilityError) as exc_info:
        resolve_audio_device(
            desc,
            direction="capture",
            sample_rate_hz=16000,
            channels=1,
            sample_format="int16",
            devices=devices,
            check_func=failing_check,
        )

    err_msg = str(exc_info.value)
    assert "does not support capture format" in err_msg
    assert "Invalid sample rate" in err_msg


def test_no_match_raises_not_found_with_diagnostic_devices() -> None:
    devices = _s330_test_devices()

    # Case 1: Pattern does not match any device
    desc_missing = AudioDeviceDescriptor(name_pattern="NonExistentMicrophone")
    with pytest.raises(AudioDeviceNotFoundError) as exc_info:
        resolve_audio_device(
            desc_missing,
            direction="capture",
            devices=devices,
            check_capability=False,
        )
    assert "No matching audio capture device found for pattern 'NonExistentMicrophone'" in str(
        exc_info.value
    )

    # Case 2: Pattern matches device, but requested host_api does not match
    desc_wrong_api = AudioDeviceDescriptor(
        name_pattern="Anker PowerConf S330",
        host_api="ASIO",
    )
    with pytest.raises(AudioDeviceNotFoundError) as exc_info:
        resolve_audio_device(
            desc_wrong_api,
            direction="capture",
            devices=devices,
            check_capability=False,
        )
    err_msg = str(exc_info.value)
    assert "not on requested host API 'ASIO'" in err_msg
    assert "Matching devices exist on host APIs" in err_msg


def test_coordinated_both_input_and_output_resolution() -> None:
    devices = _s330_test_devices()
    noop_check = lambda **kwargs: None  # noqa: E731

    config = AudioRuntimeConfig(
        input_device=AudioDeviceDescriptor(
            name_pattern="Anker PowerConf S330",
            host_api="MME",
        ),
        # output_device specifies name pattern but leaves host_api to coordinate with input
        output_device=AudioDeviceDescriptor(
            name_pattern="Anker PowerConf S330",
        ),
        target_sample_rate_hz=16000,
        channels=1,
    )

    res_in, res_out = resolve_audio_devices(
        config,
        devices=devices,
        check_input_func=noop_check,
        check_output_func=noop_check,
    )

    assert res_in is not None
    assert res_out is not None
    assert res_in.device_index == 1
    assert res_out.device_index == 5
    # Full-duplex pairing: both streams matched to the same host API family
    assert res_in.host_api_name == "MME"
    assert res_out.host_api_name == "MME"


def test_audio_device_descriptor_field_aliases_and_validation() -> None:
    # Validation alias "name" for "name_pattern"
    d1 = AudioDeviceDescriptor(name="S330", hostapi="MME")
    assert d1.name_pattern == "S330"
    assert d1.name == "S330"
    assert d1.host_api == "MME"

    # Direction normalization from "input" -> "capture", "output" -> "playback"
    d_in = AudioDeviceDescriptor.model_validate({"mode": "input", "name": "mic"})
    assert d_in.direction == "capture"

    d_out = AudioDeviceDescriptor.model_validate({"direction": "output", "name": "spk"})
    assert d_out.direction == "playback"


def test_diagnose_audio_devices_produces_safe_data_without_persisting_indexes() -> None:
    devices = _s330_test_devices()
    host_apis = [{"name": "MME"}, {"name": "Windows WASAPI"}]

    config = AudioRuntimeConfig(
        input_device=AudioDeviceDescriptor(
            name_pattern="Anker PowerConf S330",
            host_api="MME",
        ),
        output_device=AudioDeviceDescriptor(
            name_pattern="Anker PowerConf S330",
            host_api="MME",
        ),
    )

    diag = diagnose_audio_devices(
        config,
        devices=devices,
        host_apis=host_apis,
        default_indices=(1, 4),
    )

    assert diag["enumerated"] is True
    assert diag["device_count"] == len(devices)
    assert diag["host_apis"] == ["MME", "Windows WASAPI"]
    assert diag["full_duplex_host_api_match"] is True

    # Check input and output diagnostics
    input_diag = diag["input"]
    assert input_diag["matched"] is True
    assert "S330" in input_diag["device_name"]
    assert input_diag["host_api"] == "MME"
    assert input_diag["capability_supported"] is True
    assert "device_index" not in input_diag  # No index persisted in diagnostic output

    output_diag = diag["output"]
    assert output_diag["matched"] is True
    assert "S330" in output_diag["device_name"]
    assert output_diag["host_api"] == "MME"
    assert output_diag["capability_supported"] is True
    assert "device_index" not in output_diag

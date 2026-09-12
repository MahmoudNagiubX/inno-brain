from pathlib import Path

from innobrain.audio.models import AudioDevice
from innobrain.cli import build_parser, main, offline_check


def test_parser_exposes_check_and_run() -> None:
    assert build_parser().parse_args(["check"]).command == "check"
    assert build_parser().parse_args(["run"]).command == "run"


def test_check_is_offline_and_reports_names_only(monkeypatch, capsys) -> None:
    def missing_assets(**kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("innobrain.cli.resolve_e5_assets", missing_assets)
    monkeypatch.setattr("innobrain.cli.list_audio_devices", lambda: [])
    monkeypatch.setattr("innobrain.cli.get_default_device_indices", lambda: (None, None))
    environment = {"SPEECHMATICS_API_KEY": "top-secret-value"}

    result = offline_check(Path.cwd(), environment=environment)
    code = main(["check"], root=Path.cwd(), environment=environment)
    output = capsys.readouterr().out

    assert result["network_calls_made"] is False
    assert result["audio_stream_started"] is False
    assert code == 0
    assert "SPEECHMATICS_API_KEY" not in output
    assert "top-secret-value" not in output


def test_check_reports_safe_audio_diagnostics_without_secrets_or_persisted_indexes(
    monkeypatch, capsys
) -> None:
    fake_devices = [
        AudioDevice(0, "Mock Input", 1, 0, 16000.0, "MME", 0),
        AudioDevice(1, "Mock Output", 0, 2, 16000.0, "MME", 0),
    ]
    monkeypatch.setattr("innobrain.cli.list_audio_devices", lambda: fake_devices)
    monkeypatch.setattr("innobrain.cli.get_default_device_indices", lambda: (0, 1))
    monkeypatch.setattr("innobrain.cli.list_host_apis", lambda: [{"name": "MME"}])
    def missing_e5(**kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("innobrain.cli.resolve_e5_assets", missing_e5)
    monkeypatch.setattr(
        "innobrain.audio.devices.validate_device_format",
        lambda *args, **kwargs: None,
    )

    secret_env = {"SPEECHMATICS_API_KEY": "my-secret-key-123"}
    result = offline_check(Path.cwd(), environment=secret_env)
    code = main(["check"], root=Path.cwd(), environment=secret_env)
    output = capsys.readouterr().out

    assert code == 0
    assert "my-secret-key-123" not in output
    audio_info = result["audio"]
    assert audio_info["enumerated"] is True
    assert audio_info["device_count"] == 2
    assert audio_info["host_apis"] == ["MME"]
    assert audio_info["software_aec_enabled"] is False
    assert audio_info["software_ns_enabled"] is False
    # Diagnostic input/output report capability without persisting numeric index in descriptor
    assert audio_info["input"] is not None
    assert audio_info["output"] is not None


def test_run_refuses_missing_credentials_before_audio(monkeypatch, capsys) -> None:
    audio_calls = []
    monkeypatch.setattr(
        "innobrain.audio.stream.SoundDevicePCMStream.start",
        lambda self: audio_calls.append(True),
    )

    code = main(["run"], root=Path.cwd(), environment={})
    output = capsys.readouterr().out

    assert code == 2
    assert "SPEECHMATICS_API_KEY" in output
    assert audio_calls == []

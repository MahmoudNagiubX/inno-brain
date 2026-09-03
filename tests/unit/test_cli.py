from pathlib import Path

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

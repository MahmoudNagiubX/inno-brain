import json
from pathlib import Path
from types import MappingProxyType

from innobrain.cli import build_parser, main, offline_check, offline_wake_check

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_cli_parser_accepts_wake_check() -> None:
    parser = build_parser()
    args = parser.parse_args(["wake-check"])
    assert args.command == "wake-check"

    args_check = parser.parse_args(["check"])
    assert args_check.command == "check"

    args_run = parser.parse_args(["run"])
    assert args_run.command == "run"


def test_offline_wake_check_reports_local_status_without_network_or_stream() -> None:
    result = offline_wake_check(REPOSITORY_ROOT)

    assert "status" in result
    assert result["status"] in ("data_pending", "ready", "bypassed")
    assert "phrase" in result
    assert "Heyino" in str(result["phrase"])
    assert result["canonical_label"] == "heyino"
    assert result["network_calls_made"] is False
    assert result["audio_stream_started"] is False

    # Attention parameters reported
    att = result["attention"]
    assert att["followup_window_ms"] == 4500.0
    assert att["followup_window_cap_ms"] == 8000.0
    assert att["max_session_duration_seconds"] == 120.0
    assert att["rejected_background_limit"] == 1

    # Candidate engines inspected
    candidates = result["candidate_engines"]
    assert "openwakeword" in candidates
    assert "porcupine" in candidates


def test_offline_wake_check_never_exposes_secrets() -> None:
    secret_key = "secret_porcupine_key_999"
    env = {"PORCUPINE_ACCESS_KEY": secret_key}

    result = offline_wake_check(REPOSITORY_ROOT, environment=env)
    serialized = json.dumps(result)

    # Secret string must NEVER appear anywhere in the output
    assert secret_key not in serialized
    # Only boolean presence is reported
    assert result["candidate_engines"]["porcupine"]["access_key_configured"] is True


def test_offline_check_includes_wake_and_attention_status() -> None:
    result = offline_check(REPOSITORY_ROOT)

    assert "wake" in result
    assert "attention" in result
    assert result["wake"]["canonical_label"] == "heyino"
    assert "phrase" in result["wake"]
    assert "status" in result["wake"]
    assert result["attention"]["followup_window_ms"] == 4500.0


def test_cli_main_wake_check_executes_and_exits_zero(capsys) -> None:
    exit_code = main(["wake-check"], root=REPOSITORY_ROOT)
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "status" in data
    assert data["network_calls_made"] is False
    assert data["audio_stream_started"] is False


def test_cli_env_file_fills_private_copy_without_mutating_mapping(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "FROM_FILE=file-value\nEXPLICIT=from-file\n",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_wake_check(root: Path, *, environment=None):
        captured.update(environment or {})
        return {
            "status": "data_pending",
            "network_calls_made": False,
            "audio_stream_started": False,
        }

    monkeypatch.setattr("innobrain.cli.offline_wake_check", fake_wake_check)
    source = MappingProxyType({"EXPLICIT": "from-caller"})

    assert main(["wake-check"], root=tmp_path, environment=source) == 0
    assert captured["FROM_FILE"] == "file-value"
    assert captured["EXPLICIT"] == "from-caller"

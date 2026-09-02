import importlib.util
from pathlib import Path


def _load_eventctl():
    path = Path(__file__).resolve().parents[3] / "scripts" / "phase4" / "eventctl.py"
    spec = importlib.util.spec_from_file_location("phase4_eventctl", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_help_does_not_import_docling() -> None:
    module = _load_eventctl()
    parser = module.build_parser()
    assert parser.prog == "eventctl"
    assert {action.dest for action in parser._subparsers._group_actions} == {"command"}
    commands = next(iter(parser._subparsers._group_actions)).choices
    assert set(commands) == {
        "build",
        "validate",
        "install",
        "list",
        "status",
        "activate",
        "rollback",
        "fetch",
    }


def test_build_reports_isolated_builder_setup_when_docling_is_missing(monkeypatch, capsys) -> None:
    module = _load_eventctl()
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: None)
    args = module.build_parser().parse_args(
        ["build", "--source", "source", "--output", "out.innoevent"]
    )
    assert module._build(args) == 2
    assert ".venv-event-builder" in capsys.readouterr().err

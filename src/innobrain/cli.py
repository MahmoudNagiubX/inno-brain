import argparse
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from innobrain.audio.devices import get_default_device_indices, list_audio_devices
from innobrain.config.loader import load_all_configs
from innobrain.event.activation import ActivationManager
from innobrain.event.registry import EventRegistry
from innobrain.knowledge.embedding_assets import resolve_e5_assets
from innobrain.providers.errors import MissingProviderCredential
from innobrain.providers.registry import ProviderRegistry, build_provider_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m innobrain")
    parser.add_argument("command", choices=("check", "run"))
    return parser


def _active_event(root: Path, data_root: str) -> dict[str, str] | None:
    path = Path(data_root)
    if not path.is_absolute():
        path = root / path
    registry = EventRegistry(path)
    record = ActivationManager(path, registry).active()
    if record is None:
        return None
    return {"event_id": record.event_id, "event_version": record.event_version}


def offline_check(
    root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    env = os.environ if environment is None else environment
    config = load_all_configs(root)
    credentials = {
        item.name: item.configured
        for item in ProviderRegistry(env).availability()
    }
    try:
        assets = resolve_e5_assets(download=False)
        e5_assets = assets.model_path.is_file() and assets.tokenizer_path.is_file()
    except Exception:
        e5_assets = False
    try:
        devices = list_audio_devices()
        defaults = get_default_device_indices()
        audio = {
            "enumerated": True,
            "device_count": len(devices),
            "default_input": defaults[0],
            "default_output": defaults[1],
        }
    except Exception as exc:
        audio = {"enumerated": False, "error_type": type(exc).__name__}
    active = _active_event(root, config.runtime.events.data_root)
    graph_ready = active is not None and e5_assets and all(credentials.values())
    return {
        "status": "ready" if graph_ready else "not_ready",
        "active_event": active,
        "provider_credentials": credentials,
        "e5_assets_present": e5_assets,
        "audio": audio,
        "graph_constructable": graph_ready,
        "network_calls_made": False,
        "audio_stream_started": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    root: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path.cwd() if root is None else root
    if args.command == "check":
        print(json.dumps(offline_check(project_root, environment=environment), sort_keys=True))
        return 0

    config = load_all_configs(project_root)
    try:
        build_provider_bundle(config, environment=environment)
    except MissingProviderCredential as exc:
        print(f"startup refused: {exc}")
        return 2
    print("startup refused: Gate 5C remains blocked pending independent re-review")
    return 2


__all__ = ["build_parser", "main", "offline_check"]

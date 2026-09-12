import argparse
import asyncio
import importlib.util
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from innobrain.audio.devices import (
    diagnose_audio_devices,
    get_default_device_indices,
    list_audio_devices,
    list_host_apis,
)
from innobrain.config.loader import load_all_configs, load_env_file
from innobrain.event.activation import ActivationManager
from innobrain.event.registry import EventRegistry
from innobrain.knowledge.embedding_assets import resolve_e5_assets
from innobrain.providers.errors import MissingProviderCredential
from innobrain.providers.registry import ProviderRegistry, build_provider_bundle
from innobrain.wake.contracts import WakeOperatingMode, WakeStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m innobrain")
    parser.add_argument("command", choices=("check", "wake-check", "run"))
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


def offline_wake_check(
    root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Inspect local wake and attention configuration, models, and dependencies offline."""
    env = os.environ if environment is None else environment
    config = load_all_configs(root)
    wake_cfg = config.runtime.wake_word
    att_cfg = config.runtime.attention

    candidates: dict[str, dict[str, object]] = {}
    for engine_name, meta in wake_cfg.candidate_engines.items():
        model_path = meta.model_path
        model_file = (
            (root / model_path)
            if model_path and not Path(model_path).is_absolute()
            else (Path(model_path) if model_path else None)
        )
        model_present = model_file.is_file() if model_file is not None else False

        info: dict[str, object] = {
            "model_path": model_path,
            "model_present": model_present,
            "frame_length_samples": meta.frame_length_samples,
            "threshold": meta.threshold,
        }
        if engine_name == "openwakeword":
            dep_installed = importlib.util.find_spec("openwakeword") is not None
            info["dependency_installed"] = dep_installed
            ready = dep_installed and model_present
            info["ready"] = ready
            info["status"] = "ready" if ready else "data_pending"
        elif engine_name == "porcupine":
            dep_installed = importlib.util.find_spec("pvporcupine") is not None
            has_key = bool(env.get("PORCUPINE_ACCESS_KEY") or env.get("PICOVOICE_ACCESS_KEY"))
            info["dependency_installed"] = dep_installed
            info["access_key_configured"] = has_key
            ready = dep_installed and model_present and has_key
            info["ready"] = ready
            info["status"] = "ready" if ready else "data_pending"
        else:
            info["ready"] = model_present
            info["status"] = "ready" if model_present else "data_pending"
        candidates[engine_name] = info

    active_candidate = candidates.get(wake_cfg.engine_type, {})
    active_ready = active_candidate.get("ready", False)
    operating_mode = WakeOperatingMode(wake_cfg.operating_mode)
    if operating_mode is WakeOperatingMode.DEVELOPMENT_BYPASS:
        status = WakeStatus.BYPASSED.value
    elif active_ready:
        status = WakeStatus.READY.value
    else:
        status = WakeStatus.DATA_PENDING.value

    attention_info = {
        "followup_window_ms": att_cfg.followup_window_ms,
        "followup_window_cap_ms": att_cfg.followup_window_cap_ms,
        "max_session_duration_seconds": att_cfg.max_session_duration_seconds,
        "rejected_background_limit": att_cfg.rejected_background_limit,
        "wake_cooldown_seconds": att_cfg.wake_cooldown_seconds,
    }

    return {
        "status": status,
        "operating_mode": operating_mode.value,
        "phrase": wake_cfg.phrase,
        "canonical_label": wake_cfg.canonical_label,
        "enabled": wake_cfg.enabled,
        "engine_type": wake_cfg.engine_type,
        "active_engine_ready": active_ready,
        "threshold": wake_cfg.threshold,
        "cooldown_seconds": wake_cfg.cooldown_seconds,
        "candidate_engines": candidates,
        "attention": attention_info,
        "network_calls_made": False,
        "audio_stream_started": False,
    }


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
    provider_health = ProviderRegistry(env).capability_health(config)
    try:
        assets = resolve_e5_assets(download=False)
        e5_assets = assets.model_path.is_file() and assets.tokenizer_path.is_file()
    except Exception:
        e5_assets = False
    try:
        devices = list_audio_devices()
        defaults = get_default_device_indices()
        host_apis = list_host_apis()
        audio_diag = diagnose_audio_devices(
            config.runtime.audio,
            devices=devices,
            host_apis=host_apis,
            default_indices=defaults,
        )
        audio = {
            "enumerated": True,
            "device_count": len(devices),
            "default_input": defaults[0],
            "default_output": defaults[1],
            "host_apis": audio_diag.get("host_apis", []),
            "input": audio_diag.get("input"),
            "output": audio_diag.get("output"),
            "full_duplex_host_api_match": audio_diag.get("full_duplex_host_api_match"),
            "software_aec_enabled": config.runtime.audio.software_aec_enabled,
            "software_ns_enabled": config.runtime.audio.software_ns_enabled,
        }
    except Exception as exc:
        audio = {"enumerated": False, "error_type": type(exc).__name__}
    active = _active_event(root, config.runtime.events.data_root)
    graph_ready = active is not None and e5_assets and provider_health.stt_available

    wake_check_res = offline_wake_check(root, environment=environment)

    return {
        "status": "ready" if graph_ready else "not_ready",
        "active_event": active,
        "provider_credentials": credentials,
        "provider_capabilities": provider_health.to_dict(),
        "e5_assets_present": e5_assets,
        "audio": audio,
        "wake": {
            "status": wake_check_res["status"],
            "engine_type": wake_check_res["engine_type"],
            "phrase": wake_check_res["phrase"],
            "canonical_label": wake_check_res["canonical_label"],
            "active_engine_ready": wake_check_res["active_engine_ready"],
        },
        "attention": {
            "followup_window_ms": config.runtime.attention.followup_window_ms,
            "max_session_duration_seconds": config.runtime.attention.max_session_duration_seconds,
            "rejected_background_limit": config.runtime.attention.rejected_background_limit,
        },
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

    # Merge .env into a private mapping. Explicit process/test values win and
    # caller-provided mappings are never mutated.
    effective_environment = dict(os.environ if environment is None else environment)
    load_env_file(project_root / ".env", target_env=effective_environment)

    if args.command == "check":
        print(
            json.dumps(
                offline_check(project_root, environment=effective_environment),
                sort_keys=True,
            )
        )
        return 0

    if args.command == "wake-check":
        print(
            json.dumps(
                offline_wake_check(project_root, environment=effective_environment),
                sort_keys=True,
            )
        )
        return 0

    config = load_all_configs(project_root)
    try:
        providers = build_provider_bundle(config, environment=effective_environment)
    except MissingProviderCredential as exc:
        print(f"startup refused: {exc}")
        return 2

    from innobrain.app import build_application

    async def run_application() -> None:
        app = build_application(
            config=config,
            provider_bundle=providers,
            environment=effective_environment,
        )
        try:
            await app.start()
            print("InnoBrain running; press Ctrl+C to stop")
            await asyncio.Event().wait()
        finally:
            await app.stop()

    try:
        asyncio.run(run_application())
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"startup failed: {type(exc).__name__}: {exc}")
        return 2
    return 0


__all__ = ["build_parser", "main", "offline_check", "offline_wake_check"]

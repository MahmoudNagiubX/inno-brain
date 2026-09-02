"""Real builder/runtime smoke; exits deferred when local production assets are absent."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from innobrain.conversation.memory import SessionMemory
from innobrain.event.activation import ActivationManager
from innobrain.event.builder import build_event_package
from innobrain.event.installer import install_event_package
from innobrain.event.registry import EventRegistry
from innobrain.event.runtime import RuntimeContextSwitcher
from innobrain.event.validation import PackageVerificationPolicy, verify_event_package
from innobrain.knowledge.e5_onnx import MultilingualE5OnnxProvider
from innobrain.knowledge.embedding_assets import resolve_e5_assets

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


async def run_smoke(cache_dir: Path, data_root: Path, output_dir: Path) -> dict[str, object]:
    if importlib.util.find_spec("docling") is None:
        return {
            "status": "deferred",
            "reason": "docling==2.124.0 is not installed in builder environment",
        }
    try:
        assets = resolve_e5_assets(cache_dir=cache_dir, download=False)
    except Exception as exc:  # noqa: BLE001 - smoke reports deferred asset state.
        return {
            "status": "deferred",
            "reason": f"real E5 assets unavailable: {type(exc).__name__}: {exc}",
        }

    key_dir = output_dir / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    private_key_path = key_dir / "phase4-smoke-test-only.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_id = "phase4-smoke-test-only"
    trusted_keys = {key_id: private_key.public_key()}
    policy = PackageVerificationPolicy(environment="production", trusted_keys=trusted_keys)
    provider = MultilingualE5OnnxProvider(
        model_path=assets.model_path,
        tokenizer_path=assets.tokenizer_path,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = []
    for fixture_name in ("event_alpha", "event_beta"):
        package = output_dir / f"{fixture_name}.innoevent"
        await build_event_package(
            REPOSITORY_ROOT / "fixtures" / "phase4" / fixture_name,
            package,
            embedding_provider=provider,
            tokenizer=provider.tokenizer,
            deployable=True,
            signing_key=private_key_path,
            key_id=key_id,
            cache_dir=cache_dir,
            allow_plaintext_fallback=False,
        )
        verify_event_package(package, policy=policy)
        installed = install_event_package(package, data_root, verification_policy=policy)
        installed.close()
        packages.append(package.name)

    registry = EventRegistry(data_root)
    alpha = registry.get("event-alpha")
    beta = registry.get("event-beta")
    memory = SessionMemory()
    switcher = RuntimeContextSwitcher(memory, embedding_provider=provider)
    manager = ActivationManager(
        data_root, registry, idle_guard=lambda: True, switch_hook=switcher.switch
    )
    manager.activate("event-alpha", build_id=alpha.build_id)
    alpha_lexical = switcher.current.repository.lexical_search("event-alpha", "alpha compass", 5)
    alpha_rag = await switcher.current.retriever.retrieve("alpha compass")
    manager.activate("event-beta", build_id=beta.build_id)
    beta_lexical = switcher.current.repository.lexical_search("event-beta", "beta lantern", 5)
    leak = switcher.current.repository.lexical_search("event-beta", "alpha compass", 5)
    manager.rollback()
    rollback_event = switcher.current.record.event_id
    switcher.close()
    return {
        "status": "passed",
        "packages": packages,
        "alpha_exact_rows": len(alpha_lexical),
        "alpha_rag_rows": len(alpha_rag.evidence),
        "beta_exact_rows": len(beta_lexical),
        "beta_alpha_leak_rows": len(leak),
        "rollback_event": rollback_event,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=REPOSITORY_ROOT / ".builder-cache")
    parser.add_argument(
        "--data-root", type=Path, default=REPOSITORY_ROOT / "runtime_data" / "smoke"
    )
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "artifacts" / "phase4")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            run_smoke(
                args.cache_dir.resolve(), args.data_root.resolve(), args.output_dir.resolve()
            )
        )
    except Exception as exc:  # noqa: BLE001 - smoke reports exact deferred/failure state.
        result = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"passed", "deferred"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

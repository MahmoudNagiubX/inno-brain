import os
import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from .models import PersonaConfig, ProjectConfigs, ProviderCandidatesConfig, RuntimeConfig

T = TypeVar("T", bound=BaseModel)
_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(
    env_path: Path | None = None,
    *,
    target_env: MutableMapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Safely load environment variables from an offline .env file.

    - Reads only for missing variables (does not overwrite existing environment keys).
    - Ignores blank, comment (#), and malformed lines (missing '=').
    - Strips matching single or double quotes around values.
    - Never logs or returns secret values (only returns the tuple of variable names that were set).
    - Preserves explicit process/environment mapping precedence.
    """
    path = Path(".env") if env_path is None else env_path
    if not path.is_file():
        return ()

    target = os.environ if target_env is None else target_env
    loaded_keys: list[str] = []

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return ()

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if not key or _ENV_KEY_PATTERN.fullmatch(key) is None:
            continue
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        if key not in target:
            target[key] = val
            loaded_keys.append(key)

    return tuple(loaded_keys)


def load_yaml_model(path: Path, model_type: type[T]) -> T:
    if not path.is_file():
        raise FileNotFoundError(path)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")

    return model_type.model_validate(raw)


def load_all_configs(root: Path) -> ProjectConfigs:
    config_dir = root / "config"

    return ProjectConfigs(
        runtime=load_yaml_model(config_dir / "runtime.yaml", RuntimeConfig),
        providers=load_yaml_model(
            config_dir / "providers.yaml",
            ProviderCandidatesConfig,
        ),
        persona=load_yaml_model(config_dir / "persona.yaml", PersonaConfig),
    )

from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from .models import PersonaConfig, ProjectConfigs, ProviderCandidatesConfig, RuntimeConfig

T = TypeVar("T", bound=BaseModel)


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

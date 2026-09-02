from pathlib import Path

import pytest
from pydantic import ValidationError

from innobrain.config import RuntimeConfig, load_all_configs, load_yaml_model

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_load_all_configs_uses_egyptian_first_laptop_defaults() -> None:
    configs = load_all_configs(REPOSITORY_ROOT)

    assert configs.runtime.primary_locale == "ar-EG"
    assert configs.runtime.development_platform == "laptop"
    assert configs.runtime.audio.input_device is None
    assert configs.runtime.audio.output_device is None
    assert configs.runtime.audio.software_aec_enabled is False
    assert configs.runtime.audio.software_ns_enabled is False


def test_unknown_runtime_keys_are_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
        app_name: InnoBrain
        environment: development
        primary_locale: ar-EG
        secondary_locale: en
        development_platform: laptop
        unexpected: true
        audio:
          backend: sounddevice
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_yaml_model(config_path, RuntimeConfig)

from pathlib import Path

import pytest
from pydantic import ValidationError

from innobrain.config import RuntimeConfig, load_all_configs, load_yaml_model

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_load_all_configs_uses_egyptian_first_s330_windows_defaults() -> None:
    configs = load_all_configs(REPOSITORY_ROOT)

    assert configs.runtime.primary_locale == "ar-EG"
    assert configs.runtime.development_platform == "laptop"
    assert configs.runtime.audio.input_device is not None
    assert configs.runtime.audio.input_device.name_pattern == "Anker PowerConf S330"
    assert configs.runtime.audio.input_device.host_api == "MME"
    assert configs.runtime.audio.output_device is not None
    assert configs.runtime.audio.output_device.name_pattern == "Anker PowerConf S330"
    assert configs.runtime.audio.output_device.host_api == "MME"
    assert configs.runtime.audio.software_aec_enabled is False
    assert configs.runtime.audio.software_ns_enabled is False
    assert configs.runtime.realtime.audio_queue_max_chunks == 100
    assert configs.runtime.realtime.vad.confidence == 0.7
    assert configs.runtime.realtime.vad.start_secs == 0.2
    assert configs.runtime.realtime.vad.stop_secs == 0.2
    assert configs.runtime.realtime.vad.min_volume == 0.6
    assert configs.runtime.realtime.smart_turn.enabled is True
    assert configs.runtime.realtime.smart_turn.wait_for_transcript is False
    assert configs.runtime.realtime.smart_turn.cpu_count == 1
    assert configs.runtime.realtime.mock_response_tone_hz == 440.0
    assert configs.runtime.events.data_root == "runtime_data"
    assert configs.runtime.events.require_signature_in_production is True
    assert configs.runtime.events.allow_unsigned_development is False
    assert configs.runtime.events.allow_remote_package_fetch is False
    assert configs.runtime.events.allowed_remote_hosts == []
    assert configs.runtime.events.max_archive_bytes == 536_870_912
    assert configs.runtime.events.max_file_count == 2000
    assert configs.runtime.events.max_uncompressed_bytes == 1_073_741_824
    assert configs.runtime.events.max_single_file_bytes == 268_435_456


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

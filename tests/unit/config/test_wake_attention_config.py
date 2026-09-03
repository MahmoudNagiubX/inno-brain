from pathlib import Path

import pytest
from pydantic import ValidationError

from innobrain.config import load_all_configs
from innobrain.config.models import (
    AttentionRuntimeConfig,
    WakeCandidateMetadata,
    WakeWordRuntimeConfig,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_wake_and_attention_models_defaults() -> None:
    wake_cfg = WakeWordRuntimeConfig()
    assert wake_cfg.enabled is True
    assert "Heyino" in wake_cfg.phrase
    assert "H-E-Y-I-N-N-O" in wake_cfg.phrase
    assert wake_cfg.canonical_label == "heyino"
    assert wake_cfg.engine_type == "openwakeword"
    assert wake_cfg.model_path is None
    assert wake_cfg.threshold == 0.5
    assert wake_cfg.cooldown_seconds == 1.5
    assert "openwakeword" in wake_cfg.candidate_engines
    assert "porcupine" in wake_cfg.candidate_engines
    assert wake_cfg.candidate_engines["openwakeword"].frame_length_samples == 1280
    assert wake_cfg.candidate_engines["porcupine"].frame_length_samples == 512

    att_cfg = AttentionRuntimeConfig()
    assert att_cfg.followup_window_ms == 4500.0
    assert att_cfg.followup_window_cap_ms == 8000.0
    assert att_cfg.max_session_duration_seconds == 120.0
    assert att_cfg.rejected_background_limit == 1
    assert att_cfg.wake_cooldown_seconds == 1.5


def test_runtime_yaml_loads_matching_wake_and_attention_defaults() -> None:
    configs = load_all_configs(REPOSITORY_ROOT)

    wake = configs.runtime.wake_word
    assert wake.enabled is True
    assert "Heyino" in wake.phrase
    assert "H-E-Y-I-N-N-O" in wake.phrase
    assert wake.canonical_label == "heyino"
    assert wake.engine_type == "openwakeword"
    assert wake.threshold == 0.5
    assert (
        wake.candidate_engines["openwakeword"].model_path
        == "models/wake/heyino_openwakeword_v0.onnx"
    )
    assert wake.candidate_engines["porcupine"].model_path == "models/wake/heyino_porcupine.ppn"

    attention = configs.runtime.attention
    assert attention.followup_window_ms == 4500.0
    assert attention.followup_window_cap_ms == 8000.0
    assert attention.max_session_duration_seconds == 120.0
    assert attention.rejected_background_limit == 1
    assert attention.wake_cooldown_seconds == 1.5

    # Realtime VAD and Smart Turn settings are preserved unmodified
    assert configs.runtime.realtime.vad.confidence == 0.7
    assert configs.runtime.realtime.vad.start_secs == 0.2
    assert configs.runtime.realtime.vad.stop_secs == 0.2
    assert configs.runtime.realtime.vad.min_volume == 0.6
    assert configs.runtime.realtime.smart_turn.enabled is True
    assert configs.runtime.realtime.smart_turn.wait_for_transcript is False
    assert configs.runtime.realtime.smart_turn.cpu_count == 1


def test_wake_and_attention_strict_validation() -> None:
    with pytest.raises(ValidationError):
        WakeWordRuntimeConfig(unknown_field="invalid")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        AttentionRuntimeConfig(extra_param=123)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        WakeCandidateMetadata(non_existent="fail")  # type: ignore[call-arg]

    # Negative threshold forbidden
    with pytest.raises(ValidationError):
        WakeWordRuntimeConfig(threshold=-0.1)

    with pytest.raises(ValidationError):
        WakeWordRuntimeConfig(phrase="Other")

    with pytest.raises(ValidationError):
        WakeWordRuntimeConfig(canonical_label="other")

    with pytest.raises(ValidationError):
        WakeWordRuntimeConfig(engine_type="unknown")

    # Negative follow-up window forbidden
    with pytest.raises(ValidationError):
        AttentionRuntimeConfig(followup_window_ms=-100.0)

    # Rejected background limit must be >= 1
    with pytest.raises(ValidationError):
        AttentionRuntimeConfig(rejected_background_limit=0)

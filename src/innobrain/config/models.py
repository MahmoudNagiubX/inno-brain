from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AudioRuntimeConfig(StrictModel):
    backend: Literal["default", "sounddevice"] = "sounddevice"
    input_device: str | int | None = None
    output_device: str | int | None = None
    target_sample_rate_hz: int = Field(default=16000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    frame_ms: int = Field(default=20, ge=10, le=100)
    software_aec_enabled: bool = False
    software_ns_enabled: bool = False


class VADRuntimeConfig(StrictModel):
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    start_secs: float = Field(default=0.2, ge=0.0, le=2.0)
    stop_secs: float = Field(default=0.2, ge=0.0, le=3.0)
    min_volume: float = Field(default=0.6, ge=0.0, le=1.0)


class SmartTurnRuntimeConfig(StrictModel):
    enabled: bool = True
    wait_for_transcript: bool = False
    cpu_count: int = Field(default=1, ge=1, le=8)


class RealtimeRuntimeConfig(StrictModel):
    audio_queue_max_chunks: int = Field(default=100, ge=10, le=1000)
    vad: VADRuntimeConfig
    smart_turn: SmartTurnRuntimeConfig
    mock_think_delay_ms: int = Field(default=150, ge=0, le=2000)
    mock_response_tone_hz: float = Field(default=440.0, ge=100.0, le=2000.0)
    mock_response_duration_secs: float = Field(default=6.0, ge=1.0, le=30.0)
    mock_response_volume: float = Field(default=0.08, ge=0.01, le=0.25)


class RuntimeConfig(StrictModel):
    app_name: str
    environment: Literal["development", "test", "production"]
    primary_locale: str
    secondary_locale: str
    development_platform: Literal["laptop", "raspberry_pi"]
    audio: AudioRuntimeConfig
    realtime: RealtimeRuntimeConfig


class ProviderCandidatesConfig(StrictModel):
    selection_status: Literal["benchmark_pending", "selected"]
    stt_candidates: list[str]
    llm_candidates: list[str]
    tts_candidates: list[str]
    embedding_candidates: list[str]


class PersonaConfig(StrictModel):
    primary_language: str
    dialect: str
    english_priority: Literal["secondary"]
    response_style: Literal["concise_spoken"]
    max_default_sentences: int = Field(default=3, ge=1, le=5)


class ProjectConfigs(StrictModel):
    runtime: RuntimeConfig
    providers: ProviderCandidatesConfig
    persona: PersonaConfig

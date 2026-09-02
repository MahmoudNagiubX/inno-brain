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


class RuntimeConfig(StrictModel):
    app_name: str
    environment: Literal["development", "test", "production"]
    primary_locale: str
    secondary_locale: str
    development_platform: Literal["laptop", "raspberry_pi"]
    audio: AudioRuntimeConfig


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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from innobrain.audio.models import AudioDeviceDescriptor


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AudioRuntimeConfig(StrictModel):
    backend: Literal["default", "sounddevice"] = "sounddevice"
    input_device: AudioDeviceDescriptor | str | int | None = None
    output_device: AudioDeviceDescriptor | str | int | None = None
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


class ConversationRuntimeConfig(StrictModel):
    memory_max_turns: int = Field(default=10, ge=1, le=100)
    memory_ttl_seconds: float = Field(default=300.0, ge=0.0, le=86400.0)


class EventPackageRuntimeConfig(StrictModel):
    data_root: str = "runtime_data"
    require_signature_in_production: bool = True
    allow_unsigned_development: bool = False
    allow_remote_package_fetch: bool = False
    allowed_remote_hosts: list[str] = []
    max_archive_bytes: int = 536_870_912
    max_file_count: int = 2000
    max_uncompressed_bytes: int = 1_073_741_824
    max_single_file_bytes: int = 268_435_456


class WakeCandidateMetadata(StrictModel):
    model_path: str | None = None
    frame_length_samples: int = Field(default=1280, ge=1)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class WakeWordRuntimeConfig(StrictModel):
    enabled: bool = True
    operating_mode: Literal["wake_required", "development_bypass"] = "wake_required"
    phrase: Literal["Heyino/H-E-Y-I-N-N-O"] = "Heyino/H-E-Y-I-N-N-O"
    canonical_label: Literal["heyino"] = "heyino"
    engine_type: Literal["openwakeword", "porcupine", "fake"] = "openwakeword"
    model_path: str | None = None
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=1.5, ge=0.0, le=30.0)
    preroll_ms: int = Field(default=1500, ge=100, le=10000)
    candidate_engines: dict[str, WakeCandidateMetadata] = Field(
        default_factory=lambda: {
            "openwakeword": WakeCandidateMetadata(
                model_path="models/wake/heyino_openwakeword_v0.onnx",
                frame_length_samples=1280,
                threshold=0.5,
            ),
            "porcupine": WakeCandidateMetadata(
                model_path="models/wake/heyino_porcupine.ppn",
                frame_length_samples=512,
                threshold=0.5,
            ),
        }
    )


class AttentionRuntimeConfig(StrictModel):
    followup_window_ms: float = Field(default=4500.0, ge=0.0)
    followup_window_cap_ms: float = Field(default=8000.0, ge=0.0)
    max_session_duration_seconds: float = Field(default=120.0, gt=0.0)
    rejected_background_limit: int = Field(default=1, ge=1)
    wake_cooldown_seconds: float = Field(default=1.5, ge=0.0)


class RuntimeConfig(StrictModel):
    app_name: str
    environment: Literal["development", "test", "production"]
    primary_locale: str
    secondary_locale: str
    development_platform: Literal["laptop", "raspberry_pi"]
    audio: AudioRuntimeConfig
    realtime: RealtimeRuntimeConfig
    conversation: ConversationRuntimeConfig = ConversationRuntimeConfig()
    events: EventPackageRuntimeConfig = EventPackageRuntimeConfig()
    wake_word: WakeWordRuntimeConfig = WakeWordRuntimeConfig()
    attention: AttentionRuntimeConfig = AttentionRuntimeConfig()

    @model_validator(mode="after")
    def reject_production_bypass(self) -> "RuntimeConfig":
        if (
            self.environment == "production"
            and self.wake_word.operating_mode == "development_bypass"
        ):
            raise ValueError("development_bypass wake mode is forbidden in production")
        return self


class SpeechmaticsProviderConfig(StrictModel):
    language: str = "auto"
    endpointing: Literal["external"] = "external"
    api_key_env: str = "SPEECHMATICS_API_KEY"


class DeepgramProviderConfig(StrictModel):
    model: str = "nova-3"
    language: str = "multi"
    api_key_env: str = "DEEPGRAM_API_KEY"
    keyterm_prompting: bool = True


class STTProviderConfig(StrictModel):
    primary: Literal["speechmatics", "deepgram"] = "speechmatics"
    fallback: list[Literal["speechmatics", "deepgram"]] = ["deepgram"]
    speechmatics: SpeechmaticsProviderConfig = SpeechmaticsProviderConfig()
    deepgram: DeepgramProviderConfig = DeepgramProviderConfig()


class GroqProviderConfig(StrictModel):
    model: str = "openai/gpt-oss-120b"
    fallback_model: str = "openai/gpt-oss-20b"
    api_key_env: str = "GROQ_API_KEY"


class LLMProviderConfig(StrictModel):
    primary: Literal["groq"] = "groq"
    groq: GroqProviderConfig = GroqProviderConfig()


class AzureTTSProviderConfig(StrictModel):
    locale: str = "ar-EG"
    voice: str = "ar-EG-ShakirNeural"
    english_locale: str = "en-US"
    english_voice: str = "en-US-JennyNeural"
    sample_rate_hz: int = Field(default=16000, ge=8000, le=48000)
    key_env: str = "AZURE_SPEECH_KEY"
    region_env: str = "AZURE_SPEECH_REGION"


class TTSProviderConfig(StrictModel):
    primary: Literal["azure"] = "azure"
    azure: AzureTTSProviderConfig = AzureTTSProviderConfig()


class EmbeddingProviderConfig(StrictModel):
    provider: Literal["multilingual_e5_onnx"] = "multilingual_e5_onnx"
    model_id: str = "intfloat/multilingual-e5-small"
    revision: str = "614241f"
    dimension: int = Field(default=384, ge=1)
    max_tokens: int = Field(default=512, ge=1)


class RetrievalConfig(StrictModel):
    lexical_top_k: int = Field(default=12, ge=1)
    dense_top_k: int = Field(default=12, ge=1)
    final_top_k: int = Field(default=5, ge=1)
    rrf_k: int = Field(default=60, ge=1)


class ProviderConfig(StrictModel):
    selection_status: Literal["phase3_baseline_selected"]
    stt: STTProviderConfig
    llm: LLMProviderConfig
    tts: TTSProviderConfig
    embedding: EmbeddingProviderConfig
    retrieval: RetrievalConfig


ProviderCandidatesConfig = ProviderConfig


class PersonaConfig(StrictModel):
    primary_language: str
    dialect: str
    english_priority: Literal["secondary"]
    response_style: Literal["concise_spoken"]
    male_voice_required: bool = True
    ground_event_claims_only: bool = True
    max_default_sentences: int = Field(default=3, ge=1, le=5)


class ProjectConfigs(StrictModel):
    runtime: RuntimeConfig
    providers: ProviderConfig
    persona: PersonaConfig

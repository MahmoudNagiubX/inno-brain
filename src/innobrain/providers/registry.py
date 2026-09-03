import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

from innobrain.config.models import ProjectConfigs

from .azure_tts import AzureTTSProvider
from .contracts import LLMProvider, STTProvider, TTSProvider
from .deepgram_stt import DeepgramSTTProvider
from .errors import MissingProviderCredential
from .groq_llm import GroqLLMProvider
from .speechmatics_stt import SpeechmaticsSTTProvider
from .stt_failover import FailoverSTTProvider


@dataclass(frozen=True, slots=True)
class ProviderAvailability:
    name: str
    configured: bool
    reason: str


class ProviderRegistry:
    """Report provider readiness without reading or returning secret values."""

    _PROVIDERS = (
        ("speechmatics", ("SPEECHMATICS_API_KEY",)),
        ("deepgram", ("DEEPGRAM_API_KEY",)),
        ("groq", ("GROQ_API_KEY",)),
        ("azure", ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")),
    )

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self._environment = os.environ if environment is None else environment

    def availability(self) -> tuple[ProviderAvailability, ...]:
        result: list[ProviderAvailability] = []
        for name, required_keys in self._PROVIDERS:
            missing = tuple(key for key in required_keys if not self._environment.get(key))
            if missing:
                result.append(
                    ProviderAvailability(
                        name=name,
                        configured=False,
                        reason=f"missing credential environment variable(s): {', '.join(missing)}",
                    )
                )
            else:
                result.append(ProviderAvailability(name=name, configured=True, reason="configured"))
        return tuple(result)

    def first_available_stt_name(self) -> str | None:
        for availability in self.availability():
            if availability.name in {"speechmatics", "deepgram"} and availability.configured:
                return availability.name
        return None


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    stt: FailoverSTTProvider = field(repr=False)
    llm: LLMProvider = field(repr=False)
    tts: TTSProvider = field(repr=False)


ProviderConstructor = Callable[..., object]


def _required_secret(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not value:
        raise MissingProviderCredential(f"missing credential environment variable: {name}")
    return value


def build_provider_bundle(
    config: ProjectConfigs,
    *,
    environment: Mapping[str, str] | None = None,
    constructors: Mapping[str, ProviderConstructor] | None = None,
) -> ProviderBundle:
    """Construct configured providers without starting them or making network calls."""

    env = os.environ if environment is None else environment
    factories: dict[str, ProviderConstructor] = {
        "speechmatics": SpeechmaticsSTTProvider,
        "deepgram": DeepgramSTTProvider,
        "groq": GroqLLMProvider,
        "azure": AzureTTSProvider,
    }
    if constructors is not None:
        factories.update(constructors)

    stt_order = [config.providers.stt.primary, *config.providers.stt.fallback]
    unique_stt_order = list(dict.fromkeys(stt_order))
    if len(unique_stt_order) < 2:
        raise ValueError("STT configuration requires a distinct primary and fallback")
    stt_secrets: dict[str, str] = {}
    for name in unique_stt_order[:2]:
        if name == "speechmatics":
            settings = config.providers.stt.speechmatics
        else:
            settings = config.providers.stt.deepgram
        stt_secrets[name] = _required_secret(env, settings.api_key_env)

    groq = config.providers.llm.groq
    groq_key = _required_secret(env, groq.api_key_env)
    azure = config.providers.tts.azure
    azure_key = _required_secret(env, azure.key_env)
    azure_region = _required_secret(env, azure.region_env)

    stt_instances: list[STTProvider] = []
    for name in unique_stt_order[:2]:
        kwargs = {"api_key": stt_secrets[name]}
        stt_instances.append(cast(STTProvider, factories[name](**kwargs)))

    llm = cast(
        LLMProvider,
        factories[config.providers.llm.primary](
            api_key=groq_key,
            model=groq.model,
            fallback_model=groq.fallback_model,
        ),
    )
    tts = cast(
        TTSProvider,
        factories[config.providers.tts.primary](
            api_key=azure_key,
            region=azure_region,
            sample_rate_hz=azure.sample_rate_hz,
        ),
    )
    return ProviderBundle(
        stt=FailoverSTTProvider(stt_instances[0], stt_instances[1]),
        llm=llm,
        tts=tts,
    )


__all__ = [
    "ProviderAvailability",
    "ProviderBundle",
    "ProviderRegistry",
    "build_provider_bundle",
]

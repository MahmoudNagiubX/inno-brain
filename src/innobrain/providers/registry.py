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


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Capability state safe to expose in health and CLI diagnostics."""

    selected_stt: str | None = None
    fallback_stt: str | None = None
    stt_available: bool = False
    llm_provider: str | None = None
    llm_available: bool = False
    tts_provider: str | None = None
    tts_available: bool = False

    @property
    def degraded(self) -> bool:
        return not (self.stt_available and self.llm_available and self.tts_available)

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_stt": self.selected_stt,
            "fallback_stt": self.fallback_stt,
            "fallback_available": self.fallback_stt is not None,
            "stt_available": self.stt_available,
            "llm_provider": self.llm_provider,
            "llm_available": self.llm_available,
            "tts_provider": self.tts_provider,
            "tts_available": self.tts_available,
            "degraded": self.degraded,
        }


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

    def capability_health(self, config: ProjectConfigs) -> ProviderHealth:
        stt_order = list(
            dict.fromkeys([config.providers.stt.primary, *config.providers.stt.fallback])
        )
        available_stt = [
            name
            for name in stt_order
            if self._credential_configured(
                name,
                config.providers.stt.speechmatics.api_key_env
                if name == "speechmatics"
                else config.providers.stt.deepgram.api_key_env,
            )
        ]
        llm_configured = self._credential_configured(
            "groq", config.providers.llm.groq.api_key_env
        )
        tts_configured = all(
            self._credential_configured("azure", env_name)
            for env_name in (
                config.providers.tts.azure.key_env,
                config.providers.tts.azure.region_env,
            )
        )
        return ProviderHealth(
            selected_stt=available_stt[0] if available_stt else None,
            fallback_stt=available_stt[1] if len(available_stt) > 1 else None,
            stt_available=bool(available_stt),
            llm_provider="groq" if llm_configured else None,
            llm_available=llm_configured,
            tts_provider="azure" if tts_configured else None,
            tts_available=tts_configured,
        )

    def _credential_configured(self, provider: str, env_name: str) -> bool:
        del provider
        return bool(self._environment.get(env_name))


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    stt: FailoverSTTProvider | None = field(repr=False)
    llm: LLMProvider | None = field(repr=False)
    tts: TTSProvider | None = field(repr=False)
    health: ProviderHealth | None = None

    def capability_health(self) -> ProviderHealth:
        if self.health is not None:
            return self.health
        stt_name = None
        fallback_name = None
        if self.stt is not None:
            stt_name = getattr(self.stt.primary, "name", None)
            fallback_name = getattr(self.stt.fallback, "name", None)
        return ProviderHealth(
            selected_stt=stt_name,
            fallback_stt=fallback_name,
            stt_available=self.stt is not None,
            llm_provider=getattr(self.llm, "name", None),
            llm_available=self.llm is not None,
            tts_provider=getattr(self.tts, "name", None),
            tts_available=self.tts is not None,
        )


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

    stt_order = list(
        dict.fromkeys([config.providers.stt.primary, *config.providers.stt.fallback])
    )
    configured_stt: list[str] = []
    stt_secrets: dict[str, str] = {}
    for name in stt_order:
        settings = (
            config.providers.stt.speechmatics
            if name == "speechmatics"
            else config.providers.stt.deepgram
        )
        secret = env.get(settings.api_key_env)
        if secret:
            configured_stt.append(name)
            stt_secrets[name] = secret
        if len(configured_stt) == 2:
            break

    stt_instances: list[STTProvider] = []
    for name in configured_stt:
        kwargs = {"api_key": stt_secrets[name]}
        stt_instances.append(cast(STTProvider, factories[name](**kwargs)))

    stt: FailoverSTTProvider | None = None
    if stt_instances:
        stt = FailoverSTTProvider(
            stt_instances[0], stt_instances[1] if len(stt_instances) > 1 else None
        )

    groq = config.providers.llm.groq
    llm: LLMProvider | None = None
    if env.get(groq.api_key_env):
        llm = cast(
            LLMProvider,
            factories[config.providers.llm.primary](
                api_key=env[groq.api_key_env],
                model=groq.model,
                fallback_model=groq.fallback_model,
            ),
        )

    azure = config.providers.tts.azure
    tts: TTSProvider | None = None
    if env.get(azure.key_env) and env.get(azure.region_env):
        tts = cast(
            TTSProvider,
            factories[config.providers.tts.primary](
                api_key=env[azure.key_env],
                region=env[azure.region_env],
                sample_rate_hz=azure.sample_rate_hz,
            ),
        )

    health = ProviderHealth(
        selected_stt=configured_stt[0] if configured_stt else None,
        fallback_stt=configured_stt[1] if len(configured_stt) > 1 else None,
        stt_available=stt is not None,
        llm_provider=getattr(llm, "name", None),
        llm_available=llm is not None,
        tts_provider=getattr(tts, "name", None),
        tts_available=tts is not None,
    )
    return ProviderBundle(
        stt=stt,
        llm=llm,
        tts=tts,
        health=health,
    )


__all__ = [
    "ProviderAvailability",
    "ProviderBundle",
    "ProviderHealth",
    "ProviderRegistry",
    "build_provider_bundle",
]

import os
from collections.abc import Mapping
from dataclasses import dataclass


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

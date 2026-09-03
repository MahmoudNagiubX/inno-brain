from collections.abc import Callable
from pathlib import Path

import pytest

from innobrain.config.loader import load_all_configs
from innobrain.providers.errors import MissingProviderCredential
from innobrain.providers.registry import build_provider_bundle


class ConstructedProvider:
    def __init__(
        self,
        name: str,
        calls: list[tuple[str, dict[str, object]]],
        **kwargs: object,
    ) -> None:
        self.name = name
        calls.append((name, kwargs))


def _constructors(calls: list[tuple[str, dict[str, object]]]) -> dict[str, Callable[..., object]]:
    def constructor(name: str) -> Callable[..., object]:
        return lambda **kwargs: ConstructedProvider(name, calls, **kwargs)

    return {name: constructor(name) for name in ("speechmatics", "deepgram", "groq", "azure")}


def test_provider_factory_follows_config_and_only_constructs(tmp_path) -> None:
    del tmp_path
    config = load_all_configs(Path.cwd())
    calls: list[tuple[str, dict[str, object]]] = []
    bundle = build_provider_bundle(
        config,
        environment={
            "SPEECHMATICS_API_KEY": "speech-secret",
            "DEEPGRAM_API_KEY": "deep-secret",
            "GROQ_API_KEY": "groq-secret",
            "AZURE_SPEECH_KEY": "azure-secret",
            "AZURE_SPEECH_REGION": "egyptnorth",
        },
        constructors=_constructors(calls),
    )

    assert bundle.stt.primary.name == "speechmatics"
    assert bundle.stt.fallback.name == "deepgram"
    assert bundle.llm.name == "groq"
    assert bundle.tts.name == "azure"
    assert [name for name, _ in calls] == ["speechmatics", "deepgram", "groq", "azure"]
    assert "speech-secret" not in repr(bundle)


def test_provider_factory_missing_secret_names_variable_without_value() -> None:
    config = load_all_configs(Path.cwd())

    with pytest.raises(MissingProviderCredential) as caught:
        build_provider_bundle(config, environment={"SPEECHMATICS_API_KEY": "do-not-print"})

    assert "DEEPGRAM_API_KEY" in str(caught.value)
    assert "do-not-print" not in str(caught.value)

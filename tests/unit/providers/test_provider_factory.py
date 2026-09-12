from collections.abc import Callable
from pathlib import Path

import pytest

from innobrain.config.loader import load_all_configs
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

    bundle = build_provider_bundle(
        config,
        environment={"SPEECHMATICS_API_KEY": "do-not-print"},
        constructors=_constructors([]),
    )

    assert bundle.stt is not None
    assert bundle.stt.primary.name == "speechmatics"
    assert bundle.stt.fallback is None
    assert bundle.llm is None
    assert bundle.tts is None


@pytest.mark.parametrize(
    ("environment", "expected_primary", "expected_fallback"),
    [
        ({"SPEECHMATICS_API_KEY": "speech"}, "speechmatics", None),
        ({"DEEPGRAM_API_KEY": "deep"}, "deepgram", None),
        (
            {"SPEECHMATICS_API_KEY": "speech", "DEEPGRAM_API_KEY": "deep"},
            "speechmatics",
            "deepgram",
        ),
    ],
)
def test_provider_factory_selects_available_stt_capabilities(
    environment, expected_primary, expected_fallback
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    bundle = build_provider_bundle(
        load_all_configs(Path.cwd()),
        environment=environment,
        constructors=_constructors(calls),
    )

    assert bundle.stt is not None
    assert bundle.stt.primary.name == expected_primary
    assert (bundle.stt.fallback.name if bundle.stt.fallback else None) == expected_fallback
    assert bundle.health is not None
    assert bundle.health.selected_stt == expected_primary
    assert bundle.health.fallback_stt == expected_fallback


def test_provider_factory_no_stt_is_constructable_but_not_ready() -> None:
    bundle = build_provider_bundle(
        load_all_configs(Path.cwd()),
        environment={},
        constructors=_constructors([]),
    )

    assert bundle.stt is None
    assert bundle.llm is None
    assert bundle.tts is None
    assert bundle.health.stt_available is False
    assert bundle.health.llm_available is False
    assert bundle.health.tts_available is False


def test_provider_factory_missing_optional_providers_does_not_block_stt() -> None:
    bundle = build_provider_bundle(
        load_all_configs(Path.cwd()),
        environment={"SPEECHMATICS_API_KEY": "speech"},
        constructors=_constructors([]),
    )

    assert bundle.stt is not None
    assert bundle.health.stt_available is True
    assert bundle.health.llm_available is False
    assert bundle.health.tts_available is False


def test_provider_factory_passes_multilingual_and_voice_configuration_to_adapters() -> None:
    config = load_all_configs(Path.cwd())
    stt_config = config.providers.stt.model_copy(
        update={
            "speechmatics": config.providers.stt.speechmatics.model_copy(
                update={"language": "auto-en-ar"}
            ),
            "deepgram": config.providers.stt.deepgram.model_copy(
                update={"model": "nova-test", "language": "multi-test"}
            ),
        }
    )
    tts_config = config.providers.tts.model_copy(
        update={
            "azure": config.providers.tts.azure.model_copy(
                update={
                    "locale": "ar-EG",
                    "voice": "ar-EG-TestNeural",
                    "english_locale": "en-GB",
                    "english_voice": "en-GB-TestNeural",
                }
            )
        }
    )
    config = config.model_copy(
        update={
            "providers": config.providers.model_copy(
                update={"stt": stt_config, "tts": tts_config}
            )
        }
    )
    calls: list[tuple[str, dict[str, object]]] = []

    build_provider_bundle(
        config,
        environment={
            "SPEECHMATICS_API_KEY": "speech",
            "DEEPGRAM_API_KEY": "deep",
            "AZURE_SPEECH_KEY": "azure",
            "AZURE_SPEECH_REGION": "region",
        },
        constructors=_constructors(calls),
    )

    by_name = {name: kwargs for name, kwargs in calls}
    assert by_name["speechmatics"]["language"] == "auto-en-ar"
    assert by_name["deepgram"] == {
        "api_key": "deep",
        "model": "nova-test",
        "language": "multi-test",
    }
    assert by_name["azure"]["english_locale"] == "en-GB"
    assert by_name["azure"]["english_voice"] == "en-GB-TestNeural"

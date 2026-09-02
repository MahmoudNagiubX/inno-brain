from innobrain.providers.registry import ProviderRegistry


def test_registry_prefers_speechmatics_without_revealing_credentials(monkeypatch) -> None:
    monkeypatch.setenv("SPEECHMATICS_API_KEY", "speech-secret")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "deep-secret")

    registry = ProviderRegistry()

    assert registry.first_available_stt_name() == "speechmatics"
    statuses = {item.name: item for item in registry.availability()}
    assert statuses["speechmatics"].configured is True
    assert "speech-secret" not in statuses["speechmatics"].reason
    assert statuses["speechmatics"].reason == "configured"


def test_registry_falls_back_to_deepgram_and_handles_no_credentials(monkeypatch) -> None:
    monkeypatch.delenv("SPEECHMATICS_API_KEY", raising=False)
    monkeypatch.setenv("DEEPGRAM_API_KEY", "deep-secret")

    registry = ProviderRegistry()

    assert registry.first_available_stt_name() == "deepgram"
    assert registry.availability()[0].configured is False
    assert "SPEECHMATICS_API_KEY" in registry.availability()[0].reason

    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    assert ProviderRegistry().first_available_stt_name() is None

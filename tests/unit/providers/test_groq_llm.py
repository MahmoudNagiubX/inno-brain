from types import SimpleNamespace

import pytest

from innobrain.providers import ChatMessage
from innobrain.providers.errors import MissingProviderCredential
from innobrain.providers.groq_llm import GroqLLMProvider


class FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)

        async def chunks():
            yield SimpleNamespace(choices=[SimpleNamespace(delta={"content": "أهلاً "})])
            yield SimpleNamespace(choices=[SimpleNamespace(delta={"content": "بيك"})])

        return chunks()


class FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


@pytest.mark.asyncio
async def test_groq_stream_yields_only_text_deltas_and_uses_primary_model():
    client = FakeClient()
    provider = GroqLLMProvider(client=client)

    result = [
        item
        async for item in provider.stream(
            [ChatMessage("user", "hello")],
            tools=(),
            context=None,
        )
    ]

    assert "".join(result) == "أهلاً بيك"
    assert client.chat.completions.calls[0]["model"] == "openai/gpt-oss-120b"
    assert client.chat.completions.calls[0]["stream"] is True


def test_groq_factory_requires_credential_only_when_constructed(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(MissingProviderCredential):
        GroqLLMProvider()

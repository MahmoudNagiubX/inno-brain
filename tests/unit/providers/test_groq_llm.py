import asyncio
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


@pytest.mark.asyncio
async def test_cancelling_consumer_explicitly_closes_active_groq_stream():
    class BlockingStream:
        def __init__(self):
            self.first_emitted = asyncio.Event()
            self.release = asyncio.Event()
            self.closed = False
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index == 0:
                self.index += 1
                self.first_emitted.set()
                return SimpleNamespace(
                    choices=[SimpleNamespace(delta={"content": "أول"})]
                )
            await self.release.wait()
            raise StopAsyncIteration

        async def aclose(self):
            self.closed = True
            self.release.set()

    stream = BlockingStream()

    class BlockingCompletions:
        async def create(self, **_kwargs):
            return stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=BlockingCompletions()))
    provider = GroqLLMProvider(client=client)

    async def consume():
        async for _part in provider.stream([ChatMessage("user", "hello")], (), None):
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(stream.first_emitted.wait(), timeout=0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert stream.closed is True

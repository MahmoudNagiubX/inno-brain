import inspect
import os
from collections.abc import AsyncIterator, Sequence

from openai import AsyncOpenAI

from .contracts import ChatMessage
from .errors import MissingProviderCredential, ProviderUnavailable


class GroqLLMProvider:
    name = "groq"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: object | None = None,
        model: str = "openai/gpt-oss-120b",
        fallback_model: str = "openai/gpt-oss-20b",
    ) -> None:
        self.model = model
        self.fallback_model = fallback_model
        if client is None:
            api_key = api_key or os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise MissingProviderCredential("GROQ_API_KEY is not configured")
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        self.client = client
        self._active_stream: object | None = None

    def stream(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[object],
        context: object,
    ) -> AsyncIterator[str]:
        del context
        return self._stream_with_fallback(messages, tools)

    async def _stream_with_fallback(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[object],
    ) -> AsyncIterator[str]:
        payload = [{"role": item.role, "content": item.content} for item in messages]
        last_error: Exception | None = None
        for model in (self.model, self.fallback_model):
            emitted = False
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=payload,
                    tools=list(tools) or None,
                    stream=True,
                    max_completion_tokens=256,
                    reasoning_effort="low",
                )
                self._active_stream = (
                    await response if inspect.isawaitable(response) else response
                )
                async for chunk in self._active_stream:
                    delta = chunk.choices[0].delta
                    content = (
                        delta.get("content")
                        if isinstance(delta, dict)
                        else getattr(delta, "content", None)
                    )
                    if content:
                        emitted = True
                        yield str(content)
                return
            except Exception as exc:
                last_error = exc
                if emitted:
                    raise ProviderUnavailable("Groq stream failed after emitting text") from exc
            finally:
                self._active_stream = None
        raise ProviderUnavailable(
            "Groq primary and fallback models are unavailable"
        ) from last_error

    async def cancel(self) -> None:
        active = self._active_stream
        self._active_stream = None
        if active is None:
            return
        close = getattr(active, "aclose", None) or getattr(active, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

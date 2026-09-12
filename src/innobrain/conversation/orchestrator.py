import asyncio
import inspect
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from innobrain.providers import ChatMessage

from .grounding import GroundingContext, render_grounding_context
from .knowledge_binding import ActiveKnowledgeBinding
from .language import TurnLanguage, decide_turn_language
from .memory import SessionMemory
from .persona import system_policy
from .sentence_chunker import SentenceChunker


class AnswerRoute(StrEnum):
    EXACT = "exact"
    RAG_LLM = "rag_llm"
    RAG_DEGRADED = "rag_degraded"
    NO_EVIDENCE = "no_evidence"


@dataclass(frozen=True, slots=True)
class BrainResult:
    text: str
    route: AnswerRoute
    evidence_ids: tuple[str, ...]
    provider: str | None
    entities: tuple[str, ...] = ()
    language: str = TurnLanguage.AR_EG.value


class GroundedOrchestrator:
    def __init__(
        self,
        resolver: object | None = None,
        retriever: object | None = None,
        *,
        memory: SessionMemory | None = None,
        llm_provider: object | None = None,
        policy: str | None = None,
        knowledge: ActiveKnowledgeBinding | None = None,
    ) -> None:
        if knowledge is None and (resolver is None or retriever is None):
            raise ValueError("resolver and retriever are required without a knowledge binding")
        self.resolver = resolver
        self.retriever = retriever
        self.knowledge = knowledge
        self.memory = memory or SessionMemory()
        self.llm_provider = llm_provider
        self.policy = policy

    async def answer(
        self,
        user_text: str,
        *,
        delivery_confirmed: bool = False,
        delivery_callback: Callable[[str], Awaitable[bool] | bool] | None = None,
        language: str | None = None,
    ) -> BrainResult:
        self.memory.expire_if_idle()
        language_decision = decide_turn_language(
            user_text,
            provider_language=language,
            prior=self.memory.language_style,
        )
        response_language = language_decision.response
        resolver, retriever = self._knowledge_components()
        exact = resolver.resolve(
            user_text,
            active_entities=self.memory.active_entities(),
        )
        if exact is not None:
            localize = getattr(resolver, "localize", None)
            if response_language is TurnLanguage.EN and localize is not None:
                exact = localize(exact, response_language.value)
            result = BrainResult(
                text=exact.text,
                route=AnswerRoute.EXACT,
                evidence_ids=exact.evidence_ids,
                provider=None,
                entities=exact.entities,
                language=response_language.value,
            )
            await self._commit_after_delivery(
                user_text,
                result,
                exact.entities,
                delivery_confirmed,
                delivery_callback,
            )
            return result

        evidence_pack = await retriever.retrieve(user_text)
        if not evidence_pack.evidence:
            result = BrainResult(
                text="مش لاقي معلومة مؤكدة عن السؤال ده في بيانات الـevent.",
                route=AnswerRoute.NO_EVIDENCE,
                evidence_ids=(),
                provider=None,
                language=response_language.value,
            )
            if response_language is TurnLanguage.EN:
                result = replace(
                    result,
                    text="I couldn't find a confirmed answer to that in the event data.",
                )
            await self._commit_after_delivery(
                user_text,
                result,
                (),
                delivery_confirmed,
                delivery_callback,
            )
            return result

        context = GroundingContext(evidence=evidence_pack, memory=self.memory.recent_turns())
        messages = (
            ChatMessage(
                role="system",
                content=self._system_policy(response_language.value),
            ),
            ChatMessage(role="user", content=user_text),
            ChatMessage(role="user", content=render_grounding_context(context)),
        )
        try:
            if self.llm_provider is None:
                raise RuntimeError("LLM provider unavailable")
            parts: list[str] = []
            stream = self.llm_provider.stream(messages, tools=(), context=context)
            async for part in stream:
                parts.append(str(part))
            text = "".join(parts).strip()
            if not text:
                raise RuntimeError("LLM returned an empty response")
            result = BrainResult(
                text=text,
                route=AnswerRoute.RAG_LLM,
                evidence_ids=tuple(item.evidence_id for item in evidence_pack.evidence),
                provider=getattr(self.llm_provider, "name", "llm"),
                language=response_language.value,
            )
        except Exception:
            result = BrainResult(
                text=evidence_pack.evidence[0].text,
                route=AnswerRoute.RAG_DEGRADED,
                evidence_ids=tuple(item.evidence_id for item in evidence_pack.evidence),
                provider=None,
                language=response_language.value,
            )
        await self._commit_after_delivery(
            user_text,
            result,
            (),
            delivery_confirmed,
            delivery_callback,
        )
        return result

    async def stream_answer(
        self,
        user_text: str,
        *,
        on_chunk: Callable[[str], Awaitable[None] | None],
        language: str | None = None,
    ) -> BrainResult:
        """Stream safe spoken chunks while retaining one final grounded result.

        This method deliberately owns no delivery commit. The voice runtime commits only
        after all emitted PCM has finished playback, so cancellation cannot commit a
        response that was only partially spoken.
        """

        self.memory.expire_if_idle()
        language_decision = decide_turn_language(
            user_text,
            provider_language=language,
            prior=self.memory.language_style,
        )
        response_language = language_decision.response
        resolver, retriever = self._knowledge_components()
        exact = resolver.resolve(
            user_text,
            active_entities=self.memory.active_entities(),
        )
        if exact is not None:
            localize = getattr(resolver, "localize", None)
            if response_language is TurnLanguage.EN and localize is not None:
                exact = localize(exact, response_language.value)
            result = BrainResult(
                text=exact.text,
                route=AnswerRoute.EXACT,
                evidence_ids=exact.evidence_ids,
                provider=None,
                entities=exact.entities,
                language=response_language.value,
            )
            await self._emit_chunk(on_chunk, result.text)
            return result

        evidence_pack = await retriever.retrieve(user_text)
        if not evidence_pack.evidence:
            text = (
                "I couldn't find a confirmed answer to that in the event data."
                if response_language is TurnLanguage.EN
                else (
                    "Ù…Ø´ Ù„Ø§Ù‚ÙŠ Ù…Ø¹Ù„ÙˆÙ…Ø© Ù…Ø¤ÙƒØ¯Ø© Ø¹Ù† Ø§Ù„Ø³Ø¤Ø§Ù„ Ø¯Ù‡ "
                    "ÙÙŠ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù€event."
                )
            )
            result = BrainResult(
                text=text,
                route=AnswerRoute.NO_EVIDENCE,
                evidence_ids=(),
                provider=None,
                language=response_language.value,
            )
            await self._emit_chunk(on_chunk, result.text)
            return result

        context = GroundingContext(evidence=evidence_pack, memory=self.memory.recent_turns())
        messages = (
            ChatMessage(
                role="system",
                content=self._system_policy(response_language.value),
            ),
            ChatMessage(role="user", content=user_text),
            ChatMessage(role="user", content=render_grounding_context(context)),
        )
        if self.llm_provider is None:
            result = BrainResult(
                text=evidence_pack.evidence[0].text,
                route=AnswerRoute.RAG_DEGRADED,
                evidence_ids=tuple(item.evidence_id for item in evidence_pack.evidence),
                provider=None,
                language=response_language.value,
            )
            await self._emit_chunk(on_chunk, result.text)
            return result

        parts: list[str] = []
        chunker = SentenceChunker()
        try:
            stream = self.llm_provider.stream(messages, tools=(), context=context)
            async for part in stream:
                value = str(part)
                if not value:
                    continue
                parts.append(value)
                for chunk in chunker.feed(value):
                    await self._emit_chunk(on_chunk, chunk)
            for chunk in chunker.flush():
                await self._emit_chunk(on_chunk, chunk)
            text = "".join(parts).strip()
            if not text:
                raise RuntimeError("LLM returned an empty response")
        except asyncio.CancelledError:
            raise
        except Exception:
            if parts:
                raise
            result = BrainResult(
                text=evidence_pack.evidence[0].text,
                route=AnswerRoute.RAG_DEGRADED,
                evidence_ids=tuple(item.evidence_id for item in evidence_pack.evidence),
                provider=None,
                language=response_language.value,
            )
            await self._emit_chunk(on_chunk, result.text)
            return result

        return BrainResult(
            text=text,
            route=AnswerRoute.RAG_LLM,
            evidence_ids=tuple(item.evidence_id for item in evidence_pack.evidence),
            provider=getattr(self.llm_provider, "name", "llm"),
            language=response_language.value,
        )

    async def respond(self, user_text: str, **kwargs: object) -> BrainResult:
        return await self.answer(user_text, **kwargs)  # type: ignore[arg-type]

    async def cancel(self) -> None:
        if self.llm_provider is None:
            return
        cancel = getattr(self.llm_provider, "cancel", None)
        if cancel is None:
            return
        result = cancel()
        if inspect.isawaitable(result):
            await result

    def _knowledge_components(self) -> tuple[object, object]:
        if self.knowledge is not None:
            snapshot = self.knowledge.snapshot()
            return snapshot.resolver, snapshot.retriever
        assert self.resolver is not None and self.retriever is not None
        return self.resolver, self.retriever

    def _system_policy(self, response_language: str) -> str:
        if self.policy is None:
            return system_policy(response_language=response_language)
        language_text = (
            "Respond in natural English for this turn."
            if response_language == TurnLanguage.EN.value
            else "Respond in natural Egyptian Arabic for this turn."
        )
        return (
            f"{self.policy}\n{language_text} "
            "Preserve English names and technical terms naturally."
        )

    @staticmethod
    async def _emit_chunk(
        callback: Callable[[str], Awaitable[None] | None],
        text: str,
    ) -> None:
        result = callback(text)
        if inspect.isawaitable(result):
            await result

    def commit_delivered(
        self,
        user_text: str,
        result: BrainResult,
        entities: Sequence[str] | None = None,
    ) -> None:
        self.memory.add_turn(
            user_text,
            result.text,
            result.entities if entities is None else entities,
        )
        self.memory.set_language_style(result.language)

    async def _commit_after_delivery(
        self,
        user_text: str,
        result: BrainResult,
        entities: Sequence[str],
        delivery_confirmed: bool,
        delivery_callback: Callable[[str], Awaitable[bool] | bool] | None,
    ) -> None:
        delivered = delivery_confirmed
        if delivery_callback is not None:
            callback_result = delivery_callback(result.text)
            delivered = (
                await callback_result
                if inspect.isawaitable(callback_result)
                else bool(callback_result)
            )
        if delivered:
            self.memory.add_turn(user_text, result.text, entities)
            self.memory.set_language_style(result.language)

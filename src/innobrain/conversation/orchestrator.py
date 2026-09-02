import inspect
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from innobrain.providers import ChatMessage

from .grounding import GroundingContext, render_grounding_context
from .memory import SessionMemory
from .persona import system_policy


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


class GroundedOrchestrator:
    def __init__(
        self,
        resolver: object,
        retriever: object,
        *,
        memory: SessionMemory | None = None,
        llm_provider: object | None = None,
        policy: str | None = None,
    ) -> None:
        self.resolver = resolver
        self.retriever = retriever
        self.memory = memory or SessionMemory()
        self.llm_provider = llm_provider
        self.policy = policy or system_policy()

    async def answer(
        self,
        user_text: str,
        *,
        delivery_confirmed: bool = False,
        delivery_callback: Callable[[str], Awaitable[bool] | bool] | None = None,
    ) -> BrainResult:
        self.memory.expire_if_idle()
        exact = self.resolver.resolve(
            user_text,
            active_entities=self.memory.active_entities(),
        )
        if exact is not None:
            result = BrainResult(
                text=exact.text,
                route=AnswerRoute.EXACT,
                evidence_ids=exact.evidence_ids,
                provider=None,
                entities=exact.entities,
            )
            await self._commit_after_delivery(
                user_text,
                result,
                exact.entities,
                delivery_confirmed,
                delivery_callback,
            )
            return result

        evidence_pack = await self.retriever.retrieve(user_text)
        if not evidence_pack.evidence:
            result = BrainResult(
                text="مش لاقي معلومة مؤكدة عن السؤال ده في بيانات الـevent.",
                route=AnswerRoute.NO_EVIDENCE,
                evidence_ids=(),
                provider=None,
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
            ChatMessage(role="system", content=self.policy),
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
            )
        except Exception:
            result = BrainResult(
                text=evidence_pack.evidence[0].text,
                route=AnswerRoute.RAG_DEGRADED,
                evidence_ids=tuple(item.evidence_id for item in evidence_pack.evidence),
                provider=None,
            )
        await self._commit_after_delivery(
            user_text,
            result,
            (),
            delivery_confirmed,
            delivery_callback,
        )
        return result

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

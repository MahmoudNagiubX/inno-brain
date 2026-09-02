from dataclasses import dataclass

from innobrain.knowledge.models import EvidencePack

from .memory import MemoryTurn


@dataclass(frozen=True, slots=True)
class GroundingContext:
    evidence: EvidencePack
    memory: tuple[MemoryTurn, ...] = ()


def render_grounding_context(context: GroundingContext) -> str:
    """Serialize untrusted evidence into a data-only block for an LLM request."""

    evidence_lines = [
        f"[{item.evidence_id} | {item.source.value}] {item.text}"
        for item in context.evidence.evidence
    ]
    memory_lines = [
        f"user: {turn.user_text}\nassistant: {turn.assistant_text}"
        for turn in context.memory
    ]
    return (
        "<event_evidence>\n"
        + ("\n".join(evidence_lines) if evidence_lines else "(none)")
        + "\n</event_evidence>\n"
        "<recent_conversation>\n"
        + ("\n".join(memory_lines) if memory_lines else "(none)")
        + "\n</recent_conversation>"
    )

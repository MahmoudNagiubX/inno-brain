from pathlib import Path

from innobrain.conversation.orchestrator import AnswerRoute
from scripts.phase3.text_demo import answer_text

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_text_demo_covers_exact_grounded_and_no_evidence_routes(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.sqlite3"
    exact_time = answer_text("Future of AI in Events الساعة كام؟", db_path=db_path)
    exact_booth = answer_text("بوث Innovatronics فين؟", db_path=db_path)
    grounded = answer_text("ابدأ الايفنت منين؟", db_path=db_path)
    unknown = answer_text("مين رئيس فرنسا؟", db_path=db_path)

    assert exact_time.route is AnswerRoute.EXACT
    assert exact_booth.route is AnswerRoute.EXACT
    assert grounded.route in {AnswerRoute.RAG_LLM, AnswerRoute.RAG_DEGRADED}
    assert unknown.route is AnswerRoute.NO_EVIDENCE

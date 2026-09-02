from pathlib import Path

from scripts.phase3.benchmark_rag import run_benchmark

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_fixture_rag_metrics_meet_phase3_thresholds(tmp_path: Path) -> None:
    count, recall, mrr = run_benchmark(
        db_path=tmp_path / "demo.sqlite3",
        queries_path=REPOSITORY_ROOT / "evals" / "rag" / "phase3_queries.yaml",
    )

    assert count >= 16
    assert recall >= 0.90
    assert mrr >= 0.75

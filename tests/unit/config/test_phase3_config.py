from pathlib import Path

from innobrain.config import load_all_configs

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_phase3_provider_baseline_is_selected_and_pinned() -> None:
    configs = load_all_configs(REPOSITORY_ROOT)

    assert configs.providers.stt.primary == "speechmatics"
    assert configs.providers.tts.azure.voice == "ar-EG-ShakirNeural"
    assert configs.providers.llm.groq.model == "openai/gpt-oss-120b"
    assert configs.providers.embedding.dimension == 384
    assert configs.providers.retrieval.rrf_k == 60

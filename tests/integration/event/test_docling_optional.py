import importlib.util
from pathlib import Path

import pytest

from innobrain.event.authoring import DocumentSource
from innobrain.event.parser import parse_document


@pytest.mark.skipif(
    importlib.util.find_spec("docling") is None,
    reason="builder-only Docling is not installed",
)
def test_live_docling_converts_local_markdown(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Local guide\n\nDocling content", encoding="utf-8")
    document = DocumentSource(
        id="doc",
        path="guide.md",
        title="Guide",
        language="en",
        authority_level="official",
    )

    parsed = parse_document(document, tmp_path, cache_dir=tmp_path / "cache")

    assert parsed.text.strip()

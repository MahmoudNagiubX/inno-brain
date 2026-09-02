from pathlib import Path

from innobrain.event.authoring import DocumentSource
from innobrain.event.chunking import chunk_document
from innobrain.event.parser import ParsedDocument


class _CharacterTokenizer:
    def encode(self, text: str) -> object:
        return type("Encoding", (), {"ids": list(text)})()


def _document() -> DocumentSource:
    return DocumentSource(
        id="doc",
        path="documents/guide.md",
        title="Guide",
        language="en",
        authority_level="official",
        valid_from=None,
        valid_until=None,
    )


def test_chunker_preserves_text_order_and_provenance_under_hard_cap() -> None:
    text = "First paragraph.\n\nSecond paragraph with a little more content."
    parsed = ParsedDocument(
        document_id="doc",
        title="Guide",
        source_path=Path("documents/guide.md"),
        docling_document=None,
        text=text,
        headings=("Guide",),
        page_numbers=(1,),
    )

    chunks = chunk_document(parsed, _document(), tokenizer=_CharacterTokenizer(), max_tokens=384)

    assert "\n\n".join(chunk.text for chunk in chunks) == text
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].headings == ("Guide",)
    assert chunks[0].page_numbers == (1,)
    assert chunks[0].authority_level == "official"
    assert chunks[0].source_path == "documents/guide.md"


def test_oversized_content_is_split_without_silent_truncation() -> None:
    text = "".join(str(index % 10) for index in range(1000))
    parsed = ParsedDocument(
        document_id="doc",
        title="Guide",
        source_path=Path("guide.txt"),
        docling_document=None,
        text=text,
    )

    chunks = chunk_document(parsed, _document(), tokenizer=_CharacterTokenizer(), max_tokens=384)

    assert "".join(chunk.text for chunk in chunks) == text
    assert len(chunks) >= 3
    assert all(chunk.embedding_row == index for index, chunk in enumerate(chunks))
    assert all(chunk.token_count <= 384 for chunk in chunks)


def test_chunker_uses_document_retrieval_metadata() -> None:
    parsed = ParsedDocument(
        document_id="doc",
        title="Guide",
        source_path=Path("guide.txt"),
        docling_document=None,
        text="Current schedule",
    )

    chunk = chunk_document(parsed, _document(), tokenizer=_CharacterTokenizer())[0]

    assert chunk.normalized_text == "current schedule"
    assert chunk.language == "en"
    assert chunk.valid_from is None
    assert chunk.valid_until is None

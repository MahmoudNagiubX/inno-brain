import sys
from pathlib import Path

import pytest

from innobrain.event.authoring import DocumentSource
from innobrain.event.errors import EventSchemaError
from innobrain.event.parser import ParsedDocument, parse_document


def _document(path: str = "guide.txt") -> DocumentSource:
    return DocumentSource(
        id="doc",
        path=path,
        title="Guide",
        language="en",
        authority_level="official",
    )


def test_txt_is_read_as_local_utf8(tmp_path: Path) -> None:
    source = tmp_path / "guide.txt"
    source.write_text("ALPHA-COMPASS\nمرحبا", encoding="utf-8")

    result = parse_document(_document(), tmp_path)

    assert isinstance(result, ParsedDocument)
    assert result.text == "ALPHA-COMPASS\nمرحبا"
    assert result.docling_document is None


class _FakeDoclingDocument:
    def export_to_markdown(self) -> str:
        return "# Converted\n\nConverted content"


class _FakeConversion:
    document = _FakeDoclingDocument()


class _FakeConverter:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def convert(self, path: str) -> _FakeConversion:
        self.paths.append(path)
        return _FakeConversion()


def test_non_txt_uses_injected_docling_converter(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("source", encoding="utf-8")
    converter = _FakeConverter()

    result = parse_document(_document("guide.md"), tmp_path, converter=converter)

    assert result.text == "# Converted\n\nConverted content"
    assert result.docling_document is not None
    assert converter.paths == [str(source)]


@pytest.mark.parametrize("path", ["https://example.com/guide.pdf", "http://example.com/guide.txt"])
def test_url_sources_are_rejected(path: str, tmp_path: Path) -> None:
    with pytest.raises(EventSchemaError, match="local"):
        parse_document(_document(path), tmp_path)


def test_unsupported_format_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "guide.exe"
    source.write_bytes(b"not a document")

    with pytest.raises(EventSchemaError, match="unsupported"):
        parse_document(_document("guide.exe"), tmp_path)


def test_runtime_parser_module_does_not_import_docling() -> None:
    assert "docling" not in sys.modules

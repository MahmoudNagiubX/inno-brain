from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .authoring import DocumentSource
from .errors import EventSchemaError

SUPPORTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".html",
        ".xhtml",
        ".md",
        ".csv",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".bmp",
        ".webp",
        ".doc",
        ".xls",
        ".ppt",
    }
)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    document_id: str
    title: str
    source_path: Path
    docling_document: object | None
    text: str
    headings: tuple[str, ...] = ()
    page_numbers: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()


def _safe_source_path(document: DocumentSource, source_root: Path) -> Path:
    parsed = urlsplit(document.path)
    if parsed.scheme or parsed.netloc:
        raise EventSchemaError("event document sources must be local files, not URLs")
    root = source_root.resolve()
    source = (root / document.path).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise EventSchemaError(f"document path escapes source root: {document.path}") from exc
    if not source.is_file():
        raise EventSchemaError(f"document source does not exist: {document.path}")
    return source


def _headings(text: str) -> tuple[str, ...]:
    return tuple(line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#"))


def _text_from_docling_result(result: object) -> tuple[object, str]:
    docling_document = getattr(result, "document", result)
    for method_name in ("export_to_markdown", "export_to_text"):
        method = getattr(docling_document, method_name, None)
        if method is not None:
            text = method()
            if isinstance(text, str):
                return docling_document, text
    text = getattr(result, "text", None) or getattr(docling_document, "text", None)
    if isinstance(text, str):
        return docling_document, text
    raise EventSchemaError("Docling conversion returned no text")


def _make_default_converter(cache_dir: Path | None) -> object:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise EventSchemaError(
            "Docling is required for this document format in the builder environment"
        ) from exc

    # These policy values are deliberately explicit at the adapter boundary. The
    # builder must provide local model artifacts and never enable remote services
    # or external plugins for event content.
    policy = {
        "enable_remote_services": False,
        "allow_external_plugins": False,
        "artifacts_path": str(cache_dir) if cache_dir else None,
    }
    try:
        return DocumentConverter(**policy)
    except TypeError:
        converter = DocumentConverter()
        for name, value in policy.items():
            if value is not None and hasattr(converter, name):
                setattr(converter, name, value)
        return converter


def parse_document(
    document: DocumentSource,
    source_root: Path | str,
    *,
    converter: object | None = None,
    cache_dir: Path | str | None = None,
    allow_plaintext_fallback: bool = True,
) -> ParsedDocument:
    source_root = Path(source_root)
    source_path = _safe_source_path(document, source_root)
    extension = source_path.suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        raise EventSchemaError(f"unsupported event document format: {extension or '<none>'}")

    if extension == ".txt":
        try:
            text = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise EventSchemaError(f"text document is not valid UTF-8: {document.path}") from exc
        return ParsedDocument(
            document_id=document.id,
            title=document.title,
            source_path=source_path,
            docling_document=None,
            text=text,
            headings=_headings(text),
        )

    try:
        active_converter = converter or _make_default_converter(
            Path(cache_dir) if cache_dir else None
        )
    except EventSchemaError:
        if extension == ".md" and allow_plaintext_fallback:
            text = source_path.read_text(encoding="utf-8")
            return ParsedDocument(
                document_id=document.id,
                title=document.title,
                source_path=source_path,
                docling_document=None,
                text=text,
                headings=_headings(text),
                warnings=("Docling unavailable; Markdown plaintext fallback used",),
            )
        raise

    convert = getattr(active_converter, "convert", None)
    if convert is None:
        raise EventSchemaError("Docling converter does not expose convert()")
    try:
        result = convert(str(source_path))
        docling_document, text = _text_from_docling_result(result)
    except EventSchemaError:
        raise
    except Exception as exc:  # noqa: BLE001 - builder adapter reports converter failures.
        raise EventSchemaError(f"Docling failed to parse {document.path}: {exc}") from exc
    return ParsedDocument(
        document_id=document.id,
        title=document.title,
        source_path=source_path,
        docling_document=docling_document,
        text=text,
        headings=_headings(text),
    )


__all__ = ["ParsedDocument", "SUPPORTED_EXTENSIONS", "parse_document"]

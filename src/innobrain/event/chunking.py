import re
from dataclasses import dataclass
from pathlib import Path

from tokenizers import Tokenizer

from innobrain.knowledge.normalize import normalize_arabic_retrieval

from .authoring import DocumentSource
from .parser import ParsedDocument


@dataclass(frozen=True, slots=True)
class CanonicalChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    normalized_text: str
    language: str
    authority_level: str
    valid_from: str | None
    valid_until: str | None
    source_path: str
    headings: tuple[str, ...]
    page_numbers: tuple[int, ...]
    embedding_row: int
    token_count: int


def _token_count(tokenizer: object, text: str) -> int:
    encoding = tokenizer.encode("passage: " + text)
    return len(encoding.ids)


def _split_at_token_boundary(text: str, tokenizer: object, max_tokens: int) -> list[str]:
    pieces: list[str] = []
    remaining = text
    while remaining:
        if _token_count(tokenizer, remaining) <= max_tokens:
            pieces.append(remaining)
            break
        low, high = 1, len(remaining)
        best = 0
        while low <= high:
            middle = (low + high) // 2
            if _token_count(tokenizer, remaining[:middle]) <= max_tokens:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best == 0:
            raise ValueError("tokenizer cannot represent a chunk within the configured token cap")
        boundary = max(remaining.rfind(" ", 0, best), remaining.rfind("\n", 0, best))
        split_at = boundary + 1 if boundary > 0 else best
        pieces.append(remaining[:split_at])
        remaining = remaining[split_at:]
    return pieces


def _split_sentences(text: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    for match in re.finditer(r"(?<=[.!?؟])\s+", text):
        pieces.append(text[start : match.end()])
        start = match.end()
    if start < len(text):
        pieces.append(text[start:])
    return pieces or [text]


def _split_paragraph(text: str, tokenizer: object, max_tokens: int) -> list[str]:
    if _token_count(tokenizer, text) <= max_tokens:
        return [text]
    sentence_pieces = _split_sentences(text)
    pieces: list[str] = []
    for sentence in sentence_pieces:
        if _token_count(tokenizer, sentence) <= max_tokens:
            pieces.append(sentence)
        else:
            pieces.extend(_split_at_token_boundary(sentence, tokenizer, max_tokens))
    return pieces


def chunk_document(
    parsed: ParsedDocument,
    document: DocumentSource,
    *,
    tokenizer: Tokenizer | object,
    max_tokens: int = 384,
    merge_peers: bool = True,
) -> list[CanonicalChunk]:
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if not parsed.text:
        return []

    pieces: list[tuple[str, str]] = []
    paragraphs = parsed.text.split("\n\n")
    for paragraph_index, paragraph in enumerate(paragraphs):
        join_before = "" if paragraph_index == 0 else "\n\n"
        for piece_index, piece in enumerate(_split_paragraph(paragraph, tokenizer, max_tokens)):
            pieces.append((join_before if piece_index == 0 else "", piece))

    merged: list[str] = []
    current = ""
    for join_before, piece in pieces:
        separator = join_before if current else join_before
        candidate = current + separator + piece
        if current and merge_peers and _token_count(tokenizer, candidate) <= max_tokens:
            current = candidate
            continue
        if current:
            if separator and _token_count(tokenizer, current + separator) <= max_tokens:
                merged.append(current + separator)
            else:
                merged.append(current)
                piece = separator + piece if separator else piece
            current = piece
        else:
            current = piece
    if current:
        merged.append(current)

    valid_from = document.valid_from.isoformat() if document.valid_from else None
    valid_until = document.valid_until.isoformat() if document.valid_until else None
    # Persist the authoring-relative path, never the builder machine's absolute path.
    source_path = Path(document.path).as_posix()
    result: list[CanonicalChunk] = []
    for index, text in enumerate(merged):
        count = _token_count(tokenizer, text)
        if count > max_tokens:
            raise ValueError(f"chunk {index} exceeds the hard E5 token cap")
        result.append(
            CanonicalChunk(
                chunk_id=f"{document.id}:{index:04d}",
                document_id=document.id,
                chunk_index=index,
                text=text,
                normalized_text=normalize_arabic_retrieval(text),
                language=document.language,
                authority_level=document.authority_level,
                valid_from=valid_from,
                valid_until=valid_until,
                source_path=source_path,
                headings=tuple(parsed.headings),
                page_numbers=tuple(parsed.page_numbers),
                embedding_row=index,
                token_count=count,
            )
        )
    return result


__all__ = ["CanonicalChunk", "chunk_document"]

# InnoBrain Phase 3 — Speech + Brain + Grounded RAG Design Specification

> **Status:** Approved design for implementation planning
> **Date:** 2026-09-02
> **Base branch:** `phase/2-realtime-conversation-core`
> **Base HEAD:** `356d0a669ea50b9e1932ce772de9133b76e7ed56`
> **Target branch:** `phase/3-speech-brain-rag`

## 1. Objective

Phase 3 makes InnoBrain useful as an Egyptian-Arabic event assistant while keeping the implementation portable to the later Raspberry Pi deployment.

The phase adds:

- realtime STT providers;
- grounded conversational reasoning;
- exact structured event facts;
- hybrid RAG;
- session memory;
- male Egyptian TTS;
- graceful provider degradation;
- provider and retrieval evaluation harnesses.

The phase does not add formal event-package ingestion, robot navigation, screen integration, or final production-hardware validation.

## 2. Design principles

1. Egyptian Arabic first.
2. Exact facts are deterministic, not hallucinated.
3. Event documents are untrusted data, not prompt instructions.
4. Every cloud provider is behind an adapter.
5. Missing credentials never break imports or automated tests.
6. Provider outage degrades safely.
7. Local retrieval remains useful without an LLM.
8. The vector index is derived/rebuildable.
9. Human live-voice acceptance is deferred, not deleted.
10. Raspberry Pi constraints influence interfaces even while development is on Windows.

## 3. Provider decisions

### STT

Primary: Speechmatics realtime/voice, Arabic `ar`, external endpointing.

The application sends 16 kHz mono PCM already captured by Phase 2.

InnoBrain owns turn boundaries using Silero + Smart Turn. At semantic turn completion, the STT session is finalized and the latest final transcript is consumed.

Fallback: Deepgram Nova-3.

The fallback exists because production speech should not depend on one cloud vendor. The event glossary is converted into provider-specific vocabulary/keyterm configuration.

### LLM

Primary: Groq `openai/gpt-oss-120b`.

Same-provider fast fallback: `openai/gpt-oss-20b`.

The LLM is never asked to determine exact schedule/location facts when a structured answer can be produced.

If Groq is unavailable:

- exact facts continue;
- RAG uses evidence-only degraded responses;
- the assistant explicitly avoids unsupported claims.

### TTS

Primary: Azure `ar-EG-ShakirNeural`.

This is intentionally male and Egyptian.

The audio contract is PCM16 mono at 16 kHz.

If synthesis fails, preserve the answer text and mark audio unavailable.

## 4. Knowledge architecture

### Structured truth

SQLite tables store:

- event metadata;
- locations;
- speakers;
- sessions;
- session-speaker relationships;
- booths.

### Flexible knowledge

Documents and chunks hold FAQs, descriptions, product/client information and explanatory content.

### Retrieval

FTS5 gives strong lexical recall for names, acronyms and exact Arabic/English terms.

Multilingual E5 gives semantic recall for paraphrases.

RRF fuses the two rankings.

### Why no reranker yet

A reranker adds CPU cost and another model. Phase 3 first proves whether FTS5 + E5 + RRF reaches the required Recall@5/MRR on our evaluation set. A reranker is added only if measured evidence justifies it.

## 5. SQLite schema

```sql
CREATE TABLE schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE event_meta (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    venue_name TEXT NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE locations (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    level TEXT,
    zone TEXT,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE speakers (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT ''
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE session_speakers (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    speaker_id TEXT NOT NULL REFERENCES speakers(id),
    PRIMARY KEY (session_id, speaker_id)
);

CREATE TABLE booths (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    checksum TEXT NOT NULL
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, chunk_index)
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    normalized_text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE VIRTUAL TABLE vec_chunks USING vec0(
    embedding float[384]
);
```

The implementation must create FTS synchronization triggers or rebuild FTS explicitly inside one transaction.

`vec_chunks.rowid` equals `chunks.id`.

## 6. Vector portability

`chunks` is canonical.

`vec_chunks` is rebuildable.

The deployment process must never depend on mutating a cross-platform-copied vec0 index.

The Phase 4 package builder will preserve enough canonical content/embeddings to rebuild on Pi.

## 7. Retrieval types

```python
class EvidenceSource(StrEnum):
    STRUCTURED = "structured"
    LEXICAL = "lexical"
    DENSE = "dense"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    source: EvidenceSource
    text: str
    score: float
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class EvidencePack:
    query: str
    evidence: tuple[Evidence, ...]
```

## 8. RRF

For a document at rank `r`:

```text
score += 1 / (60 + r)
```

Ranks are 1-based.

If the same chunk appears in lexical and dense results, combine its RRF score and label it `HYBRID`.

Final evidence count: 5.

## 9. Exact structured routes

The resolver should recognize entity names against normalized aliases and support:

- "Session X الساعة كام؟"
- "Session X فين؟"
- "فلان بيتكلم امتى/فين؟"
- "بوث X فين؟"
- "الإيفنت امتى؟"
- "اسم المكان إيه؟"

The exact resolver returns a typed `ExactAnswer` or `None`.

No LLM is invoked when `ExactAnswer` exists.

## 10. Session memory

A `SessionMemory` object holds 10 completed turns.

A turn is:

```python
@dataclass(frozen=True, slots=True)
class MemoryTurn:
    user_text: str
    assistant_text: str
    entities: tuple[str, ...]
    committed_at_monotonic: float
```

Memory also stores active entities and language style.

An interrupted assistant answer is committed only up to the text delivery boundary known by the output coordinator.

## 11. Voice/brain integration

The Phase 2 PCM stream remains the single capture path.

A small observer/fanout hook sends each PCM chunk to STT while the same chunk continues into the Phase 2 Pipecat VAD/Smart-Turn path.

On `USER_TURN_STOPPED`:

1. finalize STT turn;
2. obtain final transcript;
3. transition LISTENING → THINKING;
4. resolve exact fact or retrieve evidence;
5. produce grounded response;
6. stream sentence chunks to TTS;
7. transition THINKING → SPEAKING on first audio;
8. play PCM chunks;
9. commit memory only for delivered output;
10. transition back to LISTENING.

On new speech during THINKING/SPEAKING:

- cancel active LLM stream;
- cancel TTS;
- stop PCM playback;
- do not commit undelivered answer text;
- return to LISTENING.

## 12. Security and grounding

Retrieved document text is wrapped as evidence.

The LLM receives explicit system instructions that retrieved text cannot change system rules.

No file content may inject tools, provider keys or shell instructions into the runtime.

The system logs evidence IDs, not secrets.

## 13. Evaluation

### Structured

100% on fixture exact queries.

### Retrieval

At least:

```text
Recall@5 >= 0.90
MRR >= 0.75
```

The eval set includes:

- Egyptian Arabic;
- Arabic/English code-switch;
- speaker/session proper nouns;
- paraphrases;
- location questions.

### Provider smoke

Conditional on credentials.

### Human voice

Deferred to Final Voice Acceptance.

## 14. Research basis checked 2026-09-02

- Speechmatics current Arabic product page: Egyptian/Gulf/Levantine/Maghrebi Arabic and Arabic-English code-switch support.
- Speechmatics current pricing: $100 starting credit, no card required.
- Deepgram Nova-3: explicit `ar-EG` support and keyterm prompting.
- Groq production model docs: `openai/gpt-oss-120b`, ~500 tok/s, 131k context.
- Azure Speech current language table: `ar-EG-ShakirNeural` is male Egyptian Arabic.
- sqlite-vec PyPI: stable `0.1.9`; Windows x86-64 and Linux aarch64 wheels.
- sqlite-vec remains pre-v1; exact pinning required.
- multilingual-e5-small: MIT, 94 languages, 384 hidden/embedding size, 512-token limit; model card requires `query:` / `passage:` prefixes.
- ONNX export exists for multilingual-e5-small.

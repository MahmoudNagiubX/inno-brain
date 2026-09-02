# Implementation Plan: Phase 3 Speech, Brain and Grounded RAG

## Overview

Implement the approved Phase 3 design on `phase/3-speech-brain-rag`, using the completed Phase 2 realtime audio/turn layer as the base. Provider credentials remain optional for automated development, exact event facts remain deterministic, flexible knowledge uses hybrid FTS5 plus multilingual-E5 ONNX plus sqlite-vec RRF, and live voice acceptance remains deferred.

## Capability Map

| Module | Responsibility | Depends on |
|---|---|---|
| provider-contracts | provider errors, config, availability and adapters | Phase 2 contracts |
| structured-knowledge | SQLite schema, fixture, exact facts and FTS5 | provider-independent |
| dense-retrieval | E5 ONNX, sqlite-vec and RRF retrieval | structured-knowledge |
| conversation-brain | memory, grounding, persona, orchestration | structured-knowledge, dense-retrieval |
| voice-integration | PCM playback, STT/TTS streaming and brain runtime | provider-contracts, conversation-brain, Phase 2 voice |
| evaluation | demos, metrics, provider smoke and reports | all implementation modules |

Build order: provider-contracts -> structured-knowledge -> dense-retrieval -> conversation-brain -> voice-integration -> evaluation.

## Architecture Decisions

- Branch from Phase 2 HEAD `356d0a669ea50b9e1932ce772de9133b76e7ed56`; do not use stale `main`.
- Keep Pipecat `1.8.1` and Phase 2 VAD/Smart Turn settings unchanged.
- Use Speechmatics Arabic `ar` with external endpointing as primary STT and Deepgram Nova-3 `ar-EG` as fallback.
- Use Groq `openai/gpt-oss-120b` as primary LLM with `openai/gpt-oss-20b` same-provider fallback.
- Use Azure `ar-EG-ShakirNeural` at 16 kHz mono PCM as the male Egyptian TTS baseline.
- Route exact schedule/location/speaker/booth facts through structured SQLite without LLM invocation.
- Use FTS5 plus multilingual-E5-small ONNX 384d plus sqlite-vec `0.1.9`, fused with RRF `k=60`; no heavy reranker.
- Keep canonical chunks separate from rebuildable vec0 data and do not implement Phase 4 ingestion/package switching.
- Keep session memory in-process at 10 turns with a 300-second inactivity TTL and commit only delivered assistant text.

## Task List and Checkpoints

Tasks 0-1: branch safety, design synchronization and Phase 3 state.

Tasks 2-3: pinned dependencies, secret-safe configuration and provider availability.

Checkpoint A: config/dependency smoke and provider registry tests.

Tasks 4-6: Arabic normalization, SQLite/FTS5 repositories and deterministic fixture DB.

Checkpoint B: fixture DB exact routes and FTS5 tests.

Tasks 7-11: E5 ONNX, sqlite-vec, hybrid retrieval, exact resolver and RAG benchmark.

Checkpoint C: vector health, fixture exact correctness, Recall@5 and MRR gates.

Tasks 12-14: memory, grounding/persona/chunking and degraded orchestrator.

Checkpoint D: exact/no-evidence/prompt-injection/degradation tests.

Tasks 15-18: Groq, Speechmatics, Deepgram and Azure adapters.

Checkpoint E: provider fakes and conditional credential-aware smoke behavior.

Tasks 19-20: interruptible PCM playback and VoiceBrainRuntime integration.

Checkpoint F: synthetic end-to-end voice/brain/cancellation path.

Tasks 21-22: text demo and non-interactive provider smoke.

Task 23: final automated/RAG gate; real provider/model checks are reported honestly.

Tasks 24-25: Final Voice Acceptance update, Phase 3 report, Master Plan v1.11, README, push and stop before Phase 4.

## Verification Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe scripts\phase3\build_demo_db.py
.\.venv\Scripts\python.exe scripts\phase3\benchmark_rag.py
.\.venv\Scripts\python.exe scripts\phase3\provider_smoke.py --all-configured
```

Additional gates: dependency import smoke, `vec_version() == 0.1.9`, config/dependency prohibition scans, secret review, `git diff --check`, and no tracked generated artifacts.

## Boundaries

- Always: preserve Phase 1/2 evidence, keep credentials out of files, test each increment, and stop before Phase 4.
- Ask first: architecture changes, provider changes beyond the approved baseline, or any Phase 4/5 work.
- Never: rerun repeated human voice gates, tune Phase 2 VAD/Smart Turn, add PyTorch/Docling, claim production voice readiness, or commit secrets.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Optional SDK API differs by pinned version | High | Inspect installed public signatures and isolate behind adapter factories. |
| E5 assets unavailable | Medium | Keep lexical retrieval healthy; mark real dense validation deferred and use deterministic fake vectors only for algorithm tests. |
| sqlite-vec portability | High | Treat vec0 as rebuildable derived cache and record the target-platform rebuild rule. |
| Provider credentials absent | Medium | Keep imports/startup credential-free and report conditional smoke as skipped. |
| Provider failure | High | Use typed availability/errors and exact/evidence-only degraded routes. |
| Human voice acceptance deferred | Medium | Preserve the permanent Final Voice Acceptance tracker and do not call automated tests acoustic acceptance. |

## Open Questions

- Final provider quality, latency, and subjective Egyptian voice acceptance remain deferred to later validation.
- Real E5 retrieval metrics are conditional on model assets being available in the environment.

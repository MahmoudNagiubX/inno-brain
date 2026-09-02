# Phase 3 Report

## Final State

`PHASE_3_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`

## Repository

- Base Phase 2 HEAD: `356d0a669ea50b9e1932ce772de9133b76e7ed56`
- Branch: `phase/3-speech-brain-rag`
- Final HEAD: recorded after the final documentation commit and push

## Dependencies

- Pipecat: `1.8.1`
- Speechmatics Voice: `0.2.8` (`speechmatics-rt 1.1.1`)
- Deepgram SDK: `7.8.0`
- Azure Speech: `1.51.2`
- sqlite-vec: `0.1.9` (runtime reported `v0.1.9`)
- ONNX Runtime: `1.24.3`
- Tokenizers: `0.23.1`

## Provider Baseline

- STT primary: Speechmatics Voice, Arabic API language `ar`, external endpointing
- STT fallback: Deepgram Nova-3, `ar-EG`, linear16 16 kHz mono PCM
- LLM: Groq `openai/gpt-oss-120b`, fallback `openai/gpt-oss-20b`
- TTS: Azure `ar-EG-ShakirNeural`, raw 16 kHz mono PCM
- Embedding: `intfloat/multilingual-e5-small`, pinned revision `614241f`, ONNX CPU, 384 dimensions

## Structured Knowledge

- Schema: canonical SQLite event tables, FTS5 external-content index, and rebuildable vec0 index
- Exact fixture queries: `3/3` deterministic checks passed (`100%`)
- FTS5: available and synchronized by chunk insert/update/delete triggers

## Hybrid RAG

- Real E5 model loaded: No. The explicit Hugging Face asset attempt timed out; real-model validation is deferred.
- Embedding dimension: configured and enforced as `384`; synthetic vector-store tests passed.
- Algorithmic/fixture benchmark: `HYBRID_ALGORITHM_TEST=PASS`
- Recall@5: `0.9375` across 16 deterministic queries
- MRR: `0.9375`
- RRF k: `60`
- `REAL_E5_RETRIEVAL_TEST`: deferred

## Automated Verification

- pytest: `57 passed, 1 skipped` (the real E5 test is opt-in)
- Ruff: passed for `src`, `tests`, and `scripts`
- Provider smoke: all four providers returned `SKIPPED_MISSING_CREDENTIAL` under `--all-configured`
- sqlite-vec version probe: `v0.1.9`
- Heavy dependency scan: no PyTorch, torchaudio, sentence-transformers, langchain, or llama-index matches
- Secret-pattern scan: no matches
- Generated artifact tracking: no `artifacts` or `recordings` files tracked

## Degraded Behavior

- STT: credential-gated adapters and preferred Speechmatics/Deepgram availability reporting; no-key startup remains safe
- LLM: Groq primary/fallback adapter; missing or failed LLM returns local evidence-only response
- TTS: Azure adapter preserves text result when synthesis is unavailable
- Vector: embedding/vector failures fall back to lexical FTS5 retrieval

## Deferred

- human voice acceptance and natural Egyptian STT quality
- Arabic/English code-switch and event proper-name acceptance
- subjective Shakir naturalness and real TTS first-audio latency
- spoken exact-fact/RAG Q&A, real-TTS barge-in, and interrupted-memory acceptance
- Raspberry Pi 5 + Anker S330 validation
- real E5 model retrieval benchmark
- live provider smoke with credentials
- noisy event and final provider bake-off

Phase 4 is authorized by the passing automated/RAG gates and the defined deferred-validation state. Phase 4 work was not started.

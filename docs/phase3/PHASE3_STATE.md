# Phase 3 State

**Phase:** 3 - Speech + Brain + Grounded RAG
**Branch:** `phase/3-speech-brain-rag`
**Status:** `PHASE_3_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`
**Last completed task:** Task 25
**Next task:** Phase 4 - authorized, not started
**Development platform:** Windows laptop
**Primary language:** Egyptian Arabic
**STT primary:** Speechmatics - adapter implemented; smoke skipped, missing `SPEECHMATICS_API_KEY`
**STT fallback:** Deepgram Nova-3 - adapter implemented; smoke skipped, missing `DEEPGRAM_API_KEY`
**LLM:** Groq `openai/gpt-oss-120b` - adapter implemented; smoke skipped, missing `GROQ_API_KEY`
**TTS:** Azure `ar-EG-ShakirNeural` - adapter implemented; smoke skipped, missing Azure key/region
**RAG:** SQLite structured + FTS5 + sqlite-vec 0.1.9 + RRF implemented; fixture Recall@5 0.9375, MRR 0.9375; real E5 deferred
**Provider smoke:** all four explicitly skipped with `SKIPPED_MISSING_CREDENTIAL`
**Live voice acceptance:** deferred
**Pi/S330:** deferred
**Phase 4 authorized:** Yes - after passing automated/RAG gates; not started

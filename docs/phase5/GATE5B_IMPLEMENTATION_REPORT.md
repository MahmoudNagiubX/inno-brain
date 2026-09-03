# Gate 5B Pre-Voice Remediation Implementation Report

## Outcome

- State: `GATE_5B_IMPLEMENTATION_COMPLETE_REVIEW_PENDING`
- Audit baseline: `f5d97ec39f43da2f02ee4d54b90b387991ef8553`
- Implementation HEAD before final documentation:
  `920899c123098d704024f63dfe1e225fd4ae623d`
- Branch: `phase/5b-remediation`
- Gate 5C: blocked pending a separate GPT-5.6 Sol re-review
- Real provider calls: not run
- Human microphone tests: not run
- Robot, Screen, and ROS work: not started

This report records implementation evidence. It does not independently declare
the audit findings closed and does not set `READY_FOR_PHASE5_VOICE`.

## Original blocker to regression evidence

| Original blocker | Implemented boundary | Regression evidence |
|---|---|---|
| P0 archive TOCTOU | Verification, signature acceptance, extraction, and source preservation use one owned open archive; every extracted member is size- and SHA-256-checked while written. | `tests/security/event/test_archive_toctou.py` |
| P1 production entrypoint | `ProviderBundle`, `InnoBrainApplication`, `build_application()`, and offline `python -m innobrain check` form one production-intent composition and lifecycle boundary. | `tests/unit/providers/test_provider_factory.py`, `tests/integration/test_application.py`, `tests/unit/test_cli.py` |
| P1 event-brain rebind | `ActiveKnowledgeBinding` swaps an immutable resolver/retriever snapshot; each answer takes one snapshot; switching resets memory before closing the prior context. | `tests/e2e/event/test_event_switch_no_leak.py` |
| P1 STT async/turn isolation | SDK callbacks bridge via the owning loop, blocking Deepgram operations run off-loop, and monotonic turn buffers aggregate final segments while rejecting stale events. | `tests/unit/providers/test_transcript_buffer.py`, `test_speechmatics_stt.py`, `test_deepgram_stt.py` |
| P1 STT failover | Speechmatics remains primary and Deepgram fallback; startup/pre-first-audio failures can switch immediately, while mid-turn failures fail that turn without replay and switch on the next turn. | `tests/unit/providers/test_stt_failover.py` |
| P1 barge-in cancellation | Local playback abort occurs first; LLM and TTS cancellation then run concurrently under bounded waits; late PCM writes are rejected by tests. | `tests/integration/voice/test_barge_in_cancellation_order.py`, `tests/unit/providers/test_groq_llm.py` |
| P1 state recovery | STT, brain, TTS, playback, background-task, and shutdown failures are observed, cleaned up, and recover to `LISTENING` or `IDLE` without returning stale answers. | `tests/integration/voice/test_failure_recovery.py` |
| P1 memory carry-over | Exact-answer entities propagate through `BrainResult`, commit only after delivery, and feed deterministic unambiguous follow-ups; ambiguous entities are not guessed. | `tests/unit/knowledge/test_structured_resolver.py`, `tests/unit/conversation/test_orchestrator.py` |

## Included first-live correctness support

- Hybrid lexical and dense results use one injected reference clock and exclude
  expired or future chunks after fusion and before evidence rendering.
- Structured runtime observations cover turn/state/provider/event/route,
  evidence count, barge-in/fault stage, and monotonic timing markers without
  logging raw transcripts or credential values.
- The exact production graph test keeps real turn runtime, voice runtime,
  failover owner, knowledge binding, resolver, retriever, orchestrator, and
  session memory while replacing only provider-network and audio-device edges.
- The graph proves audio forwarding, transcript finalization, exact answers,
  second-turn entity follow-up, TTS PCM, playback, memory commit, interruption,
  failure recovery, and return to `LISTENING`.

## Fresh verification evidence

Executed on the Windows laptop on 2026-09-03:

| Gate | Result |
|---|---|
| `python -m pytest -q` | `192 passed, 2 skipped, 1 warning` |
| `python -m ruff check src tests scripts` | pass |
| `python -m pip check` | no broken requirements |
| `git diff --check` | pass |
| `python -m pytest tests\security\event -q` | `2 passed` |
| `python -m innobrain check` | completed offline; no network or audio stream |

The two expected skips remain the builder-only Docling test and opt-in real E5
model test. The warning is the expected duplicate-ZIP-name adversarial fixture
warning.

The offline check enumerated 20 laptop audio devices with default input index 1
and output index 3. It reported `not_ready` because this checkout has no active
runtime event, local E5 assets, or provider credentials. No secret values were
printed, no provider network request was made, and no microphone stream opened.

## Preserved validation debt and stop boundary

All prior live provider, controlled Egyptian interaction, live barge-in,
end-to-end acoustic, Raspberry Pi 5, and Anker S330 validation debt remains.
Gate 5C may begin only if the separate Sol re-review of the audit baseline
against the pushed remediation branch determines that P0 and P1 are both zero.

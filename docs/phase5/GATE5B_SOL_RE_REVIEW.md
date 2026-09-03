# Gate 5B Targeted Sol Re-review

**Status:** `GATE_5B_RE_REVIEW_BLOCKED`

**Original audit HEAD:** `f5d97ec39f43da2f02ee4d54b90b387991ef8553`

**Remediation HEAD reviewed:** `f1c93a460ddf4819f4703073bdbaa8859e6c0527`

**Review branch:** `review/gate5b-sol-rereview`

**Scope:** Targeted re-review of the original P0 and seven P1 findings only.
No broad A-to-Z audit, production-code change, real provider call, microphone
test, Gate 5C execution, Robot, Screen, or ROS work was performed.

## Verdict

Gate 5C is **not authorized**. The archive P0 is closed, but three original P1
findings are only partially closed. The required condition P0=0 and P1=0 with
no new blocking regression is therefore not met, and
`READY_FOR_PHASE5_VOICE` is not recorded.

| Original blocker | Re-review result |
|---|---|
| P0: verified archive bytes can differ from extracted bytes | **CLOSED** |
| P1: no production-intent application constructs the complete voice graph | **CLOSED** |
| P1: active event switching does not replace the brain's knowledge objects | **PARTIALLY CLOSED** |
| P1: STT adapters are not async-safe, turn-isolated streams | **PARTIALLY CLOSED** |
| P1: configured Speechmatics-to-Deepgram fallback is not a runtime fallback | **CLOSED** |
| P1: barge-in delays playback stop behind response cancellation | **CLOSED** |
| P1: response failures can be silent and leave state `SPEAKING` | **PARTIALLY CLOSED** |
| P1: session memory is not wired for exact entity carry-over | **CLOSED** |

Result: P0 fully open `0`; P1 fully open or partially closed `3`.

## Finding-by-finding evidence

### P0 archive TOCTOU — CLOSED

`VerifiedArchive` retains one open file handle and `ZipFile` from validation
through extraction (`src/innobrain/event/validation.py:49-80,124-222`). The
extractor streams each authenticated member and rechecks size and SHA-256 while
writing (`src/innobrain/event/archive.py:131-176`). Installation extracts and
copies the source package through that same verified object
(`src/innobrain/event/installer.py:276-278`). Adversarial regressions replace the
path after verification and tamper with extracted member bytes
(`tests/security/event/test_archive_toctou.py:17-77`). Both targeted security
tests pass.

### P1 production-intent application — CLOSED

`InnoBrainApplication` now owns the provider bundle, active event context,
knowledge binding, session memory, orchestrator, playback, and
`VoiceBrainRuntime`, with rollback-safe start/stop ownership
(`src/innobrain/app.py:20-119`). `python -m innobrain check` builds this graph;
the `run` path intentionally remains refused until Gate 5C authorization
(`src/innobrain/cli.py:74-92`). Composition and lifecycle are tested in
`tests/integration/test_application.py:58-98`, and the production graph with
fake external boundaries passes in
`tests/integration/voice/test_real_graph_with_fake_boundaries.py:152-230`.

### P1 active-event brain rebind — PARTIALLY CLOSED

The standalone mechanism is sound in the tested path: `RuntimeContextSwitcher`
opens a new read-only context, swaps the `ActiveKnowledgeBinding`, resets memory,
and closes the prior context (`src/innobrain/event/runtime.py:65-103`), while the
orchestrator takes one binding snapshot per answer
(`src/innobrain/conversation/orchestrator.py:59-67`). The Alpha to Beta to
rollback zero-leak regression passes
(`tests/e2e/event/test_event_switch_no_leak.py:57-94`).

The production application does not own or construct a `RuntimeContextSwitcher`
and does not provide its switch hook to an `ActivationManager`.
`_open_configured_event()` calls `ActivationManager(...).active()` only, then
`build_application()` creates a one-time knowledge binding
(`src/innobrain/app.py:56-100`). Consequently an event activated while the
production application is alive is not guaranteed to rebind the brain. The
original production-path blocker remains.

### P1 async-safe, turn-isolated STT — PARTIALLY CLOSED

Thread-to-loop mutation and per-turn buffering were added through
`call_soon_threadsafe` and active-turn rejection
(`src/innobrain/providers/transcript_buffer.py:22-87`). Deepgram blocking calls
were moved through `asyncio.to_thread`
(`src/innobrain/providers/deepgram_stt.py:103-171`).

Speechmatics turn mapping is still incorrect for the installed
`speechmatics-voice==0.2.8` callback model. SDK `SegmentMessage` has no
`turn_id`, while end-of-turn IDs start at zero and increment. The adapter uses
`_message_turn_id(message) or self._active_turn_id` for all callbacks
(`src/innobrain/providers/speechmatics_stt.py:161-174`). SDK turn ID `0` is
therefore replaced with application turn ID `1`; on the second turn, SDK ID `1`
is treated as application ID `1` and rejected by the buffer for active
application turn ID `2`. An offline installed-shape diagnostic produced:

```text
FIRST 1 turn-0
SECOND ProviderTimeout Speechmatics did not return a final segment
```

The regression doubles inject non-SDK `turn_id` fields into segment callbacks
and cover only one successful normal turn
(`tests/unit/providers/test_speechmatics_stt.py:33-40,52-74,84-111`). They do
not catch this real multi-turn mismatch. Turn isolation is therefore not ready
for real voice execution.

### P1 runtime STT failover — CLOSED

`FailoverSTTProvider` now handles primary startup failure, pre-audio failover,
and safe next-turn failover after mid-turn/final failure without replaying
accepted PCM (`src/innobrain/providers/stt_failover.py:39-152`). The matching
boundary cases and cleanup are covered in
`tests/unit/providers/test_stt_failover.py:89-166`. This finding is closed
independently of the remaining Speechmatics adapter turn-mapping defect above.

### P1 barge-in cancellation ordering — CLOSED

For `SPEAKING`, interruption transitions first, awaits local playback cancel,
then cancels the response and returns to listening
(`src/innobrain/voice/interruption.py:34-49`). Response cancellation explicitly
cancels the owned response task and invokes bounded LLM/TTS cancellation
(`src/innobrain/voice/brain_runtime.py:99-131`). Delayed/hung cancellation and
write-after-cancel races pass
(`tests/integration/voice/test_barge_in_cancellation_order.py:131-181`).

### P1 failure recovery — PARTIALLY CLOSED

Normal final-STT and post-first-PCM TTS failures are now observed, cleaned up,
and tested to return to listening
(`tests/integration/voice/test_failure_recovery.py:129-164`). However,
`_handle_fault()` awaits playback and provider cleanup before its state recovery
transition, without a recovery `finally`; cancellation helpers suppress only
`CancelledError` and timeout, not provider exceptions
(`src/innobrain/voice/brain_runtime.py:127-132,234-255`). The interruption path
has the same transition-after-cleanup structure
(`src/innobrain/voice/interruption.py:38-48`).

An offline diagnostic that made `playback.cancel()` raise after a TTS failure
produced:

```text
PROPAGATED RuntimeError speaker cleanup failed
STATE SPEAKING
```

There is no regression test for cleanup/cancellation exceptions. The requested
state-recovery guarantee is therefore incomplete.

### P1 exact entity follow-ups — CLOSED

`BrainResult` carries typed entities, exact results preserve them, and
`commit_delivered()` stores delivered result entities
(`src/innobrain/conversation/orchestrator.py:27-27,65-80,154-183`). Exact
resolution receives `SessionMemory.active_entities()`
(`src/innobrain/conversation/orchestrator.py:65-68`). Two-turn exact follow-up,
ambiguity rejection, and production-graph two-turn tests pass
(`tests/unit/knowledge/test_structured_resolver.py:72-104` and
`tests/integration/voice/test_real_graph_with_fake_boundaries.py:152-192`).

## Fresh verification

All commands ran from remediation HEAD `f1c93a460ddf4819f4703073bdbaa8859e6c0527`
on the documentation-only review branch before documentation changes.

| Check | Result |
|---|---|
| `.venv\\Scripts\\python.exe -m pytest -q` | `192 passed, 2 skipped, 1 warning in 11.30s` |
| `.venv\\Scripts\\python.exe -m ruff check src tests scripts` | PASS |
| `.venv\\Scripts\\python.exe -m pip check` | PASS |
| `git diff --check` and audit-to-remediation `git diff --check` | PASS |
| `pytest tests\\security\\event -q` | `2 passed in 1.20s` |
| application and production-graph integration tests | `4 passed in 5.63s` |
| targeted original-blocker regressions | `29 passed in 5.39s` |

The green suite contains no new blocking regression in its covered behavior,
but it does not invalidate the two reproduced gaps or the missing production
event-switch wiring. Gate 5C, real providers, and human voice remain stopped.

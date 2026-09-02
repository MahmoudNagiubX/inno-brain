# Pre-Phase-5 GPT-5.6 Sol System Audit

## 1. Executive Verdict

`REMEDIATION_REQUIRED_BEFORE_PHASE5_VOICE`

The Phase 1–4 repository contains substantial, generally well-separated
building blocks, and its fresh automated suite is green. It is not yet safe to
run the first controlled real end-to-end voice conversation. The highest-risk
fact is not test count: no production-intent entrypoint constructs the complete
microphone → turn detection → STT → active-event brain/RAG → LLM → TTS →
speaker graph. Static and targeted runtime review also found one package
verification bypass class and seven blocking integration defects.

Per the approved Gate 5A rule, Phase 5 Gate 5C is blocked. Gate 5B must address
all P0/P1 findings in a separate change. This audit did not repair code.

## 2. Baseline

- Required source branch: `phase/4-dynamic-event-package`
- Reviewed source SHA: `cc6addddc18a829deaf6a5e8155a157d9edf8c61`
- Remote baseline SHA: `cc6addddc18a829deaf6a5e8155a157d9edf8c61`
- Review branch: `review/pre-phase5-sol-audit`
- Master Plan after approved roadmap-only commit: v1.14
- Pytest: `148 passed, 2 skipped, 1 warning in 4.50s`
- Ruff: PASS
- `pip check`: PASS
- `git diff --check`: PASS
- Phase 2 dependency smoke: PASS
- Phase 2 synthetic cancellation harness: PASS; not acoustic acceptance
- Phase 3 RAG on a fresh temporary database: Recall@5 `0.9375`, MRR `0.9375`
- Phase 4 real Docling/E5 signed smoke in temporary directories: PASS
- Live provider and human microphone checks: not run

The first default Phase 3 benchmark invocation failed because its ignored
default database predated schema v2. A fresh database passed. This is recorded
as a reproducibility finding, not a RAG algorithm failure.

## 3. Architecture Verdict

The intended modular-monolith boundaries mostly exist, but composition is
unfinished.

| Module | Responsibility and public surface | Incoming → outgoing dependencies | Real runtime wiring |
|---|---|---|---|
| `audio` | device helpers, WAV I/O, `SoundDevicePCMStream` | sounddevice callback → bounded asyncio queue | Wired into `RealtimeTurnRuntime`; input device is configurable |
| `config` | strict YAML models and loader | YAML → typed runtime/provider/persona values | Runtime settings are partly consumed; provider settings are mostly descriptive |
| `voice` | Pipecat VAD/Smart Turn, state, interruption, playback, `VoiceBrainRuntime` | audio → STT/orchestrator/TTS/playback | Integration class exists, but no real factory/entrypoint constructs it |
| `providers` | STT/LLM/TTS contracts and four adapters | environment credentials → external SDKs | Used independently in smoke scripts; no complete provider router/composition |
| `conversation` | exact/RAG routing, grounding, memory, chunking | resolver/retriever/LLM → `BrainResult` | Used in text demo and fake voice test; not bound to active event switching |
| `knowledge` | event SQLite, exact resolver, FTS5/E5/vec/RRF | read-only event DB → evidence | Correctly used by standalone event context and text demo |
| `event` | signed package lifecycle and active context | package/registry → read-only repository/retriever | Standalone switching works; live brain references are not rebound |
| `robot` | future scaffold | none | Not implemented, correctly deferred to Phase 6 |
| `telemetry` | basic logger setup | Python logging | No turn/provider/latency instrumentation is wired |

Provider-specific code remains mostly behind contracts, and Windows device IDs
do not leak into conversation logic. The principal architectural split is that
Phase 2 voice, Phase 3 brain/providers, and Phase 4 active-event context remain
parallel compositions rather than one owned application lifecycle.

## 4. End-to-End Composition Verdict

The source supports this hypothetical call chain:

```text
SoundDevicePCMStream.chunks()
  → RealtimeTurnRuntime._feed_audio()
  → VoiceBrainRuntime._on_audio_chunk()
  → one injected STTProvider.stream_audio()
  → Pipecat VADProcessor + Smart Turn UserTurnProcessor
  → VoiceBrainRuntime._on_turn_event(USER_TURN_STOPPED)
  → injected STTProvider.final_text()
  → injected GroundedOrchestrator.answer()
      → StructuredResolver, else HybridRetriever
      → injected LLMProvider for grounded evidence
  → complete BrainResult text
  → SentenceChunker
  → injected TTSProvider.stream()
  → PCMStreamPlaybackController
```

The construction trace stops before runtime: `VoiceBrainRuntime` is instantiated
only by an integration test using fakes. `text_demo.py` constructs a fixture
database/orchestrator but no audio, STT, TTS, or playback. Provider smoke
constructs each external adapter independently. Phase 4 smoke constructs an
active context but no resolver, orchestrator, or voice runtime. There is no
application entrypoint, factory, lifecycle owner, or test for the actual graph.

Boundary ownership is therefore fragmented. Audio and turn lifecycle belong to
`RealtimeTurnRuntime`; response lifecycle belongs to `VoiceBrainRuntime`;
active-event lifecycle belongs to `RuntimeContextSwitcher`; provider selection
is merely reported by `ProviderRegistry`. Nothing owns all four consistently.

## 5. Findings Summary

| Severity | Count |
|---|---:|
| P0 | 1 |
| P1 | 7 |
| P2 | 9 |
| P3 | 3 |

## 6. Blocking Findings

### [P0] Verified archive bytes can differ from extracted archive bytes

**Area:** Security / Event

**Evidence:**
- `src/innobrain/event/validation.py:75-76`
- `src/innobrain/event/validation.py:127-148`
- `src/innobrain/event/archive.py:102-150`
- `src/innobrain/event/installer.py:266-272`

**What happens:** Package verification opens the supplied path, validates the
signature and payload hashes, then calls `extract_validated_archive()`. That
function reopens the path and checks names/declared sizes, but does not recheck
payload hashes while extracting. On platforms that permit atomic path
replacement, a local process able to write the package directory can replace
the file between those opens with an archive having the same names and sizes.
The replacement payload is then extracted although its bytes were never
covered by the accepted signature/hash pass.

**Why it matters:** This crosses the core untrusted-package boundary and can
install content different from the content authenticated by Ed25519. It is a
package verification bypass, which is P0 under the audit rubric.

**Recommended direction:** Verify and extract from one immutable staged file or
one already-open handle, and validate every digest while writing extracted
bytes. Add an adversarial path-replacement regression test.

**Blocks real voice test:** Yes

### [P1] No production-intent application can construct the complete voice graph

**Area:** Architecture / Voice

**Evidence:**
- `src/innobrain/voice/brain_runtime.py:17-54`
- `scripts/phase3/text_demo.py:21-39`
- `tests/integration/voice/test_brain_runtime.py:15-96`
- `pyproject.toml:5-38`
- Symbol search found no production `VoiceBrainRuntime` construction and no project script entrypoint.

**What happens:** The composition class requires injected STT, orchestrator,
TTS, and playback objects, but only the fake integration test supplies them.
Separate demos cover turn detection, text RAG, providers, and event switching.

**Why it matters:** The requested live process cannot be launched without new
source code. Startup, shutdown, active-event selection, provider selection, and
resource cleanup have no common owner.

**Recommended direction:** Add one production-intent factory/entrypoint in Gate
5B that consumes typed config, opens the active event, constructs every real
adapter, and owns deterministic start/stop rollback. Test that exact graph with
external boundaries substituted, not internal layers replaced.

**Blocks real voice test:** Yes

### [P1] Active event switching does not replace the brain's knowledge objects

**Area:** Event / Brain / RAG

**Evidence:**
- `src/innobrain/event/runtime.py:54-71`
- `src/innobrain/conversation/orchestrator.py:28-42`
- `tests/e2e/event/test_event_switch_no_leak.py:64-85`

**What happens:** The switcher replaces only `switcher.current`. A
`GroundedOrchestrator` retains the resolver and retriever passed at construction.
The two-event test queries `switcher.current.repository` directly; it never
constructs or switches an orchestrator or `VoiceBrainRuntime`.

**Why it matters:** A future voice process can keep answering from the old event
after activation, or hold a repository whose connection was closed. Standalone
zero-leak context tests do not prove live-brain isolation.

**Recommended direction:** Make one composition owner atomically replace the
resolver/retriever used by the brain at an idle boundary, then close the old
context and test voice-level Alpha → Beta → rollback queries.

**Blocks real voice test:** Yes

### [P1] STT adapters are not async-safe, turn-isolated streams

**Area:** STT / Concurrency

**Evidence:**
- `src/innobrain/providers/deepgram_stt.py:76-103`
- `src/innobrain/providers/deepgram_stt.py:108-137`
- `src/innobrain/providers/deepgram_stt.py:147-154`
- `src/innobrain/providers/speechmatics_stt.py:79-107`
- `.venv/Lib/site-packages/deepgram/listen/v1/client.py:75-76`
- `.venv/Lib/site-packages/deepgram/listen/v1/socket_client.py:132-185`
- `tests/unit/providers/test_deepgram_stt.py:6-56`

**What happens:** Deepgram 7.8.0's selected `listen.v1.connect()` and socket are
synchronous. Connection entry and every `send_media()` execute on the asyncio
loop, while callbacks are emitted by a listener running in a worker thread.
Those callbacks call `asyncio.Queue.put_nowait()` directly, which is not a
thread-safe bridge. Both STT adapters also put provider-final segments into one
unscoped queue and return one item per Smart Turn stop; they have no turn ID,
queue drain, or multi-segment aggregation. The fakes invoke one callback on the
event-loop thread and cannot expose either defect.

**Why it matters:** Real Deepgram traffic can stall VAD/cancellation, corrupt
queue coordination, or deliver a stale/partial prior segment as the next turn.
Speechmatics can likewise leave extra final segments for a later turn.

**Recommended direction:** Use the SDK's async transport or isolate all sync I/O,
bridge callbacks with `loop.call_soon_threadsafe`, and introduce explicit
per-turn transcript accumulation/finalization with stale-event rejection.

**Blocks real voice test:** Yes

### [P1] Configured Speechmatics-to-Deepgram fallback is not a runtime fallback

**Area:** STT / Config

**Evidence:**
- `config/providers.yaml:3-15`
- `src/innobrain/providers/registry.py:13-46`
- `src/innobrain/voice/brain_runtime.py:20-38`

**What happens:** The registry reports credentials and returns one initially
available provider name. It does not construct a router, monitor provider
failure, transfer a turn, or start the configured fallback. `VoiceBrainRuntime`
accepts exactly one STT object.

**Why it matters:** A Speechmatics connect/send/finalize failure terminates that
turn path instead of degrading to Deepgram as documented.

**Recommended direction:** Introduce a typed STT failover owner with explicit
safe boundaries for startup failure versus in-progress-turn failure, lifecycle
cleanup, health reporting, and tests using both adapters' real contracts.

**Blocks real voice test:** Yes

### [P1] Barge-in stops playback only after potentially slow response cancellation

**Area:** Voice / Cancellation

**Evidence:**
- `src/innobrain/voice/interruption.py:34-48`
- `src/innobrain/voice/brain_runtime.py:69-81`
- `src/innobrain/providers/groq_llm.py:65-96`
- `tests/unit/voice/test_interruption.py:42-66`

**What happens:** In `SPEAKING`, interruption awaits response cancellation,
including TTS cancellation, before calling playback cancellation. The test
explicitly locks in `response` then `playback`. During `THINKING`, canceling the
response task does not call the orchestrator's LLM provider `cancel()`; the Groq
generator clears its handle in `finally` without necessarily closing the
provider stream.

**Why it matters:** Network/provider cancellation latency can keep audible PCM
playing beyond the barge-in target, and canceled generation can remain
unaccounted for. The 0.032 ms synthetic result uses no response callback and
does not exercise this path.

**Recommended direction:** Abort local playback first, then cancel owned LLM/TTS
work concurrently with bounded waits; close provider streams explicitly and
test delayed/hung cancellation plus write-after-cancel races.

**Blocks real voice test:** Yes

### [P1] Response failures can be silent and leave the state permanently SPEAKING

**Area:** Voice / Observability

**Evidence:**
- `src/innobrain/voice/brain_runtime.py:96-122`
- `src/innobrain/voice/brain_runtime.py:127-130`
- Targeted diagnostic result: `STATE SPEAKING` after a TTS exception following first PCM.

**What happens:** A broad exception handler returns `last_result` without
logging. It returns to `LISTENING` only when the current state is `THINKING`.
Playback/TTS failure after first PCM leaves state `SPEAKING` and does not
guarantee stream cleanup. Final-transcript exceptions occur in an unobserved
background task and bypass this handler entirely.

**Why it matters:** One ordinary provider or speaker error can make subsequent
turns look like interruptions, hide the original cause, and strand the process
in an apparently active state.

**Recommended direction:** Use a top-level response lifecycle with typed error
recording and unconditional cleanup/state recovery. Observe every background
task result and preserve a structured degraded text result without replaying a
stale answer.

**Blocks real voice test:** Yes

### [P1] Session memory is stored but not functionally wired for entity carry-over

**Area:** Brain / Memory

**Evidence:**
- `src/innobrain/knowledge/structured_resolver.py:18-23`
- `src/innobrain/knowledge/structured_resolver.py:37-43`
- `src/innobrain/conversation/orchestrator.py:52-66`
- `src/innobrain/conversation/orchestrator.py:127-133`
- `src/innobrain/voice/brain_runtime.py:96-115`

**What happens:** Exact answers create entity IDs, but `BrainResult` does not
carry them. The live runtime calls `commit_delivered()` without entities, so
those IDs are lost. The structured resolver accepts only the current query and
does not consult `SessionMemory.active_entities()`. Memory text reaches the LLM
RAG prompt, but exact follow-ups such as “طب الساعة كام؟” cannot resolve the
previous structured entity deterministically.

**Why it matters:** The claimed conversational memory does not satisfy the
normal multi-turn exact-fact path required for Egyptian references. Existing
memory tests validate storage limits, not contextual resolution through the
voice composition.

**Recommended direction:** Preserve typed entities in the brain result and feed
validated active entities into exact resolution. Add a two-turn test through
the same composition intended for the live app.

**Blocks real voice test:** Yes

## 7. Important Non-Blocking Findings

### [P2] Retrieval does not apply validity windows in the actual hybrid path

**Area:** RAG

**Evidence:**
- `src/innobrain/knowledge/retrieval.py:57-83`
- `src/innobrain/knowledge/repository.py:129-172`
- `tests/unit/knowledge/test_phase4_schema.py:37-107`

**What happens:** The repository can exclude expired chunks only when a
`reference_time` is supplied. `HybridRetriever` never supplies one, and dense
IDs are fetched without a validity filter. Authority affects only lexical
tie-breaking, not fused conflict handling.

**Why it matters:** Controlled voice can run on curated current fixtures, but a
real event package can surface expired or lower-authority evidence.

**Recommended direction:** Apply one event-time/authority policy after fusion
and before evidence rendering, with dense and lexical regression cases.

**Blocks real voice test:** No

### [P2] Activation can diverge live context from the durable active pointer

**Area:** Event / Concurrency

**Evidence:**
- `src/innobrain/event/activation.py:109-128`
- `src/innobrain/event/runtime.py:62-71`
- `tests/integration/event/test_activation.py:72-87`

**What happens:** The switch hook commits the in-process context and closes the
old one before pointer replacement/history append. If either durable write
fails, the process uses the new event while disk still names the old event.

**Why it matters:** It weakens rollback/restart consistency, though it need not
block a controlled voice run that performs no event switch.

**Recommended direction:** Define one recoverable transaction order and restore
the old live context or fail before exposing the new context when persistence
fails.

**Blocks real voice test:** No

### [P2] Production CLI cannot load trusted event signing keys

**Area:** Config / Security

**Evidence:**
- `config/trusted_event_keys.yaml.example:1`
- `scripts/phase4/eventctl.py:60-67`
- `src/innobrain/event/validation.py:99-109`

**What happens:** Production policy requires a trusted key, but `eventctl`
constructs policy without loading any keys. The example trust file has no
consumer. Production `validate`/`install` therefore rejects every signed
package unless another Python caller manually builds policy.

**Why it matters:** This blocks normal event operations, not an isolated voice
attempt against a preinstalled fixture.

**Recommended direction:** Add strict public-key configuration loading and key
rotation semantics at the production composition boundary.

**Blocks real voice test:** No

### [P2] LLM output is fully buffered before TTS starts

**Area:** Brain / TTS / Performance

**Evidence:**
- `src/innobrain/conversation/orchestrator.py:92-107`
- `src/innobrain/voice/brain_runtime.py:96-109`

**What happens:** The orchestrator consumes the entire Groq stream into a list,
then returns one `BrainResult`; only afterward does sentence chunking and TTS
begin.

**Why it matters:** The implementation cannot meet a streaming time-to-first-
audio design under realistic LLM latency, although it can still perform a
controlled functional voice trial after blockers are fixed.

**Recommended direction:** Stream grounded text through the sentence chunker
while preserving a final committed answer and cancellation boundary.

**Blocks real voice test:** No

### [P2] Declared provider/audio configuration is not the construction authority

**Area:** Config / Platform

**Evidence:**
- `config/providers.yaml:3-44`
- `src/innobrain/providers/speechmatics_stt.py:58-72`
- `src/innobrain/providers/deepgram_stt.py:49-69`
- `src/innobrain/providers/azure_tts.py:23-40`
- `src/innobrain/voice/pcm_playback.py:12-27`

**What happens:** Provider model/language/voice/glossary values are hard-coded
inside adapters, and PCM playback has no output-device argument. The active
event glossary is not wired to either STT. YAML can change without changing
runtime behavior, and configured S330 output selection cannot be applied.

**Why it matters:** Laptop defaults can support a controlled test, but provider
changes and later Pi/S330 selection are brittle.

**Recommended direction:** Make the factory pass all validated settings and
active-event glossary values into adapters; reject unsupported combinations.

**Blocks real voice test:** No

### [P2] First live run has almost no actionable observability

**Area:** Observability

**Evidence:**
- `src/innobrain/telemetry/logging.py:1-26`
- `src/innobrain/voice/brain_runtime.py:56-130`
- `src/innobrain/conversation/orchestrator.py:92-114`

**What happens:** Logging configuration exists, but the voice/brain/providers do
not emit turn ID, provider, event ID/version, route, evidence IDs, first audio,
failure, cancellation, or shutdown events. Several degradation paths catch
exceptions without recording them.

**Why it matters:** Even after functional blockers are fixed, provider and
latency failures will be difficult to distinguish during the first live run.

**Recommended direction:** Add structured per-turn lifecycle events without raw
audio or secrets; ensure every caught provider exception is visible.

**Blocks real voice test:** No

### [P2] Dependency state is compatible locally but not reproducible or vulnerability-audited

**Area:** Dependencies / Security

**Evidence:**
- `pyproject.toml:10-38`
- Fresh `pip freeze`: 82 distributions
- `python -m pip_audit --version`: `No module named pip_audit`

**What happens:** Several critical dependencies use broad ranges and there is no
committed resolved lock. `pip check` proves metadata consistency only. No CVE
scanner was installed, and this review intentionally did not alter dependencies.

**Why it matters:** A rebuild can resolve a different transitive graph, and the
audit cannot claim absence of known vulnerabilities. Local Windows Python 3.14
success also does not prove Linux aarch64/Pi wheel availability.

**Recommended direction:** Establish one locked runtime and builder resolution,
run a supported vulnerability/license inventory in CI, and verify Linux
aarch64 installation separately.

**Blocks real voice test:** No

### [P2] Default RAG benchmark trusts an incompatible ignored database

**Area:** Tests / Developer Experience

**Evidence:**
- `scripts/phase3/benchmark_rag.py:59-70`
- `scripts/phase3/build_demo_db.py:16-36`
- Fresh default command failed with missing `chunks.authority_level`; a new temporary DB passed.

**What happens:** The benchmark rebuilds only when the ignored default DB is
absent, not when its schema is stale.

**Why it matters:** Fresh verification can fail or, for subtler schema drift,
measure old data. This does not invalidate the fresh temporary result.

**Recommended direction:** Build benchmarks in a fresh temporary database or
validate schema/build identity before reuse.

**Blocks real voice test:** No

### [P2] Voice startup and shutdown are not transactional

**Area:** Voice / Lifecycle

**Evidence:**
- `src/innobrain/voice/brain_runtime.py:56-67`
- `src/innobrain/voice/pipecat_runtime.py:145-188`

**What happens:** STT starts before turn runtime without rollback if microphone
or Pipecat startup fails. Shutdown stops STT before stopping capture/feed. The
turn runtime marks analyzers cleaned permanently but allows another `start()`
call on the same object.

**Why it matters:** Failed startup or restart can leak provider resources or
send audio into a stopped STT connection. A single well-behaved launch may
work, so this remains P2 behind the larger composition blockers.

**Recommended direction:** Give the application owner transactional startup in
reverse-cleanup order, stop capture before STT, and define restartability or
enforce single-use instances.

**Blocks real voice test:** No

## 8. Minor Debt

| Severity | Evidence | Debt |
|---|---|---|
| P3 | `src/innobrain/voice/playback.py:18-99`; `src/innobrain/voice/pcm_playback.py:9-69` | Two sounddevice playback abstractions have different ownership/cancellation semantics. Keep the tone harness explicitly dev-only and select one production playback boundary. |
| P3 | `config/runtime.yaml:31-34`; `src/innobrain/config/models.py:38-41` | Phase 2 mock-think/tone settings remain in the core runtime model although only the demo harness needs them. |
| P3 | `README.md:35-36`; `docs/phase3/PHASE3_REPORT.md:8` | README still says generic “Phase 5 authorized,” and the Phase 3 report retains a final-HEAD placeholder. They are historical/documentation cleanup, not runtime blockers. |

## 9. Critical Readiness Questions

| # | Question | Answer | Evidence summary |
|---:|---|---|---|
| 1 | Single production-intent application entrypoint? | NO | No real `VoiceBrainRuntime` construction or project entrypoint |
| 2 | Complete live graph constructible without source edits? | NO | Separate demos only |
| 3 | Mic PCM wired into selected STT? | PARTIAL | Callback exists; no selected-provider composition |
| 4 | Smart Turn is turn authority? | YES | Pipecat VAD start + Smart Turn stop, `wait_for_transcript=False` |
| 5 | Final transcript wired into brain? | PARTIAL | `VoiceBrainRuntime` does so for one injected STT; no real graph |
| 6 | Active event wired into exact resolver/RAG? | NO | Context switcher is not bound to orchestrator |
| 7 | Groq wired into grounded RAG generation? | PARTIAL | Orchestrator supports injection; text demo optional only |
| 8 | Shakir TTS wired into PCM playback? | PARTIAL | Compatible interfaces; no real construction path |
| 9 | Barge-in coherently cancels response/TTS/playback? | NO | Playback cancellation is delayed; LLM cancel not propagated |
| 10 | Provider failures diagnosable? | NO | Broad silent handlers and no turn telemetry |
| 11 | Process shuts down cleanly? | PARTIAL | Synthetic Pipecat test passes; full lifecycle has ordering gaps |
| 12 | Session memory correct across normal turns? | PARTIAL | Bounded text storage works; exact entity carry-over does not |
| 13 | Memory safe across interruption? | YES | Delivery commit occurs only after playback completion; cancellation re-raises |
| 14 | Memory reset on event switch? | YES | Standalone switcher resets shared memory |
| 15 | Event switch replaces knowledge context used by brain? | NO | No orchestrator rebinding |
| 16 | Safe to attempt controlled real voice testing? | NO | P0/P1 findings and no executable graph |
| 17 | Event-production-ready today? | NO | Live providers/voice, Pi/S330/noise and security/remediation remain |

## 10. Test Confidence

The 150-test suite gives strong confidence in strict authoring, package
structure checks, signatures under non-racing conditions, target-local DB
compilation, read-only access, retrieval algorithms, standalone event
switching, and small state/cancellation units. The fresh Phase 4 real
Docling/E5 smoke is valuable production-like evidence for the builder/runtime
package path.

Confidence is low at integration seams. The only `VoiceBrainRuntime` test
replaces PCM input, STT, orchestrator, TTS, and playback with fakes. Provider
tests use simplified callbacks and do not model Deepgram's synchronous listener
thread. No test constructs the expected application graph, binds active-event
switching to the orchestrator, runs multi-turn exact references, injects slow
provider cancellation, fails playback after first PCM, or checks pointer-write
failure after a live context switch. The live provider, subjective Egyptian
speech, acoustic barge-in, and Pi/S330 evidence remains correctly deferred.

## 11. Documentation Claim Audit

| Material claim | Status | Evidence |
|---|---|---|
| Phase 1 laptop capture/playback and user listening pass | VERIFIED | Phase report, retained WAV path, current audio unit coverage; not rerun by policy |
| Pi/S330 production validation deferred | DEFERRED AS DOCUMENTED | Master Plan and Final Voice Acceptance |
| Phase 2 Pipecat/Silero/Smart Turn implementation | VERIFIED | Dependency smoke and synthetic pipeline tests |
| Phase 2 Egyptian hesitation/live barge-in accepted | DEFERRED AS DOCUMENTED | Explicitly not claimed |
| Phase 3 provider adapters implemented | VERIFIED | Source and unit tests |
| Phase 3 Speechmatics → Deepgram runtime fallback | CONTRADICTED | Registry selects availability only; no failover router |
| Phase 3 exact/RAG/no-evidence behavior | PARTIALLY VERIFIED | Fresh RAG benchmark passes; validity and live composition gaps remain |
| Phase 3 session memory supports contextual entities | PARTIALLY VERIFIED | Storage/TTL pass; exact carry-over is not wired |
| Real E5 later validated in Phase 4 | VERIFIED | Fresh real builder smoke passed |
| Phase 4 signed package and standalone zero-leak switching | PARTIALLY VERIFIED | Fresh smoke passes; verify/extract TOCTOU and live-brain rebinding gaps remain |
| Phase 4 complete means event-production-ready | NOT CLAIMED | Report correctly preserves validation debt |
| Current voice/provider acceptance complete | DEFERRED AS DOCUMENTED | Final tracker remains deferred |

## 12. Recommended Next Action

Proceed only to Gate 5B on a separate remediation branch/plan. Fix and prove the
P0 package boundary first, then create the single application composition and
address all remaining P1 findings with seam-level tests. Re-run the full suite,
security matrix, real Phase 4 smoke, and a keyless synthetic full-graph test.
Only a follow-up review finding P0=0 and P1=0 may authorize Gate 5C real
provider/voice execution.

Do not start Robot, Screen, or ROS work during remediation.

## 13. Explicitly Deferred

- Live Speechmatics, Deepgram, Groq, and Azure behavior because credentials were not used
- Subjective Egyptian STT accuracy and Shakir TTS quality
- Real end-to-end first-audio latency
- Real acoustic barge-in and post-interruption conversation
- Raspberry Pi 5 and Anker PowerConf S330 compatibility
- Noisy-event and multi-hour operation
- Final provider bake-off and event-production acceptance
- A current CVE-database verdict; no audit scanner was installed in this review

# InnoBrain — Pre-Gate 5C.1 Full System Audit

**Audit date:** 2026-09-12 (Africa/Cairo)
**Repository:** `MahmoudNagiubX/inno-brain`
**Audited branch:** `phase/5c0-wake-attention`
**Audit mode:** read-only system audit; no production fixes, provider calls, wake training, or Phase 6 work performed

## 1. Executive verdict

The repository is a coherent implementation foundation, but it is not ready for real voice acceptance or event-robot deployment. The historical Gate 5B.1 targeted re-review correctly closed the earlier archive TOCTOU and selected lifecycle/STT/cancellation findings, and the fresh automated suite is green in the repository virtual environment. That evidence does not establish the new product gates.

Fresh independent verdict:

| Severity | Count | Meaning |
|---|---:|---|
| P0 | 0 | No fresh corruption/security finding meeting the P0 definition. The authenticated-open-archive fix and security tests remain effective. |
| P1 | 6 | Blocks reliable core voice, wake-bypassed development, S330 full-duplex behavior, graceful degraded startup, low-latency speech, or required multilingual behavior. |
| P2 | 11 | Important robustness, recovery, observability, operator, event-activation, dependency, and acceptance-readiness debt. |
| P3 | 3 | Documentation/cleanup improvements that do not independently block the core runtime. |

The most important conclusion is not a wake-word result. Wake data and calibration are correctly deferred, but the current `enabled: false` wake path is a degraded sleeping router that suppresses all downstream PCM; it is not a deliberate development bypass. Core voice cannot therefore be validated without a trained wake model unless the graph is assembled manually with injected boundaries.

The required English and Arabic/English code-switch experience is also not implemented as a real code path. `secondary_locale: en` is configuration metadata only. STT, transcript metadata, persona policy, exact-answer templates, and TTS are all effectively Arabic/Egyptian-Arabic fixed paths. The current tests use synthetic Arabic-oriented fakes and do not exercise language selection or an English voice.

The Anker PowerConf S330 is physically present on this Windows machine. The safe PortAudio inspection found S330 capture and playback entries, but the runtime currently leaves both device selectors null, uses the Windows default input and output independently, and never applies `output_device` to playback. At audit time the default input was S330 MME index 1 while the default output was Realtek index 4. That prevents the S330 from receiving its own playback reference and means its internal echo-cancellation behavior is not being exercised by the current graph.

Recommended action: accept this audit, update the Master Plan, then implement only the P1 remediation as a new **Gate 5C.1 Core Voice + Multilingual + Windows S330 Development Gate**, with wake explicitly bypassed and wake training still deferred. Do not begin Phase 6 or wake-model collection from this audit.

## 2. Verified repository baseline

### Git and remote verification

The audit began by running `git fetch --prune origin` and then checking the branch, local commit, remote branch, and `git ls-remote` result.

| Check | Result |
|---|---|
| Working directory | `C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain\inno-brain` |
| Branch | `phase/5c0-wake-attention` |
| Local HEAD | `569c295f5e9e24ee9086a9a491e909f248cdcaf0` |
| `origin/phase/5c0-wake-attention` | `569c295f5e9e24ee9086a9a491e909f248cdcaf0` |
| `git ls-remote origin refs/heads/phase/5c0-wake-attention` | `569c295f5e9e24ee9086a9a491e909f248cdcaf0` |
| HEAD subject | `docs: record Heyino corpus workflow hardening` |
| Initial `git status --short --branch` | clean; tracking the expected remote branch |
| Initial `git diff --check` | clean |

The only intended worktree change from this audit is this report. No branch was created or switched. No repository was cloned. The 13 existing sibling donor repositories were inspected read-only when relevant; their recorded commits and clean states are listed in [Section 11](#11-proposed-donorrepo-additions).

### Read scope

`MASTER_PLAN.md` was read completely (version 1.19, 4,499 lines). All Phase 1–5 state/report material was read, including:

- `docs/reviews/PRE_PHASE5_SOL_AUDIT.md`
- `docs/phase5/GATE5B_IMPLEMENTATION_REPORT.md`
- `docs/phase5/GATE5B_SOL_RE_REVIEW.md`
- `docs/phase5/GATE5B1_FINAL_BLOCKERS_REPORT.md`
- `docs/phase5/GATE5B1_FINAL_SOL_RE_REVIEW.md`
- `docs/phase5/GATE5C0_WAKE_ATTENTION_REPORT.md`
- `docs/phase5/wake/HEYINO_WAKE_BENCHMARK.md`
- the Phase 1–5 state/integration/progress reports and the final voice acceptance document

The production/configuration/test/script surface was inventoried before judgment: 81 Python production files under `src`, 4 configuration files, 93 test files, 24 scripts, and 5 evaluation files. The system has no `uv.lock`, `poetry.lock`, `Pipfile.lock`, or requirements lock file; `docs/research/DONOR_REPOS.lock.yaml` is a donor inventory, not a production dependency lock.

## 3. Architecture map

The intended and mostly assembled graph is:

```text
S330 / sounddevice PCM capture
        |
        v
WakeAttentionBridge
        |
        +--> WakeAudioRouter + local wake engine while SLEEPING
        |       (pre-roll stays local; no cloud STT while sleeping)
        |
        +--> Pipecat RealtimeTurnRuntime
                Silero VAD -> Smart Turn v3 -> user turn events
                |
                +--> VoiceBrainRuntime -> STT audio stream
                                      Speechmatics primary
                                      Deepgram fallback
                |
                +--> final transcript -> GroundedOrchestrator
                                      StructuredResolver
                                      HybridRetriever
                                      SQLite / FTS5 / sqlite-vec / E5
                                      Groq LLM or evidence-only degraded path
                |
                +--> SentenceChunker -> Azure TTS -> PCM playback
                                                   -> S330 speaker
```

`InnoBrainApplication` is the intended lifecycle owner. It assembles provider adapters, the active read-only event context, `ActiveKnowledgeBinding`, `SessionMemory`, `GroundedOrchestrator`, `AttentionController`, `WakeAudioRouter`, `WakeAttentionBridge`, `VoiceBrainRuntime`, and `ActivationManager` (`src/innobrain/app.py:61-73, 215-328`). Event activation is guarded by `VoiceBrainRuntime.is_quiescent`, swaps the knowledge binding, resets memory, and closes the old context (`src/innobrain/app.py:309-314`, `src/innobrain/event/runtime.py:65-110`).

The main implementation mismatch is at the capture/turn boundary: `RealtimeTurnRuntime._feed_audio` invokes the STT observer before it queues the same frame into the VAD/Smart Turn pipeline (`src/innobrain/voice/pipecat_runtime.py:193-218`). `VoiceBrainRuntime` does not call `stt.begin_turn()` until the later user-turn-start event (`src/innobrain/voice/brain_runtime.py:175-193`). The conceptual graph is therefore not the temporal graph used by the current code.

## 4. Current real implementation state

### Lifecycle and event isolation

- One application object owns the runtime and event activation path.
- Startup failure calls the application cleanup path and event switching is guarded against active response/turn work.
- Event contexts use read-only SQLite connections and the archive verifier authenticates the open archive, rehashing members while extracting. Fresh archive security and TOCTOU tests passed.
- `SessionMemory` is bounded to ten turns and 300 seconds by the current YAML. Delivered-response commit occurs after playback; interrupted drafts are not committed in the normal response path.
- Runtime restart is not a supported/reliable state transition: `InnoBrainApplication.stop()` closes the current context and wake router, while a later `start()` reuses the same object without rebuilding either (`src/innobrain/app.py:169-181`). The voice pipeline can appear to start again, but the active context is gone and the router remains closed/degraded.
- `ActivationManager` calls the live switch hook before writing the durable active pointer/history (`src/innobrain/event/activation.py:109-128`). A filesystem failure between those operations can leave live memory/knowledge and the next-process pointer disagreeing.

### Audio subsystem

- `SoundDevicePCMStream` creates a `RawInputStream` with one channel and `int16` PCM at the configured sample rate (`src/innobrain/audio/stream.py:50-65`). It does not resample, validate the selected host API’s actual format before opening, or retain PortAudio callback status.
- The queue is bounded and drops the oldest chunk when full (`src/innobrain/audio/stream.py:96-102`). Counters exist, but drop policy has no threshold, fault, operator signal, or input-overrun distinction.
- Device enumeration returns index, name, input/output channel counts, and default sample rate only (`src/innobrain/audio/devices.py:8-26`). Host API identity and a stable device descriptor are not retained.
- `AudioRuntimeConfig.output_device` is loaded but is not passed to `PCMStreamPlaybackController` (`src/innobrain/config/models.py:10-18`, `src/innobrain/voice/pcm_playback.py:20-27`). The alternate tone backend also calls `sd.play` without a device (`src/innobrain/voice/playback.py:18-24`).
- Software AEC/NS are disabled in YAML and no software AEC/NS processing is active, which is the safe S330 starting posture. The booleans are configuration fields, not an implemented processing contract.
- No real capture/playback stream was opened in this audit. Only device enumeration and PortAudio format capability queries were performed.

### Realtime voice graph and cancellation

- Pipecat 1.8.1, Silero VAD, and local Smart Turn v3 are assembled and load in the existing virtual environment.
- The `smart_turn.enabled` flag is present but `RealtimeTurnRuntime` constructs and uses `LocalSmartTurnAnalyzerV3` unconditionally (`src/innobrain/config/models.py:28-32`, `src/innobrain/voice/pipecat_runtime.py:68-89`).
- Barge-in ordering is explicit: local playback is cancelled before remote response cancellation (`src/innobrain/voice/interruption.py:34-64`), and current recovery tests cover provider/playback cleanup exceptions.
- STT, LLM, and TTS are cancellable at adapter boundaries, but blocking provider operations are not uniformly bounded and several callback/task generations are not isolated. See P2 findings.
- The LLM result is fully buffered before sentence chunking and TTS (`src/innobrain/conversation/orchestrator.py:103-126`, `src/innobrain/voice/brain_runtime.py:253-270`), so the graph does not yet optimize time-to-first-useful-audio.

### STT providers

- Speechmatics adapter is pinned in the project to `speechmatics-voice==0.2.8`, uses external endpointing, and has a separate provider-session counter that correctly accepts provider turn ID zero (`src/innobrain/providers/speechmatics_stt.py:74-81, 113-153, 202-214`).
- Deepgram is configured in code as Nova-3, `ar-EG`, linear16, 16 kHz, mono, with keyterms (`src/innobrain/providers/deepgram_stt.py:69-79`). The installed virtual environment currently has `deepgram-sdk 7.8.1`; the project range permits any `>=6.1.1,<8` version.
- Both adapters bridge callbacks through `TurnTranscriptBuffer`, but the buffer emits `language="ar-EG"` for every final transcript and suppresses every repeated final segment with the same normalized text (`src/innobrain/providers/transcript_buffer.py:42-56, 67-84`).
- `FailoverSTTProvider` correctly avoids silently replaying accepted audio after a mid-turn failure, but it intentionally fails the current turn and activates fallback on the next (`src/innobrain/providers/stt_failover.py:89-107`).
- No real provider session, Arabic accuracy, English accuracy, code-switch behavior, network timeout, or provider restart was exercised.

### Brain, grounding, memory, and event knowledge

- Exact structured answers bypass the LLM; hybrid retrieval uses one reference clock for lexical and dense result filtering and falls back to lexical retrieval if dense embedding/search fails (`src/innobrain/knowledge/retrieval.py:60-126`).
- The RAG prompt treats retrieved content as untrusted data and the no-evidence path declines to invent facts. Event package data is event-scoped, and event switching resets the current memory turns.
- The default policy is hard-coded to natural Egyptian Arabic and preservation of English technical terms (`src/innobrain/conversation/persona.py:13-26`). `ProjectConfigs.persona` is loaded, but `build_application` does not translate it into the `Persona` used by `GroundedOrchestrator`; the orchestrator calls `system_policy()` without a configured persona (`src/innobrain/app.py:256-264`, `src/innobrain/conversation/orchestrator.py:43-48`).
- `SessionMemory` exposes `language_style`, but no production path updates or consumes it, and `reset()` clears turns without resetting the language style (`src/innobrain/conversation/memory.py:32, 82-90`).
- Exact resolver templates are Egyptian-Arabic-oriented. English retrieval terms and multilingual E5 improve search coverage, but they do not select response language or TTS voice.

### TTS and playback

- Azure is configured for raw 16 kHz mono PCM and the hard-coded `ar-EG-ShakirNeural` voice (`src/innobrain/providers/azure_tts.py:31-44`). The configured locale/voice values are not passed by the provider registry (`src/innobrain/providers/registry.py:107-132`).
- Sentence-level Azure streaming is bridged through an asyncio queue, but cancellation uses a shared active queue/task and does not establish a generation token or await/cancel the synthesis task before a new stream (`src/innobrain/providers/azure_tts.py:51-89, 114-123`).
- PCM playback always opens the default output device and has no configured output-device argument (`src/innobrain/voice/pcm_playback.py:20-27`).

### Attention and wake

- The local wake boundary is present and keeps sleeping PCM local; engaged/follow-up PCM is routed to VAD/STT. The wake data/benchmark report correctly remains `DATA_PENDING`/provisional, with no trained Heyino model selected.
- `build_wake_engine()` returns a degraded engine when `wake_word.enabled` is false (`src/innobrain/wake/factory.py:18-81`). The bridge then leaves attention in `SLEEPING` and returns empty PCM for every non-wake chunk (`src/innobrain/wake/bridge.py:42-69`). There is no deliberate `wake_mode: bypass` or `always_engaged_development` path.
- Wake engines expect 16 kHz PCM16, but the generic runtime permits 8–48 kHz and does not reject a non-16 kHz wake configuration (`src/innobrain/wake/contracts.py`, `src/innobrain/config/models.py:10-18`).
- Follow-up/session timers are checked on incoming chunks rather than by a background timer (`src/innobrain/attention/controller.py:301-324`, `src/innobrain/wake/bridge.py:51-54`). This is safe against closing mid-utterance, but the health state can remain follow-up-engaged while there is no incoming audio.

### Configuration, secrets, telemetry, and CLI

- `.env` is absent and `.env.example` contains names only. The loader preserves explicit environment precedence and never returns secret values (`src/innobrain/config/loader.py:16-62`). No secret was printed or sent.
- `ProviderRegistry` reports availability, but `build_provider_bundle()` requires credentials for both STT providers, Groq, and Azure before the runtime can even be assembled (`src/innobrain/providers/registry.py:77-138`).
- `python -m innobrain check` and `wake-check` are offline-only and do not open a stream. `check` reports only device count/default indices, not the S330 candidates, host APIs, capability checks, or selected output route (`src/innobrain/cli.py:108-161`). `run` has no device, event, provider, or wake-bypass diagnostic/override arguments.
- Runtime observations include state, provider names, event identity, route, evidence count, and timing labels, but not language, numeric provider/first-token/first-audio latency, sample rate, host API/device identity, queue drops, clipping/noise, mute/disconnect, CPU/RAM/temperature, or network state (`src/innobrain/telemetry/runtime_events.py:17-32`).

## 5. P0/P1/P2/P3 findings

### P0 findings

No fresh P0 finding. The prior archive verification defect is not reopened: `open_verified_event_package()` retains the authenticated open file/ZipFile and extraction rehashes the authenticated members (`src/innobrain/event/validation.py:124-230`, `src/innobrain/event/archive.py`), and the two fresh security tests passed.

### P1 findings

#### P1-MULTI-001 — Required English and code-switch response path is not implemented

- **Exact file/function:** `src/innobrain/providers/speechmatics_stt.py:74-80` (`SpeechmaticsSTTProvider.__init__`); `src/innobrain/providers/deepgram_stt.py:69-79` (`DeepgramSTTProvider.__init__`); `src/innobrain/providers/transcript_buffer.py:51-55,73-78`; `src/innobrain/conversation/persona.py:13-26`; `src/innobrain/providers/azure_tts.py:31-39`; `src/innobrain/providers/registry.py:95-132`; `config/runtime.yaml:3-4`; `config/providers.yaml:7-31`.
- **Reproduction/concrete reasoning:** `secondary_locale: en` is found only in configuration/model loading/tests; no runtime language-selection call consumes it. Speechmatics is constructed with `language="ar"`, Deepgram with `language="ar-EG"`, every transcript event is labeled `ar-EG`, the brain policy always says Egyptian Arabic, and Azure is permanently set to `ar-EG-ShakirNeural`. The registry does not pass configured STT language/model or TTS locale/voice into the adapters. An English utterance therefore enters an Arabic-fixed STT path and an Arabic-fixed response/TTS path. This conclusion is code-derived and was intentionally not tested by calling a cloud provider.
- **Impact on event robot:** English → English, Arabic → English, English → Arabic, natural mixed utterances, language continuity, and an English TTS voice cannot be accepted as product behavior. Preserving English names in an Arabic prompt is not language switching.
- **Proposed minimal fix:** Add an explicit per-turn language decision/metadata contract; use a provider mode that can detect or accept Arabic/English mixed input; pass config-driven language/locale/voice settings; select a response language from the current turn plus bounded conversation policy; make exact templates and the system policy language-aware; map English and Egyptian-Arabic speech to deliberate TTS voice/SSML behavior. Keep Arabic-first defaults.
- **Exact regression test needed:** With fake STT events labeled `ar-EG`, `en`, and `mixed`, assert the generated brain policy, exact/RAG answer language, `SessionMemory.language_style`, and TTS voice/locale for Arabic → English, English → Arabic, and mixed proper-noun turns. Add a registry-construction test that changes non-default YAML language/voice values and verifies those values reach each adapter.

#### P1-S330-001 — S330 input/output routing is not stable and configured playback selection is ignored

- **Exact file/function:** `src/innobrain/config/models.py:10-18` (`AudioRuntimeConfig`); `src/innobrain/voice/pipecat_runtime.py:50-55` (`RealtimeTurnRuntime.__init__`); `src/innobrain/voice/pcm_playback.py:9-27` (`PCMStreamPlaybackController.start`); `src/innobrain/voice/playback.py:18-24`; `src/innobrain/audio/devices.py:8-26`.
- **Reproduction/concrete reasoning:** The current YAML leaves both device selectors null. The safe device query found default input `[1]` as `Anker PowerConf S330 (2- USB Au...)` through MME and default output `[4]` as `Speakers (Realtek(R) Audio)`. The likely S330 MME playback device is index 5. `RealtimeTurnRuntime` passes only `input_device`; `PCMStreamPlaybackController` does not accept or pass an output device, and `sd.play` also uses the default. `AudioDevice` does not retain host API identity, while the same S330 appears under MME, DirectSound, WASAPI, and WDM-KS with duplicate/ambiguous names.
- **Impact on event robot:** The current graph can capture from the S330 while playing through Realtek. The S330’s internal echo-cancellation reference is therefore not the same mic+speaker path required by the product decision. Device indices can change, names are duplicated, and a configured output selector cannot make the runtime use S330 playback.
- **Proposed minimal fix:** Define a stable configured device descriptor containing name pattern plus host API and capability constraints; resolve it at startup without persisting a Windows index; pass the resolved input and output descriptors to one coordinated full-duplex backend; fail with actionable diagnostics on ambiguity or disconnect. Preserve a separate Pi/ALSA descriptor path.
- **Exact regression test needed:** Mock `sounddevice.query_devices`, `RawInputStream`, and `RawOutputStream` with duplicate S330 names across host APIs. Assert deterministic input/output resolution, both streams receive the same selected S330 host/API family, and a changed device index does not alter selection. Add a no-match/ambiguous-match diagnostic test.

#### P1-WAKE-001 — Disabling wake disables the voice graph instead of providing a deliberate development bypass

- **Exact file/function:** `src/innobrain/wake/factory.py:18-81` (`DegradedWakeWordEngine`/`build_wake_engine`); `src/innobrain/wake/bridge.py:42-69` (`WakeAttentionBridge.process_chunk`); `src/innobrain/app.py:266-298`; `src/innobrain/config/models.py:67-89`; `src/innobrain/cli.py:35-105`.
- **Reproduction/concrete reasoning:** A safe offline construction with `WakeWordRuntimeConfig(enabled=False)` produced `engine_ready=False`, `mode='sleeping'`, `attention='SLEEPING'`, and `downstream_bytes=0` for a PCM chunk. The disabled engine never detects, and the bridge suppresses the chunk. `wake-check` reports `data_pending`; no `bypass`/`always_engaged_development` mode exists.
- **Impact on event robot:** The required core STT → brain → TTS validation cannot be run before Heyino data/model training. Manually injecting a fake wake engine is a test seam, not an operator-usable development mode, and does not prove the configured application path.
- **Proposed minimal fix:** Add an explicit development-only attention mode such as `wake_mode: bypass`, which forwards PCM to the existing VAD/Smart Turn/STT path while retaining the wake/attention objects and making the mode visible in health. Keep normal `enabled: false` sleeping behavior and make it impossible to enable bypass in production configuration.
- **Exact regression test needed:** Build the real application graph with wake bypass and assert PCM reaches VAD/STT without a wake model; build normal disabled/sleeping mode and assert PCM is suppressed; assert production configuration rejects bypass. Add a CLI/offline-check assertion that distinguishes `bypassed`, `sleeping`, and `data_pending`.

#### P1-TURN-001 — STT receives audio before application turn ownership begins

- **Exact file/function:** `src/innobrain/voice/pipecat_runtime.py:193-218` (`RealtimeTurnRuntime._feed_audio`); `src/innobrain/voice/brain_runtime.py:175-193,387-398`; `src/innobrain/providers/stt_failover.py:72-88`; `tests/unit/providers/test_stt_failover.py:70-85`.
- **Reproduction/concrete reasoning:** For each routed chunk, `_feed_audio` awaits `_on_audio_chunk_callback` and therefore `VoiceBrainRuntime._on_audio_chunk()` before queueing `InputAudioRawFrame` into Pipecat. The later VAD event calls `begin_turn()`. The existing failover test explicitly codifies that pre-turn audio reaches STT before `begin_turn`. `TurnTranscriptBuffer` has no active application turn before that point, so callback text associated with the early audio can be discarded or attributed outside the intended application turn.
- **Impact on event robot:** The first syllables of a natural utterance or a same-breath wake command can be lost or assigned to the wrong turn. This directly affects Arabic pronunciation, English recognition, code-switching, turn IDs, and follow-up continuity.
- **Proposed minimal fix:** Make turn ownership explicit before sending user speech to a provider: either let VAD/turn start establish a provider turn before forwarding speech, or define a bounded pre-turn provider session with an exact handoff/replay contract. Do not rely on provider-side buffering with no application turn.
- **Exact regression test needed:** Feed a synthetic first speech frame through the real `RealtimeTurnRuntime` boundary and record calls. Assert `begin_turn(application_turn_id)` precedes the first speech PCM sent to STT and the resulting final transcript includes the first frame. Add the same-breath wake handoff case.

#### P1-STARTUP-001 — Provider construction prevents graceful degraded startup

- **Exact file/function:** `src/innobrain/providers/registry.py:77-138` (`build_provider_bundle`); `src/innobrain/cli.py:196-201` (`main` run path); `tests/unit/test_cli.py:31-43`.
- **Reproduction/concrete reasoning:** Calling `build_provider_bundle(load_all_configs(root), environment={})` returns `MissingProviderCredential: missing credential environment variable: SPEECHMATICS_API_KEY` before any runtime graph is assembled. The function then requires the fallback STT credential, Groq credential, Azure key, and Azure region. The CLI refuses `run` before audio. This is safe for the audit, but it contradicts the Master Plan’s requirement to skip absent fallback providers, keep exact facts usable during provider outage, and preserve a typed text-only/degraded path when Azure is unavailable.
- **Impact on event robot:** A deployment with only one STT provider, or with a temporary Groq/Azure outage, cannot start the application far enough to serve exact event facts or expose a controlled degraded state. Failover logic exists only after adapters have been manually constructed with fakes or all required credentials.
- **Proposed minimal fix:** Make provider construction availability-aware: require a usable STT path for live voice, skip missing fallback credentials, and represent missing LLM/TTS as typed degraded capabilities so exact/evidence-only/text-only behavior can start. Report the selected provider and unavailable capabilities without secrets.
- **Exact regression test needed:** Construct with only Speechmatics, only Deepgram, only one STT plus no Groq/Azure, and no credentials. Assert the intended typed capability state, exact-answer path, no audio start when no STT exists, and fallback selection when the primary credential is absent.

#### P1-LATENCY-001 — LLM streaming is buffered before TTS, defeating the first-audio target

- **Exact file/function:** `src/innobrain/conversation/orchestrator.py:103-139` (`GroundedOrchestrator.answer`); `src/innobrain/voice/brain_runtime.py:253-282` (`VoiceBrainRuntime._respond`); `MASTER_PLAN.md:3815-3847`.
- **Reproduction/concrete reasoning:** The LLM adapter returns an async stream, but `GroundedOrchestrator.answer()` appends every part to a list and returns only after the stream ends. `VoiceBrainRuntime` then sentence-chunks the completed string and starts TTS. A fake LLM that yields a first sentence and waits before ending cannot cause a TTS call during the wait.
- **Impact on event robot:** First useful audio waits for full model completion, increasing perceived latency and making barge-in/cancellation less natural. This conflicts with the explicit P50/P95 first-audio targets and the Master Plan rule to optimize time to first useful audio.
- **Proposed minimal fix:** Introduce a cancellable incremental LLM → sentence chunker → TTS/playback pipeline, while retaining a bounded final answer for grounding/commit. Preserve no-evidence/exact routes and do not commit interrupted output as delivered.
- **Exact regression test needed:** Use a fake LLM that emits a sentence, blocks on an event, and then emits the remainder. Assert first TTS/playback PCM occurs before the LLM stream completes; cancel during the block and assert the stream, TTS, playback, and memory commit all terminate without stale output.

### P2 findings

#### P2-AUDIO-001 — Audio format, callback status, and queue-loss handling are incomplete

- **Exact file/function:** `src/innobrain/audio/stream.py:15-125`; `src/innobrain/audio/devices.py:8-26`; `src/innobrain/config/models.py:10-18`.
- **Reproduction/concrete reasoning:** The callback deletes the PortAudio `status` argument (`stream.py:104-117`), hardcodes one input channel, and forwards raw bytes without sample-rate conversion or format validation. A full queue silently drops the oldest chunk and increments only a counter. On this machine, a safe `check_input_settings` query accepted S330 MME index 1 at 16 kHz/int16/mono, while the S330 WASAPI input index 15 rejected 16 kHz as `Invalid sample rate` and S330 WDM-KS input index 29 rejected the sample format. The runtime has no host-API selection or fallback policy.
- **Impact on event robot:** Host-API/default changes can turn a nominal 16 kHz configuration into startup failure or a mismatched stream; overruns, under-runs, clipping, and lost PCM are not actionable during an event.
- **Proposed minimal fix:** Validate the resolved device format before opening; make conversion/resampling explicit; capture callback status and input metrics; expose drop/overrun thresholds as health/fault signals; define a controlled reconnect policy.
- **Exact regression test needed:** Inject PortAudio status flags, unsupported-rate responses, odd channel formats, and queue overflow into the stream boundary. Assert diagnostics identify the device/host API/rate and that a configured drop threshold changes health without corrupting the iterator.

#### P2-LIFECYCLE-001 — Stop/start and partial cleanup are not a supported recovery contract

- **Exact file/function:** `src/innobrain/app.py:146-181`; `src/innobrain/voice/brain_runtime.py:96-121`; `src/innobrain/voice/pipecat_runtime.py:148-191`; `src/innobrain/wake/router.py:236-250`.
- **Reproduction/concrete reasoning:** `InnoBrainApplication.stop()` closes `context_switcher.current` and sets it to `None`, closes the wake router by setting `_ready=False`, and does not rebuild either on a later `start()`. The voice runtime and Pipecat worker may start again on the same object, but the active event context is absent and wake health remains closed/degraded. In addition, `VoiceBrainRuntime.stop()` performs provider/turn/playback cleanup sequentially; if `turn_runtime.stop()` raises, later STT/playback cleanup is skipped even though the final state is reset.
- **Impact on event robot:** A device/provider recovery or supervised in-process restart can produce a running-looking process with no active event context, stale binding, closed wake routing, or leaked provider resources.
- **Proposed minimal fix:** Choose and enforce one lifecycle contract: either make the application one-shot and have the operator recreate it, or implement a complete restart that rebuilds context/router/workers. Aggregate cleanup failures while attempting every owner’s cleanup.
- **Exact regression test needed:** Start → stop → start the same application and assert active event, router health, and a grounded query remain valid. Inject an exception at each stop stage and assert all later cleanup owners are still called and the process exposes a degraded/closed state rather than a false ready state.

#### P2-STT-001 — Provider callback edge cases and blocking operations remain under-specified

- **Exact file/function:** `src/innobrain/providers/deepgram_stt.py:103-126,134-174,184-196`; `src/innobrain/providers/speechmatics_stt.py:109-164`; `src/innobrain/providers/transcript_buffer.py:42-84`.
- **Reproduction/concrete reasoning:** Deepgram resolves `turn_id` with `message_turn_id or self._active_turn_id` (`deepgram_stt.py:184-187`), so a provider callback carrying valid turn ID `0` is treated as absent and can be attributed to the current application turn. The current tests cover nonzero IDs but not this case. `send_media`, connection setup, finalize, and close are moved to threads but have no operation timeout beyond the final transcript wait. The transcript buffer deduplicates repeated final strings globally within a turn, which can erase a legitimate repeated word/phrase, and emits a fixed Arabic language label.
- **Impact on event robot:** A provider callback shape or slow socket can stall a realtime turn; stale/zero IDs or repeated words can corrupt the transcript used for exact event resolution and multilingual detection.
- **Proposed minimal fix:** Use explicit `is not None` turn-ID handling, provider-specific callback contract tests, bounded operations with typed timeout/failover behavior, and segment identity/timestamp deduplication rather than text-only deduplication. Carry provider language metadata.
- **Exact regression test needed:** Inject Deepgram-shaped callbacks with IDs `0`, `1`, stale IDs, repeated adjacent words, worker-thread callbacks, and blocked send/finalize operations. Assert correct turn isolation, preserved repetition, typed timeout, and fallback state.

#### P2-TTS-001 — Azure cancellation can leak late callbacks/audio into a later response

- **Exact file/function:** `src/innobrain/providers/azure_tts.py:51-89,114-123`; `src/innobrain/voice/pcm_playback.py:20-53`.
- **Reproduction/concrete reasoning:** Azure stores one global active queue/task. `cancel()` calls `stop_speaking_async()` and puts an end marker, but does not cancel/await the active synthesis task or attach a generation to callbacks. A late SDK callback can therefore enqueue data after cancellation or after a new stream replaces `_active_queue`. PCM playback similarly clears `_stream` before an in-flight `to_thread(stream.write, ...)` necessarily returns.
- **Impact on event robot:** Interrupted speech can produce late/stale audio, overlap a new answer, or hang during provider shutdown. This is particularly risky with S330 full-duplex playback and barge-in.
- **Proposed minimal fix:** Give each synthesis/playback session a generation token; cancel and await the old task with a bounded timeout; ignore callback data for old generations; serialize start/write/cancel state transitions.
- **Exact regression test needed:** Delay a fake Azure callback across cancel and a new stream, then delay a fake PCM write across playback cancel/start. Assert no old chunk reaches the new queue/output and all operations finish within the cancellation bound.

#### P2-EVENT-001 — Live event context can diverge from the durable activation pointer

- **Exact file/function:** `src/innobrain/event/activation.py:109-128`; `src/innobrain/event/runtime.py:89-110`.
- **Reproduction/concrete reasoning:** `_activate()` invokes `switch_hook(candidate)` before `_write_pointer(candidate)` and `_append_history(candidate, action)`. `RuntimeContextSwitcher.switch()` swaps the active knowledge snapshot, resets memory, and closes the old context before the durable pointer is written. A controlled failure injected into pointer or history writing leaves the process serving the new event while the next process reads the old pointer. There is no rollback of the binding/current context on that write failure.
- **Impact on event robot:** An operator may see one event in the live robot and another after restart; event facts and visitor context can be inconsistent across a package switch failure.
- **Proposed minimal fix:** Use a prepare/commit/rollback activation transaction: validate/open the candidate, durably commit pointer/history, atomically swap the live binding, and retain the old context until commit succeeds; or implement an explicit rollback journal.
- **Exact regression test needed:** Force `_write_pointer()` and `_append_history()` to fail independently during activation. Assert the live binding, memory, current pointer, and open-context ownership remain on the old event and no partially committed history is reported.

#### P2-EVENT-002 — Registry health and production trust-key CLI state are not authoritative

- **Exact file/function:** `src/innobrain/event/registry.py:20-78`; `scripts/phase4/eventctl.py:60-67`.
- **Reproduction/concrete reasoning:** `InstalledEventRecord.healthy` trusts the four integer values in `install_report.json` plus file existence; registry discovery does not reopen the SQLite database or recalculate health. The activation candidate path performs an additional read-only check, but `list/status` can report a stale report as healthy. Separately, `eventctl._policy()` creates `PackageVerificationPolicy` without loading `config/trusted_event_keys.yaml`; there is no operator path in that CLI to supply trusted public keys for production validation.
- **Impact on event operations:** Corrupt or changed installed databases can look healthy in status output, and a signed production package cannot be validated through the documented CLI trust configuration without an additional programmatic path.
- **Proposed minimal fix:** Revalidate the database/index health for operator status or distinguish report health from live health; load trusted keys only from an explicit configured file with clear failure diagnostics and no secret logging.
- **Exact regression test needed:** Mutate/remove an installed database after its report is written and assert `list/status` shows unhealthy. Provide a fixture trusted-key file and assert production CLI validation accepts the signed package; missing/unknown keys must fail with an actionable non-secret message.

#### P2-OBS-001 — Telemetry cannot prove the required voice/S330 acceptance targets

- **Exact file/function:** `src/innobrain/telemetry/runtime_events.py:17-59`; `src/innobrain/app.py:93-121`; `src/innobrain/audio/stream.py:9-13`.
- **Reproduction/concrete reasoning:** Runtime observations have timing labels but no duration/first-token/first-audio values, language, audio sample rate, selected host API/device, clipping/noise metrics, disconnect/reconnect state, or numeric queue-drop/overrun events. `ApplicationHealth.ready` is based only on attention/wake health and does not include provider readiness, active event version, E5 readiness, or voice-start state. Audio stats expose only received/dropped chunk counts.
- **Impact on event robot:** The team cannot establish P50/P95 first-audio, barge-in stop time, provider identity at failure, S330 headroom/noise behavior, or whether a “ready” process can actually answer.
- **Proposed minimal fix:** Add a privacy-safe per-turn/session measurement schema and health snapshot covering language, provider lifecycle, numeric latency markers, device/format, queue/drop/overrun, clipping/noise, network state, and resource/thermal data. Keep raw visitor audio out of default logs.
- **Exact regression test needed:** Emit a synthetic turn and assert all required markers are monotonic and correlated by session/turn ID, provider/device fields contain no secret/raw PCM, and health becomes degraded on configured queue/provider/device faults.

#### P2-CLI-001 — Offline/operator diagnostics are too coarse for the new hardware workflow

- **Exact file/function:** `src/innobrain/cli.py:18-21,35-105,108-161,196-224`; `src/innobrain/audio/devices.py:25-41`; `src/innobrain/wake/factory.py:86-99`.
- **Reproduction/concrete reasoning:** `check` returns device count and default numeric indices but does not print S330 matches, host API, channels, default rates, 16 kHz capability, or the resolved input/output route. `wake-check` reports `data_pending` for the configured engine but has no bypass-mode result. The wake factory resolves relative model paths from the process working directory, while the CLI resolves candidate paths relative to the project root. `run` has no explicit device/event/attention diagnostic options.
- **Impact on event robot:** An operator cannot distinguish “S330 absent,” “S330 present but wrong host API/rate,” “wake data pending,” and “wake deliberately bypassed” from the supported CLI. Running from another working directory can also produce inconsistent wake asset results.
- **Proposed minimal fix:** Add actionable JSON/text diagnostics for stable device descriptors and `check_*_settings`, provider capability state, active event/E5, wake mode, and path resolution. Add explicit development-only `--attention-mode bypass`/configuration visibility; resolve all relative paths from the project root.
- **Exact regression test needed:** Run `check` against mocked duplicate S330 devices, unsupported rates, missing event/E5/provider credentials, disabled wake, and bypass mode. Assert stable non-secret diagnostic fields and correct exit codes.

#### P2-DEP-001 — Dependency resolution is not reproducible across Windows and Raspberry Pi

- **Exact file/function:** `pyproject.toml:10-27`; current `.venv` metadata; `docs/research/DONOR_INSPECTION.md:42-45,69-76,143-146`.
- **Reproduction/concrete reasoning:** There is no production lock file. Several key packages use ranges (`deepgram-sdk>=6.1.1,<8`, `numpy>=2,<3`, `openai>=1.74,<3`, `tokenizers>=0.21,<1`, `sounddevice>=0.5,<1`). The current venv is Python 3.14.6 with `deepgram-sdk 7.8.1`, `numpy 2.5.2`, and the exact Pipecat/Speechmatics/Azure/ONNX versions listed in the report. No Raspberry Pi/aarch64 install or long-run compatibility evidence exists.
- **Impact on event robot:** A fresh Windows or Pi deployment can receive different SDK callback behavior, native wheels, performance, or unsupported ARM/Python combinations while source tests remain green.
- **Proposed minimal fix:** Produce a reviewed runtime lock/constraints set per platform, add Python/ARM CI or a Pi smoke gate, and pin provider/native versions whose callback contracts are relied upon. Keep builder-only Docling isolated.
- **Exact regression test needed:** Install from the committed lock in a clean Windows environment and a Raspberry Pi 5/aarch64 environment; run provider import/contract, ONNX, sqlite-vec, audio capability, and Pipecat startup checks before accepting a lock update.

#### P2-DEP-002 — sqlite-vec source/license provenance remains unresolved

- **Exact file/function:** `pyproject.toml:24`; `docs/research/DONOR_REPOS.lock.yaml:36-45`; `docs/research/DONOR_INSPECTION.md:117-150`.
- **Reproduction/concrete reasoning:** `sqlite-vec==0.1.9` is a production dependency and its installed package metadata reports MIT/Apache-2.0, but the inspected donor commit has no root `LICENSE` or `COPYING` evidence and explicitly records `REVIEW_REQUIRED`; the donor README also describes the project as pre-v1. No repository-level approval or binary/ARM provenance record is present.
- **Impact on event robot:** Legal/provenance review and native-extension reproducibility are incomplete for a core RAG dependency shipped to an event device.
- **Proposed minimal fix:** Obtain and record authoritative upstream/package license evidence, notices, source/binary provenance, and the exact ARM build plan before production distribution. Keep the dependency isolated behind `VectorStore`.
- **Exact regression test needed:** Add a release dependency/license manifest check that fails on `REVIEW_REQUIRED`, verifies the approved package hash/license evidence, and runs the vector-store smoke on the target ARM artifact.

#### P2-ATTN-001 — Attention timeout/health state depends on future audio

- **Exact file/function:** `src/innobrain/attention/controller.py:301-324,349-362`; `src/innobrain/wake/bridge.py:42-54`; `src/innobrain/app.py:93-120`.
- **Reproduction/concrete reasoning:** `AttentionController.check_timeouts()` is called by `WakeAttentionBridge.process_chunk()` only when a new PCM chunk arrives. After a response, a silent system can remain in `FOLLOWUP_WINDOW` in health beyond the configured 4.5–8 second window until another chunk causes a check. `reset()` clears session internals but does not clear all historical wake/reply/close timestamps exposed by health.
- **Impact on event robot:** Watchdogs and operators can see stale engagement/follow-up state, and event-switch/reset diagnostics can misrepresent the current session even though the next audio chunk is eventually handled conservatively.
- **Proposed minimal fix:** Use a cancellable attention timer owned by the application or make health queries perform an injected-clock timeout transition; reset all observable timing history or label it as historical.
- **Exact regression test needed:** Advance an injected clock without delivering PCM and assert the state/health expires at the configured deadline; reset after a wake/reply and assert no prior timestamps/session identifiers remain in the current-health snapshot.

### P3 findings

#### P3-DOC-001 — Master Plan and README still describe the old validation order and hardware state

- **Exact file/function:** `MASTER_PLAN.md:6-12,205-240,2294-2331,3556-3627`; `README.md:9-13,35-43`.
- **Reproduction/concrete reasoning:** The Plan says the S330 is not currently used, laptop audio remains primary, English is secondary, and the next action is Heyino corpus/calibration before real voice. README repeats laptop/default output and “S330 production validation pending.” The new product decision reverses the immediate order: S330 is physically available and primary for development; wake collection is deferred until after core voice/multilingual validation; English/code-switching is a completion gate.
- **Impact on event robot:** Operators and future agents can follow a stale gate order or mistake `secondary_locale: en` and wake implementation status for product readiness.
- **Proposed minimal fix:** Apply the exact Master Plan changes in Section 10 and update README/status/changelog together. This audit does not edit those files.
- **Exact regression test needed:** Add a documentation/status consistency check that asserts the current baseline, S330-primary development mode, wake-deferred order, and English/code-switch completion gate are present and old “collect wake next” wording is absent.

#### P3-LEGACY-001 — Legacy live-audio demos are not clearly separated from the offline audit/runtime workflow

- **Exact file/function:** `scripts/phase2/turn_detection_demo.py:16-58`; `scripts/phase2/barge_in_demo.py`; `scripts/phase3/provider_smoke.py:33-115`.
- **Reproduction/concrete reasoning:** The Phase 2 demos query/open live audio and write diagnostic artifacts, while provider smoke calls real services whenever credentials are present. They are separate from `python -m innobrain check`, but the repository does not provide a single prominent safety classification in their command help.
- **Impact on event robot:** An operator following an old phase script can open the microphone, mutate artifacts, or call a provider when only an offline diagnostic was intended.
- **Proposed minimal fix:** Mark legacy demos `LIVE/DESTRUCTIVE-TO-EXTERNAL-SERVICE` or `LIVE-MIC`, require an explicit opt-in flag, and document them separately from offline checks.
- **Exact regression test needed:** Invoke each script’s help/default path in a subprocess and assert it does not open audio or call a provider without an explicit live opt-in.

#### P3-PLAYBACK-001 — Placeholder tone playback and production PCM playback remain parallel abstractions

- **Exact file/function:** `src/innobrain/voice/playback.py:18-99`; `src/innobrain/voice/pcm_playback.py:9-69`; `src/innobrain/config/models.py:34-41`.
- **Reproduction/concrete reasoning:** The production brain uses `PCMStreamPlaybackController`, while the Pipecat runtime owns a separate tone-oriented `PlaybackController`/`SoundDevicePlaybackBackend`. Mock response tone settings remain in the runtime configuration but are not a clear production/test boundary.
- **Impact on event robot:** Cancellation, output-device selection, and health behavior can diverge between demos, tests, and the production graph.
- **Proposed minimal fix:** Keep a clearly named test harness, or converge both onto one playback/session contract after S330 routing is defined. Do not tune production acceptance from the tone path.
- **Exact regression test needed:** Assert the production application always selects the configured PCM playback path and that the demo path cannot be mistaken for production in CLI/help/status output.

## 6. Multilingual readiness matrix

Status is about actual current behavior, not the presence of a config field or a donor repository. No cloud provider was called during this audit.

| Required behavior | Status | Code evidence and reasoning |
|---|---|---|
| Arabic question → natural Egyptian Arabic answer | PARTIAL | Arabic-fixed STT, Egyptian-Arabic policy, Arabic Azure voice, exact/RAG routes exist. Automated tests use fakes and fixture text; no real Speechmatics/Azure acoustic or quality acceptance has run. |
| English question → natural English answer | FAIL | Speechmatics `language="ar"`, Deepgram `language="ar-EG"`, policy says Egyptian Arabic, exact templates are Arabic-oriented, and Azure is hard-coded to `ar-EG-ShakirNeural`. |
| Arabic turn → English next turn | FAIL | No language detector/turn language policy or response-language selection; `secondary_locale` is not consumed. |
| English turn → Arabic next turn | FAIL | Default Arabic output is not evidence of understanding English or deliberate language following; English input is still sent to Arabic-fixed STT and memory language is not updated. |
| Arabic + English mixed utterance | PARTIAL | Event glossary/keyterms and multilingual E5 provide some mixed-token retrieval support; the actual STT modes are fixed Arabic and there is no mixed-language evaluation or per-turn response policy. |
| English proper nouns inside Egyptian Arabic | PARTIAL | Prompt asks to preserve English technical/proper nouns and the static provider glossaries include several event names; no dynamic event glossary injection, real STT test, or TTS pronunciation acceptance exists. |
| Response-language selection | FAIL | No production code reads `primary_locale`, `secondary_locale`, transcript language, or `SessionMemory.language_style` to choose a response language. |
| Correct English TTS voice | FAIL | Azure is permanently configured as `ar-EG-ShakirNeural`; configured locale/voice are not passed through the registry and no English voice map exists. |
| Conversational memory across language switches | FAIL | Turn/entity memory is bounded and event-reset-aware, but language state is unused and not reset; no language-switch regression or real conversation path exists. |

## 7. S330 readiness matrix

The following device data came from safe local `sounddevice`/PortAudio enumeration and `check_*_settings` capability queries. No `RawInputStream` or `RawOutputStream` was opened, no audio was recorded, and no playback occurred.

### Observed likely S330 entries

| Direction | PortAudio index observed | Name | Host API | Max channels | Default rate | 16 kHz mono `int16` capability query |
|---|---:|---|---|---:|---:|---|
| Input | 1 | `Anker PowerConf S330 (2- USB Au...` | MME | 2 | 44,100 Hz | PASS (`check_input_settings` returned successfully) |
| Input | 7 | `Anker PowerConf S330 (2- USB Audio Device)` | Windows DirectSound | 2 | 44,100 Hz | Not separately accepted as the selected route |
| Input | 15 | `Anker PowerConf S330 (2- USB Audio Device)` | Windows WASAPI | 2 | 48,000 Hz | FAIL: `Invalid sample rate` |
| Input | 25 | `Anker PowerConf S330 (USB Audio Device)` | Windows WDM-KS | 2 | 48,000 Hz | Not selected; alternate WDM input |
| Input | 29 | `Input (Anker PowerConf S330)` | Windows WDM-KS | 2 | 48,000 Hz | FAIL: `Sample format not supported` |
| Output | 5 | `Speakers (Anker PowerConf S330)` | MME | 8 | 44,100 Hz | PASS (`check_output_settings` returned successfully) |
| Output | 11 | `Speakers (Anker PowerConf S330)` | Windows DirectSound | 8 | 44,100 Hz | Not separately accepted as the selected route |
| Output | 12 | `Speakers (Anker PowerConf S330)` | Windows WASAPI | 2 | 48,000 Hz | FAIL: `Invalid sample rate` |
| Output | 27 | `Output 1 (Anker PowerConf S330)` | Windows WDM-KS | 2 | 48,000 Hz | FAIL: `Sample format not supported` |
| Output | 28 | `Output 2 (Anker PowerConf S330)` | Windows WDM-KS | 8 | 44,100 Hz | Alternate WDM output |
| Output | 30 | `Speakers (Anker PowerConf S330)` | Windows WDM-KS | 2 | 48,000 Hz | Alternate WDM output |

The PortAudio defaults at inspection time were input `1` and output `4`; output `4` was `Speakers (Realtek(R) Audio)`, not S330. Indices above are evidence from this machine only and must not be hard-coded.

| Capability | Status | Evidence and acceptance gap |
|---|---|---|
| Device discovery | PASS | S330 capture/playback entries were enumerated under MME, DirectSound, WASAPI, and WDM-KS. |
| Stable selection by properties | FAIL | Runtime stores only optional `str|int`; `AudioDevice` omits host API; duplicate names and changing indices are unresolved. |
| 16 kHz capture | NEEDS PHYSICAL TEST | MME capability query passed for index 1; no stream was opened and other host APIs rejected the requested format/rate. |
| PCM16 mono | PASS | Capture requests `channels=1`, `dtype="int16"`; physical bytes and device DSP output still need capture validation. |
| Full duplex | NEEDS PHYSICAL TEST | Separate input/output streams exist conceptually, but no same-S330 simultaneous record/playback test has run. |
| Playback | PARTIAL | MME S330 output capability query passed, but production playback ignores `output_device` and defaults to Realtek on this host. |
| Internal S330 AEC assumptions | PARTIAL | The Master Plan correctly prefers S330 hardware DSP and same-device output, but current default routing does not provide the same-device playback reference. |
| Software AEC disabled | PASS | YAML default is false and no software AEC is applied. The flags are not an enforced measured-processing contract. |
| Input clipping/headroom observability | FAIL | No runtime peak, RMS, clipping percentage, or headroom metrics. Existing WAV analysis is offline/legacy, not live health. |
| Noise-floor measurement | FAIL | No live noise-floor or speech/noise slice measurement in the runtime or CLI. |
| Queue drops | PARTIAL | Oldest-drop counter exists, but PortAudio status and threshold/fault telemetry are absent. |
| Mute/device disconnect behavior | FAIL | No physical mute state, callback status, disconnect detection, or user-visible fault/recovery path. |
| Recovery/reconnect | FAIL | No input/output device reconnect policy; stream stop/start is not a tested hot-recovery contract. |
| Windows readiness | PARTIAL | Device visibility and MME 16 kHz capability are confirmed; routed full-duplex physical acceptance is not. |
| Raspberry Pi readiness | NEEDS PHYSICAL TEST | No ALSA enumeration, Pi USB record/playback, ARM dependency install, or thermal/soak evidence. |

## 8. Test and verification evidence

All checks below were run after the fresh baseline review using the repository’s existing `.venv` (`Python 3.14.6`). The literal global `python` command resolves to `C:\Users\mahmo\AppData\Local\Python\pythoncore-3.14-64\python.exe`; it lacks project dependencies and failed test collection with missing `pydantic`, `PyYAML`, `pipecat`, and other modules. No packages were installed to repair that environment.

| Command | Result | Evidence |
|---|---|---|
| `git status --short --branch` | PASS at audit start | Clean `phase/5c0-wake-attention...origin/phase/5c0-wake-attention`; final status will include only this report. |
| `git diff --check` | PASS at audit start | No whitespace errors. |
| `.venv\Scripts\python.exe -m pytest -q` | PASS | `369 passed, 2 skipped, 1 warning in 18.88s`; skips were optional Docling and opt-in real E5 model test. Warning was an intentional duplicate ZIP member fixture. |
| `.venv\Scripts\python.exe -m ruff check src tests scripts` | PASS | `All checks passed!` |
| `.venv\Scripts\python.exe -m pip check` | PASS | `No broken requirements found.` |
| `.venv\Scripts\python.exe -m innobrain check` | PASS as offline diagnostic | Exit 0; `status=not_ready`, no active event, E5 assets absent, all four provider credential flags false, 31 devices enumerated, default input 1/output 4, no network/audio stream. |
| `.venv\Scripts\python.exe -m innobrain wake-check` | PASS as offline diagnostic | Exit 0; `status=data_pending`, both candidate dependencies/assets unavailable, no network/audio stream. No wake acceptance claimed. |
| Safe PortAudio enumeration | PASS | 31 local devices queried; likely S330 input/output entries and host APIs recorded above. |
| Safe PortAudio format checks | MIXED by host API | MME S330 input/output accepted 16 kHz mono `int16`; WASAPI/WDM examples rejected the requested settings. No stream opened. |
| Real providers | NOT RUN | No Speechmatics, Deepgram, Groq, or Azure calls. |
| Heyino training/recording | NOT RUN | No model training, calibration, or repetitive manual capture. |
| Raspberry Pi / physical S330 audio | NOT RUN | No Pi or simultaneous physical stream test. |

### What the current tests prove and do not prove

The 371 collected tests provide good coverage for archive verification, event package structure, synthetic event switching, fake-provider failover, callback thread bridging, cancellation ordering, attention transitions, and corpus metadata safety. The `test_real_graph_with_fake_boundaries.py` integration tests assemble the internal graph but inject fake STT, LLM, TTS, stream, and playback edges (`tests/integration/voice/test_real_graph_with_fake_boundaries.py:25-148`).

They do not prove:

- real Speechmatics 0.2.8 or Deepgram 7.x callback/network behavior;
- English STT, English TTS, Arabic/English language switching, or mixed-language response policy;
- actual S330 capture level, DSP/AEC, simultaneous playback, mute, disconnect, or noise behavior;
- stable device property resolution across Windows host APIs or Pi ALSA;
- the first-speech ordering through real VAD/Smart Turn into STT;
- LLM first-token/first-audio latency;
- in-process application restart after context/router closure;
- wake-bypassed configured application behavior;
- long-duration, event-noise, thermal, or network-outage acceptance.

## 9. Validation debt

The following debt is intentional or newly exposed and must remain visible:

1. **Arabic real voice:** controlled Egyptian human turn/hesitation, provider smoke, and final audio quality are still absent.
2. **English and code-switch:** no implementation-level language matrix or real acoustic/voice acceptance exists; this is now a required completion gate, not optional secondary polish.
3. **S330 Windows calibration:** no physical stream has been opened in this audit; no RMS/peak/noise/clipping/headroom baseline, AEC reference test, mute behavior, or 2+ hour soak exists.
4. **Pi 5:** no ALSA device selection, ARM dependency install, USB full-duplex, CPU/RAM/thermal, or long-run evidence exists.
5. **Wake:** Heyino corpus/model/training/calibration remains deferred and unmeasured. Existing wake tests are structural/injected evidence only.
6. **Provider resilience:** no live timeout, reconnect, credential-partial, provider outage, or failover acceptance exists.
7. **Latency:** no numeric end-of-turn → first useful audio, first-token, first-TTS PCM, playback-stop, or P95 measurements are emitted.
8. **Event operations:** signed production package trust-key CLI flow, post-install database integrity revalidation, and activation commit/rollback under filesystem failure need evidence.
9. **Reproducibility:** no committed runtime lock or Pi-compatible dependency evidence exists.
10. **Robot integration:** Robot/Screen/ROS is deliberately not started; this audit does not authorize Phase 6.

## 10. Proposed remediation order and exact Master Plan changes

### Proposed implementation order after review

1. **Change control:** accept this audit and update `MASTER_PLAN.md`, `README.md`, and the changelog; do not modify architecture beyond the explicit contracts below.
2. **Core voice safety:** add an explicit development wake bypass, repair the STT turn ownership ordering, and add the regression tests described in all P1 findings.
3. **S330 Windows audio contract:** add property-based discovery/selection, apply both input and output routes, validate the selected host API/rate/format, and make same-device full duplex observable. Keep software AEC/NS disabled until measured.
4. **Provider/degraded construction:** make missing fallback/LLM/TTS credentials capability states rather than graph-construction blockers, while preserving a clear failure when no live STT exists.
5. **Language contract:** implement per-turn language metadata, response-language policy, configured persona use, mixed-language preservation, exact-answer localization, and Arabic/English TTS voice selection.
6. **Streaming and recovery:** stream LLM sentences into TTS, add generation-safe cancellation, complete lifecycle recovery, and add the required latency/health markers.
7. **Windows S330 physical gate:** with the real S330 as the primary device, run safe controlled capture/playback/duplex, noise/headroom/clipping, mute/disconnect/reconnect, and sustained-use tests. Do not use a hardcoded index.
8. **Controlled real-provider gate:** validate Egyptian Arabic first, then English, then Arabic/English switches and mixed utterances, with no acceptance claim from fakes.
9. **Wake gate last:** only after core voice, multilingual behavior, and S330 calibration pass should the separate Heyino collection/training/calibration gate resume.
10. **Pi gate:** validate the same contracts on Raspberry Pi 5/ALSA before event deployment. Phase 6 remains after the proven Phase 5 conversation runtime.

### Exact recommended Master Plan edits

These are recommendations only; this audit does not edit `MASTER_PLAN.md`.

1. **Development hardware:** replace the old “S330 is not currently used” and “laptop microphone/output is current development audio” statements in `MASTER_PLAN.md:205-240` with: “The S330 A3308 is physically available and is the primary Windows development microphone and speaker. Device selection is by properties/host API/capability, never a persisted index. Pi 5 remains a later deployment target.”
2. **Language gate:** replace the old English-secondary wording in `MASTER_PLAN.md:6-12,46-54` with: “Egyptian Arabic is first priority; natural English conversation and Arabic/English code-switching are required completion gates. `secondary_locale: en` is not evidence of implementation. Acceptance must include Arabic→English, English→Arabic, mixed utterances, English proper nouns, response-language selection, English TTS, and memory across switches.”
3. **Gate order:** update `MASTER_PLAN.md:3556-3627` so wake corpus/training/calibration is explicitly deferred until after core voice, multilingual, and S330 validation. Preserve the wake architecture and add a development-only wake-bypass mode with no cloud STT while normal sleeping.
4. **Audio contract:** add a locked contract for a resolved S330 input/output pair, host API, supported sample rate, PCM16 mono format, full-duplex behavior, physical mute/disconnect behavior, queue/drop metrics, clipping/headroom/noise metrics, and Windows-to-Pi capability differences. Retain “software AEC/NS disabled by default until measurement.”
5. **Provider contract:** record that provider credentials are optional capability inputs; missing fallback/LLM/TTS must produce typed degraded states, while at least one live STT is required for live voice. Configuration must reach provider language/model/locale/voice fields.
6. **Latency/telemetry:** preserve the existing targets in `MASTER_PLAN.md:3815-3847` and make first-token, first-useful-audio, playback-stop, provider, language, device, queue, and network measurements explicit exit evidence under `MASTER_PLAN.md:3929-3953`.
7. **Status/changelog:** replace stale Gate 5C0 checkpoint/count wording (`MASTER_PLAN.md:3602-3627`) with the verified current HEAD/report references and state clearly that this audit found no P0 but did find P1 blockers.

## 11. Proposed donor/repo additions

**PROPOSED ONLY: none. No clone performed.**

The existing 13 read-only donors cover the relevant reference capabilities:

| Existing donor | Recorded license | Relevant coverage |
|---|---|---|
| `pipecat` | BSD-2-Clause | Runtime/pipeline/provider patterns; already the production dependency. |
| `smart-turn` | BSD-2-Clause | Semantic end-of-turn contract. |
| `silero-vad` | MIT | VAD/reference behavior. |
| `pywebrtc-audio` | Apache-2.0 | Optional AEC/NS/AGC reference; should remain measurement-gated. |
| `metro-asr` | MIT | Egyptian/code-switch STT candidate/reference. |
| `VoiceTuT-TTS` | Apache-2.0 | Egyptian TTS/code-switch/normalization reference. |
| `voice-agent-starter`, `GLaDOS` | MIT | Cancellation, full-duplex, memory, and lifecycle reference. |
| `compact-rag`, `llama.cpp` | MIT | Small-device retrieval/local-model reference. |
| `pepper-android-realtime-chat` | MIT | Robot/screen/tool lifecycle reference for a later phase. |
| `docling` | MIT | Builder-only ingestion reference. |
| `sqlite-vec` | Review required in donor record | Existing vector dependency; license/provenance must be closed before release. |

The missing capabilities found here are integration contracts, configuration authority, real hardware behavior, language policy, and acceptance evidence. A new open-source repository would not fix them. `docs/research/DONOR_REPOS.lock.yaml` records all 13 as reference-only; their working trees were clean at inspection time. No new donor is justified without a future, separately approved capability gap and license review.

## 12. Exact recommended next gate

### **Gate 5C.1 — Core Voice + Multilingual + Windows S330 Development Gate (wake bypassed)**

Do not start it until this audit is reviewed. Its entry conditions should be:

- HEAD/baseline and this audit accepted;
- Master Plan changes above approved;
- no wake corpus/training dependency;
- no Phase 6 work;
- no real cloud calls in its offline structural stage.

Its exit conditions should be:

1. all six P1 findings have targeted implementation and regression evidence;
2. the configured application runs through an explicit development wake bypass while normal sleeping still blocks cloud STT;
3. the actual S330 is selected by properties, capture and playback are routed to the same intended device path, and safe 16 kHz/PCM16/full-duplex checks are recorded;
4. Egyptian Arabic, English, Arabic→English, English→Arabic, mixed utterance, English proper noun, language-memory, and English TTS contract tests pass;
5. LLM/TTS first-audio streaming and interruption metrics are emitted;
6. `pytest`, Ruff, `pip check`, offline `check`, offline `wake-check`, and `git diff --check` are green in the intended virtual environment;
7. remaining real-provider, human-speaking, S330 acoustic, and Pi evidence is explicitly listed rather than implied.

Only after Gate 5C.1 passes should the project open a controlled real-provider/Egyptian voice gate, then the English/code-switch completion gate, then the deferred Heyino data/training/calibration gate. Robot/Screen/ROS work remains out of scope.

## Terminal checkpoint

```text
HEAD=569c295f5e9e24ee9086a9a491e909f248cdcaf0
tests=369 passed, 2 skipped (venv); Ruff=PASS; pip_check=PASS
P0=0 P1=6 P2=11 P3=3
S330=PARTIAL — discovered; MME 16 kHz capability passed; same-device full-duplex/routing/acoustic acceptance pending
multilingual=FAIL — Arabic-first path only; English/code-switch response/TTS selection absent
recommended_next=Review this audit, update Master Plan, then implement Gate 5C.1 with explicit wake bypass and S330-primary routing; defer wake training and Phase 6
```

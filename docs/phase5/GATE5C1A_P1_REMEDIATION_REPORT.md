# InnoBrain — Gate 5C.1A P1 Structural Remediation Report

**Date:** 2026-09-12 (Africa/Cairo)
**Repository:** `MahmoudNagiubX/inno-brain`
**Branch:** `phase/5c1-core-voice-multilingual-s330`
**Audited source branch:** `phase/5c0-wake-attention`
**Audited baseline:** `569c295f5e9e24ee9086a9a491e909f248cdcaf0`
**Implementation commit:** `b8ee3ce` (`feat(voice): close Gate 5C1A structural P1s`)
**Master Plan version:** `1.20`

This report records the structural implementation for Gate 5C.1A. It does not
certify live provider quality, acoustic behavior, full-duplex echo cancellation,
or Raspberry Pi readiness.

## 1. Executive verdict

All six requested P1 boundaries are structurally closed:

| Finding | Structural status | Acceptance boundary still pending |
|---|---|---|
| P1-MULTI-001 | **CLOSED** | Live Arabic, English, and mixed-utterance provider acceptance |
| P1-S330-001 | **CLOSED** | Physical S330 full-duplex, AEC, noise, clipping, disconnect, and recovery tests |
| P1-WAKE-001 | **CLOSED** | Later Heyino data/model calibration; normal wake acceptance |
| P1-TURN-001 | **CLOSED** | Live-provider callback and acoustic first-syllable validation |
| P1-STARTUP-001 | **CLOSED** | Live provider outage/failover validation |
| P1-LATENCY-001 | **CLOSED** | Live cloud latency and physical playback timing measurements |

No P0 was found in the source audit. No real Speechmatics, Deepgram, Groq, or
Azure request was made. No microphone or playback stream was opened. No Heyino
training or recording was started. No new donor repository was cloned, and Phase
6 remains stopped.

The next gate is a controlled, local S330 physical validation. It must happen
before live Arabic provider voice, live English/code-switch validation, or
Heyino training/calibration.

## 2. Verified repository baseline and delivery

Before implementation, the repository was fetched/pruned and the audited
working branch resolved to the expected commit:

| Item | Evidence |
|---|---|
| Source baseline branch | `origin/phase/5c0-wake-attention` |
| Source baseline HEAD | `569c295f5e9e24ee9086a9a491e909f248cdcaf0` |
| Remediation branch | `phase/5c1-core-voice-multilingual-s330` |
| Implementation commit | `b8ee3ce` |
| Earlier feature commits | `48b0c82` audio routing; `127d227` wake bypass; `3c01c48` capability-aware providers |
| Product plan | `MASTER_PLAN.md` v1.20 |
| New donor repositories | None |
| External service calls | None |

The primary audit is retained at
`docs/reviews/PRE_GATE5C1_FULL_SYSTEM_AUDIT.md`. Its three Markdown line-break
trailing spaces were removed so the delivered branch passes `git diff --check`;
the audit content and findings were not otherwise changed.

## 3. Resulting architecture map

```text
runtime.yaml / providers.yaml
        |
        +--> AudioDeviceDescriptor(input + output)
        |       -> enumerate current devices
        |       -> resolve by properties and capability
        |       -> validate before opening
        |
        +--> SoundDevicePCMStream (resolved capture)
        |       -> PCM/VAD/Smart Turn
        |       -> application pre-turn ownership buffer
        |       -> STT begin_turn -> exactly-once PCM handoff
        |
        +--> WakeAudioRouter / WakeAttentionBridge
        |       -> wake_required: sleeping audio remains local
        |       -> development_bypass: explicit, observable, dev-only
        |
        +--> transcript metadata (ar-EG / en / mixed / unknown)
                -> per-turn language decision
                -> exact structured resolver or grounded RAG
                -> language-aware LLM policy / incremental stream
                -> sentence-safe chunks
                -> one dominant TTS locale/voice per response
                -> PCM playback on the resolved S330 output
                -> commit memory only after delivered playback
```

The S330 Windows profile resolves both directions by descriptor and prefers the
same validated MME host-API family when that profile is capable. No numeric
PortAudio index is persisted in configuration or used as a product selector.
Software AEC and noise suppression remain disabled by default.

## 4. P1 closure details

### P1-MULTI-001 — Real multilingual contract

**Status: CLOSED — structural contract; acoustic/live acceptance pending.**

**Exact implementation locations:**

- `src/innobrain/conversation/language.py`: `TurnLanguage`,
  `LanguageDecision`, `decide_turn_language()`, and provider metadata
  normalization.
- `src/innobrain/conversation/persona.py`: language-aware system policy.
- `src/innobrain/conversation/orchestrator.py`:
  `GroundedOrchestrator.answer()`, `stream_answer()`, language selection,
  exact/no-evidence localization, and delivered-memory updates.
- `src/innobrain/conversation/memory.py`: bounded language-style state and reset.
- `src/innobrain/providers/transcript_buffer.py`: per-turn provider language
  metadata instead of an unconditional Arabic label.
- `src/innobrain/providers/speechmatics_stt.py` and
  `src/innobrain/providers/deepgram_stt.py`: configurable/metadata-preserving
  language modes (`auto` and `multi` defaults).
- `src/innobrain/knowledge/structured_resolver.py`: English and Egyptian-Arabic
  exact-answer rendering without requiring an LLM translation step.
- `src/innobrain/providers/azure_tts.py`: configurable Arabic and English
  locale/voice selection, with one dominant voice per response.
- `src/innobrain/providers/registry.py`, `config/providers.yaml`, and
  `src/innobrain/config/models.py`: configuration propagation.

**Former reproduction and concrete reasoning:** The audited implementation
fixed Speechmatics, Deepgram, the persona, transcript labels, and Azure to
Arabic defaults. `secondary_locale: en` was not consumed by the runtime. An
English turn therefore could not reliably enter an English STT/brain/TTS path.

**Minimal remediation used:** A turn now has explicit `ar-EG`, `en`, `mixed`, or
`unknown` state. Explicit user requests and provider metadata take precedence;
script evidence is only a fallback, not the sole production detector. Mixed
input responds primarily in Egyptian Arabic while preserving English terms.
Exact facts are localized from the same grounded entities. TTS selects a
configured dominant voice for the response rather than switching voices for
each technical noun.

**Regression tests:**

- `tests/unit/conversation/test_language.py`:
  `test_arabic_turn_selects_egyptian_arabic_response`,
  `test_english_turn_selects_english_response`,
  `test_language_switch_and_explicit_requests_override_prior_style`, and
  `test_provider_metadata_is_preferred_over_script_fallback_when_unambiguous`.
- `tests/unit/conversation/test_orchestrator.py`:
  `test_orchestrator_sets_response_language_and_preserves_it_after_delivery`,
  `test_delivered_turns_can_switch_english_and_egyptian_arabic`, and
  `test_stream_answer_preserves_exact_and_no_evidence_fast_paths`.
- `tests/unit/knowledge/test_structured_resolver.py` and
  `tests/unit/conversation/test_grounding.py`: English exact facts, mixed
  technical names, and grounded response behavior.
- `tests/unit/providers/test_speechmatics_stt.py`,
  `test_deepgram_stt.py`, `test_provider_factory.py`, and
  `test_azure_tts.py`: provider metadata/config propagation and configured
  English voice/locale selection.
- `tests/integration/test_application_event_switch.py` and
  `tests/unit/conversation/test_memory.py`: event-switch language reset and
  bounded language memory.

**Event-robot impact:** The core can now represent and route Arabic, English,
mixed, and turn-to-turn language switches without forcing a single-language UX.
Event evidence remains language-independent and exact-answer routes do not need
an LLM merely to translate a fact.

**Remaining debt:** Real Speechmatics/Deepgram Arabic accuracy, English
accuracy, code-switch recognition, Groq language adherence, and Azure natural
speech quality require live-provider tests and are intentionally not accepted
by fake-boundary tests.

### P1-S330-001 — Stable S330 input and output routing

**Status: CLOSED — structural routing contract; physical S330 behavior pending.**

**Exact implementation locations:**

- `src/innobrain/audio/models.py`: `AudioDeviceDescriptor` and resolution data.
- `src/innobrain/audio/devices.py`: `resolve_audio_device()`,
  `resolve_audio_devices()`, capability validation, ambiguity diagnostics, and
  same-host-family pairing.
- `src/innobrain/audio/stream.py`: resolve/validate capture before opening and
  safe selected-device health fields.
- `src/innobrain/voice/pcm_playback.py` and `src/innobrain/voice/playback.py`:
  output descriptor reaches `RawOutputStream`/the playback backend.
- `src/innobrain/voice/pipecat_runtime.py` and application construction:
  input/output descriptor wiring.
- `config/runtime.yaml`: explicit S330 input and output descriptors, 1-channel,
  16 kHz, PCM16, MME development profile.

**Former reproduction and concrete reasoning:** The audited graph passed an
input selector but ignored configured output selection and could capture from
the S330 while playing through the Windows Realtek default. Numeric indices were
unstable across host APIs and duplicate S330 names were ambiguous.

**Minimal remediation used:** Configuration stores property descriptors only:
name pattern, host API preference, direction, channels, requested rate, and
format. Runtime enumeration resolves current indices, checks capability before
opening, rejects ambiguity/no-match, and routes input and output deliberately.
The output controller now passes the resolved output to `RawOutputStream`.

**Regression tests:**

- `tests/unit/audio/test_devices.py`:
  `test_duplicate_s330_names_resolves_deterministically_with_host_api`,
  `test_duplicate_s330_names_without_host_api_raises_ambiguity_error`,
  `test_changing_numeric_indexes_preserves_selection_without_hardcoded_indexes`,
  `test_capability_check_pass_and_fail`,
  `test_no_match_raises_not_found_with_diagnostic_devices`,
  `test_coordinated_both_input_and_output_resolution`, and
  `test_diagnose_audio_devices_produces_safe_data_without_persisting_indexes`.
- `tests/unit/audio/test_stream.py` and
  `tests/unit/voice/test_pcm_playback.py`: resolved input/output reaches the
  injected stream factories and output device.
- `tests/unit/config/test_loader.py`: runtime YAML loads the S330 descriptors.

**Fresh safe device evidence:** The current Windows machine enumerated 31
devices across MME, Windows DirectSound, Windows WASAPI, and Windows WDM-KS.
The S330 entries include:

| Direction | Host API | Current observed name | Max channels | Default rate |
|---|---|---|---:|---:|
| Input | MME | `Anker PowerConf S330 (2- USB Au...` | 2 | 44100 Hz |
| Output | MME | `Speakers (Anker PowerConf S330)` | 8 | 44100 Hz |
| Input | DirectSound | `Anker PowerConf S330 (2- USB Audio Device)` | 2 | 44100 Hz |
| Output | DirectSound | `Speakers (Anker PowerConf S330)` | 8 | 44100 Hz |
| Input | WASAPI | `Anker PowerConf S330 (2- USB Audio Device)` | 2 | 48000 Hz |
| Output | WASAPI | `Speakers (Anker PowerConf S330)` | 2 | 48000 Hz |
| Input/output | WDM-KS | several S330 endpoint names | 2/8 | 44100/48000 Hz |

The fresh offline `innobrain check` capability query resolved the configured
MME input and output, accepted 16 kHz/int16/mono capability for both, reported
`full_duplex_host_api_match: true`, and reported software AEC/NS disabled. No
stream was opened.

**Event-robot impact:** The graph now has a stable, inspectable route to the
same S330 capture/playback family and can fail before opening with actionable
diagnostics when capability or identity is unavailable.

**Remaining debt:** Physical full-duplex playback/capture, hardware AEC
reference behavior, speech/noise headroom, clipping, noise floor, queue loss,
mute/disconnect, and reconnect recovery are not proven by capability queries.
Pi/ALSA selection is also outside this gate.

### P1-WAKE-001 — Explicit development wake bypass

**Status: CLOSED — explicit development mode; Heyino data and normal wake acceptance pending.**

**Exact implementation locations:**

- `src/innobrain/wake/contracts.py`: `WakeOperatingMode` and `WakeStatus`.
- `src/innobrain/config/models.py`: typed operating mode and production
  rejection of `development_bypass`.
- `src/innobrain/wake/router.py` and `src/innobrain/wake/bridge.py`: bypass
  forwarding, normal sleeping suppression, and observable health.
- `src/innobrain/wake/factory.py`, `src/innobrain/attention/controller.py`,
  and `src/innobrain/cli.py`: application wiring, attention behavior, and
  diagnostics.
- `config/runtime.yaml`: explicit development-only bypass profile.

**Former reproduction and concrete reasoning:** With wake disabled or model
data pending, the old bridge suppressed PCM and the configured voice graph
could not be validated before Heyino training. A fake engine was not an
operator-usable mode and could obscure the real application path.

**Minimal remediation used:** `wake_required` remains the normal mode. In
explicit `development_bypass`, the router forwards PCM into the existing VAD,
Smart Turn, and STT path without inventing a wake event per chunk. The nested
wake architecture remains constructed and observable. `WakeStatus` and CLI
output distinguish `READY`, `DATA_PENDING`, `BYPASSED`, and `DEGRADED`. Runtime
configuration rejects bypass when the environment is production. Normal
sleeping mode still keeps audio local and suppresses cloud STT before wake.

**Regression tests:**

- `tests/unit/wake/test_bypass.py`:
  `test_development_bypass_forwards_pcm_without_calling_engine`,
  `test_wake_required_sleeping_still_suppresses_pcm_and_calls_engine`,
  `test_data_pending_and_degraded_statuses_are_distinct`, and
  `test_runtime_yaml_explicitly_selects_development_bypass`.
- `tests/integration/wake/test_one_stream_integration.py`:
  `test_sleeping_pcm_suppression_and_canonical_wake_handoff`, follow-up, wake
  suppression, and recovery cases.
- `tests/unit/config/test_wake_attention_config.py` and
  `tests/unit/cli/test_cli_wake_check.py`: production rejection and explicit
  health/CLI state.

**Event-robot impact:** Core voice can be tested deliberately without a
trained Heyino model, while a normal sleeping deployment cannot silently
become always-engaged.

**Remaining debt:** Heyino corpus collection, training, threshold calibration,
false-accept/false-reject measurement, and normal wake acceptance are deferred
until after core voice and multilingual validation, as required.

### P1-TURN-001 — STT turn ownership and first audio

**Status: CLOSED — application turn ownership contract; live callback timing pending.**

**Exact implementation locations:**

- `src/innobrain/voice/brain_runtime.py`: bounded pre-turn PCM buffer,
  `_accept_pre_turn_audio()`, serialized STT handoff, `handle_user_turn_started()`,
  `handle_user_turn_stopped()`, generation checks, and stale-response guards.
- `src/innobrain/voice/pipecat_runtime.py`: VAD frame is queued before the STT
  observer path.
- `src/innobrain/providers/stt_failover.py` and transcript ownership paths:
  begin/stop/failover semantics remain explicit.

**Former reproduction and concrete reasoning:** The old `_feed_audio` path sent
the observer PCM to STT before the later VAD/Smart Turn event established the
application turn. The first syllable could therefore be outside the intended
turn ownership.

**Minimal remediation used:** Pre-turn speech is bounded in memory and is not
sent to STT. On `handle_user_turn_started()`, `stt.begin_turn()` occurs first;
the buffered frames are then replayed once under the STT audio lock. Subsequent
frames belong to the active application turn. Finalizing turns stop accepting
new pre-turn audio, and response generation guards prevent stale callbacks or
PCM from a cancelled turn. Pipecat receives the VAD frame before the STT
observer callback so VAD/Smart Turn ordering is preserved.

**Regression tests:**

- `tests/integration/voice/test_brain_runtime.py`:
  `test_first_pre_turn_audio_is_buffered_until_stt_turn_ownership_exists`,
  `test_voice_runtime_owns_monotonic_turn_ids_and_stop_without_start_is_safe`,
  `test_voice_runtime_rejects_stale_transcript_from_prior_turn`, and the
  streaming cancellation test.
- `tests/unit/voice/test_pipecat_runtime.py`:
  `test_feed_audio_queues_vad_frame_before_stt_observer`.
- Existing wake handoff/follow-up and interruption suites cover same-breath wake
  continuation, sequential turns, follow-up state, barge-in ordering, and
  cancellation recovery:
  `tests/integration/wake/test_one_stream_integration.py`,
  `tests/integration/voice/test_barge_in_cancellation_order.py`, and
  `tests/unit/voice/test_interruption.py`.

**Event-robot impact:** First speech content is no longer silently sent before
the application owns the turn; this protects Arabic onset, English onset,
mixed-language recognition, follow-up continuity, and provider turn mapping.

**Remaining debt:** Real Speechmatics/Deepgram callback-thread timing,
provider-side buffering, network failure, and acoustic onset latency require
live-provider and physical tests.

### P1-STARTUP-001 — Capability-aware provider assembly

**Status: CLOSED — capability-aware construction; live provider behavior pending.**

**Exact implementation locations:**

- `src/innobrain/providers/registry.py`: optional provider construction,
  `ProviderHealth`, safe capability reporting, and configured selection.
- `src/innobrain/providers/stt_failover.py`: optional fallback behavior.
- `src/innobrain/app.py` and `src/innobrain/cli.py`: readiness/degraded health.
- `src/innobrain/voice/brain_runtime.py`: typed no-STT failure and text-only
  behavior when TTS is unavailable.

**Former reproduction and concrete reasoning:** The old provider bundle raised
on the first missing Speechmatics key and required every fallback/LLM/TTS
credential before the runtime graph could be constructed. That prevented
single-provider and exact/evidence-only degraded paths.

**Minimal remediation used:** Speechmatics-only, Deepgram-only, or both are
valid STT capability states. No STT constructs a non-ready bundle rather than
pretending live voice is ready. Groq and Azure are optional capabilities;
missing LLM/TTS are visible in health. Exact/evidence-only text paths remain
available without an LLM, while no-STT live voice fails explicitly at start.
Provider health reports selected STT, fallback, LLM, and TTS availability
without secret values.

**Regression tests:**

- `tests/unit/providers/test_provider_factory.py`:
  `test_provider_factory_selects_available_stt_capabilities`,
  `test_provider_factory_no_stt_is_constructable_but_not_ready`,
  `test_provider_factory_missing_optional_providers_does_not_block_stt`, and
  `test_provider_factory_passes_multilingual_and_voice_configuration_to_adapters`.
- `tests/unit/providers/test_registry.py`,
  `tests/unit/providers/test_stt_failover.py`, and
  `tests/integration/voice/test_brain_runtime.py`:
  fallback, typed no-STT, exact path, missing TTS, and no-secret health cases.
- All provider factory tests use fakes/configured test environments and made no
  provider network calls.

**Event-robot impact:** A deployment can start far enough to expose an honest
degraded state and serve exact text facts when optional providers are absent;
it cannot claim live voice readiness without an STT capability.

**Remaining debt:** Real provider startup, authentication failure, timeouts,
mid-turn failover, and service outage behavior still require explicit live
validation under a separately approved provider test gate.

### P1-LATENCY-001 — Incremental LLM to TTS

**Status: CLOSED — cancellable structural streaming path; live latency pending.**

**Exact implementation locations:**

- `src/innobrain/conversation/orchestrator.py`: `stream_answer()`, grounded
  incremental output, `SentenceChunker`, exact/no-evidence fast paths, and
  final `BrainResult` preservation.
- `src/innobrain/voice/brain_runtime.py`: incremental TTS/playback scheduling,
  cancellation generation, timing events, and commit-after-delivery.
- `src/innobrain/providers/azure_tts.py`: per-response locale/voice selection
  compatible with incremental calls.

**Former reproduction and concrete reasoning:** The old `answer()` collected
the entire LLM stream before `VoiceBrainRuntime` sentence-chunked it and called
TTS. A fake first sentence followed by a delayed remainder could not produce
audio during the delay.

**Minimal remediation used:** `stream_answer()` emits only safe complete
sentence/utterance chunks while the LLM remains active. The runtime starts TTS
for each chunk, uses one dominant response voice, preserves a final grounded
`BrainResult`, and commits only after playback completes. Exact/no-evidence
paths remain immediate. Cancellation stops new chunks, cancels active work, and
does not commit an undelivered response; response generations prevent stale PCM.

Required timing events now include turn start, speech stop, final transcript,
brain first chunk, TTS request start, first PCM, playback stop, and brain
completion where those boundaries are present in the runtime event stream.

**Regression tests:**

- `tests/integration/voice/test_brain_runtime.py`:
  `test_streaming_brain_starts_tts_before_llm_stream_completes_and_commits_after_playback`
  and `test_streaming_brain_cancellation_during_llm_wait_does_not_commit`.
- `tests/unit/conversation/test_orchestrator.py`:
  `test_stream_answer_preserves_exact_and_no_evidence_fast_paths` and the
  grounding/cancellation tests.
- `tests/integration/voice/test_barge_in_cancellation_order.py` and
  `tests/unit/voice/test_interruption.py`: playback-first cancellation, stale
  PCM prevention, and recovery behavior.

**Event-robot impact:** First useful speech can begin before full model
completion, improving perceived latency and preserving natural interruption.

**Remaining debt:** P50/P95 first-PCM, provider token timing, Azure synthesis
timing, S330 playback timing, and full acoustic barge-in measurements require
live services and the physical device.

## 5. Fresh verification evidence

All commands below ran from the repository `.venv`:

| Check | Result |
|---|---|
| `python -m pytest` | **414 passed, 2 skipped, 1 warning** in 13.37s |
| Ruff (`python -m ruff check src tests`) | **All checks passed** |
| `python -m pip check` | **No broken requirements found** |
| `git diff --check` | **Pass** |
| `python -m innobrain check` | **Passes safely; status `not_ready` because current env has no provider credentials/E5 assets; `network_calls_made=false`, `audio_stream_started=false`** |
| `python -m innobrain wake-check` | **Passes safely; `operating_mode=development_bypass`, `status=bypassed`, model candidates `data_pending`, `network_calls_made=false`, `audio_stream_started=false`** |

The two skipped tests are optional Docling and optional E5 model tests. The one
warning is the existing duplicate ZIP member fixture warning.

The offline application check reported:

- 31 enumerated Windows devices and all four host APIs;
- configured S330 input/output matched under MME;
- 16 kHz/int16/mono capability accepted for both configured directions;
- `full_duplex_host_api_match=true`;
- software AEC disabled and software NS disabled;
- no active event, no E5 asset, and no live STT credentials, so readiness was
  honestly `not_ready` rather than falsely green.

No command in this gate opened an input/output stream or called a cloud
provider.

## 6. Validation debt intentionally left open

These are not hidden acceptance claims:

1. S330 physical full-duplex capture/playback, hardware AEC reference behavior,
   software-AEC/NS decision from measurements, clipping/headroom, noise floor,
   queue drops, mute/disconnect, and reconnect recovery.
2. Real Arabic Speechmatics/Deepgram quality and turn behavior.
3. Real English and Arabic/English code-switch recognition and response quality.
4. Live Groq/Azure first-token/first-PCM/cancellation/error timing.
5. Event-package switch/restart lifecycle hardening and broader P2 observability.
6. Python/Pi 5 aarch64 dependency and runtime validation.
7. Heyino dataset collection, training, threshold calibration, and normal wake
   acceptance.
8. Robot/Screen/ROS Phase 6.

The audit's 11 P2 findings and 3 P3 findings remain deferred except for the
requested documentation/status refresh. No unrelated remediation was folded
into this gate.

## 7. Master Plan and status updates

`MASTER_PLAN.md` v1.20 and `README.md` now record:

- S330 A3308 as the primary Windows development microphone and speaker;
- property/capability device selection with no persisted numeric index;
- same S330 input/output preference and software AEC/NS disabled by default;
- explicit development wake bypass, forbidden in production;
- Egyptian Arabic first, with English and Arabic/English code-switching as
  completion gates;
- structural Core Voice -> physical S330 local -> live Arabic -> live English/
  code-switch -> hardening -> Heyino calibration -> Pi -> Robot/Screen/ROS
  ordering;
- no claim that structural tests equal acoustic, live-provider, or Pi
  acceptance.

## 8. Donor/repository additions

**None proposed.** The existing code, dependencies, and injected fake-provider
boundaries cover the structural capability required for this gate. No new
repository was cloned or added. Any future open-source addition would require
a separate capability and license review before approval.

## 9. Exact recommended next gate

### Gate 5C.1B — Controlled local S330 physical validation

Run only after this branch is reviewed and approved. Use the configured S330
property descriptors and safe operator diagnostics to validate, on this Windows
machine:

1. selected input/output identity and same-host routing;
2. 16 kHz PCM16 mono capture and output behavior;
3. full-duplex playback/microphone interaction and S330 hardware AEC;
4. clipping/headroom and noise-floor measurements;
5. queue/drop/underrun visibility;
6. mute, USB disconnect, and reconnect behavior;
7. bounded local barge-in/playback cancellation.

Do not start live cloud providers, Heyino training, Pi deployment, or Phase 6
as part of this report or automatically after it.

## 10. Terminal checkpoint

```text
HEAD                 b8ee3ce  (implementation commit; report commit follows)
tests                414 passed, 2 skipped
P0                   0
P1                   0 remaining (6 structurally CLOSED)
P2                   11 deferred
P3                   3 audit findings (status/docs refreshed)
S330                 STRUCTURAL_READY / PHYSICAL_PENDING
multilingual         STRUCTURAL_READY / LIVE_ACCEPTANCE_PENDING
recommended action   Gate 5C.1B controlled local S330 physical validation
```

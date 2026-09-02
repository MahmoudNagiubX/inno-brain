# Pre-Phase-5 Sol Audit Commands

Date: 2026-09-02

Baseline: `cc6addddc18a829deaf6a5e8155a157d9edf8c61`

Review branch: `review/pre-phase5-sol-audit`

No command in this audit opened a microphone, speaker, paid provider, Robot,
Screen, or ROS path. Temporary diagnostic outputs were written outside the
repository or to ignored locations.

## Safety preflight

```powershell
git status --short
git branch --show-current
git fetch origin
git rev-parse HEAD
git rev-parse origin/phase/4-dynamic-event-package
```

Result before branch creation:

```text
status: clean
branch: phase/4-dynamic-event-package
local HEAD:  cc6addddc18a829deaf6a5e8155a157d9edf8c61
remote HEAD: cc6addddc18a829deaf6a5e8155a157d9edf8c61
```

```powershell
git switch -c review/pre-phase5-sol-audit
git rev-parse HEAD
git status --short
```

Result: branch created at the required baseline; status clean.

## One-time repository map

```powershell
git ls-files
```

Result: 224 tracked paths. The inventory was run once. Relevant groups were:

```text
src/innobrain/audio          sounddevice discovery, WAV I/O, bounded PCM stream
src/innobrain/config         strict YAML models and loader
src/innobrain/voice          Pipecat turn runtime, state, interruption, two playback paths,
                             VoiceBrainRuntime
src/innobrain/providers      contracts, availability registry, Speechmatics, Deepgram,
                             Groq and Azure adapters
src/innobrain/conversation   grounding, exact/RAG orchestration, sentence chunking, memory
src/innobrain/knowledge      SQLite schema/repository, exact resolver, E5, FTS5/vec/RRF
src/innobrain/event          signed package build/verify/install/activate/switch/rollback
src/innobrain/robot          empty Phase 6 scaffold only
src/innobrain/telemetry      logging setup only
scripts/phase1..phase4       phase-specific probes, demos, smokes and event CLI
tests                       150 collected tests; only one VoiceBrainRuntime integration test
```

```powershell
.\.venv\Scripts\python.exe -m pytest --collect-only -q
```

Result: `150 tests collected in 3.29s`.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip freeze
```

Result:

```text
pip check: No broken requirements found.
pip freeze: 82 resolved distributions
selected versions:
  pipecat-ai==1.8.1
  speechmatics-voice==0.2.8
  speechmatics-rt==1.1.1
  deepgram-sdk==7.8.0
  openai==2.54.0
  azure-cognitiveservices-speech==1.51.2
  onnxruntime==1.24.3
  sqlite-vec==0.1.9
  cryptography==50.0.1
  sounddevice==0.5.6
```

The project has no committed resolved dependency lock. `pip freeze` is local
evidence, not a reproducible installation contract.

## Fresh baseline verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```text
148 passed, 2 skipped, 1 warning in 4.50s
SKIPPED: builder-only Docling absent from normal .venv
SKIPPED: opt-in real E5 test
WARNING: expected duplicate-name archive security fixture warning
```

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

```text
Ruff: All checks passed!
pip check: No broken requirements found.
git diff --check: PASS
```

## Phase-specific deterministic verification

```powershell
.\.venv\Scripts\python.exe scripts\phase2\dependency_smoke.py
```

```text
PIPECAT_VERSION=1.8.1
SILERO_INIT_OK
SMART_TURN_V3_INIT_OK
```

```powershell
.\.venv\Scripts\python.exe scripts\phase2\barge_in_demo.py --synthetic `
  --results-path "$env:TEMP\innobrain-prephase5-barge-in.jsonl"
```

```text
interrupted=true
prior_state=SPEAKING
final_state=LISTENING
playback_active=false
event_to_playback_stop_ms=0.0324
acceptance_status=DEFERRED_NOT_RUN
```

This is synthetic software evidence, not acoustic barge-in acceptance.

The default Phase 3 benchmark first failed against an ignored stale database:

```powershell
.\.venv\Scripts\python.exe scripts\phase3\benchmark_rag.py
```

```text
sqlite3.OperationalError: no such column: chunks.authority_level
```

Inspection showed `artifacts/phase3/demo_event.sqlite3` had the pre-Phase-4
seven-column `chunks` table. The script rebuilds only when the path is absent.
Running the same benchmark against a new temporary database proved the current
source and fixture are sound:

```text
HYBRID_ALGORITHM_TEST=PASS
REAL_E5_RETRIEVAL_TEST=NOT_RUN
QUERIES=16
RECALL_AT_5=0.9375
MRR=0.9375
```

The isolated builder environment was run with fresh temporary data/output
directories:

```powershell
.\.venv-event-builder\Scripts\python.exe scripts\phase4\phase4_smoke.py `
  --cache-dir .builder-cache --data-root <temporary> --output-dir <temporary>
```

```text
status=passed
alpha_exact_rows=1
alpha_rag_rows=1
beta_exact_rows=1
beta_alpha_leak_rows=0
rollback_event=event-alpha
```

Provider smoke was forced to the missing-credential state so it could not make
external or paid calls:

```text
speechmatics SKIPPED_MISSING_CREDENTIAL
deepgram     SKIPPED_MISSING_CREDENTIAL
groq         SKIPPED_MISSING_CREDENTIAL
azure        SKIPPED_MISSING_CREDENTIAL
```

## Targeted audit probes

```powershell
git grep -n -I -E "API_KEY|SECRET|TOKEN|PRIVATE KEY|PASSWORD"
```

Result: variable names and documentation only; no credential value or private
key was found.

```powershell
.\.venv\Scripts\python.exe -m pip_audit --version
```

Result: `No module named pip_audit`. No dependency was installed for this
review, so a current vulnerability-database verdict is explicitly unavailable.

```text
normal runtime import availability:
docling_spec=None
torch_spec=None
onnxruntime_spec=True
sqlite_vec_spec=True
```

Installed Deepgram 7.8.0 API inspection found that
`DeepgramClient.listen.v1.connect()` is a synchronous context manager and its
`V1SocketClient.start_listening()` and `send_media()` methods are synchronous.
The listener emits callbacks on the thread used by `start_listening()`.

A no-source-change diagnostic injected a TTS stream failure after first PCM.
`VoiceBrainRuntime.handle_user_turn_stopped()` returned while the state remained:

```text
STATE SPEAKING
```

This reproduces the failure-state finding in the final report.

## Final documentation-scope checks

The final commands are recorded after the audit files were completed:

```powershell
git diff --check
git status --short
git diff --name-only cc6addddc18a829deaf6a5e8155a157d9edf8c61...HEAD
```

Allowed paths only:

```text
MASTER_PLAN.md
docs/reviews/PRE_PHASE5_SOL_AUDIT.md
docs/reviews/PRE_PHASE5_SOL_AUDIT_COMMANDS.md
docs/reviews/PRE_PHASE5_SOL_AUDIT_STATE.md
```

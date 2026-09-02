# InnoBrain — Phase 2 Continuation Override: Defer Live Voice Validation

> **Purpose:** Resume the blocked Phase 2 branch without repeating human-speaking tests now. Finish Phase 2 implementation and automated verification, explicitly defer live voice acceptance to the final project validation track, then authorize Phase 3.
>
> **Authoritative architecture:** `MASTER_PLAN.md` / attached `InnoBrain_MASTER_PLAN_v1.8.md`
>
> **Current branch:** `phase/2-realtime-conversation-core`
>
> **Known pushed state:** `936ad65`
>
> **Do NOT tune VAD or Smart Turn settings in this continuation.**
>
> **Do NOT start Phase 3 inside this task.**

---

# 1. Decision being applied

The earlier Phase 2 plan treated Task 12/13 human-speaking tests as mandatory blocking gates.

That rule is superseded.

The developer wants to finish building the system first and perform human-speaking acceptance near the end.

Therefore:

```text
Phase 2 code + automated tests
            ↓
PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
            ↓
Phase 3 development authorized
            ↓
Later phases
            ↓
Final Voice Acceptance
```

This is a scheduling/process change, not a change to the locked architecture.

Keep:

```text
Pipecat 1.8.1
Silero VAD
Smart Turn v3
16 kHz mono laptop PCM
current VAD parameters
wait_for_transcript=False
current state machine/cancellation architecture
```

Do not reinterpret the current live attempt as a parameter benchmark.

---

# 2. Current evidence to preserve

Current known Phase 2 state:

```text
Branch: phase/2-realtime-conversation-core
Pushed state commit: 936ad65

Automated:
22 passed
Ruff PASS

Offline VAD:
12 speech starts
7 speech stops

Live silence:
0 false starts

Uncontrolled live speaking attempt:
42 events
14 USER_TURN_STARTED
14 USER_TURN_INFERENCE_TRIGGERED
14 USER_TURN_STOPPED

Test B:
not validated as one coherent controlled turn

Hesitation:
0/3 in the attempted run, but the interaction was not a controlled acceptance run

Test D:
not run

Task 13:
not started

Phase 3:
not started
```

Do not delete this evidence.

Do not convert it to PASS.

Do not use it to tune thresholds.

---

# 3. New Phase 2 end state

The target end state for this continuation is exactly:

```text
PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
```

Meaning:

- implementation is ready to build upon;
- automated verification is green;
- interactive voice acceptance is pending by explicit project decision;
- Phase 3 is authorized;
- production/event voice readiness is NOT claimed.

---

# 4. Task 0 — Safety preflight

From:

```powershell
Set-Location "C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain"
```

Run:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git fetch origin
```

Required branch:

```text
phase/2-realtime-conversation-core
```

If dirty:

STOP. Do not discard or stash user work.

If local branch is behind remote:

```powershell
git pull --ff-only origin "phase/2-realtime-conversation-core"
```

Verify current state document still records the Task 12 block/evidence.

---

# 5. Task 1 — Sync the new Master Plan decision

Copy attached:

```text
InnoBrain_MASTER_PLAN_v1.8.md
```

to:

```text
MASTER_PLAN.md
```

Copy this file to:

```text
CODEX_PHASE2_DEFER_LIVE_VALIDATION.md
```

Before replacing the Master Plan, verify Phase 1 and existing Phase 2 evidence is not lost.

Then update:

```text
docs/phase2/PHASE2_STATE.md
```

to:

```markdown
# Phase 2 State

**Phase:** 2 — Realtime Conversation Core  
**Branch:** `phase/2-realtime-conversation-core`  
**Status:** `IN_PROGRESS_VALIDATION_DEFERRED`  
**Last completed task:** Task 11 — Offline Phase 1 recording VAD probe  
**Next task:** Complete remaining non-interactive Phase 2 implementation  
**Development platform:** Windows laptop  
**Primary language:** Egyptian Arabic (`ar-EG`)  
**Pipecat:** 1.8.1 import/model initialization PASS  
**Silero VAD:** Runtime initialization PASS; final human acceptance deferred  
**Smart Turn:** v3 runtime initialization PASS; final human acceptance deferred  
**Automated foundation:** 22 tests PASS; Ruff PASS at prior checkpoint  
**Offline VAD probe:** SPEECH_STARTS=12; SPEECH_STOPS=7  
**Live silence evidence:** 0 false starts  
**Prior live speaking evidence:** 42 events preserved; acceptance inconclusive/deferred  
**Barge-in live acceptance:** Deferred  
**Final Voice Acceptance:** Required later  
**Pi/S330:** Deferred deployment validation  
**Phase 3 authorized:** Not until this continuation wrap-up completes
```

Commit:

```powershell
git add MASTER_PLAN.md CODEX_PHASE2_DEFER_LIVE_VALIDATION.md docs/phase2/PHASE2_STATE.md
git commit -m "docs: defer Phase 2 live voice acceptance"
```

---

# 6. Task 2 — Finish the Task 13 evaluation harness without live human execution

The original Task 13 implementation artifact must still exist even though the live gate is deferred.

Required file:

```text
scripts/phase2/barge_in_demo.py
```

If it already exists, inspect it and do not rewrite unnecessarily.

If absent, implement it according to the original Phase 2 Task 13 architecture:

- load current runtime config;
- use current `ConversationStateMachine`;
- use current `PlaybackController`;
- use current `InterruptionController`;
- use current `RealtimeTurnRuntime`;
- start a low-volume generated tone only when explicitly triggered;
- record barge-in results to gitignored `artifacts/phase2/barge_in_results.jsonl`;
- never use TTS;
- never call an API;
- clean up on Ctrl+C.

Do NOT run the human speaking trial now.

## Add/confirm automated cancellation test

There must be an automated test that proves the software cancellation path independent of the microphone:

```text
LISTENING
→ THINKING
→ SPEAKING
→ synthetic/programmatic user-turn-start callback
→ INTERRUPTED
→ playback cancel
→ LISTENING
```

Required assertions:

- playback cancel called once;
- final state LISTENING;
- no overlapping playback session;
- interruption result exists.

Do not fabricate a human latency number.

Automated cancellation duration may be measured for debugging, but it is not the deferred live barge-in metric.

Run relevant tests red/green if code is added.

---

# 7. Task 3 — Create Final Voice Acceptance tracking document

Create:

```text
docs/validation/FINAL_VOICE_ACCEPTANCE.md
```

Use:

```markdown
# Final Voice Acceptance

**Status:** DEFERRED  
**Reason:** Interactive voice acceptance is intentionally postponed until the complete system is available.  
**Required before production/event readiness:** Yes

## Preserved Phase 2 Evidence

- 22 automated tests passed at Phase 2 checkpoint.
- Ruff passed.
- Offline VAD: 12 starts / 7 stops.
- 10-second intentional silence: 0 false starts.
- One uncontrolled live speaking attempt produced 42 events:
  - 14 starts
  - 14 inference triggers
  - 14 stops
- Normal-turn acceptance: not validated.
- Egyptian hesitation acceptance: not validated.
- Correction test: not run.
- Live barge-in test: not run.

The uncontrolled speaking attempt is diagnostic evidence only.
Do not tune VAD/Smart Turn from it.

## Final Acceptance Tests

Run on the completed system:

1. Background/silence false-trigger test.
2. Normal Egyptian turn.
3. Egyptian thinking pause / hesitation continuation.
4. Correction / afterthought.
5. Natural multi-turn Egyptian conversation.
6. Egyptian-English code-switching.
7. Real assistant speech barge-in.
8. Context preservation after interruption.
9. Noisy-room conversation.
10. Repeated interruptions.
11. Long-session stability.
12. Raspberry Pi 5 + Anker S330 production validation.

## Pass Rule

Project/event voice readiness cannot be declared until the relevant final tests pass.
```

This file is the permanent debt tracker so the deferred tests are not forgotten.

---

# 8. Task 4 — Full automated Phase 2 wrap-up verification

Run fresh:

```powershell
.\.venv\Scripts\python.exe scripts\phase2\dependency_smoke.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
```

Do not reuse the old `22 passed` number if the new suite contains more tests.

Record the NEW exact pytest result.

Verify config remains unchanged:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from innobrain.config import load_all_configs; c=load_all_configs(Path('.')); print(c.runtime.realtime.vad.confidence, c.runtime.realtime.vad.start_secs, c.runtime.realtime.vad.stop_secs, c.runtime.realtime.vad.min_volume, c.runtime.realtime.smart_turn.wait_for_transcript)"
```

Expected:

```text
0.7 0.2 0.2 0.6 False
```

Verify no Phase 3 provider dependency was added:

```powershell
Select-String -Path pyproject.toml -Pattern "deepgram|speechmatics|azure-cognitiveservices|groq|google-genai|elevenlabs|sqlite-vec|sentence-transformers"
```

Expected:

no matches.

Verify runtime artifacts are not tracked:

```powershell
git ls-files recordings artifacts
```

Expected:

no output.

If automated verification fails, fix the actual Phase 2 implementation issue.

Do not waive automated failures under the validation-deferred policy.

---

# 9. Task 5 — Phase 2 report

Create/update:

```text
docs/phase2/PHASE2_REPORT.md
```

Required status:

```text
PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
```

The report must clearly separate:

## Implemented

- Pipecat 1.8.1.
- Silero VAD runtime.
- Smart Turn v3 runtime.
- sounddevice realtime PCM.
- conversation state machine.
- interruptible single-session playback.
- interruption controller.
- turn-event logging.
- Egyptian evaluation scenarios.
- turn-detection demo.
- barge-in demo/harness.
- automated/synthetic pipeline tests.

## Fresh automated result

Use exact current values from Task 4.

## Preserved live evidence

Record the 42-event attempt exactly.

Label:

```text
DIAGNOSTIC / NOT AN ACCEPTANCE PASS
```

## Deferred

- controlled normal-turn live acceptance;
- Egyptian hesitation live acceptance;
- correction live acceptance;
- real microphone barge-in acceptance;
- final end-to-end conversational acceptance;
- Pi/S330/AEC production validation.

## Progression decision

State:

```text
Phase 3 development is authorized because the Phase 2 implementation is complete and automated verification passes.

This does not certify production voice quality.
```

---

# 10. Task 6 — Update Master Plan to the post-wrap-up version

After Task 4 is green, update:

```text
MASTER_PLAN.md
```

Bump:

```text
v1.8 → v1.9
```

Header status:

```text
Phase 1 complete; Phase 2 implementation complete with live validation deferred; Phase 3 authorized but not started
```

Record the fresh automated test count.

Record:

```text
Phase 2 state:
PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
```

Record the current branch final HEAD only after the final commit exists.

Do not write:

```text
PHASE_2_COMPLETE
```

unless the deferred human acceptance actually runs later.

Add v1.9 changelog entry.

---

# 11. Task 7 — Update README and final state

README must say:

```text
Current status: Phase 2 implementation complete; interactive voice acceptance deferred.

Implemented:
- realtime PCM pipeline
- Pipecat 1.8.1
- Silero VAD
- Smart Turn v3
- conversation state machine
- cancellation/interruption framework

Deferred validation:
- controlled Egyptian turn/hesitation test
- live barge-in acceptance
- final end-to-end voice acceptance
- Raspberry Pi/S330 production validation

Next:
Phase 3 — Speech + Brain + RAG.
```

Update `PHASE2_STATE.md`:

```text
Status: PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED
Last completed task: Phase 2 continuation wrap-up
Next task: STOP — wait for Phase 3 handoff
Automated verification: PASS
Live voice acceptance: DEFERRED
Final Voice Acceptance tracker: docs/validation/FINAL_VOICE_ACCEPTANCE.md
Pi/S330: DEFERRED
Phase 3 authorized: Yes
```

---

# 12. Task 8 — Fresh final verification, commit and push

Run AGAIN immediately before final commit:

```powershell
.\.venv\Scripts\python.exe scripts\phase2\dependency_smoke.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
```

Read the output.

No completion claim before these fresh commands pass.

Then:

```powershell
git add `
  MASTER_PLAN.md `
  README.md `
  CODEX_PHASE2_DEFER_LIVE_VALIDATION.md `
  docs `
  scripts `
  src `
  tests

git commit -m "feat: complete Phase 2 implementation with voice validation deferred"
```

Verify:

```powershell
git status --short
git rev-parse HEAD
```

Working tree must be clean.

Push:

```powershell
git push -u origin "phase/2-realtime-conversation-core"
```

Do not merge.

Do not start Phase 3.

---

# 13. Final Codex response

Return:

```text
Phase 2 state:
PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED

Branch:
phase/2-realtime-conversation-core

Final HEAD:
<sha>

Automated:
pytest: <fresh exact result>
Ruff: PASS
dependency smoke: PASS

Implemented:
Pipecat/Silero/Smart Turn/realtime PCM/state/cancellation/evaluation harnesses

Live voice acceptance:
DEFERRED TO FINAL_VOICE_ACCEPTANCE

Preserved live evidence:
42 events (14 starts / 14 inference / 14 stops)
not treated as acceptance

VAD/Smart Turn thresholds:
UNCHANGED

Pi/S330:
DEFERRED

Master Plan:
updated to v1.9

Phase 3:
AUTHORIZED BUT NOT STARTED

STOPPED before Phase 3.
```

---

# 14. Hard stop / failure rules

- If automated tests fail: Phase 2 is blocked; do not defer automated correctness.
- If dependency smoke fails: Phase 2 is blocked.
- If Ruff fails: fix it before wrap-up.
- If `barge_in_demo.py` cannot be implemented against the existing interfaces: diagnose the code issue; do not change architecture without Master Plan update.
- Do not rerun human speaking tests in this continuation.
- Do not tune VAD thresholds.
- Do not tune Smart Turn.
- Do not start STT/LLM/TTS/RAG.
- Do not start Phase 3.
- Do not claim `PHASE_2_COMPLETE`.
- Do not delete the existing JSONL diagnostic evidence.

**End of continuation override.**

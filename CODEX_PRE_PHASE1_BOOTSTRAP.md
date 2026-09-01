# InnoBrain — Codex Pre-Phase-1 Bootstrap Handoff

> **For Codex:** Read this file completely, then read `MASTER_PLAN.md` completely before making any changes.
>
> **Task type:** Workspace/bootstrap only.
>
> **Do NOT start Phase 1 implementation.**
>
> **Primary goal:** Prepare a clean, documented, reproducible workspace so the next Codex task can begin Phase 1 immediately.
>
> **Project priority:** Egyptian Arabic is the primary MVP language. English is secondary and must not drive architecture decisions.
>
> **Source of truth:** `MASTER_PLAN.md`.
>
> **Change-control rule:** If this bootstrap uncovers a fact that requires an architecture change, STOP, document the finding, and do not silently change the architecture. The Master Plan must be updated before implementation continues.

---

# 1. One-Line Execution Instruction

Use this exact instruction when this file and the Master Plan are attached:

> **Read `CODEX_PRE_PHASE1_BOOTSTRAP.md` and `InnoBrain_MASTER_PLAN_v1.2.md` fully, then execute the pre-Phase-1 bootstrap exactly as specified: create the `InnoBrainWorkspace`, create/push the `inno-brain` GitHub repo, clone and inspect the frozen donor repos, scaffold the production repo, write the donor inventory/inspection reports, verify everything, and STOP before Phase 1 implementation.**

---

# 2. Hard Boundaries

You ARE allowed to:

- create folders.
- initialize Git.
- create/connect the GitHub repository.
- copy documentation.
- clone donor repositories.
- inspect files.
- record licenses and commit SHAs.
- create the production directory skeleton.
- create documentation and metadata files.
- create `.gitignore`.
- create a minimal README.
- perform non-destructive verification.
- commit and push the bootstrap state.

You are NOT allowed to:

- implement the voice pipeline.
- install or configure production STT/TTS/LLM providers.
- download model weights.
- implement Pipecat runtime logic.
- implement RAG retrieval code.
- implement SQLite schemas beyond placeholder/scaffold files.
- implement ROS/navigation.
- copy donor source code into production yet.
- change architecture choices.
- add extra donor repositories.
- remove repositories from the frozen set.
- commit API keys or secrets.
- run destructive Git commands against unrelated repositories.
- delete or overwrite an existing GitHub repository.

The final state must be:

**"Workspace ready for Phase 1" — not "Phase 1 started."**

---

# 3. Expected Workspace Layout

Create the workspace in the working directory selected by the user.

```text
InnoBrainWorkspace/
│
├── inno-brain/                      # OUR production GitHub repository
│   ├── MASTER_PLAN.md
│   ├── CODEX_PRE_PHASE1_BOOTSTRAP.md
│   ├── README.md
│   ├── .gitignore
│   │
│   ├── src/
│   │   └── innobrain/
│   │       ├── __init__.py
│   │       ├── audio/
│   │       ├── voice/
│   │       ├── providers/
│   │       │   ├── stt/
│   │       │   ├── llm/
│   │       │   ├── tts/
│   │       │   └── embeddings/
│   │       ├── conversation/
│   │       ├── knowledge/
│   │       ├── event/
│   │       ├── robot/
│   │       └── telemetry/
│   │
│   ├── config/
│   ├── events/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── evals/
│   │   ├── audio/
│   │   ├── stt/
│   │   ├── rag/
│   │   ├── tts/
│   │   ├── conversation/
│   │   └── latency/
│   ├── scripts/
│   └── docs/
│       ├── research/
│       │   ├── DONOR_REPOS.md
│       │   ├── DONOR_REPOS.lock.yaml
│       │   └── DONOR_INSPECTION.md
│       └── bootstrap/
│           └── BOOTSTRAP_REPORT.md
│
└── donor-repos/                     # sibling research repositories
    ├── pipecat/
    ├── smart-turn/
    ├── silero-vad/
    ├── sqlite-vec/
    ├── pywebrtc-audio/
    ├── llama.cpp/
    ├── metro-asr/
    ├── VoiceTuT-TTS/
    ├── voice-agent-starter/
    ├── GLaDOS/
    ├── pepper-android-realtime-chat/
    ├── compact-rag/
    └── docling/
```

Empty production directories may contain `.gitkeep` files when needed so Git tracks the intended structure.

The `donor-repos/` directory MUST NOT be nested inside `inno-brain/`.

---

# 4. GitHub Repository Requirements

Repository:

`inno-brain`

Recommended visibility:

`private`

Default branch:

`main`

Before creating anything, run:

```bash
git --version
gh --version
gh auth status
```

If GitHub CLI authentication succeeds:

1. Check whether a repository named `inno-brain` already exists for the authenticated owner.
2. If it does NOT exist, create a new private repository.
3. If it DOES exist:
   - inspect its remote metadata.
   - do not overwrite it.
   - do not force push.
   - stop remote-creation work and report the conflict unless it is clearly the intended empty/new repository.

Preferred creation flow after local scaffold:

```bash
cd InnoBrainWorkspace/inno-brain
git init -b main
git add .
git commit -m "chore: bootstrap InnoBrain workspace"
gh repo create inno-brain --private --source . --remote origin --push
```

If `gh auth status` fails:

- continue the LOCAL bootstrap.
- initialize local Git.
- make the local bootstrap commit.
- do NOT fabricate a remote.
- record `GitHub remote creation blocked: authentication required` in `docs/bootstrap/BOOTSTRAP_REPORT.md`.
- provide the exact next command the user must run after authentication.

Never request or store a GitHub token inside repository files.

---

# 5. Frozen Donor Repository Set

Clone exactly these 13 repositories for V1.

Use shallow clones (`--depth 1`) unless a repository requires history to understand a critical implementation detail.

## Foundation

### 1. Pipecat

```bash
git clone --depth 1 https://github.com/pipecat-ai/pipecat.git donor-repos/pipecat
```

Role:

- realtime voice runtime.
- frame/pipeline architecture.
- provider integration patterns.
- interruption/turn-processing reference.

Inspect first:

- `README.md`
- package/source layout.
- voice examples.
- turn-management examples.
- service/provider interfaces.
- interruption/cancellation-related code.
- tests related to pipelines and interruptions.

### 2. Smart Turn

```bash
git clone --depth 1 https://github.com/pipecat-ai/smart-turn.git donor-repos/smart-turn
```

Role:

- semantic end-of-turn detection.

Inspect first:

- `README.md`
- `inference.py`
- `predict.py`
- `requirements_aarch64.txt`
- model input expectations.
- Arabic language support.
- 16 kHz PCM assumptions.

### 3. Silero VAD

```bash
git clone --depth 1 https://github.com/snakers4/silero-vad.git donor-repos/silero-vad
```

Role:

- lightweight speech activity detection.

Inspect first:

- README.
- Python inference examples.
- ONNX support.
- sample-rate requirements.
- streaming/state handling.
- licensing/model licensing notes.

### 4. sqlite-vec

```bash
git clone --depth 1 https://github.com/asg017/sqlite-vec.git donor-repos/sqlite-vec
```

Role:

- local vector storage/search inside SQLite.

Inspect first:

- README.
- Python bindings/install docs.
- `vec0` examples.
- metadata filtering.
- float/int8 options.
- Raspberry Pi/ARM notes.
- current version and pre-v1 warning.

### 5. pywebrtc-audio

```bash
git clone --depth 1 https://github.com/strands-labs/pywebrtc-audio.git donor-repos/pywebrtc-audio
```

Role:

- optional WebRTC AEC/NS/AGC processing if Anker S330 DSP is insufficient.

Inspect first:

- README.
- Python API.
- near/far audio interface.
- supported sample rates/frame sizes.
- Linux/aarch64 packaging.
- benchmarks.
- examples involving playback-reference AEC.

### 6. llama.cpp

```bash
git clone --depth 1 https://github.com/ggml-org/llama.cpp.git donor-repos/llama.cpp
```

Role:

- local fallback LLM runtime on Raspberry Pi/ARM.

Inspect first:

- ARM/Linux build documentation.
- server/OpenAI-compatible mode.
- memory-mapping and quantization support.
- relevant performance flags.
- do NOT build or download models during bootstrap.

---

# 6. Egyptian Speech Repositories

### 7. Metro-ASR

```bash
git clone --depth 1 https://github.com/MohammedAly22/metro-asr.git donor-repos/metro-asr
```

Role:

- local Egyptian-Arabic STT finalist/fallback candidate.

Inspect first:

- README.
- model sizes.
- inference path.
- CPU assumptions.
- sample rate/input format.
- Arabic-English handling.
- streaming limitations.
- model license and code license separately.

Do NOT download model weights during bootstrap.

### 8. VoiceTuT-TTS

```bash
git clone --depth 1 https://github.com/MohammedAly22/VoiceTuT-TTS.git donor-repos/VoiceTuT-TTS
```

Role:

- Egyptian-Arabic TTS reference.
- Egyptian text-normalization donor.
- Arabic/English code-switch pronunciation reference.

Inspect first:

- README.
- normalization modules.
- lexicon/diacritics handling.
- streaming implementation.
- provider/API-like boundaries.
- model and code licenses.
- hardware/VRAM requirements.

Do NOT download large weights during bootstrap.

---

# 7. Voice Architecture Donors

### 9. voice-agent-starter

```bash
git clone --depth 1 https://github.com/sarmakska/voice-agent-starter.git donor-repos/voice-agent-starter
```

Role:

- clean STT/LLM/TTS adapter boundaries.
- state transitions.
- barge-in cancellation.
- testing patterns.

Inspect first:

- architecture README.
- provider adapters.
- duplex pipeline.
- cancellation code.
- tool-call passthrough.
- barge-in/integration tests.

Important:

This is a design/code donor, NOT our runtime foundation.

### 10. GLaDOS

```bash
git clone --depth 1 https://github.com/dnhkng/GLaDOS.git donor-repos/GLaDOS
```

Role:

- low-latency natural voice-assistant patterns.
- interruption handling.
- memory/context design.
- proactive/event architecture reference.

Inspect first:

- `README.md`
- `src/`
- audio pipeline.
- interruption logic.
- memory implementation.
- context assembly.
- latency-focused implementation.
- tests.
- configuration structure.

Do NOT copy personality/IP-specific behavior into InnoBrain.

### 11. Pepper Realtime AI Assistant

```bash
git clone --depth 1 https://github.com/studerus/pepper-android-realtime-chat.git donor-repos/pepper-android-realtime-chat
```

Role:

- physical robot + realtime AI reference.
- semantic tools.
- navigation/function calling.
- perception events.
- multimodal robot lifecycle.

Inspect first:

- README architecture.
- function-calling/tool definitions.
- navigation abstraction.
- event/perception system.
- session lifecycle.
- tablet/screen integration.
- graceful-degradation patterns.

Important:

Do not import Pepper/Android-specific layers into the production Python architecture.

---

# 8. RAG and Knowledge Donors

### 12. Compact RAG

```bash
git clone --depth 1 https://github.com/araobp/compact-rag.git donor-repos/compact-rag
```

Role:

- Raspberry-Pi-oriented RAG architecture.
- SQLite + sqlite-vec usage.
- hybrid structured/vector concepts.
- service/deployment ideas.

Inspect first:

- README.
- SQLite schema.
- sqlite-vec integration.
- retrieval logic.
- service layout.
- systemd/deployment notes.

Important:

Its external API/model choices are references only. InnoBrain keeps provider adapters and local-first retrieval.

### 13. Docling

```bash
git clone --depth 1 https://github.com/docling-project/docling.git donor-repos/docling
```

Role:

- pre-event document ingestion/parsing.

Inspect first:

- supported formats.
- conversion/document model.
- table/layout extraction.
- export formats.
- Python API.
- dependency weight.
- whether ingestion should stay off-Pi.

Do NOT install the full Docling dependency stack during bootstrap.

---

# 9. Repositories Explicitly NOT Cloned Now

Do not add these during this task:

- QwenCleo-ASR.
- sherpa-onnx.
- FlagEmbedding.
- protoVoice.
- WhisperLive.
- faster-whisper.
- whisper.cpp.
- DeepFilterNet.
- RNNoise.
- LiveKit Agents.
- TEN Framework.
- any new repository discovered during inspection.

If one appears valuable, record it under:

`Potential Future Donors`

inside `docs/research/DONOR_INSPECTION.md`.

Do not clone it.

---

# 10. Donor Repository Inventory

After cloning, collect for every donor:

```bash
git -C <repo_path> remote get-url origin
git -C <repo_path> branch --show-current
git -C <repo_path> rev-parse HEAD
git -C <repo_path> status --short
```

Also inspect:

- root license files.
- README.
- package metadata.
- relevant subdirectories.

Create:

`inno-brain/docs/research/DONOR_REPOS.lock.yaml`

Use this structure:

```yaml
generated_at: "<ISO-8601>"
repositories:
  - name: pipecat
    url: https://github.com/pipecat-ai/pipecat.git
    local_path: ../donor-repos/pipecat
    branch: main
    commit: "<40-char SHA>"
    license: "<license found in repository>"
    category: foundation
    role: "Realtime voice runtime and provider/pipeline reference"
    production_dependency: false
```

Requirements:

- exact commit SHA.
- no guessed licenses.
- if license is ambiguous, write `REVIEW_REQUIRED` and explain in the inspection report.
- `production_dependency: false` for every donor at bootstrap time.

---

# 11. Donor Inspection Report

Create:

`inno-brain/docs/research/DONOR_INSPECTION.md`

For EACH repository include:

```markdown
## Repo Name

**URL:** ...
**Commit inspected:** ...
**License:** ...
**Why cloned:** ...
**Most relevant files/directories:**
- ...

**What InnoBrain can reuse/adapt:**
- ...

**What InnoBrain should NOT copy/adopt:**
- ...

**Dependencies / hardware assumptions:**
- ...

**Phase(s) this repo may help:**
- Phase 1 / Phase 2 / ...

**Inspection verdict:**
- KEEP
- KEEP AS REFERENCE ONLY
- LICENSE REVIEW REQUIRED
```

The report must distinguish:

- reusable source code.
- architecture inspiration.
- model weights.
- third-party datasets.
- licenses.

Do not assume a repository's code license automatically covers model weights or datasets.

---

# 12. Production Repository Scaffold

Inside `inno-brain/`, create the folder structure shown in Section 3.

Create only minimal files.

## `src/innobrain/__init__.py`

Use:

```python
"""InnoBrain AI/voice subsystem."""
```

Do NOT implement runtime logic.

## `.gitignore`

At minimum ignore:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Secrets
.env
.env.*
!.env.example
*.pem
*.key

# Models / large runtime artifacts
models/
*.gguf
*.onnx
*.safetensors
*.bin

# Event runtime data
events/current/
*.db-wal
*.db-shm

# Logs / captures
logs/
recordings/
*.wav

# OS / IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
```

Do NOT ignore the Master Plan.

## `README.md`

Keep bootstrap-level only.

It should state:

- project name: InnoBrain.
- purpose: Egyptian-Arabic-first AI/voice brain for the event robot.
- Raspberry Pi 5 8GB target.
- Anker PowerConf S330 audio hardware.
- Master Plan is the source of truth.
- implementation has not started yet.
- current status: Pre-Phase-1 bootstrap.
- donor repos are siblings and are not production dependencies.
- next milestone: Phase 1 Foundation + Hardware Validation.

Do not duplicate the full Master Plan into README.

---

# 13. Copy Required Documentation

Copy the attached/current Master Plan into:

`inno-brain/MASTER_PLAN.md`

Copy this bootstrap file into:

`inno-brain/CODEX_PRE_PHASE1_BOOTSTRAP.md`

Do not rename the canonical file inside the production repo.

The canonical in-repo name is:

`MASTER_PLAN.md`

---

# 14. Bootstrap Report

Create:

`inno-brain/docs/bootstrap/BOOTSTRAP_REPORT.md`

Include:

## Environment

- OS.
- shell.
- Git version.
- GitHub CLI version.
- GitHub auth status.
- Python version detected.
- workspace absolute path.

## Production Repository

- local path.
- Git status.
- branch.
- remote URL if created.
- visibility if known.
- initial commit SHA.

## Donors

- expected count: 13.
- actual count.
- donor paths.
- whether every donor is clean.
- whether every donor has an inventory entry.

## Inspection

- report exists.
- any licenses requiring review.
- any repository missing expected files.
- any broken/dead repository URLs.

## Architecture Findings

List only findings that may require Master Plan changes.

If none:

`No architecture-blocking findings discovered during bootstrap.`

## Blockers

List exact blockers.

## Final State

Use exactly one:

- `READY_FOR_PHASE_1`
- `BLOCKED_BEFORE_PHASE_1`

Do not claim READY unless all verification checks below pass.

---

# 15. Verification Checklist

Run fresh verification immediately before completion.

## Workspace

Confirm:

```text
InnoBrainWorkspace/
├── inno-brain/
└── donor-repos/
```

## Donor count

There must be exactly 13 expected donor repository directories.

Do not count hidden folders.

## Donor Git health

For each donor:

```bash
git -C <repo> rev-parse --is-inside-work-tree
git -C <repo> status --short
git -C <repo> rev-parse HEAD
```

Expected:

- inside work tree = true.
- status output empty.
- valid 40-character commit SHA.

## Production Git health

Run:

```bash
cd inno-brain
git status
git branch --show-current
git log -1 --oneline
git remote -v
```

Expected when GitHub auth was available:

- branch `main`.
- clean working tree after final commit.
- `origin` configured.
- bootstrap commit exists.
- push succeeded.

When auth was unavailable:

- local repo still has `main`.
- local bootstrap commit exists.
- report states remote blocker.

## Documentation

Verify these exist:

```text
MASTER_PLAN.md
CODEX_PRE_PHASE1_BOOTSTRAP.md
docs/research/DONOR_REPOS.md
docs/research/DONOR_REPOS.lock.yaml
docs/research/DONOR_INSPECTION.md
docs/bootstrap/BOOTSTRAP_REPORT.md
```

`DONOR_REPOS.md` should be a short human-readable index generated from the lock/inventory work.

## Architecture boundary

Search production code for direct relative imports/references to `donor-repos`.

There must be no production import from sibling donor directories.

## Secrets

Search staged/tracked files for obvious API key/token patterns.

Do not print secret values in logs.

If a real secret is found:

- remove it from Git tracking.
- document the incident.
- do not push until corrected.

---

# 16. Commit Strategy

Use small commits where practical.

Recommended:

### Commit 1

```text
chore: scaffold InnoBrain repository
```

Contains:

- directory structure.
- `.gitignore`.
- README.
- Master Plan.
- bootstrap handoff.

### Commit 2

```text
docs: add donor repository inventory and inspection
```

Contains:

- donor lock file.
- donor index.
- inspection report.
- bootstrap report.

If the repository is tiny enough that one bootstrap commit is clearer, one commit is acceptable.

Never commit cloned donor repositories into `inno-brain`.

---

# 17. Stop Condition

STOP after the workspace bootstrap.

Do not continue into Phase 1.

Your final response to the user must summarize:

1. workspace path.
2. production repo path.
3. GitHub remote URL or auth blocker.
4. donor repos cloned: `13/13` or actual count.
5. inspection report path.
6. licenses needing review.
7. bootstrap verification result.
8. exact final state:
   - `READY_FOR_PHASE_1`
   - or `BLOCKED_BEFORE_PHASE_1`
9. one short sentence describing the next action:
   - `Next: begin Phase 1 — Foundation + Hardware Validation.`

Do NOT say Phase 1 has started.

---

# 18. Failure Handling

If any donor clone fails:

1. retry once.
2. verify the canonical GitHub URL.
3. do not silently replace it with another repository.
4. record failure in bootstrap report.
5. final state becomes `BLOCKED_BEFORE_PHASE_1` unless the failure is explicitly waived by the user.

If a license is missing/unclear:

- complete the clone.
- mark `REVIEW_REQUIRED`.
- do not copy code from that donor.
- bootstrap may still be READY if the repo is reference-only and no code has been reused.

If GitHub repository creation fails:

- complete local bootstrap.
- do not delete/recreate unrelated repositories.
- report the exact CLI error category without exposing secrets.

If the Master Plan and this handoff contradict each other:

**The newer Master Plan is authoritative for architecture.**

For bootstrap mechanics, this handoff is authoritative unless it conflicts with the Master Plan.

---

# 19. Definition of Done

The pre-Phase-1 bootstrap is done only when:

- `InnoBrainWorkspace` exists.
- `inno-brain` production repo exists.
- production repo is initialized on `main`.
- GitHub repo is created/pushed OR auth blocker is explicitly documented.
- the latest Master Plan exists as `inno-brain/MASTER_PLAN.md`.
- this handoff exists inside the repo.
- all 13 frozen donors were cloned successfully.
- all donors have exact SHA/license inventory entries.
- all donor repos were inspected.
- donor inspection report exists.
- production scaffold exists.
- no Phase 1 implementation was started.
- no model weights were downloaded.
- no secrets were committed.
- verification was run fresh.
- Bootstrap Report contains `READY_FOR_PHASE_1`.

---

**End of Codex Pre-Phase-1 Bootstrap Handoff**

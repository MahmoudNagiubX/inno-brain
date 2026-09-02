# InnoBrain Phase 2 — Realtime Conversation Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` when available. If those skills are unavailable in the current Codex environment, follow this document task-by-task without improvising. Steps use checkbox syntax for tracking.
>
> **Goal:** Build and validate InnoBrain's laptop realtime interaction core: streaming microphone PCM, Pipecat, Silero VAD, Smart Turn semantic endpointing, strict conversation state, and fast interruption/cancellation — without adding STT, LLM, TTS, RAG, memory, or robot integration.
>
> **Architecture:** Keep the Phase 1 `sounddevice` audio backend. Feed 16 kHz mono PCM chunks into a pinned Pipecat 1.8.1 `PipelineWorker` as `InputAudioRawFrame`s. The pipeline runs `VADProcessor(SileroVADAnalyzer)` then `UserTurnProcessor` configured with VAD-based turn start and `LocalSmartTurnAnalyzerV3` turn stop with `wait_for_transcript=False`. InnoBrain owns product state and cancellation outside provider-specific code.
>
> **Tech Stack:** Windows 11, Python 3.14.6 currently; project supports `>=3.11,<3.15`; `pipecat-ai==1.8.1`; `sounddevice`; NumPy; Pydantic; PyYAML; pytest; pytest-asyncio; Ruff.
>
> **Spec:** `MASTER_PLAN.md`
>
> **Starting source branch:** `phase/1-foundation-laptop-audio`
>
> **Expected Phase 1 source HEAD:** `03b46778133ccb5cd8308d8cff739448470c2f1d`
>
> **Phase 2 branch:** `phase/2-realtime-conversation-core`
>
> **Primary product language:** Egyptian Arabic (`ar-EG`).
>
> **STOP RULE:** Do not start Phase 3.

---

# Global Constraints

- Development and interactive testing are on the Windows laptop.
- Raspberry Pi 5 and Anker S330 are deployment targets and are NOT Phase 2 blockers.
- Phase 2 branch MUST inherit completed Phase 1 code.
- Do not branch Phase 2 from stale `main`.
- Pipecat is pinned to `1.8.1`.
- Do not install Pipecat from the sibling donor checkout.
- Do not use `pipecat-ai[local]` or PyAudio in Phase 2.
- Do not replace Phase 1 `sounddevice` I/O with a different audio backend.
- Use Pipecat's packaged `SileroVADAnalyzer` and `LocalSmartTurnAnalyzerV3`.
- No separate Silero/Smart-Turn model download.
- No STT SDK/provider.
- No LLM SDK/provider.
- No TTS SDK/provider.
- No API keys.
- No network AI calls.
- No RAG/SQLite/vector work.
- No memory implementation.
- No ROS/navigation/screen work.
- No software AEC/NS in Phase 2.
- Do not hard-code Windows audio device indices into committed configuration.
- Do not modify donor repositories.
- Existing donor inspection is authoritative unless an exact source file is needed.
- Every code task follows red → green → Ruff → commit.
- One task at a time.
- Maximum two direct fixes for an unexpected execution error; after that mark the task blocked instead of redesigning.
- Never claim a live microphone/turn/barge-in test passed without running it.
- Never mark Phase 2 complete before the user interaction gate passes.
- Do not merge the Phase 2 branch automatically.

---

# Why these exact Pipecat choices are locked

The pinned stable package is:

```text
pipecat-ai==1.8.1
```

The required imports exist in the Pipecat 1.8.1 release:

```python
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndFrame, InputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.turns.user_start import VADUserTurnStartStrategy
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_processor import UserTurnProcessor
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner
```

Critical Phase 2 rule:

```python
TurnAnalyzerUserTurnStopStrategy(
    turn_analyzer=LocalSmartTurnAnalyzerV3(...),
    wait_for_transcript=False,
)
```

`wait_for_transcript=False` is mandatory in Phase 2 because there is intentionally no STT yet.

The Pipecat default VAD baseline at 1.8.1 is:

```text
confidence = 0.7
start_secs = 0.2
stop_secs = 0.2
min_volume = 0.6
```

Do not silently tune these.

---

# Phase 2 final states

Use exactly one:

```text
PHASE_2_COMPLETE
PHASE_2_WAITING_FOR_INTERACTION_CONFIRMATION
PHASE_2_BLOCKED
```

---

# Task Map

```text
Task 0   Verify Phase 1 source and create Phase 2 branch
Task 1   Sync Master Plan v1.7 + Phase 2 state docs
Task 2   Pin/install Pipecat 1.8.1 + dependency smoke
Task 3   Add realtime/VAD/Smart-Turn config
Task 4   Implement strict conversation state machine
Task 5   Implement single-session interruptible playback
Task 6   Implement interruption controller + latency record
Task 7   Implement async laptop PCM input pump
Task 8   Implement Pipecat VAD + Smart Turn runtime
Task 9   Add Phase 2 Egyptian eval scenarios + text echo demo
Task 10  Automated Phase 2 verification
Task 11  Offline Phase 1 recording VAD probe
Task 12  Live Egyptian turn-detection tests
Task 13  Live barge-in/cancellation test
Task 14  Stop for user interaction confirmation
Task 15  Finalize report, Master Plan v1.8, push branch
STOP
```

---

# Task 0 — Verify Phase 1 source and create the Phase 2 branch

**Files:** none.

**Purpose:** Ensure Phase 2 includes Phase 1 and does not branch from stale `main`.

- [ ] **Step 1: Go to production repo**

```powershell
Set-Location "C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain"
```

- [ ] **Step 2: Check for user work**

```powershell
git status --short
```

Expected:

```text
<no output>
```

If not empty:

**STOP. Do not stash, reset, discard, or overwrite anything. Report the paths.**

- [ ] **Step 3: Fetch remotes**

```powershell
git fetch origin
```

- [ ] **Step 4: Switch to completed Phase 1 branch**

```powershell
git switch "phase/1-foundation-laptop-audio"
git pull --ff-only origin "phase/1-foundation-laptop-audio"
```

- [ ] **Step 5: Verify source state**

```powershell
git rev-parse HEAD
Select-String -Path docs\phase1\PHASE1_REPORT.md -Pattern "PHASE_1_COMPLETE"
Select-String -Path MASTER_PLAN.md -Pattern "Version:\*\* 1.6"
```

Expected planning-time HEAD:

```text
03b46778133ccb5cd8308d8cff739448470c2f1d
```

If HEAD is newer, accept it only if:

- working tree is clean;
- `PHASE_1_COMPLETE` is still present;
- Master Plan is v1.6 or a legitimate later patch;
- no Phase 2 implementation has already begun.

Do NOT reset a legitimate newer Phase 1 branch.

- [ ] **Step 6: Create/switch Phase 2 branch**

Check:

```powershell
git branch --list "phase/2-realtime-conversation-core"
```

If absent:

```powershell
git switch -c "phase/2-realtime-conversation-core"
```

If already present:

```powershell
git switch "phase/2-realtime-conversation-core"
```

- [ ] **Step 7: Verify branch**

```powershell
git branch --show-current
git status --short
```

Expected:

```text
phase/2-realtime-conversation-core
```

and clean status.

**Checkpoint:** Phase 2 branch exists and contains completed Phase 1.

---

# Task 1 — Sync Master Plan v1.7 and Phase 2 execution docs

**Files:**
- Replace/update: `MASTER_PLAN.md`
- Create: `CODEX_PHASE2_REALTIME_CONVERSATION_CORE.md`
- Create: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Consumes: Phase 1 repository state.
- Produces: authoritative Phase 2 scope/status for every later task.

The user will attach:

```text
InnoBrain_MASTER_PLAN_v1.7.md
CODEX_PHASE2_REALTIME_CONVERSATION_CORE.md
```

- [ ] **Step 1: Preserve Phase 1 evidence before replacing Master Plan**

Run:

```powershell
Select-String -Path MASTER_PLAN.md -Pattern "PHASE_1_COMPLETE|03b46778133ccb5cd8308d8cff739448470c2f1d|9 passed|Ruff"
```

Then copy the attached v1.7 file to `MASTER_PLAN.md`.

After replacement verify the same Phase 1 facts still exist.

If attached v1.7 is missing an actual Phase 1 fact that exists in current v1.6:

**Do not delete the fact. Merge the missing Phase 1 fact into v1.7 before committing.**

- [ ] **Step 2: Copy this Phase 2 handoff into repo**

Canonical filename:

```text
CODEX_PHASE2_REALTIME_CONVERSATION_CORE.md
```

- [ ] **Step 3: Create Phase 2 state**

Create `docs/phase2/PHASE2_STATE.md`:

```markdown
# Phase 2 State

**Phase:** 2 — Realtime Conversation Core  
**Branch:** `phase/2-realtime-conversation-core`  
**Status:** `IN_PROGRESS`  
**Last completed task:** Task 1  
**Next task:** Task 2 — Pin/install Pipecat 1.8.1 + dependency smoke  
**Development platform:** Windows laptop  
**Primary language:** Egyptian Arabic (`ar-EG`)  
**Pipecat:** Not installed for Phase 2 yet  
**Silero VAD:** Not validated yet  
**Smart Turn:** Not validated yet  
**Live turn detection:** Not started  
**Barge-in:** Not started  
**Pi/S330:** Deferred deployment validation  
**Phase 3 authorized:** No
```

- [ ] **Step 4: Verify docs**

```powershell
Select-String -Path MASTER_PLAN.md -Pattern "Version:\*\* 1.7"
Select-String -Path MASTER_PLAN.md -Pattern "PHASE_1_COMPLETE"
Test-Path CODEX_PHASE2_REALTIME_CONVERSATION_CORE.md
Test-Path docs\phase2\PHASE2_STATE.md
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add MASTER_PLAN.md CODEX_PHASE2_REALTIME_CONVERSATION_CORE.md docs/phase2/PHASE2_STATE.md
git commit -m "docs: start Phase 2 realtime conversation core"
```

---

# Task 2 — Pin and install Pipecat 1.8.1

**Files:**
- Modify: `pyproject.toml`
- Create: `scripts/phase2/dependency_smoke.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Produces: stable imports used by Tasks 8+.

## Dependency changes

Modify project dependencies to add exactly:

```toml
"pipecat-ai==1.8.1",
```

Modify `dev` dependencies to add:

```toml
"pytest-asyncio>=1,<2",
```

Do NOT add:

```text
pipecat-ai[local]
pyaudio
silero-vad
smart-turn
torch
torchaudio
transformers
```

Phase 2 uses the local models already packaged by Pipecat.

- [ ] **Step 1: Edit `pyproject.toml`**

Expected relevant shape:

```toml
dependencies = [
    "numpy>=2.0,<3",
    "pipecat-ai==1.8.1",
    "pydantic>=2.13,<3",
    "PyYAML>=6,<7",
    "sounddevice>=0.5,<1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8,<10",
    "pytest-asyncio>=1,<2",
    "pytest-cov>=5,<8",
    "ruff>=0.12,<1",
]
```

- [ ] **Step 2: Install updated project**

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Do not create a second environment unless the current `.venv` is missing/corrupt.

If installation fails due to a specific Pipecat transitive dependency:

1. read the actual resolver/wheel error;
2. retry once with the upgraded pip;
3. do not unpin Pipecat;
4. do not randomly downgrade packages;
5. if still failing, set `PHASE_2_BLOCKED` and report the exact dependency.

- [ ] **Step 3: Create dependency smoke script**

Create `scripts/phase2/dependency_smoke.py`:

```python
import asyncio
from importlib.metadata import version

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer


async def main() -> int:
    installed = version("pipecat-ai")
    if installed != "1.8.1":
        raise RuntimeError(f"Expected pipecat-ai 1.8.1, got {installed}")

    vad = SileroVADAnalyzer(sample_rate=16000)
    smart_turn = LocalSmartTurnAnalyzerV3(cpu_count=1)

    try:
        print(f"PIPECAT_VERSION={installed}")
        print("SILERO_INIT_OK")
        print("SMART_TURN_V3_INIT_OK")
    finally:
        await vad.cleanup()
        await smart_turn.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 4: Run smoke**

```powershell
.\.venv\Scripts\python.exe scripts\phase2\dependency_smoke.py
```

Expected:

```text
PIPECAT_VERSION=1.8.1
SILERO_INIT_OK
SMART_TURN_V3_INIT_OK
```

- [ ] **Step 5: Regression**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
```

Expected at this point: existing Phase 1 tests still pass.

- [ ] **Step 6: Update state + commit**

Set:

```text
Last completed task: Task 2
Next task: Task 3 — Add realtime/VAD/Smart-Turn config
Pipecat: 1.8.1 import/model initialization PASS
```

Commit:

```powershell
git add pyproject.toml scripts/phase2/dependency_smoke.py docs/phase2/PHASE2_STATE.md
git commit -m "build: pin Phase 2 Pipecat runtime"
```

---

# Task 3 — Add realtime, VAD, and Smart Turn configuration

**Files:**
- Modify: `src/innobrain/config/models.py`
- Modify: `config/runtime.yaml`
- Modify: `tests/unit/config/test_loader.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Produces:
  - `RuntimeConfig.realtime`
  - `VADRuntimeConfig`
  - `SmartTurnRuntimeConfig`
  - `RealtimeRuntimeConfig`

- [ ] **Step 1: Extend failing config assertions first**

Add assertions to the existing config test:

```python
assert configs.runtime.realtime.audio_queue_max_chunks == 100
assert configs.runtime.realtime.vad.confidence == 0.7
assert configs.runtime.realtime.vad.start_secs == 0.2
assert configs.runtime.realtime.vad.stop_secs == 0.2
assert configs.runtime.realtime.vad.min_volume == 0.6
assert configs.runtime.realtime.smart_turn.enabled is True
assert configs.runtime.realtime.smart_turn.wait_for_transcript is False
assert configs.runtime.realtime.smart_turn.cpu_count == 1
assert configs.runtime.realtime.mock_response_tone_hz == 440.0
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\config\test_loader.py -q
```

Expected: FAIL because the new realtime config does not exist yet.

- [ ] **Step 2: Add config models**

Add to `src/innobrain/config/models.py`:

```python
class VADRuntimeConfig(StrictModel):
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    start_secs: float = Field(default=0.2, ge=0.0, le=2.0)
    stop_secs: float = Field(default=0.2, ge=0.0, le=3.0)
    min_volume: float = Field(default=0.6, ge=0.0, le=1.0)


class SmartTurnRuntimeConfig(StrictModel):
    enabled: bool = True
    wait_for_transcript: bool = False
    cpu_count: int = Field(default=1, ge=1, le=8)


class RealtimeRuntimeConfig(StrictModel):
    audio_queue_max_chunks: int = Field(default=100, ge=10, le=1000)
    vad: VADRuntimeConfig
    smart_turn: SmartTurnRuntimeConfig
    mock_think_delay_ms: int = Field(default=150, ge=0, le=2000)
    mock_response_tone_hz: float = Field(default=440.0, ge=100.0, le=2000.0)
    mock_response_duration_secs: float = Field(default=6.0, ge=1.0, le=30.0)
    mock_response_volume: float = Field(default=0.08, ge=0.01, le=0.25)
```

Add field to `RuntimeConfig`:

```python
realtime: RealtimeRuntimeConfig
```

Export the new models from `src/innobrain/config/__init__.py`.

- [ ] **Step 3: Update runtime YAML**

Append under the existing `audio` block:

```yaml
realtime:
  audio_queue_max_chunks: 100

  vad:
    confidence: 0.7
    start_secs: 0.2
    stop_secs: 0.2
    min_volume: 0.6

  smart_turn:
    enabled: true
    wait_for_transcript: false
    cpu_count: 1

  mock_think_delay_ms: 150
  mock_response_tone_hz: 440.0
  mock_response_duration_secs: 6.0
  mock_response_volume: 0.08
```

Do not commit numeric laptop device indices.

- [ ] **Step 4: Green test**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\config\test_loader.py -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

- [ ] **Step 5: Commit**

Update state to Task 3 complete / Task 4 next.

```powershell
git add src/innobrain/config config/runtime.yaml tests/unit/config docs/phase2/PHASE2_STATE.md
git commit -m "feat: add realtime turn configuration"
```

---

# Task 4 — Implement strict conversation state machine

**Files:**
- Create: `src/innobrain/voice/__init__.py`
- Create: `src/innobrain/voice/state.py`
- Create: `tests/unit/voice/test_state.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Produces:
  - `ConversationState`
  - `StateTransition`
  - `ConversationStateMachine`
  - `InvalidStateTransition`

## Allowed state graph

```text
IDLE → LISTENING

LISTENING → THINKING

THINKING → SPEAKING
THINKING → LISTENING
THINKING → INTERRUPTED

SPEAKING → LISTENING
SPEAKING → INTERRUPTED

INTERRUPTED → LISTENING
```

No other transition is valid.

- [ ] **Step 1: Write failing tests**

`tests/unit/voice/test_state.py`:

```python
import pytest

from innobrain.voice.state import (
    ConversationState,
    ConversationStateMachine,
    InvalidStateTransition,
)


def test_normal_turn_state_cycle() -> None:
    machine = ConversationStateMachine()

    machine.transition(ConversationState.LISTENING, "runtime_started")
    machine.transition(ConversationState.THINKING, "user_turn_complete")
    machine.transition(ConversationState.SPEAKING, "response_playback_started")
    machine.transition(ConversationState.LISTENING, "response_playback_finished")

    assert machine.state is ConversationState.LISTENING
    assert [item.to_state for item in machine.history] == [
        ConversationState.LISTENING,
        ConversationState.THINKING,
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
    ]


def test_speaking_can_be_interrupted() -> None:
    machine = ConversationStateMachine()
    machine.transition(ConversationState.LISTENING, "runtime_started")
    machine.transition(ConversationState.THINKING, "user_turn_complete")
    machine.transition(ConversationState.SPEAKING, "response_started")
    machine.transition(ConversationState.INTERRUPTED, "user_barge_in")
    machine.transition(ConversationState.LISTENING, "interruption_handled")

    assert machine.state is ConversationState.LISTENING


def test_invalid_transition_is_rejected() -> None:
    machine = ConversationStateMachine()

    with pytest.raises(InvalidStateTransition):
        machine.transition(ConversationState.SPEAKING, "invalid")
```

Run and confirm FAIL.

- [ ] **Step 2: Implement**

`src/innobrain/voice/state.py`:

```python
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter


class ConversationState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True, slots=True)
class StateTransition:
    at_monotonic: float
    from_state: ConversationState
    to_state: ConversationState
    reason: str


class InvalidStateTransition(RuntimeError):
    pass


_ALLOWED: dict[ConversationState, set[ConversationState]] = {
    ConversationState.IDLE: {ConversationState.LISTENING},
    ConversationState.LISTENING: {ConversationState.THINKING},
    ConversationState.THINKING: {
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
    },
    ConversationState.SPEAKING: {
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
    },
    ConversationState.INTERRUPTED: {ConversationState.LISTENING},
}


class ConversationStateMachine:
    def __init__(self) -> None:
        self._state = ConversationState.IDLE
        self._history: list[StateTransition] = []

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def history(self) -> tuple[StateTransition, ...]:
        return tuple(self._history)

    def transition(self, to_state: ConversationState, reason: str) -> StateTransition:
        if to_state not in _ALLOWED[self._state]:
            raise InvalidStateTransition(
                f"Invalid transition {self._state.value} -> {to_state.value}: {reason}"
            )

        transition = StateTransition(
            at_monotonic=perf_counter(),
            from_state=self._state,
            to_state=to_state,
            reason=reason,
        )
        self._state = to_state
        self._history.append(transition)
        return transition
```

Export from `voice/__init__.py`.

- [ ] **Step 3: Green + lint**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\voice\test_state.py -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

Expected new tests: 3 passed.

- [ ] **Step 4: Commit**

```powershell
git add src/innobrain/voice tests/unit/voice/test_state.py docs/phase2/PHASE2_STATE.md
git commit -m "feat: add strict conversation state machine"
```

---

# Task 5 — Implement single-session interruptible playback

**Files:**
- Create: `src/innobrain/voice/playback.py`
- Create: `tests/unit/voice/test_playback.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Produces:
  - `PlaybackBackend`
  - `SoundDevicePlaybackBackend`
  - `PlaybackController`
  - `PlaybackSnapshot`
- Contract: maximum one active playback session.

The output in Phase 2 is a quiet generated tone, not speech/TTS.

- [ ] **Step 1: Write failing async test**

Use a fake backend.

`tests/unit/voice/test_playback.py`:

```python
import asyncio

import pytest

from innobrain.voice.playback import PlaybackController


class FakePlaybackBackend:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.release = asyncio.Event()

    async def play(self, samples, sample_rate_hz: int) -> None:
        self.started += 1
        await self.release.wait()

    async def stop(self) -> None:
        self.stopped += 1
        self.release.set()


@pytest.mark.asyncio
async def test_new_playback_cancels_existing_session() -> None:
    backend = FakePlaybackBackend()
    controller = PlaybackController(backend=backend)

    first = await controller.start_tone(
        frequency_hz=440.0,
        duration_secs=5.0,
        volume=0.05,
        sample_rate_hz=16000,
    )
    await asyncio.sleep(0)

    second = await controller.start_tone(
        frequency_hz=500.0,
        duration_secs=5.0,
        volume=0.05,
        sample_rate_hz=16000,
    )
    await asyncio.sleep(0)

    assert first.session_id != second.session_id
    assert backend.stopped >= 1

    await controller.cancel()
```

Run and confirm FAIL.

- [ ] **Step 2: Implement backend/controller**

Use NumPy to generate a mono float32 sine wave.

Important behavior:

- `start_tone()` first cancels any active session.
- playback runs in an asyncio task.
- `cancel()` calls backend stop and waits for the task to finish.
- session IDs increment monotonically.
- controller must expose `is_playing`.
- completion of an old cancelled task must never mark a newer session stopped.

`SoundDevicePlaybackBackend.play()`:

```python
async def play(self, samples: np.ndarray, sample_rate_hz: int) -> None:
    sd.play(samples, samplerate=sample_rate_hz, blocking=False)
    await asyncio.to_thread(sd.wait)
```

`SoundDevicePlaybackBackend.stop()`:

```python
async def stop(self) -> None:
    sd.stop()
```

Do not use `sd.rec()` in this controller.

- [ ] **Step 3: Green + lint**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\voice\test_playback.py -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

- [ ] **Step 4: Commit**

```powershell
git add src/innobrain/voice/playback.py tests/unit/voice/test_playback.py docs/phase2/PHASE2_STATE.md
git commit -m "feat: add interruptible single-session playback"
```

---

# Task 6 — Implement interruption controller and cancellation latency record

**Files:**
- Create: `src/innobrain/voice/interruption.py`
- Create: `tests/unit/voice/test_interruption.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Consumes:
  - `ConversationStateMachine`
  - `PlaybackController`
- Produces:
  - `InterruptionResult`
  - `InterruptionController.handle_user_turn_started()`

`InterruptionResult`:

```python
@dataclass(frozen=True, slots=True)
class InterruptionResult:
    interrupted: bool
    prior_state: ConversationState
    event_to_playback_stop_ms: float | None
```

Behavior:

- If state is `SPEAKING`:
  1. transition to `INTERRUPTED`;
  2. call `await playback.cancel()`;
  3. measure from function entry to cancellation completion;
  4. transition to `LISTENING`;
  5. return interrupted result.
- If state is `THINKING`:
  1. transition to `INTERRUPTED`;
  2. invoke optional thinking-task cancellation callback if registered;
  3. transition to `LISTENING`.
- If state is `LISTENING`:
  - do not create a fake interruption;
  - return `interrupted=False`.
- IDLE should never receive live user-turn-start during a started runtime; if it does, transition runtime to LISTENING before microphone processing begins instead of handling it here.

- [ ] **Step 1: Test SPEAKING interruption**

Write test asserting:

```text
SPEAKING → INTERRUPTED → LISTENING
```

and fake playback receives cancel once.

- [ ] **Step 2: Test LISTENING speech is not interruption**

State remains LISTENING and cancel is not called.

- [ ] **Step 3: Implement minimal controller**

Use `time.perf_counter()`.

- [ ] **Step 4: Green + lint**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\voice\test_interruption.py -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

- [ ] **Step 5: Commit**

```powershell
git add src/innobrain/voice/interruption.py tests/unit/voice/test_interruption.py docs/phase2/PHASE2_STATE.md
git commit -m "feat: add realtime interruption controller"
```

---

# Task 7 — Implement async laptop PCM input pump

**Files:**
- Create: `src/innobrain/audio/stream.py`
- Create: `tests/unit/audio/test_stream.py`
- Modify: `src/innobrain/audio/__init__.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Produces `SoundDevicePCMStream`
  - `start()`
  - `stop()`
  - async `chunks()`
- Output chunk contract:
  - PCM signed 16-bit little endian
  - mono
  - configured sample rate
  - default 20 ms blocks
  - bounded queue

Do not replace Phase 1 `audio/io.py`.

## Core implementation requirements

Use:

```python
sd.RawInputStream(
    samplerate=sample_rate_hz,
    blocksize=block_frames,
    device=device,
    channels=1,
    dtype="int16",
    callback=callback,
)
```

At 16 kHz and 20 ms:

```text
block_frames = 320
expected bytes per normal block = 640
```

The sounddevice callback runs outside the event loop.

Never `await` inside the callback.

Use:

```python
loop.call_soon_threadsafe(...)
```

to place a copied `bytes(indata)` into the asyncio queue.

Bounded-queue policy:

- if queue full, drop the oldest audio chunk;
- increment `dropped_chunks`;
- never block the callback thread.

Expose stats:

```python
@dataclass(frozen=True, slots=True)
class AudioStreamStats:
    received_chunks: int
    dropped_chunks: int
```

## Unit test strategy

Do not open real microphone in unit tests.

Extract the event-loop-side enqueue logic into a method testable with a small `asyncio.Queue(maxsize=2)`.

Tests:

1. normal enqueue increments received.
2. third chunk with maxsize 2 drops oldest and increments dropped.
3. stop sentinel causes async iterator to terminate.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\audio\test_stream.py -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

Commit:

```powershell
git add src/innobrain/audio tests/unit/audio/test_stream.py docs/phase2/PHASE2_STATE.md
git commit -m "feat: add async laptop PCM stream"
```

---

# Task 8 — Implement Pipecat Silero + Smart Turn runtime

**Files:**
- Create: `src/innobrain/voice/turn_events.py`
- Create: `src/innobrain/voice/pipecat_runtime.py`
- Create: `tests/unit/voice/test_pipecat_runtime.py`
- Create: `tests/integration/voice/test_pipecat_pipeline_smoke.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

**Interfaces:**
- Consumes:
  - `SoundDevicePCMStream`
  - runtime config
  - `ConversationStateMachine`
  - `InterruptionController`
- Produces:
  - `TurnEvent`
  - `RealtimeTurnRuntime`
  - live callbacks:
    - user turn started
    - inference/semantic stop triggered
    - user turn stopped

## `turn_events.py`

Define:

```python
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter


class TurnEventType(StrEnum):
    USER_TURN_STARTED = "USER_TURN_STARTED"
    USER_TURN_INFERENCE_TRIGGERED = "USER_TURN_INFERENCE_TRIGGERED"
    USER_TURN_STOPPED = "USER_TURN_STOPPED"


@dataclass(frozen=True, slots=True)
class TurnEvent:
    event_type: TurnEventType
    at_monotonic: float
    strategy_name: str

    @classmethod
    def now(cls, event_type: TurnEventType, strategy_name: str) -> "TurnEvent":
        return cls(
            event_type=event_type,
            at_monotonic=perf_counter(),
            strategy_name=strategy_name,
        )
```

## Pipecat builder rules

Construct VAD:

```python
VADParams(
    confidence=config.realtime.vad.confidence,
    start_secs=config.realtime.vad.start_secs,
    stop_secs=config.realtime.vad.stop_secs,
    min_volume=config.realtime.vad.min_volume,
)
```

Then:

```python
SileroVADAnalyzer(
    sample_rate=config.audio.target_sample_rate_hz,
    params=vad_params,
)
```

Construct Smart Turn:

```python
LocalSmartTurnAnalyzerV3(
    cpu_count=config.realtime.smart_turn.cpu_count,
)
```

Construct user strategies explicitly:

```python
UserTurnStrategies(
    start=[VADUserTurnStartStrategy()],
    stop=[
        TurnAnalyzerUserTurnStopStrategy(
            turn_analyzer=smart_turn,
            wait_for_transcript=False,
        )
    ],
)
```

Do not rely on default turn strategies, because defaults also include transcription-based start behavior.

Construct:

```python
vad_processor = VADProcessor(vad_analyzer=vad)
turn_processor = UserTurnProcessor(
    user_turn_strategies=user_turn_strategies,
    user_turn_stop_timeout=5.0,
)
pipeline = Pipeline([vad_processor, turn_processor])
worker = PipelineWorker(
    pipeline,
    params=PipelineParams(
        audio_in_sample_rate=config.audio.target_sample_rate_hz,
        audio_out_sample_rate=config.audio.target_sample_rate_hz,
    ),
    processor_unusable_policy=ProcessorUnusablePolicy.END,
)
```

Use `WorkerRunner(handle_sigint=False)` on Windows.

Register `UserTurnProcessor` events BEFORE running the worker.

### `on_user_turn_started`

- append `TurnEvent(USER_TURN_STARTED, ...)`;
- call `InterruptionController.handle_user_turn_started()`.

### `on_user_turn_inference_triggered`

- append inference event.

### `on_user_turn_stopped`

- append stopped event.

Do not invoke STT/LLM/TTS.

## PCM feed

For each chunk from `SoundDevicePCMStream`:

```python
frame = InputAudioRawFrame(
    audio=chunk,
    sample_rate=config.audio.target_sample_rate_hz,
    num_channels=1,
)
await worker.queue_frames([frame])
```

At shutdown:

1. stop microphone source;
2. queue `EndFrame()`;
3. await runner clean shutdown;
4. cancel pending local tasks;
5. ensure playback is stopped.

Never leave the model/thread executors alive after clean exit.

## Unit tests

Unit test builder structure without microphone.

Assert:

- analyzer sample rate 16000.
- stop strategy `wait_for_transcript` is False.
- pipeline runtime does not import any provider implementation modules from `innobrain.providers.stt/llm/tts`.

If checking a private Pipecat attribute is required solely to verify configuration, prefer adding an InnoBrain dataclass snapshot returned by the builder rather than testing upstream internals.

## Integration smoke

Feed:

- Start handled by worker/runner.
- 1 second synthetic silence as PCM frames.
- clean EndFrame.

Expected:

- pipeline starts;
- accepts frames;
- shuts down without exception.

Do NOT assert that synthetic silence triggers speech.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\voice\test_pipecat_runtime.py tests\integration\voice\test_pipecat_pipeline_smoke.py -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

Commit.

---

# Task 9 — Add Egyptian Phase 2 scenarios and text echo/state demo

**Files:**
- Create: `evals/conversation/phase2_egyptian_turns.yaml`
- Create: `src/innobrain/voice/text_echo.py`
- Create: `scripts/phase2/text_echo_demo.py`
- Create: `tests/unit/voice/test_text_echo.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

## Evaluation file

Create:

```yaml
language: ar-EG
phase: 2

scenarios:
  - id: normal_turn
    instruction: "Say the phrase naturally, then stop."
    first_part: "ممكن تقولي البرنامج بتاع النهارده؟"
    continuation: null

  - id: hesitation_turn
    instruction: "Say first_part, pause 0.8-1.2 seconds, then say continuation."
    first_part: "بص أنا عايز أعرف..."
    continuation: "الـsession اللي بعد الضهر فين؟"

  - id: correction_turn
    instruction: "Say both parts naturally with a short correction pause."
    first_part: "أنا عايز Session أحمد..."
    continuation: "لا استنى، قصدي محمد."

  - id: barge_in
    instruction: "While the placeholder tone is playing, say the phrase."
    first_part: "معلش وقف"
    continuation: null

  - id: background_silence
    instruction: "Stay intentionally silent for 10 seconds."
    first_part: null
    continuation: null
```

## Text echo

This is a non-AI harness only.

API:

```python
async def echo_text_once(
    text: str,
    machine: ConversationStateMachine,
) -> str:
```

Behavior:

```text
LISTENING → THINKING → SPEAKING → LISTENING
```

Return:

```text
ECHO: <original text>
```

Do not synthesize speech.

Script accepts keyboard input and prints state transitions plus echo.

Test using:

```text
الـsession الساعة كام؟
```

Run tests, lint, commit.

---

# Task 10 — Full automated Phase 2 verification checkpoint

Run fresh:

```powershell
Set-Location "C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain"

.\.venv\Scripts\python.exe scripts\phase2\dependency_smoke.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
```

Required:

- dependency smoke PASS;
- all Phase 1 + Phase 2 tests pass;
- Ruff PASS.

Check config:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from innobrain.config import load_all_configs; c=load_all_configs(Path('.')); print(c.runtime.primary_locale, c.runtime.development_platform, c.runtime.realtime.smart_turn.wait_for_transcript)"
```

Expected:

```text
ar-EG laptop False
```

Check prohibited Phase 3 dependencies were not accidentally added:

```powershell
Select-String -Path pyproject.toml -Pattern "deepgram|speechmatics|azure-cognitiveservices|groq|google-genai|elevenlabs|sqlite-vec|sentence-transformers"
```

Expected:

```text
<no output>
```

Record in state:

```text
PHASE2_AUTOMATED_FOUNDATION_OK
```

Commit state change if needed.

---

# Task 11 — Offline Silero probe using the Phase 1 Egyptian recording

**Files:**
- Create: `scripts/phase2/offline_vad_probe.py`
- Modify: `docs/phase2/PHASE2_STATE.md`

This task uses the already-created local file when available:

```text
recordings/phase1/laptop_mic_egyptian.wav
```

The file remains gitignored.

If missing, do not fabricate it. Record:

```text
OFFLINE_PHASE1_WAV_NOT_AVAILABLE
```

and continue to the live test in Task 12.

## Script behavior

- read mono PCM16 WAV with existing `read_pcm16_wav`;
- require 16 kHz;
- feed 512-sample / 1024-byte chunks to `SileroVADAnalyzer.analyze_audio`;
- count transitions to `VADState.SPEAKING`;
- count transitions back to `VADState.QUIET`;
- print counts;
- cleanup analyzer.

Do not call Smart Turn private methods.

Expected for the known Phase 1 speech recording:

```text
SPEECH_STARTS >= 1
```

If zero:

- do not immediately tune thresholds;
- proceed to live Task 12 and compare;
- if live speech is also never detected, stop for VAD diagnosis.

Run Ruff on script and commit.

---

# Task 12 — Live Egyptian turn-detection validation

**Files:**
- Create: `scripts/phase2/turn_detection_demo.py`
- Runtime output only: `artifacts/phase2/turn_events.jsonl`
- Modify: `docs/phase2/PHASE2_STATE.md`

`artifacts/` remains gitignored.

## Demo requirements

The script must:

1. load config;
2. print default microphone device;
3. construct `ConversationStateMachine`;
4. move `IDLE → LISTENING`;
5. start `SoundDevicePCMStream`;
6. start `RealtimeTurnRuntime`;
7. print every turn event immediately;
8. append JSONL event records under `artifacts/phase2/`;
9. stop cleanly on Ctrl+C.

No network call.

## Live test A — 10-second silence

Run demo.

Stay intentionally silent for 10 seconds.

Expected:

```text
USER_TURN_STARTED count = 0
```

Ordinary incidental room noise is allowed, but repeated false starts are a failure.

## Live test B — normal Egyptian sentence

Say:

```text
ممكن تقولي البرنامج بتاع النهارده؟
```

Expected:

```text
USER_TURN_STARTED
...
USER_TURN_STOPPED
```

one coherent turn.

## Live test C — hesitation

Run three trials.

Say:

```text
بص أنا عايز أعرف...
```

pause naturally about 0.8–1.2 seconds, then:

```text
الـsession اللي بعد الضهر فين؟
```

For each trial record whether `USER_TURN_STOPPED` occurs:

- before continuation = premature;
- after continuation = preserved.

Target:

```text
preserved >= 2 of 3
```

Do not tune thresholds between individual trials.

If preserved <2/3:

- set Phase 2 `PHASE_2_BLOCKED`;
- preserve JSONL evidence;
- report Smart Turn Egyptian hesitation failure;
- do not move to Phase 3.

## Live test D — correction

Say:

```text
أنا عايز Session أحمد...
لا استنى، قصدي محمد.
```

Record whether it behaves as one reasonable turn.

This test is informative in Phase 2; hesitation test is the mandatory gate.

## Checkpoint

If mandatory tests pass:

```text
PHASE2_LIVE_TURN_DETECTION_OK
```

---

# Task 13 — Live barge-in and cancellation validation

**Files:**
- Create: `scripts/phase2/barge_in_demo.py`
- Runtime output: `artifacts/phase2/barge_in_results.jsonl`
- Modify: `docs/phase2/PHASE2_STATE.md`

## Why a tone is used

Do not play synthetic speech in Phase 2.

Laptop speech playback could leak into the laptop microphone, and laptop AEC is not a validated product assumption.

A low-volume 440 Hz tone exercises:

- active assistant playback state;
- cancellation;
- user-start event;
- no overlapping playback;

without pretending production speech echo/AEC is solved.

## Demo flow

1. runtime starts in `LISTENING`;
2. user presses Enter to start test;
3. state:
   - `LISTENING → THINKING`
   - sleep configured `mock_think_delay_ms`
   - `THINKING → SPEAKING`
4. start configured 6-second low-volume tone;
5. user says while tone is playing:

```text
معلش وقف
```

6. `USER_TURN_STARTED` calls `InterruptionController`;
7. state must become:

```text
SPEAKING → INTERRUPTED → LISTENING
```

8. tone stops;
9. log:
   - trial number;
   - turn-start monotonic timestamp;
   - playback-stop timestamp;
   - `event_to_playback_stop_ms`;
   - resulting state.

## Run three trials

Mandatory:

- 3/3 user-start events stop the tone.
- 3/3 return to LISTENING.
- no overlapping tone sessions.
- each `event_to_playback_stop_ms <= 100`.

If the actual audio seems to stop quickly but software metric exceeds 100 ms, preserve result and mark Phase 2 blocked for cancellation-latency diagnosis.

Do not reinterpret this as acoustic-onset latency.

Checkpoint:

```text
PHASE2_BARGE_IN_OK
```

---

# Task 14 — Stop for user interaction confirmation

Do not finalize Phase 2 yet.

Update:

`docs/phase2/PHASE2_STATE.md`

to:

```markdown
# Phase 2 State

**Phase:** 2 — Realtime Conversation Core  
**Branch:** `phase/2-realtime-conversation-core`  
**Status:** `PHASE_2_WAITING_FOR_INTERACTION_CONFIRMATION`  
**Last completed task:** Task 14  
**Next task:** Task 15 — finalize after user PASS  
**Development platform:** Windows laptop  
**Primary language:** Egyptian Arabic (`ar-EG`)  
**Pipecat:** 1.8.1 PASS  
**Silero VAD:** Automated/live PASS  
**Smart Turn:** Egyptian hesitation gate passed  
**Live turn detection:** PASS  
**Barge-in:** Automated/live PASS  
**Pi/S330:** Deferred deployment validation  
**Phase 3 authorized:** No
```

Fill only claims actually supported by the just-run tests.

If any claim did not pass, use `PHASE_2_BLOCKED` instead.

Push branch is optional before the user gate; if pushing, do not finalize report/master status as complete.

Ask the user exactly:

```text
Phase 2 is waiting for your interaction confirmation.

Please confirm:
1) normal Egyptian speech start/stop felt correct,
2) background silence did not keep false-triggering,
3) at least 2/3 hesitation trials waited for your continuation,
4) saying "معلش وقف" stopped the placeholder tone quickly in all 3 barge-in trials,
5) after interruption the system returned to listening and accepted another turn.

Reply PASS, or tell me which item failed.
```

STOP.

Final state until user replies:

```text
PHASE_2_WAITING_FOR_INTERACTION_CONFIRMATION
```

---

# Task 15 — Finalize Phase 2 only after user PASS

**Files:**
- Create: `docs/phase2/PHASE2_REPORT.md`
- Modify: `MASTER_PLAN.md`
- Modify: `README.md`
- Modify: `docs/phase2/PHASE2_STATE.md`

## 15.1 Phase 2 report

Write actual values only.

Required shape:

```markdown
# Phase 2 Report

## Final State
PHASE_2_COMPLETE

## Repository
- Base Phase 1 HEAD:
- Branch:
- Final implementation commit:
- Final branch HEAD:

## Environment
- OS:
- Python:
- Pipecat:
- Input device:
- Sample rate:
- Channels:
- Audio block ms:

## Automated Verification
- pytest:
- Ruff:
- Pipecat dependency smoke:
- Silero initialization:
- Smart Turn initialization:
- Pipecat synthetic-silence pipeline smoke:

## Live Egyptian Turn Detection
- 10-second silence false starts:
- Normal turn:
- Hesitation preserved trials:
- Correction scenario:

## Barge-In
- Trial 1 event-to-stop ms:
- Trial 2 event-to-stop ms:
- Trial 3 event-to-stop ms:
- Max event-to-stop ms:
- State recovery:
- Overlapping playback observed:

## Manual User Confirmation
PASS

## Important Scope Notes
- No STT was implemented.
- No LLM was implemented.
- No TTS was implemented.
- Placeholder output was a generated non-speech tone.
- Full acoustic speech-onset-to-silence barge-in is not certified here.
- Raspberry Pi/S330/AEC production validation remains deferred.
- No Phase 3 work started.

## Next
Phase 3 — Speech + Brain + RAG.
```

No placeholders may remain.

## 15.2 Update Master Plan to v1.8

Update actual Phase 2 results.

Bump:

```text
1.7 → 1.8
```

Set status:

```text
Phase 2 complete on Windows laptop; Phase 3 authorized but not started
```

Record:

- actual Pipecat 1.8.1 success;
- actual VAD settings used;
- actual Smart Turn hesitation result;
- actual barge-in software latencies;
- reminder that full acoustic/AEC production test remains deferred;
- Phase 3 authorized.

Do not claim STT/LLM/TTS exists.

## 15.3 README

Use concise status:

```text
Current status: Phase 2 complete — realtime laptop conversation core validated.

Implemented: streaming audio frames, Pipecat 1.8.1, Silero VAD, Smart Turn v3, conversation state machine, interruption/cancellation.

Not implemented yet: STT, LLM, TTS, RAG, event knowledge.

Target deployment: Raspberry Pi 5 + Anker PowerConf S330; production hardware/AEC validation remains pending.

Next: Phase 3 — Speech + Brain + RAG.
```

## 15.4 Final state

`PHASE2_STATE.md`:

```text
Status: PHASE_2_COMPLETE
Last completed task: Task 15
Next task: STOP — wait for Phase 3 handoff
Live turn detection: PASS
Egyptian hesitation gate: PASS
Barge-in: PASS
Manual interaction gate: PASS
Pi/S330: Deferred
Phase 3 authorized: Yes
```

## 15.5 Fresh final verification

Run:

```powershell
.\.venv\Scripts\python.exe scripts\phase2\dependency_smoke.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
```

Search prohibited provider work:

```powershell
Select-String -Path pyproject.toml -Pattern "deepgram|speechmatics|azure-cognitiveservices|groq|google-genai|elevenlabs|sqlite-vec|sentence-transformers"
```

Expected no matches.

Search for accidentally tracked recordings/artifacts:

```powershell
git ls-files recordings artifacts
```

Expected no output.

Check status:

```powershell
git status --short
```

Before final commit it should show only intended Phase 2 source/docs changes.

## 15.6 Commit

```powershell
git add `
  MASTER_PLAN.md `
  README.md `
  pyproject.toml `
  src `
  config `
  evals `
  scripts `
  tests `
  docs `
  CODEX_PHASE2_REALTIME_CONVERSATION_CORE.md

git commit -m "feat: complete Phase 2 realtime conversation core"
```

Then:

```powershell
git status --short
git log -5 --oneline
```

Working tree must be clean.

## 15.7 Push

```powershell
git push -u origin "phase/2-realtime-conversation-core"
```

Do NOT merge.

## Final Codex response format

Return a concise report:

```text
Phase 2 state: PHASE_2_COMPLETE

Base Phase 1 HEAD:
<sha>

Branch:
phase/2-realtime-conversation-core

Final branch HEAD:
<sha>

Tests:
<pytest result>
Ruff: PASS

Runtime:
Pipecat: 1.8.1
Silero VAD: PASS
Smart Turn v3: PASS
Egyptian hesitation: <x>/3 preserved

Barge-in:
trial latencies: <x>, <y>, <z> ms
max: <n> ms
state recovery: PASS
overlap: NONE

Manual interaction gate:
PASS

Pi/S330/AEC:
DEFERRED

Master Plan:
updated to v1.8

Phase 3:
AUTHORIZED BUT NOT STARTED

STOPPED before Phase 3.
```

Then STOP.

---

# Error Decision Table

| Failure | Exact action |
|---|---|
| Dirty repo before Phase 2 | STOP; report files; never discard |
| Phase 1 not complete | STOP |
| Phase 2 accidentally based on `main` without Phase 1 | recreate branch from Phase 1; do not cherry-pick random files |
| Pipecat version not 1.8.1 | fix dependency pin; do not code against other API |
| Pipecat install fails | pip upgrade + one retry; then BLOCKED with exact dependency |
| Silero analyzer fails to instantiate | BLOCKED; preserve exception |
| Smart Turn analyzer fails to instantiate | BLOCKED; preserve exception |
| Model tries network download | STOP; Phase 2 must use packaged models only |
| Unit test fails | fix current task only; rerun |
| Ruff fails | fix reported Phase 2 file only |
| No microphone device | check Windows mic permissions/default device |
| Audio queue drops during ordinary local test | report drop count; increase queue max only after evidence, not callback blocking |
| Offline Phase 1 WAV missing | continue to live test |
| Offline Silero sees no speech but live works | record discrepancy; live test is authoritative for Phase 2 |
| Live Silero never detects speech | BLOCKED; do not silently tune |
| Silence repeatedly false-triggers | BLOCKED; preserve event log; do not silently tune |
| Hesitation preserved <2/3 | BLOCKED for Egyptian turn-detection decision |
| Tone output feeds VAD false speech | lower tone volume once or use headphones; do not add AEC |
| User speech does not stop tone | BLOCKED interruption path |
| Event-to-stop >100 ms | BLOCKED cancellation-latency diagnosis |
| User interaction gate pending | `PHASE_2_WAITING_FOR_INTERACTION_CONFIRMATION` |
| Raspberry Pi unavailable | ignore for Phase 2 |
| S330 unavailable | ignore for Phase 2 |
| Need STT to finish task | STOP; that belongs to Phase 3 |
| Need architecture change | STOP and update Master Plan first |

---

# Luna Context-Saving Rules

The coding model is expected to be token-conscious.

For every task:

1. Read the full Master Plan once at Task 1 only.
2. Read this full Phase 2 plan once at Task 1 only.
3. For later tasks, read:
   - the current numbered task;
   - Global Constraints;
   - files being modified.
4. Do not re-read all donor repos.
5. Do not re-read all of `DONOR_INSPECTION.md`.
6. Inspect only these Pipecat donor files if the exact installed API disagrees with this plan:
   - `src/pipecat/processors/audio/vad_processor.py`
   - `src/pipecat/audio/vad/silero.py`
   - `src/pipecat/audio/turn/smart_turn/local_smart_turn_v3.py`
   - `src/pipecat/turns/user_turn_processor.py`
   - `src/pipecat/turns/user_turn_strategies.py`
   - `src/pipecat/turns/user_stop/turn_analyzer_user_turn_stop_strategy.py`
7. The installed `pipecat-ai==1.8.1` API is authoritative over a newer donor checkout if a difference appears.
8. Do not explore provider examples; Phase 2 has no providers.
9. Before Task 15, re-read only:
   - Master Plan Phase 2 contract;
   - Task 15;
   - `PHASE2_STATE.md`;
   - live JSONL result summaries.
10. Prefer deterministic commands in this file over open-ended investigation.

---

# Definition of Done

Phase 2 is complete only when all are true:

- Phase 2 branch was created from completed Phase 1.
- Phase 1 evidence is preserved.
- Master Plan v1.7 was synchronized before Phase 2 implementation.
- Pipecat exactly 1.8.1 is installed.
- Pipecat Silero analyzer initializes.
- Pipecat Smart Turn v3 analyzer initializes.
- no separate speech model was downloaded.
- realtime config is validated.
- strict state machine exists.
- invalid state transitions fail tests.
- single-session interruptible playback exists.
- playback overlap is prevented.
- interruption controller exists.
- async sounddevice PCM input exists.
- callback never blocks waiting for the asyncio consumer.
- bounded audio queue has tested overflow behavior.
- Pipecat accepts streamed `InputAudioRawFrame`s.
- pipeline order is Silero VAD then semantic user-turn processing.
- Smart Turn uses `wait_for_transcript=False`.
- synthetic-silence pipeline smoke shuts down cleanly.
- Egyptian normal speech live test passes.
- 10-second intentional silence does not repeatedly false-trigger.
- Egyptian hesitation is preserved in at least 2/3 live trials.
- live barge-in stops placeholder tone in 3/3 trials.
- event-to-playback-stop is <=100 ms in all mandatory trials.
- runtime returns to listening after interruption.
- user confirms the interaction gate.
- no STT is implemented.
- no LLM is implemented.
- no TTS is implemented.
- no RAG is implemented.
- Pi/S330/AEC remain explicitly deferred.
- Master Plan is updated with measured results and bumped to v1.8.
- full pytest suite passes fresh.
- Ruff passes fresh.
- branch is pushed.
- branch is not merged.
- Phase 3 has not started.

---

**STOP AFTER PHASE 2. DO NOT START PHASE 3.**

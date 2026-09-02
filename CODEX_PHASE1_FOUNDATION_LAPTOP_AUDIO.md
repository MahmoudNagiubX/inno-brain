# InnoBrain Phase 1 — Foundation + Laptop Audio Validation Execution Plan

> **For agentic workers:** Execute this plan task-by-task. If the `superpowers:subagent-driven-development` or `superpowers:executing-plans` workflow is available, use it; otherwise follow this file directly and do not stop merely because a named skill is unavailable.
>
> **Goal:** Build the minimal InnoBrain software foundation and prove the current Windows laptop audio path works for development, while keeping the code ready for later Raspberry Pi 5 + Anker S330 deployment.
>
> **Architecture:** Phase 1 contains no STT, LLM, TTS, RAG or realtime conversation implementation. It creates validated configuration/contracts/logging, a hardware-agnostic audio abstraction, Egyptian-Arabic audio fixtures, and deterministic laptop microphone/speaker validation tools.
>
> **Tech Stack:** Python `>=3.11,<3.15`, setuptools, Pydantic v2, PyYAML, `sounddevice`, NumPy, pytest, pytest-cov, Ruff, Windows PowerShell.
>
> **Spec:** `MASTER_PLAN.md`
>
> **Repository:** `MahmoudNagiubX/inno-brain`
>
> **Expected starting main commit from bootstrap:** `9844539cf570360f971530fa209b1c261f7bfab7`. If `main` has legitimately advanced, use the latest clean `origin/main`; never reset or force-push it.
>
> **Primary language priority:** Egyptian Arabic. English is secondary.
>
> **Current development hardware:** Windows laptop + laptop/default microphone + laptop/default output device.
>
> **Target deployment hardware:** Raspberry Pi 5 8 GB + Anker PowerConf S330.
>
> **STOP RULE:** Do not start Phase 2.

---

# 0. Strict execution rules for Codex Luna

Follow literally:

1. Work on ONE numbered task at a time.
2. Do not redesign the architecture.
3. Read the full Master Plan once at the beginning.
4. Do not reread the entire Master Plan for every task.
5. Use `docs/research/DONOR_INSPECTION.md` instead of rescanning all donors.
6. Inspect only an exact donor file when necessary.
7. Do not add dependencies not listed in this file.
8. Do not upgrade unrelated dependencies.
9. Do not refactor unrelated bootstrap files.
10. Do not install model weights.
11. Do not use API keys.
12. Do not call provider APIs.
13. Do not install or run Pipecat.
14. Do not install Silero VAD or Smart Turn yet.
15. Do not install sqlite-vec yet.
16. Do not implement RAG yet.
17. Do not implement ROS/navigation.
18. Do not modify donor repositories.
19. Do not make Raspberry Pi access a blocker.
20. Do not hard-code a laptop audio-device index in production config.
21. If a command fails, make at most two direct fixes based on the actual error.
22. If the second direct fix fails, record the exact error and stop that task.
23. After every task, run its checkpoint.
24. Update `docs/phase1/PHASE1_STATE.md` after each successful task.
25. Do not claim audio quality passed until the user listens to the WAV.
26. Do not merge the Phase 1 branch into `main`.

---

# 1. Starting facts

Current workspace:

```text
C:\Users\mahmo\Desktop\InnoBrainWorkspace
```

Production repository:

```text
C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain
```

Remote:

```text
https://github.com/MahmoudNagiubX/inno-brain.git
```

Current development:

```text
OS: Windows 11
Shell: Windows PowerShell 5.1
Python: 3.14.6
Audio input: laptop/default microphone
Audio output: laptop/default output
Raspberry Pi currently unavailable to primary developer
Anker S330 currently unavailable to primary developer
```

Bootstrap:

```text
13/13 donor repos cloned
READY_FOR_PHASE_1
```

---

# 2. Phase 1 scope

## Implement now

- Python packaging.
- isolated virtual environment.
- validated configuration.
- Egyptian-first defaults.
- provider contracts only.
- logging foundation.
- hardware-agnostic audio-device models/helpers.
- cross-platform laptop audio device listing.
- laptop microphone recording.
- laptop audio playback.
- WAV analysis.
- Egyptian-Arabic audio test phrases.
- unit tests.
- Windows verification.
- user listening gate.
- Phase 1 report.

## Do NOT implement now

- Raspberry Pi deployment.
- S330-specific validation.
- ALSA device probing.
- Pipecat.
- Silero VAD.
- Smart Turn.
- STT.
- TTS provider.
- LLM provider implementation.
- API calls.
- local models.
- llama.cpp build.
- Metro-ASR download.
- RAG.
- SQLite schema.
- FTS5.
- sqlite-vec.
- embeddings.
- memory.
- ROS/navigation.
- screen integration.

---

# 3. Final states

Exactly one:

```text
PHASE_1_COMPLETE
PHASE_1_WAITING_FOR_AUDIO_CONFIRMATION
PHASE_1_BLOCKED
```

The absence of Raspberry Pi/S330 must NEVER produce a blocked/waiting state.

---

# 4. Task order

```text
Task 0  Safety preflight + branch
Task 1  Sync Master Plan + Phase 1 docs
Task 2  Python project foundation
Task 3  Config system + Egyptian-first defaults
Task 4  Provider contracts + logging
Task 5  Audio abstraction + laptop device discovery
Task 6  Egyptian audio fixture
Task 7  Laptop recording + playback + WAV analyzer
Task 8  Full automated Windows verification
Task 9  Interactive laptop audio test
Task 10 Manual user listening gate
Task 11 Final report + Master Plan update + push
STOP
```

---

# Task 0 — Safety preflight and branch

Open PowerShell:

```powershell
Set-Location "C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain"
```

Run:

```powershell
git status --short
git branch --show-current
git remote -v
git log -3 --oneline
git fetch origin
```

If `git status --short` is not empty:

**STOP. Do not stash, reset, discard, or overwrite user work.**

If clean:

```powershell
git switch main
git pull --ff-only origin main
```

Check branch:

```powershell
git branch --list "phase/1-foundation-laptop-audio"
```

If absent:

```powershell
git switch -c "phase/1-foundation-laptop-audio"
```

If present:

```powershell
git switch "phase/1-foundation-laptop-audio"
```

Verify:

```powershell
git branch --show-current
git status --short
```

Expected:

```text
phase/1-foundation-laptop-audio
```

---

# Task 1 — Sync authoritative docs

Required attached files:

- `InnoBrain_MASTER_PLAN_v1.5.md`
- `CODEX_PHASE1_FOUNDATION_LAPTOP_AUDIO.md`

Copy Master Plan to:

```text
MASTER_PLAN.md
```

Copy execution plan to:

```text
CODEX_PHASE1_FOUNDATION_LAPTOP_AUDIO.md
```

Create:

```text
docs/phase1/PHASE1_STATE.md
```

with:

```markdown
# Phase 1 State

**Phase:** 1 — Foundation + Laptop Audio Validation  
**Branch:** `phase/1-foundation-laptop-audio`  
**Status:** `IN_PROGRESS`  
**Last completed task:** Task 1  
**Next task:** Task 2 — Python project foundation  
**Development audio:** Laptop/default microphone and output  
**Raspberry Pi deployment:** Deferred  
**S330 deployment validation:** Deferred  
**Manual acoustic gate:** Not started  
**Phase 2 authorized:** No
```

Verify:

```powershell
Select-String -Path MASTER_PLAN.md -Pattern "Version:\*\* 1.5"
Test-Path CODEX_PHASE1_FOUNDATION_LAPTOP_AUDIO.md
Test-Path docs\phase1\PHASE1_STATE.md
git diff --check
```

Commit:

```powershell
git add MASTER_PLAN.md CODEX_PHASE1_FOUNDATION_LAPTOP_AUDIO.md docs/phase1/PHASE1_STATE.md
git commit -m "docs: start Phase 1 laptop development foundation"
```

---

# Task 2 — Python project foundation

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "innobrain"
version = "0.1.0"
description = "Egyptian-Arabic-first AI and voice brain for the Innovatronics event robot."
readme = "README.md"
requires-python = ">=3.11,<3.15"
dependencies = [
    "numpy>=2.0,<3",
    "pydantic>=2.13,<3",
    "PyYAML>=6,<7",
    "sounddevice>=0.5,<1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8,<10",
    "pytest-cov>=5,<8",
    "ruff>=0.12,<1",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Create venv only if absent:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Smoke:

```powershell
.\.venv\Scripts\python.exe -c "import innobrain, sounddevice, numpy; print('PHASE1_IMPORTS_OK')"
```

Expected:

```text
PHASE1_IMPORTS_OK
```

Update state and commit:

```powershell
git add pyproject.toml docs/phase1/PHASE1_STATE.md
git commit -m "build: add Phase 1 laptop development dependencies"
```

---

# Task 3 — Config system + Egyptian-first defaults

Create:

```text
src/innobrain/config/__init__.py
src/innobrain/config/models.py
src/innobrain/config/loader.py
config/runtime.yaml
config/providers.yaml
config/persona.yaml
tests/unit/config/test_loader.py
```

Use strict Pydantic models.

`src/innobrain/config/models.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AudioRuntimeConfig(StrictModel):
    backend: Literal["default", "sounddevice"] = "sounddevice"
    input_device: str | int | None = None
    output_device: str | int | None = None
    target_sample_rate_hz: int = Field(default=16000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    frame_ms: int = Field(default=20, ge=10, le=100)
    software_aec_enabled: bool = False
    software_ns_enabled: bool = False


class RuntimeConfig(StrictModel):
    app_name: str
    environment: Literal["development", "test", "production"]
    primary_locale: str
    secondary_locale: str
    development_platform: Literal["laptop", "raspberry_pi"]
    audio: AudioRuntimeConfig


class ProviderCandidatesConfig(StrictModel):
    selection_status: Literal["benchmark_pending", "selected"]
    stt_candidates: list[str]
    llm_candidates: list[str]
    tts_candidates: list[str]
    embedding_candidates: list[str]


class PersonaConfig(StrictModel):
    primary_language: str
    dialect: str
    english_priority: Literal["secondary"]
    response_style: Literal["concise_spoken"]
    max_default_sentences: int = Field(default=3, ge=1, le=5)


class ProjectConfigs(StrictModel):
    runtime: RuntimeConfig
    providers: ProviderCandidatesConfig
    persona: PersonaConfig
```

`src/innobrain/config/loader.py`:

```python
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from .models import PersonaConfig, ProjectConfigs, ProviderCandidatesConfig, RuntimeConfig

T = TypeVar("T", bound=BaseModel)


def load_yaml_model(path: Path, model_type: type[T]) -> T:
    if not path.is_file():
        raise FileNotFoundError(path)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")

    return model_type.model_validate(raw)


def load_all_configs(root: Path) -> ProjectConfigs:
    config_dir = root / "config"

    return ProjectConfigs(
        runtime=load_yaml_model(config_dir / "runtime.yaml", RuntimeConfig),
        providers=load_yaml_model(
            config_dir / "providers.yaml",
            ProviderCandidatesConfig,
        ),
        persona=load_yaml_model(config_dir / "persona.yaml", PersonaConfig),
    )
```

`src/innobrain/config/__init__.py` should export the models and loader.

Create `config/runtime.yaml`:

```yaml
app_name: InnoBrain
environment: development
primary_locale: ar-EG
secondary_locale: en
development_platform: laptop

audio:
  backend: sounddevice
  input_device: null
  output_device: null
  target_sample_rate_hz: 16000
  channels: 1
  frame_ms: 20
  software_aec_enabled: false
  software_ns_enabled: false
```

Important:

`null` means use the operating system/default audio device.

Never commit a laptop-specific numeric device ID as the default.

Create `config/providers.yaml`:

```yaml
selection_status: benchmark_pending

stt_candidates:
  - deepgram
  - speechmatics
  - azure
  - gemini
  - metro-local

llm_candidates:
  - groq
  - gemini
  - gemma-local
  - qwen-local

tts_candidates:
  - azure-salma
  - azure-shakir
  - gemini-audio
  - elevenlabs
  - voicetut

embedding_candidates:
  - multilingual-e5-small
```

Create `config/persona.yaml`:

```yaml
primary_language: ar-EG
dialect: Egyptian Arabic
english_priority: secondary
response_style: concise_spoken
max_default_sentences: 3
```

Tests must assert:

- locale is `ar-EG`;
- development platform is `laptop`;
- device selection is `None`;
- software AEC/NS are false;
- unknown config keys are rejected.

Run tests, Ruff, commit.

---

# Task 4 — Provider contracts + logging

Create provider Protocols only:

- `STTProvider`
- `LLMProvider`
- `TTSProvider`
- `EmbeddingProvider`

Create immutable dataclasses:

- `TranscriptEvent`
- `AudioChunk`
- `ChatMessage`

Do not implement providers.

Create idempotent `configure_logging()` under `src/innobrain/telemetry/`.

Tests must include Arabic strings and verify no duplicate logging handlers.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/providers tests/unit/telemetry -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

Commit.

---

# Task 5 — Hardware-agnostic audio abstraction + laptop device discovery

Create:

```text
src/innobrain/audio/__init__.py
src/innobrain/audio/models.py
src/innobrain/audio/devices.py
tests/unit/audio/test_devices.py
scripts/phase1/list_audio_devices.py
```

`src/innobrain/audio/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float

    @property
    def can_capture(self) -> bool:
        return self.max_input_channels > 0

    @property
    def can_playback(self) -> bool:
        return self.max_output_channels > 0
```

`src/innobrain/audio/devices.py`:

```python
from collections.abc import Iterable

import sounddevice as sd

from .models import AudioDevice


def normalize_devices(raw_devices: Iterable[dict[str, object]]) -> list[AudioDevice]:
    devices: list[AudioDevice] = []

    for index, raw in enumerate(raw_devices):
        devices.append(
            AudioDevice(
                index=index,
                name=str(raw["name"]),
                max_input_channels=int(raw["max_input_channels"]),
                max_output_channels=int(raw["max_output_channels"]),
                default_sample_rate=float(raw["default_samplerate"]),
            )
        )

    return devices


def list_audio_devices() -> list[AudioDevice]:
    return normalize_devices(sd.query_devices())


def get_default_device_indices() -> tuple[int | None, int | None]:
    default = sd.default.device

    if not isinstance(default, (tuple, list)) or len(default) != 2:
        return None, None

    input_index = int(default[0]) if default[0] is not None and default[0] >= 0 else None
    output_index = int(default[1]) if default[1] is not None and default[1] >= 0 else None

    return input_index, output_index
```

`src/innobrain/audio/__init__.py` exports the public helpers.

Create unit tests using fake dictionaries only.
Do not require a physical microphone for unit tests.

Create `scripts/phase1/list_audio_devices.py`:

```python
from innobrain.audio import get_default_device_indices, list_audio_devices


def main() -> int:
    input_default, output_default = get_default_device_indices()

    print(f"Default input: {input_default}")
    print(f"Default output: {output_default}")
    print()

    for device in list_audio_devices():
        roles = []
        if device.can_capture:
            roles.append("INPUT")
        if device.can_playback:
            roles.append("OUTPUT")

        print(
            f"[{device.index}] {'/'.join(roles) or 'NONE'} | "
            f"{device.name} | default_sr={device.default_sample_rate}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```powershell
.\.venv\Scripts\python.exe scripts\phase1\list_audio_devices.py
```

Required:

- at least one INPUT device;
- at least one OUTPUT device.

If no input exists, verify Windows microphone permissions before changing code.

Do not hard-code the printed index into `config/runtime.yaml`.

Commit.

---

# Task 6 — Egyptian audio fixture

Create:

```text
evals/audio/phase1_egyptian_phrases.yaml
evals/audio/README.md
tests/unit/evals/test_phase1_phrases.py
```

Use:

```yaml
language: ar-EG
purpose: phase1_laptop_audio_validation

phrases:
  - id: greeting
    category: pure_egyptian
    text: "إزيك؟ عامل إيه؟"

  - id: event_schedule
    category: egyptian_event
    text: "ممكن تقولي البرنامج بتاع النهارده؟"

  - id: session_time
    category: code_switch
    text: "الـsession بتاعة الذكاء الاصطناعي الساعة كام؟"

  - id: registration
    category: code_switch
    text: "ممكن تقولي الـregistration فين؟"

  - id: hesitation
    category: hesitation
    text: "بص أنا عايز أعرف... ثانية بس بفكر... أيوه، الـsession اللي بعد الضهر."

  - id: correction
    category: correction
    text: "لا استنى، قصدي بكرة مش النهارده."

  - id: location
    category: code_switch
    text: "ممكن توريني الـmain stage فين؟"

  - id: long_natural
    category: natural_egyptian
    text: "أنا أول مرة أجي الإيفنت ومش عارف أبدأ منين، ممكن تقولي إيه أهم حاجة أروحها الأول؟"
```

README must state these are development audio fixtures, not final STT benchmark labels.

Run tests and commit.

---

# Task 7 — Laptop recording, playback and WAV analyzer

Create:

```text
src/innobrain/audio/io.py
scripts/phase1/record_laptop_sample.py
scripts/phase1/play_laptop_sample.py
scripts/phase1/analyze_wav.py
tests/unit/audio/test_wav_helpers.py
```

## `src/innobrain/audio/io.py`

```python
from pathlib import Path
import wave

import numpy as np
import sounddevice as sd


def record_mono(
    duration_seconds: float,
    sample_rate_hz: int,
    device: int | str | None = None,
) -> np.ndarray:
    frames = int(duration_seconds * sample_rate_hz)

    audio = sd.rec(
        frames=frames,
        samplerate=sample_rate_hz,
        channels=1,
        dtype="int16",
        device=device,
        blocking=True,
    )

    return np.asarray(audio, dtype=np.int16).reshape(-1)


def play_mono(
    samples: np.ndarray,
    sample_rate_hz: int,
    device: int | str | None = None,
) -> None:
    sd.play(
        np.asarray(samples, dtype=np.int16),
        samplerate=sample_rate_hz,
        device=device,
        blocking=True,
    )


def write_pcm16_wav(
    path: Path,
    samples: np.ndarray,
    sample_rate_hz: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    mono = np.asarray(samples, dtype=np.int16).reshape(-1)

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(mono.tobytes())


def read_pcm16_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1:
            raise ValueError("Expected mono WAV")
        if wav.getsampwidth() != 2:
            raise ValueError("Expected 16-bit PCM WAV")

        sample_rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())

    return np.frombuffer(raw, dtype=np.int16).copy(), sample_rate
```

Unit-test only `write_pcm16_wav` / `read_pcm16_wav` with generated NumPy samples.

Do not unit-test real microphone hardware.

## `record_laptop_sample.py`

Arguments:

```text
--seconds
--sample-rate
--output
--device optional
```

Defaults:

```text
seconds = 8
sample-rate = 16000
device = None
```

It must:

1. print selected device/default state;
2. countdown 3…2…1;
3. record;
4. save PCM16 mono WAV;
5. print absolute output path.

## `play_laptop_sample.py`

Arguments:

```text
wav
--device optional
```

Read with `read_pcm16_wav`, play with `play_mono`.

## `analyze_wav.py`

Use standard-library or NumPy implementation and report:

- sample rate;
- channels;
- duration;
- RMS;
- peak;
- clipping percentage.

No AI interpretation.

Run tests and Ruff.

Commit.

---

# Task 8 — Full automated Windows verification

Run:

```powershell
Set-Location "C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain"

.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -c "from pathlib import Path; from innobrain.config import load_all_configs; c=load_all_configs(Path('.')); print(c.runtime.primary_locale, c.runtime.development_platform)"
git diff --check
```

Expected config output:

```text
ar-EG laptop
```

Run:

```powershell
.\.venv\Scripts\python.exe scripts\phase1\list_audio_devices.py
```

Record default input/output names in Phase 1 state/report.

Automated checkpoint:

```text
PHASE1_SOFTWARE_FOUNDATION_OK
```

---

# Task 9 — Interactive laptop audio test

Create local directories:

```powershell
New-Item -ItemType Directory -Force recordings\phase1 | Out-Null
New-Item -ItemType Directory -Force artifacts\phase1 | Out-Null
```

Ensure `.gitignore` includes:

```gitignore
recordings/
artifacts/
```

Do not commit WAVs.

## 9.1 Record Egyptian sample

User should sit/stand at a normal laptop distance and read:

```text
أنا أول مرة أجي الإيفنت ومش عارف أبدأ منين، ممكن تقولي إيه أهم حاجة أروحها الأول؟
```

Run:

```powershell
.\.venv\Scripts\python.exe scripts\phase1\record_laptop_sample.py `
  --seconds 10 `
  --sample-rate 16000 `
  --output recordings\phase1\laptop_mic_egyptian.wav
```

Do not specify `--device` unless the OS default input is wrong.

## 9.2 Analyze

```powershell
.\.venv\Scripts\python.exe scripts\phase1\analyze_wav.py `
  recordings\phase1\laptop_mic_egyptian.wav
```

Automated sanity:

- sample rate 16000;
- mono;
- duration near requested duration;
- peak > 0;
- clipping not severe.

Do not infer intelligibility from RMS.

## 9.3 Playback

```powershell
.\.venv\Scripts\python.exe scripts\phase1\play_laptop_sample.py `
  recordings\phase1\laptop_mic_egyptian.wav
```

User must physically hear it.

## 9.4 Repeated I/O smoke

Repeat record + playback two more times using shorter 4-second samples.

Purpose:

catch immediate device/open/close issues.

Do not treat this as production soak testing.

Checkpoint:

```text
PHASE1_LAPTOP_AUDIO_AUTOMATED_OK
```

Then set:

```text
Status: PHASE_1_WAITING_FOR_AUDIO_CONFIRMATION
```

---

# Task 10 — Manual user listening gate

Ask the user:

```text
Please listen to recordings/phase1/laptop_mic_egyptian.wav and confirm:
1) the recording is clear enough for development,
2) Egyptian speech is intelligible,
3) there is no severe clipping/corruption,
4) playback works normally.

Reply PASS or tell me which item failed.
```

Do not mark Phase 1 complete until user replies.

If PASS:

continue.

If failed:

record the exact failed item.
Do not add software AEC/NS automatically.
Use `PHASE_1_BLOCKED` only if the laptop development audio path cannot be made usable after direct device/permission fixes.

---

# Task 11 — Finalize Phase 1

Only after user PASS.

Create:

```text
docs/phase1/PHASE1_REPORT.md
```

Required content:

```markdown
# Phase 1 Report

## Final State
PHASE_1_COMPLETE

## Development Environment
- OS:
- Python:
- Branch:
- Final commit:

## Audio Development Path
- Input device:
- Output device:
- Sample rate:
- Channels:
- Recording: PASS
- Playback: PASS
- Repeated I/O smoke: PASS
- Manual Egyptian listening gate: PASS

## Automated Verification
- pytest:
- Ruff:
- config load:

## Deferred Deployment Validation
- Raspberry Pi 5: NOT TESTED IN PHASE 1
- Anker PowerConf S330: NOT TESTED IN PHASE 1
- Production USB/ALSA/full-duplex/AEC/soak validation: DEFERRED
- Deployment may be validated later by another team member.

## Phase 1 Decisions
- Laptop is the active development platform.
- Core audio interfaces remain hardware-agnostic.
- No device index is hard-coded in production configuration.
- No STT/TTS/LLM API was called.
- No model was downloaded.
- No Phase 2 implementation was started.

## Blockers
None.

## Next
Phase 2 — Realtime Conversation Core.
```

Populate actual values only.

## Update `MASTER_PLAN.md`

Bump patch version from:

```text
1.5 → 1.6
```

Record:

- actual laptop input/output device names;
- confirmed 16 kHz development path;
- user listening PASS;
- Pi/S330 deployment validation still deferred;
- Phase 2 authorized.

Do not claim Pi/S330 validation.

## Update README

Use:

```text
Current status: Phase 1 complete — laptop software/audio development foundation validated.

Current development: Windows laptop + laptop microphone/output.

Target deployment: Raspberry Pi 5 8 GB + Anker PowerConf S330; production hardware validation remains pending.

Next: Phase 2 — Realtime Conversation Core.
```

## Update Phase state

```text
Status: PHASE_1_COMPLETE
Last completed task: Task 11
Next task: STOP — wait for Phase 2 handoff
Development audio: PASS
Raspberry Pi deployment: Deferred
S330 deployment validation: Deferred
Manual acoustic gate: PASS
Phase 2 authorized: Yes
```

## Fresh verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
git diff --check
git status --short
```

Check no model files were added:

```powershell
Get-ChildItem -Recurse -File -Include *.gguf,*.safetensors,*.onnx |
    Where-Object {
        $_.FullName -notmatch "\\donor-repos\\"
    }
```

Expected:

no new production model weights.

Commit:

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
  .gitignore `
  CODEX_PHASE1_FOUNDATION_LAPTOP_AUDIO.md

git commit -m "feat: complete Phase 1 laptop development foundation"
```

Verify clean:

```powershell
git status --short
git log -3 --oneline
```

Push:

```powershell
git push -u origin "phase/1-foundation-laptop-audio"
```

Do NOT merge.

Final response format:

```text
Phase 1 state: PHASE_1_COMPLETE

Branch:
phase/1-foundation-laptop-audio

Final commit:
<sha>

Windows:
<version>
Python: <version>

Tests:
pytest: PASS
Ruff: PASS

Laptop audio:
input: <device>
output: <device>
recording: PASS
playback: PASS
manual Egyptian listening: PASS

Deployment hardware:
Raspberry Pi: DEFERRED
Anker S330: DEFERRED

Master Plan:
updated to v1.6

Phase 2:
AUTHORIZED BUT NOT STARTED
```

STOP.

---

# Error decision table

| Failure | Action |
|---|---|
| Dirty repo before work | STOP; report files |
| Python outside `>=3.11,<3.15` | BLOCKED |
| `pip install` fails | pip upgrade + retry once; then BLOCKED |
| `sounddevice` import fails | inspect actual pip error; reinstall exact Phase 1 dependency once |
| No input devices listed | check Windows microphone permissions/default device; do not redesign architecture |
| No output devices listed | check Windows sound/default device |
| Wrong default mic selected | use `--device` for interactive test only; do not commit index as default |
| Mic permission denied | instruct user to enable Windows microphone access |
| Recording silent | verify OS input meter/default mic + explicit test device |
| Playback silent | verify OS output device + volume |
| Clipping severe | lower OS mic level if possible and rerun |
| User listening pending | `PHASE_1_WAITING_FOR_AUDIO_CONFIRMATION` |
| User audio fails | direct device/permission correction; do not add AEC/NS automatically |
| Raspberry Pi unavailable | IGNORE for current Phase 1 |
| Anker S330 unavailable | IGNORE for current Phase 1 |
| Need architecture change | STOP; update Master Plan decision first |

---

# Context-saving rule for Luna

For each task:

1. Read this task only.
2. Read current files being changed.
3. Refer to `DONOR_INSPECTION.md` instead of donor repos unless absolutely necessary.
4. Do not reread the full Master Plan after Task 1.
5. Before Task 11, reread only:
   - Master Plan Development vs Deployment section;
   - Master Plan Phase 1 contract;
   - Task 11;
   - `PHASE1_STATE.md`.
6. Prefer commands and exact file content from this plan over open-ended exploration.

---

# Definition of Done

Phase 1 is complete only when:

- Phase 1 branch is correct.
- Master Plan v1.5 was synchronized.
- Python environment installs.
- all unit tests pass.
- Ruff passes.
- config is Egyptian-Arabic-first.
- provider contracts exist.
- logging exists.
- audio abstraction is hardware-agnostic.
- laptop devices can be enumerated.
- laptop microphone records 16 kHz mono PCM16 WAV.
- laptop output plays WAV.
- repeated short I/O works.
- Egyptian speech recording exists.
- user listening gate passes.
- no device index is hard-coded in default production config.
- Raspberry Pi absence did not block work.
- S330 absence did not block work.
- deployment validation is explicitly documented as deferred.
- no provider API was called.
- no model weights were downloaded.
- no Phase 2 code was implemented.
- Master Plan is updated with actual Phase 1 results.
- final verification is fresh.
- branch is pushed.
- branch is NOT merged.
- final state is `PHASE_1_COMPLETE`.

---

**STOP AFTER PHASE 1. DO NOT START PHASE 2.**

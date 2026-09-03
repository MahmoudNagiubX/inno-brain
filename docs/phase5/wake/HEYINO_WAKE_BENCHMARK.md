# InnoBrain Gate 5C.0 — Heyino Wake Word Benchmark & Evaluation Protocol

> **Document Role:** Official candidate specification, evaluation protocol, and benchmark ledger for the `Heyino` wake word.
> **Date:** 2026-09-03
> **Gate:** Gate 5C.0 (Wake + Attention)
> **Branch:** `phase/5c0-wake-attention`
> **Controlling Invariant:** Synthetic data must not be presented as real acceptance. Candidate quality is provisional until separate held-out human data supports an acceptance claim.
> **Current Status:** `DATA_PENDING / PROVISIONAL`
> **Selected Engine:** `NONE (Awaiting Held-Out Human Evidence)`

---

## 1. Product Wake Phrase Specification

The product wake phrase is permanently locked across InnoBrain architecture:

| Property | Value | Notes |
|---|---|---|
| **Wake Phrase** | `Heyino` (`H-E-Y-I-N-N-O`) | Permanent product wake invocation |
| **Semantic Label** | `heyino` | Canonical constant in `innobrain.wake.contracts.CANONICAL_WAKE_LABEL` |
| **Allowed Pronunciation Variants** | `heyino`, `hey_ino`, `hayino`, `heyno`, `heyinno`, `hayinno`, `he_yino`, `هاي إينو`, `هي إينو`, `هيينو`, `هايينو` | Covers natural Egyptian Arabic and English accent variations |
| **Audio Format** | 16,000 Hz, 16-bit PCM, Mono | Single microphone stream; shared with VAD/STT |
| **Capture Policy** | Local-only offline audio | Sleeping wake audio never enters cloud STT, LLM, or TTS |

---

## 2. Acceptance Targets (Gate 5C.0)

To achieve production acceptance on deployment hardware (Raspberry Pi 5 with Anker PowerConf S330), an engine must satisfy the following thresholds on the **held-out human evaluation split**:

| Metric | Target Threshold | Scope | Rationale |
|---|---|---|---|
| **Quiet / Moderate-Noise Recall** | ≥ 98.0% | Near-field (0.5m) and Mid-field (1.5m) in quiet & ambient noise | Primary conversational interaction standard |
| **Pronunciation Variants Recall** | ≥ 95.0% | Allowed Egyptian Arabic and English pronunciation variants | Robustness across natural speaker accents |
| **Far / Event Noise Recall** | ≥ 93.0% | Far-field (3.0m) or high-energy Exhibition Crowd noise condition | Usability in noisy conference/event halls |
| **False Rejection Rate (FRR)** | ≤ 2.0% | Near-field (0.5m) and Mid-field (1.5m) quiet/ambient | Minimizes user frustration |
| **False Activations / Hour** | ≤ 0.10 FA/hr | Continuous conference ambient / office background (stretch ≤ 0.05) | Eliminates unprompted interruptions during events |
| **Median Detection Latency (P50)** | ≤ 300 ms | Average / median time from utterance completion to trigger | Conversational responsiveness |
| **P95 Detection Latency** | ≤ 300 ms | Tail latency from phrase completion to `WakeDetection` emit | Bounded worst-case response delay |
| **Mean Detection Latency** | ≤ 200 ms | Stretch mean time to detection | Natural conversational flow |
| **Data Separation** | 0% leakage | All pairs (train ↔ calib, train ↔ holdout, calib ↔ holdout) strictly disjoint | Prevents memorization and false validation |

---

## 3. Candidate Engine Comparison Matrix

Two candidate architectures are evaluated under the vendor-neutral `WakeWordEngine` contract:

| Specification Field | Candidate A: Custom openWakeWord | Candidate B: Picovoice Porcupine |
|---|---|---|
| **Engine Identifier** | `openwakeword` | `porcupine` |
| **Architecture** | Custom feed-forward / DSCNN on speech embeddings | Proprietary neural acoustic keyword spotter |
| **Model Asset Path** | `models/wake/heyino_openwakeword_v0.onnx` | `models/wake/heyino_porcupine.ppn` |
| **Model SHA-256 Hash** | `DATA_PENDING` | `DATA_PENDING` |
| **Frame Length** | 1280 samples (80 ms @ 16 kHz) | 512 samples (32 ms @ 16 kHz) |
| **Provisional Threshold / Sensitivity** | `0.50` (calibration pending) | `0.50` (calibration pending) |
| **Runtime Dependencies** | ONNX Runtime (CPU), NumPy | `pvporcupine` runtime, access key |
| **Licensing / Privacy** | Apache 2.0, 100% offline, fully local | Commercial license, 100% local audio execution |
| **Streaming Frame Latency** | 80 ms chunking | 32 ms chunking |
| **Training Pipeline** | Open-source trainer (`train_openwakeword.py`) | Picovoice Console / proprietary training |
| **Augmented Training Target** | ≥ 50,000 augmented positives | Picovoice synthetic profile generation |
| **Current Readiness** | `DATA_PENDING (Model Training Queued)` | `DATA_PENDING (Asset Generation Queued)` |

---

## 4. Corpus Architecture & Hard-Negative Families

The Heyino corpus is partitioned into three strictly isolated splits:

1. **`train`**: Base positive utterances and negative recordings used for model training and augmentation (minimum 50,000 augmented positives).
2. **`calibration`**: Separate speaker recordings used exclusively for hyperparameter tuning and operating threshold sweeps.
3. **`held_out`**: Completely unseen speakers and acoustic clips reserved exclusively for final benchmark reporting. Zero data or speaker leakage is permitted.

### 4.1 Hard-Negative Confuser Families

All evaluations must test against the following mandatory confuser categories:

| Confuser Family | Representative Clips / Syllables | Objective |
|---|---|---|
| **Phonetic Confusers** | `hey`, `inno`, `hey no`, `hey now`, `I know`, `hey you`, `hello`, `Nino`, `hey Nino`, `eno`, `aino`, `ayno`, `hino`, `inno hey`, `hey dino` | Prevent acoustic false triggers on phonetic neighbors |
| **Egyptian Conversation** | Everyday Egyptian Arabic dialogue (`ازيك يا باشا`, `صباح الخير`, `فين القاعة`, `ممكن تساعدني`) | Verify immunity to colloquial Egyptian Arabic speech |
| **English Conversation** | Conference dialogues (`where is the registration desk`, `what time is the keynote`) | Verify immunity to general English conversation |
| **Announcements** | PA system calls, workshop notifications, microphone checks | Eliminate triggers from loud venue broadcast audio |
| **Crowd / Music / Claps** | Audience applause, background music playback, hall hum, cheering | Replicate exhibition hall noise floor |
| **Bumps / Impulse Noise** | Table thumps, mic knocks, footsteps, door slams | Reject mechanical and handling transients |
| **TTS Self-Bleed** | Synthesized robot speech playback, phone assistant speech | Prevent robot from waking itself during response output |

---

## 5. Benchmark Measurement Ledger

> [!WARNING]
> No measured acceptance claim is currently made. The table below represents provisional target tracking. In accordance with Gate 5C.0 invariants, measured values will be populated only after physical recordings and held-out human evaluation are executed.

| Split | Candidate Engine | Calibrated Threshold | Measured Recall | Measured FRR | Measured FA/hr | P95 Latency | State |
|---|---|---|---|---|---|---|---|
| **Calibration** | `openwakeword` | `PROVISIONAL (0.50)` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` |
| **Calibration** | `porcupine` | `PROVISIONAL (0.50)` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` |
| **Held-Out** | `openwakeword` | `PENDING_CALIBRATION` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `PROVISIONAL` |
| **Held-Out** | `porcupine` | `PENDING_CALIBRATION` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `DATA_PENDING` | `PROVISIONAL` |

---

## 6. Execution Instructions for Integrator

All tooling is local-only, import-safe, and does not open network connections or invoke microphones in tests.

### 6.1 Recording New Corpus Clips
```powershell
# Interactive recording session
.venv\Scripts\python.exe scripts\wakeword\record_heyino_corpus.py --interactive --output-dir recordings\heyino_corpus

# Batch recording / synthetic test mode
.venv\Scripts\python.exe scripts\wakeword\record_heyino_corpus.py --output-dir recordings\heyino_corpus --split train --label heyino --mock-audio
```

### 6.2 Generating Training Plan & Verifying Prerequisites
```powershell
# Generate training plan (enforces minimum 50,000 augmented positives)
.venv\Scripts\python.exe scripts\wakeword\train_openwakeword.py --generate-plan scripts\wakeword\heyino_training_plan.json --min-positives 50000

# Check prerequisites without downloading or executing training
.venv\Scripts\python.exe scripts\wakeword\train_openwakeword.py --manifest recordings\heyino_corpus\manifest.json --check-prerequisites
```

### 6.3 Running Calibration & Held-Out Evaluation
```powershell
# Run two-stage evaluation (calibration sweep + held-out test)
.venv\Scripts\python.exe scripts\wakeword\evaluate_wakeword.py --manifest recordings\heyino_corpus\manifest.json --engine openwakeword --model-path models\wake\heyino_openwakeword_v0.onnx --output-dir artifacts\phase5\wake_eval
```

---

## 7. Decision for Integrator

1. **Engine Selection:** `NO_SELECTION_PENDING_HELD_OUT_EVALUATION`
   Neither Candidate A (`openwakeword`) nor Candidate B (`porcupine`) is selected as primary at this checkpoint. Both runtime adapters are implemented and verified under Worker A (`b3afd02`), and evaluation tooling is complete under Worker B.
2. **Acceptance Status:** `PROVISIONAL`
   A formal acceptance claim requires held-out evaluation on real Egyptian human recordings collected across varying distances and noise conditions.
3. **Data Integrity:**
   All manifests must be verified using `scripts/wakeword/heyino_corpus_spec.py::validate_manifest` to ensure zero speaker or clip leakage prior to training or benchmarking.

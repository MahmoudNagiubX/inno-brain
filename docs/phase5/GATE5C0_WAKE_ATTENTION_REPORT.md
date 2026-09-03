# Gate 5C.0 Wake + Adaptive Attention Report

**Final state:** `GATE_5C0_IMPLEMENTATION_COMPLETE_WAKE_DATA_PENDING`
**Branch:** `phase/5c0-wake-attention`
**Code checkpoint:** `b871e48`

## Decision

Gate 5C.0 implementation is complete for the offline laptop-first foundation.
The engine decision remains open: custom openWakeWord and Porcupine are both
implemented behind the same local `WakeWordEngine` boundary, but neither is
selected without the required held-out human recordings and calibration.

## Runtime behavior

The existing `SoundDevicePCMStream` remains the sole microphone owner. Raw
PCM is enqueued by the sounddevice callback and wake routing runs once on the
async feed path. In `SLEEPING`, the local detector receives audio while STT
and VAD receive nothing. A canonical detection enters `ENGAGED` and forwards
only the current detection/continuation chunk; diagnostic ring-buffer history
is never user content. Engaged and follow-up PCM continue through the existing
Silero VAD, Smart Turn, and provider path.

Attention is separate from conversation state and uses `SLEEPING`, `ENGAGED`,
and `FOLLOWUP_WINDOW`. The default follow-up window is 4500 ms with an 8000 ms
cap, the hard session cap is 120 seconds, and one rejected background input
closes the session. Addressivity recognizes explicit wake, directed cues,
conversation continuity, and background/ambiguous speech. `PresenceSignal` is
a future-safe local hook with an unknown default and no hardware calls.

## Offline artifacts and safeguards

- Fixed Heyino identity and strict configuration validation.
- Hard-negative families for phonetic confusers, Egyptian/English conversation,
  announcements, crowd/music/claps, bumps/impulses, and TTS bleed.
- Strict metadata parsing and all-pair speaker/path split isolation.
- Calibration threshold selection honors recall and measured false-activation
  targets; missing negative duration is never reported as zero FA/hour.
- Calibration sweep and held-out reports are exported separately.
- Custom training helper is explicitly builder-only and cannot silently claim a
  trained model.
- `.env` values fill only missing valid environment names, are not logged or
  returned, and do not override explicit process/test values.
- Unconfigured wake models produce a visible degraded/data-pending health
  state and never synthesize detections.
- Application activation/rollback, lifecycle cleanup, and attention reset
  clear wake/session context without a second stream.
- Corpus collection is safe to resume from the laptop: direct and module
  recorder execution work, BOM manifests are accepted, the repair tool is
  report-first and metadata-conservative, manifest writes are atomic, and
  recorder preflight blocks stale or structurally inconsistent corpora before
  microphone capture. New WAVs are never deleted because unrelated historical
  entries are broken.

## Verification record

| Gate | Result |
|---|---|
| Full pytest | `369 passed / 2 expected skips` |
| Focused wake/attention/config/application tests | `149 passed` |
| Focused Heyino corpus workflow | `20 passed` |
| Wake-unit tests | `102 passed` |
| Ruff | clean |
| pip check | no broken requirements |
| git diff check | clean |
| Offline `wake-check` | data pending; no network; no stream |
| Offline `check` | not ready due absent event/E5/providers; no network; no stream |

The two expected skips are the existing builder-only Docling check and the
opt-in real E5 model check. The single archive-security warning is from the
existing duplicate-ZIP-entry test fixture and is not a failure.

## Explicit non-actions

No real Speechmatics, Deepgram, Groq, Azure, microphone, Pi 5, Anker S330,
Robot, Screen, ROS, API credential setup, or end-to-end voice execution was
performed. Phase 6 and later work remain stopped.

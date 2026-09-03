# Gate 5C.0 State

**Branch:** `phase/5c0-wake-attention`
**Implementation checkpoint:** `7938795`
**State:** `GATE_5C0_IMPLEMENTATION_COMPLETE_WAKE_DATA_PENDING`

## Scope completed

- Fixed local wake identity: `Heyino` (`H-E-Y-I-N-N-O`), canonical label
  `heyino`.
- Added vendor-neutral wake contracts and local OpenWakeWord/Porcupine
  adapters, with no candidate selected before real held-out comparison.
- Added strict corpus metadata, pronunciation/noise/distance dimensions,
  hard-negative families, all-pair speaker/path leakage checks, calibration,
  and JSON/CSV/Markdown benchmark exports.
- Added builder-only custom-training planning and explicit data/dependency
  pending behavior; no fake model asset is produced.
- Added one-stream local routing, bounded diagnostic pre-roll, current-chunk
  same-breath handoff, orthogonal attention states, addressivity, adaptive
  follow-up, session cap, presence hook, and health/recovery snapshots.
- Wired the existing PCM/VAD/Smart Turn/provider graph through an async-side
  wake gate. Sleeping PCM is not forwarded to STT/VAD, and wake history is
  never forwarded as user content.
- Added safe project-root `.env` loading, offline `check` and `wake-check`,
  and the authorized but unexecuted `run` entrypoint.

## Evidence

- Full offline pytest: **349 passed, 2 expected skips**.
- Focused wake/attention/config/application suite: **149 passed**.
- Ruff: **clean**.
- `pip check`: **No broken requirements found**.
- `git diff --check`: **clean**.
- `python -m innobrain wake-check`: completed with
  `network_calls_made=false`, `audio_stream_started=false`, and
  `data_pending` for both candidates because model/dependency assets are not
  present in this runtime.
- `python -m innobrain check`: completed offline with no network call and no
  started stream.

## Deferred acceptance

The state is deliberately data-pending. No held-out human corpus exists yet,
so no wake engine is selected and no `WAKE_ACCEPTED` claim is made. Real
provider calls, microphone acceptance, Raspberry Pi/S330 validation, Robot,
Screen, ROS, and API setup were not performed. Phase 6 is not started.

## Next authorized step

Collect and validate the separate human Heyino corpus, run calibration and
held-out comparison for both candidates, then schedule the separately
controlled real-provider voice gate. Do not treat synthetic tests as acoustic
acceptance evidence.

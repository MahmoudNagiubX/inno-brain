# Gate 5C.0 Wake + Attention Integration Note

This note locks the shared contracts before delegated implementation. The
workers must not mutate these boundaries after the checkpoint without returning
the change to the main integrator for review.

## Shared invariants

- The product wake phrase is permanently `Heyino` (`H-E-Y-I-N-N-O`) with the
  semantic label `heyino`.
- Only the existing PCM microphone stream is opened. Wake detection, attention,
  VAD, Smart Turn and STT are consumers of that stream, not independent audio
  capture owners.
- Sleeping wake audio is local-only and never enters cloud STT, LLM or TTS.
- Existing conversation states and playback-first barge-in semantics remain
  unchanged. Attention is an orthogonal layer.
- No worker may add real provider calls, API setup, microphone acceptance, Pi,
  S330, Robot, Screen or ROS work.
- Candidate quality is provisional until separate held-out human data supports
  an acceptance claim; synthetic data must not be presented as real acceptance.

## Locked contracts

### Wake boundary

`src/innobrain/wake/contracts.py` owns:

- `WakeDetection(label, detector, detected_at_monotonic, score)`;
- `WakeWordEngine.sample_rate_hz`, `frame_length`, `process(pcm16)`,
  `reset()`, and `close()`;
- detector health fields and the common engine configuration boundary.

Adapters may wrap optional vendor/model objects, but those objects do not leak
through the contract.

### PCM and attention boundary

The bounded ring buffer preserves approximately 1.5 seconds of pre-roll and
post-detection continuation. A router sends frames to wake-only or engaged
consumers according to the attention controller; it never opens a second input
stream.

The attention layer owns `SLEEPING`, `ENGAGED`, and `FOLLOWUP_WINDOW`,
`AddressivityDecision`, `AddressivityGate`, `PresenceSignal`, session-close
reasons, counters, and watchdog-visible health. It does not replace the
conversation state machine.

### CLI/config boundary

Wake configuration is nested under `runtime.wake_word`; attention policy is
nested under `runtime.attention`. `python -m innobrain check` and
`python -m innobrain wake-check` are offline-only. `.env` is loaded only at
application startup, never committed or logged.

## Delegation order and ownership

Delegation is sequential because all workers depend on the locked contracts:

1. **Worker A — wake inference/runtime:** wake contracts, ring buffer, local
   candidate adapters, router, and wake runtime tests.
2. **Worker B — training/evaluation:** corpus metadata, hard negatives,
   pronunciation/noise evaluation, calibration, training configuration, and
   benchmark artifacts/tooling. It may consume Worker A contracts but does not
   change them.
3. **Worker C — attention/session:** orthogonal attention states, follow-up
   policy, addressivity, presence hook, session-close reasons, and tests. It may
   consume the router contract but does not change wake contracts.
4. **Worker D — application integration:** one-stream lifecycle integration,
   config, safe `.env`, CLI commands, watchdog telemetry, and cross-component
   tests. It consumes A-C interfaces and does not redesign them.

The main Codex integrator reviews every diff, runs focused tests after each
worker, resolves only interface mismatches, then runs the full offline gate.

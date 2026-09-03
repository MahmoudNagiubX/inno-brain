# Gate 5B.1 Final Targeted Sol Re-Review

**Verdict:** `READY_FOR_PHASE5_VOICE`

**Review branch:** `review/gate5b1-final-sol-rereview`

**Prior blocked-review baseline:** `532777715206d4158981ed4b2f0dfb2f938b7971`

**Reviewed implementation:** `phase/5b1-final-blockers` at
`8a1f0068c3eab5efca8f88e3675ee44dff0314b9`

This was a targeted re-review of only the three previously partially-closed
P1 findings. It was not a broad architecture audit. No production code was
changed, and no real provider calls, microphone tests, Gate 5C, Robot, Screen,
or ROS work was performed.

## Finding disposition

| Finding | Status | Exact code evidence | Exact test evidence |
|---|---|---|---|
| Production `InnoBrainApplication` live event switching/rebinding, quiescent activation, memory reset, rollback, shutdown, and zero-leak behavior | `CLOSED` | `src/innobrain/app.py:24-79,114-197` owns `RuntimeContextSwitcher` and `ActivationManager`, guards activation with `voice.is_quiescent`, exposes activation/rollback, and closes the current context on shutdown. `src/innobrain/event/runtime.py:65-115` opens the candidate context, swaps the active knowledge snapshot, resets memory, closes the old context, and clears the current reference. `src/innobrain/voice/brain_runtime.py:73-80` defines quiescence. | `tests/integration/test_application_event_switch.py:151-250` exercises the production application graph through Alpha→Beta switching, busy-state rejection, memory reset, knowledge rebinding, Alpha/Beta isolation, rollback, and current-context shutdown. `tests/e2e/event/test_event_switch_no_leak.py:55-87` preserves the existing no-leak/memory-reset regression. |
| Speechmatics 0.2.8 provider-session ID→application-turn ID mapping, including provider ID 0, installed callback shapes, sequential turns, stale callbacks, and restart | `CLOSED` | `src/innobrain/providers/speechmatics_stt.py:89-117,131-159,166-214` keeps separate active application/provider IDs, starts provider IDs at zero, accepts zero explicitly, attributes installed segment callbacks to the active application turn, rejects stale `END_OF_TURN` IDs, and resets the mapping on start/stop. | `tests/unit/providers/test_speechmatics_stt.py:5-39` constructs the installed `speechmatics-voice==0.2.8` `SegmentMessage` and `TurnStartEndResetMessage` shapes. Tests at `:105-137`, `:141-166`, `:170-207`, `:211-241`, and `:245-276` cover provider IDs 0/1/2, stale callbacks, inactive segments, restart, and worker-thread callbacks. The independent installed-shape reproduction mapped `(1,'turn-0'), (2,'turn-1'), (3,'turn-2')`. |
| Cleanup-safe state recovery for normal faults and barge-in, including playback/provider cancellation exceptions while preserving playback-first cancellation | `CLOSED` | `src/innobrain/voice/brain_runtime.py:243-313` records cleanup faults, isolates playback/provider cleanup failures, and always recovers response faults to `LISTENING`. `src/innobrain/voice/interruption.py:34-65` stops playback before response cancellation and restores `LISTENING` in `finally` blocks. | `tests/integration/voice/test_failure_recovery.py:151-285` covers normal TTS/transcript faults, playback cleanup faults, provider cleanup faults, and both cleanup faults. `tests/integration/voice/test_barge_in_cancellation_order.py:131-212` covers playback-first cancellation, no post-cancel PCM, and playback-cancel failure recovery. `tests/unit/voice/test_interruption.py:24-168` covers playback-first ordering and cancellation exceptions. The independent cleanup reproduction produced `RESULT None`, `STATE LISTENING`, and faults `tts` plus `tts.playback_cleanup`. |

## Regression and verification evidence

- Full pytest: `203 passed, 2 skipped, 1 warning in 8.17s`.
- Focused production-graph and targeted-finding suite: `31 passed in 5.05s`.
- Event security suite: `2 passed in 0.29s`.
- Closed archive-security regression: `12 passed, 1 warning in 0.19s`.
- Ruff: `All checks passed!`.
- `pip check`: `No broken requirements found.`
- `git diff --check`: passed.
- Offline `python -m innobrain check`: exit `0`, `network_calls_made=false`,
  status `not_ready` because no active event, provider credentials, or E5
  assets are present. This is expected and is not a live-voice acceptance.

The full suite retained the two expected skips: optional builder-only Docling
and the opt-in real E5 model test. The single warning is the intentional
duplicate ZIP-entry fixture used by archive-security coverage.

## Gate decision

The previously closed package TOCTOU P0 and seven audited P1 findings remain
closed. The three targeted findings above are now closed, so final counts are
**P0=0** and **P1=0**, with no new blocking regression. Gate 5C is authorized
for a separately controlled real-provider/real-voice run, but it is **not
started** by this review.

All existing validation debt remains: controlled Egyptian turn/hesitation and
barge-in acceptance, final real-provider/end-to-end voice acceptance, and
Raspberry Pi 5 plus Anker S330 validation. `READY_FOR_PHASE5_VOICE` authorizes
that next gate; it does not claim those physical or live-provider checks have
passed.

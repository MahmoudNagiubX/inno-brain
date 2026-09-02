# InnoBrain

InnoBrain is the Egyptian-Arabic-first AI/voice brain for an event robot.

The target edge hardware is a Raspberry Pi 5 with 8 GB RAM and an Anker PowerConf S330 speakerphone. The `MASTER_PLAN.md` file is the project's source of truth.

The research repositories are maintained in the sibling `donor-repos/` directory and are not production dependencies.

Current development: Windows laptop + laptop microphone/output.

Target deployment: Raspberry Pi 5 8 GB + Anker PowerConf S330; production hardware validation remains pending.

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

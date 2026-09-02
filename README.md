# InnoBrain

InnoBrain is the Egyptian-Arabic-first AI/voice brain for an event robot.

The target edge hardware is a Raspberry Pi 5 with 8 GB RAM and an Anker PowerConf S330 speakerphone. The `MASTER_PLAN.md` file is the project's source of truth.

The research repositories are maintained in the sibling `donor-repos/` directory and are not production dependencies.

Current development: Windows laptop + laptop microphone/output.

Target deployment: Raspberry Pi 5 8 GB + Anker PowerConf S330; production hardware validation remains pending.

Current status: Phase 3 implementation complete; provider and interactive voice acceptance deferred.

Implemented:
- realtime PCM pipeline
- Pipecat 1.8.1
- Silero VAD
- Smart Turn v3
- conversation state machine
- cancellation/interruption framework
- Speechmatics primary STT with Deepgram Nova-3 fallback adapters
- Groq grounded LLM adapter with `openai/gpt-oss-120b` baseline
- Azure `ar-EG-ShakirNeural` TTS adapter
- structured SQLite event facts and FTS5 + sqlite-vec/RRF retrieval
- multilingual-E5 ONNX embedding boundary
- ten-turn/300-second grounded session memory
- deterministic exact, RAG, degraded, and no-evidence text paths

Deferred validation:
- controlled Egyptian turn/hesitation test
- live barge-in acceptance
- final end-to-end voice acceptance
- Raspberry Pi/S330 production validation
- real E5 model retrieval benchmark
- provider smoke with live credentials

Next:
Phase 4 — Dynamic Event Package (authorized; not started).

# InnoBrain

InnoBrain is the Egyptian-Arabic-first AI/voice brain for an event robot.

The target edge hardware is a Raspberry Pi 5 with 8 GB RAM and an Anker PowerConf S330 speakerphone. The `MASTER_PLAN.md` file is the project's source of truth.

The research repositories are maintained in the sibling `donor-repos/` directory and are not production dependencies.

Current development: Windows laptop + laptop microphone/output.

Target deployment: Raspberry Pi 5 8 GB + Anker PowerConf S330; production hardware validation remains pending.

Current status: Gate 5B.1 final targeted Sol re-review is clean: `READY_FOR_PHASE5_VOICE`. Gate 5C.0 wake and attention implementation is complete with wake data pending: `GATE_5C0_IMPLEMENTATION_COMPLETE_WAKE_DATA_PENDING`. Real provider/API voice, interactive voice, and Pi/S330 acceptance remain deferred.

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
- self-contained signed `.innoevent` packages with strict local authoring
- builder-only Docling 2.124.0 and real multilingual-E5 package builds
- target-local read-only SQLite/FTS5/sqlite-vec databases
- atomic event activation, session-memory reset, zero-leak switching and rollback
- optional allowlisted HTTPS distribution for complete event packages only

Deferred validation:
- controlled Egyptian turn/hesitation test
- live barge-in acceptance
- final end-to-end voice acceptance
- Raspberry Pi/S330 production validation
- provider smoke with live credentials

Next:
Collect the separate held-out human Heyino corpus, calibrate and compare openWakeWord against Porcupine, then schedule the separately controlled real-provider/real-voice gate. No real provider or microphone acceptance execution occurred in Gate 5C.0.

Offline readiness inspection (does not call providers or open a microphone stream):

```powershell
python -m innobrain check
```

The `run` entrypoint is wired for the authorized runtime but remains unexecuted in Gate 5C.0; API credentials and live voice scheduling are still required.

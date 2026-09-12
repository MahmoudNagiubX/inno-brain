# InnoBrain

InnoBrain is the Egyptian-Arabic-first AI/voice brain for an event robot.

The target edge hardware is a Raspberry Pi 5 with 8 GB RAM and an Anker PowerConf S330 speakerphone. The `MASTER_PLAN.md` file is the project's source of truth.

The research repositories are maintained in the sibling `donor-repos/` directory and are not production dependencies.

Current development: Windows laptop + Anker PowerConf S330 A3308 microphone and speaker.

Target deployment: Raspberry Pi 5 8 GB + Anker PowerConf S330; production hardware validation remains pending.

Current status: Gate 5C.1A structural P1 remediation is complete on the core-voice/multilingual/S330-routing branch. The S330 is property-selected as the primary Windows development input/output, and development wake bypass is explicit and production-forbidden. Real provider/API voice, physical S330 acoustics, interactive multilingual acceptance, and Pi validation remain deferred.

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
- per-turn Arabic/English/mixed language policy with configurable English Azure voice
- capability-aware provider startup and incremental LLM sentence streaming into TTS
- development-only wake bypass with visible health/CLI state
- property/capability-based S330 input and output routing without persisted device indexes
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
- physical S330 full-duplex/acoustic validation on Windows
- Raspberry Pi production validation
- real Arabic provider voice and real English/code-switch validation
- provider smoke with live credentials

Next:
Run the controlled local S330 physical validation, then real Arabic provider voice and real English/code-switch validation. Heyino corpus collection/training/calibration remains deferred until after core voice and multilingual validation. No real provider call or physical audio stream was executed in Gate 5C.1A.

Offline readiness inspection (does not call providers or open a microphone stream):

```powershell
python -m innobrain check
```

The `run` entrypoint is wired for the authorized runtime but remains unexecuted in Gate 5C.1A; API credentials and live voice scheduling are still required.

# Donor Inspection Report

Inspection was performed against the shallow-cloned commit recorded for each
repository in `DONOR_REPOS.lock.yaml`. The root README, package metadata, root
license evidence, and the handoff-specified relevant paths were inspected.
Donors are reference material only at bootstrap time; no source was copied into
the production repository.

License entries below describe repository code evidence. Model weights, datasets,
sample media, vendored components, external SDKs, and third-party dependencies
are called out separately because a code license does not automatically cover
them.

## Pipecat

**URL:** https://github.com/pipecat-ai/pipecat.git  
**Commit inspected:** `719b580bd9c29532ed717288aef184d32286df20`  
**License:** BSD-2-Clause (`LICENSE`, `pyproject.toml`)

**Why cloned:** Locked realtime Python voice runtime and provider-neutral frame/pipeline foundation.

**Most relevant files/directories:**
- `README.md`, `pyproject.toml`
- `src/pipecat/pipeline/`
- `src/pipecat/audio/vad/`
- `src/pipecat/audio/turn/smart_turn/`
- `src/pipecat/processors/aggregators/`
- `src/pipecat/utils/async_tool_cancellation.py`
- `examples/getting-started/01a-local-audio.py`
- `examples/turn-management/`
- `tests/test_pipeline.py`, `tests/test_tts_interruptible_service.py`, and local Smart Turn tests

**What InnoBrain can reuse/adapt:** Frame-based pipeline composition, streaming
service boundaries, local audio examples, provider adapters, turn analyzers,
interruptible TTS behavior, and cancellation/test patterns.

**What InnoBrain should NOT copy/adopt:** Donor examples as the product/domain
architecture, arbitrary transports, or provider-specific assumptions. Business
logic remains in `src/innobrain` and any later Pipecat dependency must be pinned
and tested on the Pi.

**Dependencies / hardware assumptions:** Python >=3.11; core async/audio-related
Python dependencies; optional provider, local-audio, and local Smart Turn extras;
ONNX Runtime is required by the current local Smart Turn path. The repository
also tracks Silero/Smart Turn ONNX assets under its package data.

**Phase(s) this repo may help:** Phase 1, Phase 2, Phase 3, Phase 6.

**Inspection verdict:** KEEP

## Smart Turn

**URL:** https://github.com/pipecat-ai/smart-turn.git  
**Commit inspected:** `4786657e242dfe77dd138699ac564ee074a2a543`  
**License:** BSD-2-Clause (`LICENSE`)

**Why cloned:** Locked semantic end-of-turn detector for pauses versus completed thoughts.

**Most relevant files/directories:**
- `README.md`
- `inference.py`, `predict.py`, `audio_utils.py`, `model.py`
- `requirements_aarch64.txt`
- `record_and_predict.py`

**What InnoBrain can reuse/adapt:** The input contract and adapter design: 16
kHz mono PCM, up to 8 seconds, leading zero padding for short input, full-turn
re-evaluation when new speech arrives, and a probability/prediction result.

**What InnoBrain should NOT copy/adopt:** `requirements_aarch64.txt` as a Pi
deployment recipe; it targets CUDA/nightly PyTorch on aarch64 and is not evidence
of Raspberry Pi compatibility. Do not copy model files into production during
bootstrap.

**Dependencies / hardware assumptions:** ONNX Runtime, NumPy, Transformers'
Whisper feature extractor, and librosa/soundfile for the file example. The
reference model is audio-native and intended to run after lightweight VAD.

**Phase(s) this repo may help:** Phase 2 and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## Silero VAD

**URL:** https://github.com/snakers4/silero-vad.git  
**Commit inspected:** `867c2aa692646a1f1de3e94a15c9dd9f614c0acb`  
**License:** MIT (`LICENSE`, README license statement)

**Why cloned:** Locked lightweight speech activity detector and candidate for Pi streaming.

**Most relevant files/directories:**
- `README.md`, `pyproject.toml`
- `src/silero_vad/model.py`
- `src/silero_vad/utils_vad.py`
- `src/silero_vad/data/`
- `examples/pyaudio-streaming/`
- `examples/microphone_and_webRTC_integration/`
- `tests/test_basic.py`

**What InnoBrain can reuse/adapt:** Streaming state reset behavior, supported
8/16 kHz sampling, 256/512-sample windows, timestamp extraction, and low-level
microphone examples. Prefer the package/runtime interface once Phase 1 begins.

**What InnoBrain should NOT copy/adopt:** Untuned thresholds, arbitrary audio
I/O assumptions, or extra software suppression by default. The S330 already has
DSP; any additional processing must be benchmarked.

**Dependencies / hardware assumptions:** PyTorch/TorchAudio or ONNX Runtime;
audio decoding backend for file I/O; 8 kHz and 16 kHz model paths. The repository
tracks pretrained ONNX/JIT/SafeTensors files under `src/silero_vad/data`; asset
licensing must be confirmed separately from the MIT source license before any
redistribution.

**Phase(s) this repo may help:** Phase 1, Phase 2, Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## sqlite-vec

**URL:** https://github.com/asg017/sqlite-vec.git  
**Commit inspected:** `04d28bd21773981e2d266bbf6aa4efbd011eb4f6`  
**License:** REVIEW_REQUIRED — no root `LICENSE` or `COPYING` file was found.

**Why cloned:** Locked local vector-search extension for the SQLite RAG stack.

**Most relevant files/directories:**
- `README.md`
- `examples/simple-python/demo.py`
- `examples/simple-sqlite/demo.sql`
- `bindings/python/`
- `bindings/rust/`
- `tests/`
- `benchmarks/`

**What InnoBrain can reuse/adapt:** `vec0` virtual-table shape, float/int8/binary
vector concepts, KNN `match` plus distance ordering, and metadata/partition-key
filtering patterns behind an InnoBrain `VectorStore` boundary.

**What InnoBrain should NOT copy/adopt:** The bundled native extension or any
example database as an implicit production dependency. The README explicitly
warns that sqlite-vec is pre-v1 and may break; pin and isolate it only after
license review and ARM validation.

**Dependencies / hardware assumptions:** SQLite extension loading and a native
build or compatible binary; the README claims Raspberry Pi support. The repo has
no project-wide root license evidence; an example Node package declares ISC,
which does not establish the license for the repository as a whole.

**Phase(s) this repo may help:** Phase 3, Phase 4, Phase 6.

**Inspection verdict:** LICENSE REVIEW REQUIRED

## pywebrtc-audio

**URL:** https://github.com/strands-labs/pywebrtc-audio.git  
**Commit inspected:** `041c3a127121561c0bad37c9942e5e59e859babe`  
**License:** Apache-2.0 (`LICENSE`, `pyproject.toml`)

**Why cloned:** Optional reference for software AEC/NS/AGC if S330 measurements show a need.

**Most relevant files/directories:**
- `README.md`, `pyproject.toml`
- `src/pywebrtc_audio/_webrtc_audio.pyi`
- `examples/basic.py`, `examples/pyaudio_realtime.py`
- `tests/test_echo_canceller.py`, `tests/test_noise_suppressor.py`, `tests/test_streaming.py`
- `benchmarks/`
- `vendor/webrtc_audio/`

**What InnoBrain can reuse/adapt:** Near/far audio contract for AEC, 10 ms
frames at 16 kHz, optional NS/AGC/VAD, reset semantics, and benchmark structure.

**What InnoBrain should NOT copy/adopt:** Enabling AEC/NS/AGC blindly. Double
AEC or suppression can damage S330 audio; the master plan requires measurement
first. Do not import the vendored native tree directly into production.

**Dependencies / hardware assumptions:** NumPy and a C++/CMake build or wheel;
the package metadata lists aarch64 Linux wheels. Processor instances are not
thread-safe; supported rates are 16/32/48 kHz. Vendored WebRTC/RNNoise/PFFFT/
other notices require separate review.

**Phase(s) this repo may help:** Phase 1, Phase 2, Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## llama.cpp

**URL:** https://github.com/ggml-org/llama.cpp.git  
**Commit inspected:** `3466812d1f06728effe7c0f3c0671117f461672d`  
**License:** MIT (`LICENSE`, README acknowledgements)

**Why cloned:** Local fallback LLM runtime candidate for ARM/Raspberry Pi.

**Most relevant files/directories:**
- `README.md`, `docs/build.md`
- `tools/server/`, `tools/cli/`
- `ggml/`, `common/`, `src/`
- `examples/`
- `docs/development/token_generation_performance_tips.md`
- `licenses/`

**What InnoBrain can reuse/adapt:** ARM/NEON build guidance, GGUF/quantization
concepts, memory-conscious inference, and the OpenAI-compatible server boundary
for a later local fallback adapter.

**What InnoBrain should NOT copy/adopt:** Model download commands, a model choice,
or a local server during bootstrap. Do not build it or download models here.

**Dependencies / hardware assumptions:** C/C++, CMake, platform backends, and
external GGUF model files. The repository tracks vocabulary GGUF files but no
full candidate model was downloaded. Third-party components and notices under
`licenses/` remain relevant to later redistribution.

**Phase(s) this repo may help:** Phase 3 and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## Metro-ASR

**URL:** https://github.com/MohammedAly22/metro-asr.git  
**Commit inspected:** `683dd44f22c082db1039e85f254aa905fd33c246`  
**License:** MIT (`LICENSE`, README badge, `pyproject.toml`)

**Why cloned:** Local Egyptian-Arabic STT finalist/fallback candidate.

**Most relevant files/directories:**
- `README.md`, `pyproject.toml`, `docs/DEPLOYMENT.md`
- `metro_asr/engine.py`, `metro_asr/model/`, `metro_asr/data/`
- `scripts/inference.py`, `scripts/serve.py`
- `examples/streaming_server.ipynb`, `examples/quick_start.ipynb`
- `configs/`
- `test_samples/`

**What InnoBrain can reuse/adapt:** The CTC/non-autoregressive architecture
idea, detachable n-gram language head, 16 kHz waveform input, inference result
shape, and Egyptian/English code-switch evaluation concepts.

**What InnoBrain should NOT copy/adopt:** Published laptop CPU timings as Pi
evidence, large KenLM assets, or an unbenchmarked local STT default. The README
states that the comparison section has not yet been run against other systems.

**Dependencies / hardware assumptions:** Python >=3.9 and PyTorch for CPU
inference; optional pyctcdecode/KenLM for beam search; optional librosa for
compressed audio. The released model checkpoint is external to this clone and
the model/dataset licensing must be checked separately from repository code.

**Phase(s) this repo may help:** Phase 3 and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## VoiceTuT-TTS

**URL:** https://github.com/MohammedAly22/VoiceTuT-TTS.git  
**Commit inspected:** `b5302e9420cce535ced742c2c1c630a189c2f28f`  
**License:** Apache-2.0 (`LICENSE`, README, `pyproject.toml`)

**Why cloned:** Egyptian-Arabic TTS, code-switching, pronunciation, and normalization reference.

**Most relevant files/directories:**
- `README.md`, `pyproject.toml`
- `voicetut_tts/engine.py`
- `voicetut_tts/normalization.py`
- `voicetut_tts/data/diacritics.csv`, `voicetut_tts/data/names_en_ar.csv`
- `examples/`, `tests/test_normalization.py`
- `docs/audio/`, `reference_speakers/`

**What InnoBrain can reuse/adapt:** Egyptian number/date/time/currency
normalization, English-name transliteration, custom lexicon hooks, and the
streaming API that yields `(sampling_rate, waveform_chunk)` sentence by sentence.

**What InnoBrain should NOT copy/adopt:** Voice-cloning behavior, T4/GPU
performance as Pi evidence, or model assets during bootstrap. Keep consent and
disclosure requirements if this is ever evaluated.

**Dependencies / hardware assumptions:** PyTorch, OmniVoice from a separate Git
repository, Hugging Face model access, and a 24 kHz model path; the README's
performance data is measured on an NVIDIA T4. The fine-tuned checkpoint,
OmniVoice base, podcast data, reference voices, and sample audio have licensing
terms that must be reviewed separately from this repository's Apache code license.

**Phase(s) this repo may help:** Phase 3 and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## voice-agent-starter

**URL:** https://github.com/sarmakska/voice-agent-starter.git  
**Commit inspected:** `123073f8c99e682531fb29adb50e95ffaa3d2cab`  
**License:** MIT (`LICENSE`, README)

**Why cloned:** Clear full-duplex interaction and adapter/testing patterns.

**Most relevant files/directories:**
- `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`
- `apps/server/src/pipeline/orchestrator.ts`
- `apps/server/src/pipeline/vad.ts`, `tools.ts`
- `apps/server/src/adapters/stt/`, `llm/`, and `tts/`
- `apps/server/src/test/fixtures.ts`
- `apps/server/src/**/*.test.ts`

**What InnoBrain can reuse/adapt:** IDLE/LISTEN/THINK/SPEAK flow, abortable LLM
and TTS streams, barge-in reset, bounded tool-call rounds, registry-based
adapters, and fake-adapter integration tests.

**What InnoBrain should NOT copy/adopt:** TypeScript/Fastify/Next/browser
transport as the runtime foundation; its simple RMS VAD is not a substitute for
the locked Silero + Smart Turn design. Do not copy its default provider setup.

**Dependencies / hardware assumptions:** Node/TypeScript, pnpm, browser PCM
capture, WebSocket transport, and optional hosted/self-hosted provider servers.

**Phase(s) this repo may help:** Phase 2, Phase 3, and Phase 5.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## GLaDOS

**URL:** https://github.com/dnhkng/GLaDOS.git  
**Commit inspected:** `09f26d5bec0a0a5cb210c8077daceed507f5373c`  
**License:** MIT (`LICENSE.txt`)

**Why cloned:** Low-latency interruption, memory/context, and natural-assistant reference.

**Most relevant files/directories:**
- `README.md`
- `src/glados/api/`, `src/glados/TTS/`
- `src/glados/utils/spoken_text_converter.py`
- `src/glados/autonomy/events.py`, `src/glados/autonomy/agents/`
- `tests/test_websocket_audio.py`, `tests/test_conversation_store.py`, `tests/test_summarization.py`
- `docs/audio_websocket.md`, `configs/`

**What InnoBrain can reuse/adapt:** Pre-activation audio buffering, priority of
user speech over autonomy, response clipping after interruption, bounded context
compaction, shutdown ordering, and text normalization ideas.

**What InnoBrain should NOT copy/adopt:** GLaDOS personality/IP-specific behavior,
autonomous news/weather/MCP system, or desktop-oriented assumptions. Egyptian
persona and event behavior must come from the InnoBrain plan.

**Dependencies / hardware assumptions:** Multiple local/remote speech backends,
audio/TTS runtime, optional vision and MCP services, and model/runtime resources
not proven on the target Pi. MIT covers repository code, not external models,
datasets, or service dependencies.

**Phase(s) this repo may help:** Phase 2, Phase 3, and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## Pepper Realtime AI Assistant

**URL:** https://github.com/studerus/pepper-android-realtime-chat.git  
**Commit inspected:** `c83de7bedb111c9101940b7bc2979c417d0aeba1`  
**License:** MIT (`LICENSE`)

**Why cloned:** Physical-robot, semantic-tool, navigation, perception, lifecycle, and screen reference.

**Most relevant files/directories:**
- `README.md`, `app/build.gradle`
- `app/src/pepper/java/.../tools/navigation/`
- `app/src/standalone/java/.../robot/RobotSafetyGuard.kt`
- `app/src/standalone/java/.../service/PerceptionService.kt`
- `app/src/pepper/java/.../manager/NavigationServiceManager.kt`
- `app/src/main/assets/default_system_prompt.txt`
- dashboard/event manager classes and navigation tests

**What InnoBrain can reuse/adapt:** Semantic navigation/tool concepts, safety
guard boundary, lifecycle and perception event handling, screen/tablet event
patterns, and graceful robot-state handling.

**What InnoBrain should NOT copy/adopt:** Kotlin/Android/Pepper SDK layers, raw
movement tools, Pepper-specific prompts, or direct motor-control concepts. The
production boundary remains LLM -> semantic tool -> RobotGateway -> ROS.

**Dependencies / hardware assumptions:** Android Studio/Gradle, Pepper SDK,
Pepper robot services, tablet/standalone variants, and external API keys. These
are not Raspberry Pi Python runtime dependencies.

**Phase(s) this repo may help:** Phase 5.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## Compact RAG

**URL:** https://github.com/araobp/compact-rag.git  
**Commit inspected:** `993f0b3ab3bd884edfc4d346dc9b2050c6017b89`  
**License:** MIT (`LICENSE`)

**Why cloned:** Raspberry-Pi-oriented SQLite/sqlite-vec RAG and deployment reference.

**Most relevant files/directories:**
- `README.md`
- `cx/rag/`, `cx/rag/embeddings/`, `cx/rag/vector_db/`, `cx/rag/chat/`
- `db/`, `sqlite_vec/`
- `app/api.py`, `app/app.py`
- `unittest/cx/`, `unittest/api/`

**What InnoBrain can reuse/adapt:** Local DB/index separation, embedding and
document table concepts, sqlite-vec loading/query patterns, and small-device
service/deployment observations.

**What InnoBrain should NOT copy/adopt:** Prebuilt databases, bundled `vec0.so`,
sample audio/images, or external API/model choices as production architecture.
The package must use InnoBrain event/version scoping and provider adapters.

**Dependencies / hardware assumptions:** Python services, SQLite extension
loading, embedding/LLM/TTS integrations, and prebuilt sample DB/media in the
donor. Those databases, binaries, and media require separate provenance/license
review.

**Phase(s) this repo may help:** Phase 3, Phase 4, and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## Docling

**URL:** https://github.com/docling-project/docling.git  
**Commit inspected:** `33e3be26e530b37096939e7ddf300bfda6d36346`  
**License:** MIT (`LICENSE`, README, `pyproject.toml`)

**Why cloned:** Pre-event PDF/DOCX/PPTX/XLSX/HTML/Markdown ingestion candidate.

**Most relevant files/directories:**
- `README.md`, `pyproject.toml`
- `docling/document_converter.py`
- `docling/datamodel/`, `docling/backend/`, `docling/pipeline/`
- `docs/usage/supported_formats.md`
- `docs/usage/advanced_options.md`
- `docs/usage/api_server/`
- `tests/`

**What InnoBrain can reuse/adapt:** Offline conversion workflow, unified
`DoclingDocument`, structured table/layout extraction, export to Markdown/JSON/
text/JSONL chunks, format options, and resource controls such as thread limits.

**What InnoBrain should NOT copy/adopt:** Full Docling dependency stack on the
Pi or live ingestion during events. Ingestion should remain off-device where
possible, with a validated event DB/package deployed to the robot.

**Dependencies / hardware assumptions:** Python package with many optional
format/model dependencies, CPU/GPU accelerator settings, and a default thread
budget. The handoff explicitly prohibits installing the full stack during
bootstrap; model and third-party dependency licensing remains separate.

**Phase(s) this repo may help:** Phase 4 and Phase 6.

**Inspection verdict:** KEEP AS REFERENCE ONLY

## Potential Future Donors

The following were explicitly excluded by the bootstrap handoff and were not
cloned: QwenCleo-ASR, sherpa-onnx, FlagEmbedding, protoVoice, WhisperLive,
faster-whisper, whisper.cpp, DeepFilterNet, RNNoise, LiveKit Agents, TEN
Framework, and any newly discovered repository.

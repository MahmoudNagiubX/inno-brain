# InnoBrain — Master Architecture & Implementation Plan

> **Document role:** Single source of truth for the InnoBrain Event Robot AI/Voice subsystem
> **Version:** 1.9
> **Date:** 2026-09-01
> **Status:** Phase 1 complete; Phase 2 implementation complete with live validation deferred; Phase 3 authorized but not started
> **Current development platform:** Windows laptop (primary development and testing environment)
> **Current development audio:** Laptop microphone + laptop speakers/headphones
> **Target deployment hardware:** Raspberry Pi 5 — 8 GB RAM
> **Target production audio hardware:** Anker PowerConf S330 Speakerphone — Model A3308
> **Language target:** Egyptian Arabic FIRST. English is secondary. Arabic/English code-switching is supported only where it improves Egyptian usability.
> **Product target:** A low-latency, interruptible, context-aware Egyptian-Arabic event robot that feels conversational rather than like a voice FAQ kiosk.

---

# 0. Master Plan Rules

This file is the project's permanent reference.

Any major change to the following MUST update this file:

- Architecture.
- Provider/model selection.
- RAG strategy.
- Database schema.
- Audio pipeline.
- Memory model.
- Robot integration contract.
- Event package format.
- Performance targets.
- Repository structure.
- Deployment strategy.
- Major implementation dependency.

The coding agent should read this file before large implementation tasks.

Donor repositories are reference sources. Production code must not directly depend on random files inside cloned donor repositories unless that dependency is explicitly approved and documented here.


## 0.1 Mandatory Change-Control Rule

Until the coding agent takes ownership of documentation maintenance, ChatGPT is responsible for updating this Master Plan whenever an architecture, repository, provider, model, phase, data, audio, or implementation decision changes.

After the coding agent takes ownership, the same rule remains: **architecture-changing work is incomplete until this Master Plan is updated.**

## 0.2 Language Priority

The MVP priority is:

1. **Natural Egyptian Arabic conversation.**
2. Egyptian Arabic with natural English technical/proper nouns when Egyptians commonly use them.
3. English conversation is secondary and must not delay or complicate the Egyptian-Arabic MVP.

All STT, TTS, turn-taking, persona, RAG and evaluation choices should therefore optimize Egyptian Arabic first.


---

# 1. Product Goal

InnoBrain is the AI/voice brain of an event robot, with Egyptian Arabic as the primary conversational experience.

The required experience is:

1. Visitor approaches or starts speaking.
2. Robot hears speech reliably in a noisy event environment.
3. Robot understands Egyptian Arabic, English, and natural code-switching.
4. Robot knows when the visitor has actually finished the thought.
5. Robot retrieves current event/client knowledge.
6. Robot answers quickly and naturally.
7. Visitor can interrupt the robot while it is speaking.
8. Robot stops, understands the interruption, and continues with context.
9. Robot can display information or request safe robot actions.
10. Event knowledge can be replaced for another event without rewriting the AI application.

The system is NOT designed as:

- A generic chatbot attached to a robot.
- A PDF-only RAG demo.
- A command-based voice interface.
- A fully-local AI stack forced onto the Raspberry Pi regardless of latency.
- A cloud-only system that becomes useless when connectivity degrades.

---

# 2. Locked Architecture Decisions

The following decisions are accepted as the default architecture.

| Area | Decision | Status |
|---|---|---|
| Edge hardware | Raspberry Pi 5 8 GB | LOCKED |
| Main runtime | Python + Pipecat | LOCKED |
| Audio device | Anker PowerConf S330 | LOCKED |
| Conversation pipeline | Cascaded STT → LLM/RAG/Tools → TTS | LOCKED |
| Turn detection | Silero VAD + Smart Turn v3 | LOCKED |
| Interruptions | Full barge-in and cancellation | LOCKED |
| Main LLM | Fast API during testing; local model is fallback | LOCKED |
| Provider coupling | STT/LLM/TTS behind adapters | LOCKED |
| Main DB | SQLite | LOCKED |
| Keyword retrieval | SQLite FTS5 | LOCKED |
| Vector search | sqlite-vec | LOCKED |
| RAG | Core feature | LOCKED |
| Retrieval | Hybrid lexical + dense vector | LOCKED |
| Embeddings | Local multilingual embedding model initially | LOCKED |
| Session memory | Local short-term memory | LOCKED |
| Event configuration | Replaceable event package | LOCKED |
| Robot control | LLM → semantic tools → RobotGateway → ROS | LOCKED |
| Microservices | Avoid initially; one clean modular application | LOCKED |
| Kubernetes | Not used on robot | LOCKED |

Provider/model winners are intentionally NOT locked until benchmark results exist.

---

# 3. Final High-Level Architecture

```text
                           VISITOR
                              │
                              ▼
                    ANKER POWERCONF S330
                 4-mic 360° + speaker + DSP
                              │
                   hardware voice processing
                              │
                              ▼
                     Raspberry Pi 5
                              │
                  ┌───────────┴────────────┐
                  │     AUDIO RUNTIME      │
                  │ capture / playback     │
                  │ optional extra NS/AEC  │
                  └───────────┬────────────┘
                              │
                              ▼
                        Silero VAD
                              │
                              ▼
                      Smart Turn v3
                              │
                              ▼
                       Pipecat Runtime
                state / streaming / barge-in
                              │
                              ▼
                         STT Adapter
                    local OR remote provider
                              │
                              ▼
                  Conversation Orchestrator
                   context + session memory
                              │
                              ▼
                         Tool Router
                ┌─────────────┼──────────────┐
                │             │              │
                ▼             ▼              ▼
          Structured DB     Hybrid RAG     Robot/Screen
             SQLite         FTS5+Vector       Gateway
                │             │              │
                └─────────────┼──────────────┘
                              │
                              ▼
                           LLM
                              │
                              ▼
                         TTS Adapter
                              │
                              ▼
                    Anker S330 Speaker
```

---

# 4. Raspberry Pi Role

The Raspberry Pi is the REAL-TIME EDGE CONTROLLER.

It should own:

- USB audio I/O.
- Voice runtime.
- VAD.
- turn detection.
- interruption handling.
- conversation state.
- session memory.
- RAG query execution.
- SQLite event DB.
- vector index querying.
- local fallback LLM.
- screen events.
- RobotGateway.
- health checks.
- provider fallback logic.

It should NOT be forced to run every heavyweight AI model simultaneously.

Heavy ingestion, document parsing, mass embedding generation, large reranking and model training should normally happen before deployment on a laptop/server.

---


# 4.1 Development vs Deployment Mode

The project is currently developed and tested on the developer's Windows laptop.

Current development reality:

- The Raspberry Pi is not currently available to the primary developer.
- The Anker PowerConf S330 is not currently used by the primary developer.
- Day-to-day development, automated tests and interactive audio tests run on the laptop.
- The laptop's built-in/default microphone is the current development microphone.
- The laptop's normal output device is the current development speaker/output.
- Raspberry Pi deployment and production-hardware validation may be performed later by another team member.

This changes the validation workflow, but NOT the product architecture.

The codebase must remain hardware-agnostic:

```text
Core conversation/runtime logic
        │
        ▼
Audio I/O abstraction
        │
        ├── Laptop development backend
        └── Raspberry Pi / S330 deployment backend
```

Rules:

- Core STT/LLM/TTS/RAG/conversation code must not depend directly on Windows device IDs.
- Core code must not depend directly on Raspberry Pi ALSA card IDs.
- Audio device selection must be configuration-driven.
- Laptop testing is sufficient for current development phases unless a task is specifically marked as deployment validation.
- Raspberry Pi/S330-specific validation is deferred to the deployment/hardware-validation track.
- No development phase may be marked blocked merely because the Pi or S330 is unavailable.
- Production readiness still requires later validation on the real Raspberry Pi 5 + S330 before event deployment.


# 5. Audio Hardware — Anker PowerConf S330

## 5.1 Target production device

Model:

`Anker PowerConf S330 — A3308`

Official characteristics relevant to InnoBrain:

- 4-microphone array.
- 360-degree voice coverage.
- advertised pickup range up to 3 meters.
- 16 kHz microphone sample rate.
- voice enhancement.
- noise cancellation.
- automatic gain control / voice balancing.
- automatic echo cancellation.
- full-duplex communication.
- USB wired connection.
- built-in speaker.

Official sources:

- https://ca.ankerwork.com/products/a3308
- https://uk.ankerwork.com/products/a3308
- https://service.ankerwork.com/article-description/PowerConf-S330-A3308-FAQ

## 5.2 Important architecture consequence

The S330 already performs audio processing.

Therefore:

**Do not enable aggressive software AEC + NS by default.**

Initial path:

```text
S330 internal DSP
      ↓
USB PCM
      ↓
VAD / Smart Turn / STT
```

Only add software processing if measured problems remain.

Possible optional software chain:

```text
S330
 ↓
light additional filtering / WebRTC processing
 ↓
VAD
```

Double AEC or aggressive double noise suppression may damage speech quality and must be avoided unless benchmarked.

## 5.3 Speaker decision

For the first implementation, use the S330 as BOTH:

- microphone
- robot speech speaker

This gives the built-in full-duplex/echo-cancellation system the best chance to operate as intended.

If production later uses a separate louder robot speaker, the audio architecture MUST be re-tested because the S330's internal echo canceller may not have the correct reference for an external speaker.

## 5.4 Linux/Raspberry Pi validation

Anker advertises plug-and-play USB compatibility but does not explicitly certify Raspberry Pi OS in the documentation reviewed.

Therefore Phase 1 must validate:

```bash
arecord -l
aplay -l
arecord --dump-hw-params
```

Required tests:

- S330 detected as USB audio capture device.
- S330 detected as USB playback device.
- simultaneous record/playback works.
- 16 kHz capture works reliably.
- no USB underruns.
- no crackling.
- physical mute state behavior understood.
- sustained 2+ hour audio session.

## 5.5 Event placement target

Although the official maximum pickup figure is 3 m, our target operating distance should initially be:

- Ideal: 0.5–1.2 m.
- Acceptable: 1.2–2 m.
- Stress test: 2–3 m.

A robot should encourage natural standing distance rather than relying on the advertised maximum pickup radius.

---

# 6. Conversation Runtime

## 6.1 Framework

Foundation:

**Pipecat**

Reason:

- Python.
- voice-first.
- realtime streaming.
- modular STT/LLM/TTS services.
- clean frame pipeline.
- interruption handling.
- metrics/evaluation ecosystem.
- provider-neutral architecture.

Repository:

https://github.com/pipecat-ai/pipecat

Pipecat is used as a runtime framework, not as the domain architecture of the whole product.

InnoBrain business logic remains inside `src/innobrain`.

---

# 7. Conversation State Machine

Keep this intentionally simple:

```text
IDLE
  │
  ▼
LISTENING
  │
  ▼
THINKING
  │
  ▼
SPEAKING
  │
  ├──────── user interrupts ────────┐
  ▼                                 │
INTERRUPTED ─────────────────────► LISTENING
```

Other conditions such as network state, navigation state and screen state are properties, not conversation states.

---

# 8. VAD and Turn Completion

## 8.1 VAD

Use:

**Silero VAD**

Responsibility:

- detect real speech activity.
- wake conversation processing.
- detect candidate silence.
- assist interruption detection.

VAD does NOT decide whether a thought is semantically complete.

## 8.2 Semantic turn completion

Use:

**Pipecat Smart Turn v3**

Reasons:

- audio-native.
- Arabic supported.
- approximately 8M parameters.
- CPU INT8 model available.
- intended to work with lightweight VAD.
- designed to distinguish pauses from completed conversational turns.

Repository:

https://github.com/pipecat-ai/smart-turn

Recommended flow:

```text
speech
 ↓
Silero detects silence
 ↓
Smart Turn checks completion
 ├── incomplete → keep listening
 └── complete   → finalize user turn
```

---

# 9. Barge-In / Interruption Contract

Interruption is a core feature, not an enhancement.

When the robot is speaking and genuine user speech is detected:

1. Confirm incoming speech is likely the user, not residual robot audio.
2. Stop speaker playback immediately.
3. Cancel remaining TTS stream.
4. Cancel stale LLM generation when safe.
5. Cancel stale tool calls when safe.
6. Mark the assistant response as interrupted.
7. Record how much of the response was actually played.
8. Begin a new user turn.
9. Preserve useful context from the conversation.
10. Never assume the visitor heard unplayed text.

Engineering target:

`user interruption → robot audio stop <= 250 ms`

Stretch target:

`<= 150–200 ms`

---

# 10. Speech-to-Text Strategy

STT is an adapter.

Interface concept:

```python
class STTProvider:
    async def start(self): ...
    async def stream_audio(self, pcm): ...
    async def partial_text(self): ...
    async def final_text(self): ...
    async def stop(self): ...
```

## 10.1 Candidate priority

### Candidate A — Deepgram Nova-3

Why test:

- strong realtime focus.
- multilingual model.
- advertised suitability for background noise/crosstalk/far-field audio.
- keyterm prompting available.
- current new-account offer: $200 free credit, no card required.

Useful for event vocabulary such as:

- company names.
- speaker names.
- booth names.
- product names.
- acronyms.

Pricing reference:

https://deepgram.com/pricing

### Candidate B — Speechmatics

Why test:

- strong multilingual/code-switch positioning.
- realtime WebSocket.
- $100 starting credit.
- no card required for initial testing.

Pricing reference:

https://www.speechmatics.com/pricing

### Candidate C — Azure Speech

Why test:

- explicit Arabic Egypt support.
- mature production speech stack.
- F0 includes 5 audio hours/month for realtime STT.

Pricing:

https://azure.microsoft.com/en-us/pricing/details/speech/

### Candidate D — Gemini realtime transcription

Why test:

- strong multilingual ecosystem.
- free development tier on eligible models.
- useful as both transcription and native-audio comparison path.

### Local fallback — Metro-ASR Small

Repository:

https://github.com/MohammedAly22/metro-asr

Current released checkpoint:

- 61.6M parameters.
- Egyptian-Arabic-focused.
- Arabic/English-balanced tokenizer.
- CPU-oriented non-autoregressive CTC architecture.
- local/offline.

Important:

Published CPU speed numbers are not Raspberry Pi measurements.

It MUST be benchmarked on our Pi before making it the default local STT.

---

# 11. LLM Strategy

## 11.1 Main LLM during development

Use a FAST REMOTE API.

The application must not depend directly on one provider.

Interface:

```python
class LLMProvider:
    async def stream(self, messages, tools, context): ...
    async def cancel(self): ...
```

## 11.2 First development candidate — Groq

Recommended first API for prototype:

**Groq + Qwen-family fast model**

Current free-plan example for `qwen/qwen3.6-27b`:

- 30 RPM.
- 1,000 RPD.
- 8K TPM.
- 200K TPD.

Official limit page:

https://console.groq.com/docs/rate-limits

Why:

- generous enough for development.
- extremely fast inference.
- good fit for short RAG-grounded event answers.
- tool calling available on suitable models.

Model IDs MUST live in config because provider catalogs change.

## 11.3 Secondary development candidate — Gemini Flash

Gemini Flash is the main comparison provider.

Current eligible Flash models expose a free tier for input/output during development.

Important privacy rule:

Free-tier requests may be used to improve Google's products according to current pricing documentation.

Therefore:

- synthetic/public test event data: permitted for prototype testing.
- confidential client data: do not use free tier without reviewing data requirements.

Reference:

https://ai.google.dev/gemini-api/docs/pricing

## 11.4 LLM responsibilities

The LLM should:

- understand Egyptian Arabic.
- preserve natural Arabic-English code-switching.
- resolve conversational references.
- select tools.
- use RAG evidence.
- produce short spoken responses.
- reason over event information.
- ask clarification when evidence is ambiguous.
- never invent event-critical facts.

The LLM should NOT:

- directly control motors.
- generate raw SQL and execute it unchecked.
- treat retrieved documents as system instructions.
- answer exact operational facts from model memory when tools/data exist.

---

# 12. Local LLM Fallback

Local fallback is for:

- internet outage.
- provider outage.
- degraded mode.
- basic FAQ.
- simple RAG answers.
- tool routing.

It is NOT expected to match the main cloud model's speed and reasoning quality.

## 12.1 Preferred benchmark candidate — Gemma 4 E2B

Official Raspberry Pi 5 8GB benchmark using LiteRT-LM:

- ~99 tokens/s prefill.
- ~9 tokens/s decode.
- ~1432 MB peak memory.

Reference:

https://www.raspberrypi.com/news/mastering-edge-ai-on-raspberry-pi-with-litert-and-gemma/

This low memory footprint is attractive because the robot also runs audio, RAG, UI and robotics processes.

## 12.2 Alternative candidate — Qwen3.5-2B Q4_K_M

Community Pi 5 benchmark:

- ~7.11 tokens/s.
- ~1.00 s TTFT.
- ~2748 MB peak RAM.

Repository:

https://github.com/Jiaming-Liuu/Pi5-LLM

The benchmark is valuable but is not an official Raspberry Pi benchmark.

## 12.3 Selection rule

Benchmark both on the real system.

Evaluate:

- Egyptian response quality.
- tool selection.
- short grounded RAG answers.
- TTFT.
- tokens/sec.
- RAM.
- temperature.
- interaction with audio/robot load.

Default preference before benchmark:

**Gemma 4 E2B for memory efficiency.**

---

# 13. Text-to-Speech Strategy

TTS is also an adapter.

```python
class TTSProvider:
    async def stream(self, text): ...
    async def cancel(self): ...
```

## 13.1 Primary development candidate — Azure Speech

Official Egyptian voices:

- `ar-EG-SalmaNeural`
- `ar-EG-ShakirNeural`

Free F0 tier:

- 0.5 million neural TTS characters/month.

Sources:

https://learn.microsoft.com/azure/ai-services/speech-service/language-support
https://azure.microsoft.com/en-us/pricing/details/speech/

Why this is the initial baseline:

- explicit Egypt locale.
- useful recurring free allowance.
- simple deployment.
- stable API.

## 13.2 Benchmark alternatives

Test against:

- Gemini Native Audio.
- ElevenLabs.
- VoiceTut-TTS on suitable off-board GPU hardware if available.

Do not assume generic Arabic support sounds Egyptian.

Final selection requires native Egyptian listening tests.

---

# 14. Egyptian Arabic Persona

The robot should sound Egyptian, not stereotyped and not unnecessarily formal.

Rules:

- Egyptian colloquial syntax.
- concise spoken sentences.
- natural use of common English technical terms.
- no forced translation of words Egyptians normally keep in English.
- no excessive slang.
- avoid repetitive "يا باشا" style stereotypes.
- polite, professional event tone.
- preserve proper nouns.
- confirm ambiguous names or times.
- answers default to 1–3 spoken sentences unless more detail is requested.

Example:

Good:

> "الـworkshop هتبدأ الساعة 4:30 في Hall A. تحب أوريهالك على الشاشة؟"

Avoid:

> "سوف تبدأ ورشة العمل في تمام الساعة الرابعة والنصف..."

unless formal Arabic is explicitly requested.

---

# 15. Memory Design

Keep memory lightweight and explicit.

## 15.1 Active session memory

Store:

- last 8–12 turns.
- running summary.
- current speaker.
- current session.
- current booth.
- current location.
- current product.
- active navigation destination.
- user's current language style.
- assistant playback boundary for interrupted responses.

## 15.2 Reference resolution example

```text
User: "Ahmed بيتكلم فين؟"
Robot: "في Main Stage."
User: "طب الساعة كام؟"
```

Memory resolves:

`"الساعة كام؟" → Ahmed's referenced session`

## 15.3 Visitor isolation

By default:

**Do not remember a visitor after the session ends.**

Reset visitor-specific context before the next person.

Persistent visitor identity/personalization is outside V1.

---

# 16. Knowledge Architecture

RAG is a CORE part of InnoBrain.

The knowledge layer has two complementary systems.

## A. Structured Event Truth

Use SQLite for exact values:

- schedules.
- times.
- speakers.
- booths.
- rooms.
- locations.
- waypoints.
- prices.
- product IDs.
- current status.
- approved actions.

## B. Flexible Knowledge / RAG

Use RAG for:

- client profile.
- product descriptions.
- company information.
- FAQs.
- policies.
- sponsor information.
- brochures.
- long event documents.
- marketing material.
- unstructured knowledge.

Never force exact schedule truth through semantic similarity when a structured row exists.

---

# 17. Database Stack

Initial stack:

```text
SQLite
├── relational tables
├── FTS5
└── sqlite-vec
```

## 17.1 Why SQLite

- low operational complexity.
- perfect for one robot/event package.
- local/offline.
- easy backup.
- easy event replacement.
- lightweight on Pi.
- no database server process.

## 17.2 sqlite-vec

Repository:

https://github.com/asg017/sqlite-vec

Features:

- vector search inside SQLite.
- pure C.
- no external service.
- works on Raspberry Pi.
- supports float/int8/binary vectors.

Important:

`sqlite-vec` is currently pre-v1.

Therefore:

- pin exact version.
- wrap it behind `VectorStore`.
- do not spread sqlite-vec-specific SQL throughout the code.

---

# 18. RAG Retrieval Architecture

The retrieval path is HYBRID.

```text
User query
   │
   ├── raw text
   ├── normalized Egyptian Arabic
   └── optional English retrieval representation
            │
            ▼
      metadata filtering
            │
       ┌────┴─────┐
       ▼          ▼
   FTS5/BM25   Dense vector
       │          │
       └────┬─────┘
            ▼
       rank fusion
            │
            ▼
      top candidates
            │
     optional reranker
            │
            ▼
      evidence package
            │
            ▼
            LLM
```

## 18.1 Mandatory metadata

Every chunk should include:

- `event_id`
- `event_version`
- `client_id`
- `document_id`
- `source_type`
- `language`
- `authority_level`
- `valid_from`
- `valid_until`
- `chunk_id`

This prevents data from old events or clients leaking into the active event.

---

# 19. Embeddings

## 19.1 Initial local embedding model

Recommended starting model:

**multilingual-e5-small**

Reasons:

- multilingual.
- Arabic support through multilingual training.
- approximately 118M parameters.
- 384-dimensional vectors.
- 512-token maximum input.
- MIT.
- ONNX INT8 variant around 113 MB.

Reference:

https://huggingface.co/intfloat/multilingual-e5-small

## 19.2 Important resource strategy

Do NOT embed all documents on the robot during an event.

Preferred workflow:

```text
Laptop / prep machine
   ↓
parse documents
   ↓
chunk
   ↓
generate embeddings
   ↓
build event DB/index
   ↓
deploy finished event package to Pi
```

During live operation the Pi only embeds incoming queries.

This preserves CPU/RAM for realtime conversation.

---

# 20. Reranking

Do not run a heavy reranker for every query.

Initial V1:

```text
Hybrid retrieval
→ Rank fusion
→ Top K evidence
```

Add a reranker only when:

- retrieval confidence is low.
- many similar chunks exist.
- documents are long or ambiguous.
- benchmark shows measurable benefit.

A remote or off-board reranker can be used later without changing the RAG interface.

---

# 21. Event Package

Every event is a replaceable package.

Conceptual layout:

```text
events/
└── <event_id>/
    ├── manifest.yaml
    ├── event.db
    ├── assets/
    │   ├── images/
    │   ├── maps/
    │   └── qr/
    └── source/
        └── optional source metadata
```

Example manifest:

```yaml
event:
  id: evt_001
  version: 1.0.0
  client: example_client
  language:
    - ar-EG
    - en

persona:
  style: friendly-professional
  verbosity: short

features:
  navigation: true
  screen: true
  rag: true

fallback:
  help_location: registration
```

Changing event data should not require changing Python source code.

---

# 22. Event Ingestion

Document ingestion happens OFFLINE/PRE-EVENT where possible.

Candidate parser:

**Docling**

Repository:

https://github.com/docling-project/docling

Use for:

- PDF.
- DOCX.
- PPTX.
- XLSX.
- HTML.
- Markdown.

However:

Structured event files should become structured records when possible.

Example:

`agenda.xlsx` should populate `sessions`, `speakers`, `locations`.

It should not exist only as RAG chunks.

---

# 23. Suggested SQLite Tables

Minimum conceptual schema:

```text
events
event_versions
speakers
sessions
locations
booths
products
faqs
documents
chunks
media
navigation_waypoints
conversation_sessions
```

Example session fields:

```text
id
event_version_id
title
description
speaker_id
start_time
end_time
location_id
status
```

Example chunk fields:

```text
id
document_id
event_version_id
text
language
source_type
authority_level
valid_from
valid_until
```

Vector embeddings live through sqlite-vec using the chunk ID.

---

# 24. Tool Router

LLM tools are semantic and allowlisted.

Examples:

```text
get_event_schedule(...)
get_speaker(...)
get_session(...)
find_location(...)
get_booth(...)
get_product(...)
search_event_knowledge(...)
show_screen_card(...)
show_route(...)
navigate_to(...)
cancel_navigation(...)
get_navigation_status(...)
request_human_help(...)
```

The model must not directly execute:

- shell commands.
- arbitrary SQL.
- ROS velocity messages.
- arbitrary network requests.

---

# 25. Robot Gateway

Boundary:

```text
Conversation Brain
       ↓
 semantic tool
       ↓
 RobotGateway
       ↓
 ROS2 / robot navigation system
```

Example:

```json
{
  "action": "navigate_to",
  "location_id": "hall_b"
}
```

RobotGateway validates:

- destination exists.
- destination is allowed for the event.
- navigation is enabled.
- robot is in a safe state.
- semantic destination maps to an approved waypoint.

ROS/navigation remains responsible for:

- localization.
- path planning.
- obstacle avoidance.
- collision safety.
- emergency stop.
- motor commands.

---

# 26. Screen Gateway

The LLM sends semantic screen events.

Example:

```json
{
  "type": "speaker_card",
  "speaker_id": "spk_01"
}
```

Frontend decides how it looks.

Reusable screen events:

- welcome.
- schedule.
- speaker.
- booth.
- product.
- map.
- route.
- QR.
- promotion.
- navigation state.
- offline/help state.

Never let the LLM generate arbitrary production HTML for the robot display.

---

# 27. Provider Configuration

Providers are selected from configuration.

Example:

```yaml
stt:
  primary: deepgram
  fallback: metro_local

llm:
  primary: groq
  secondary: gemini
  local_fallback: gemma4_e2b

tts:
  primary: azure
  voice: ar-EG-ShakirNeural

embedding:
  primary: multilingual-e5-small
```

Changing provider should not require changing conversation logic.

---

# 28. Free-Tier Development Strategy

Current options to exploit during prototype development:

## LLM

### Groq

Useful free limits for development on selected models.

Current documented example for Qwen3.6-27B:

- 30 RPM
- 1K RPD
- 8K TPM
- 200K TPD

Reference:

https://console.groq.com/docs/rate-limits

### Gemini

Eligible Flash models offer free input/output usage within free-tier quota.

Reference:

https://ai.google.dev/gemini-api/docs/pricing

Privacy note:

free-tier data may be used to improve Google products.

## STT

### Deepgram

Current offer:

- $200 free credit.
- no credit card required.

Reference:

https://deepgram.com/pricing

### Speechmatics

Current offer:

- $100 free starting credit.
- no card required.

Reference:

https://www.speechmatics.com/pricing

### Azure

F0:

- 5 realtime STT hours/month.

Reference:

https://azure.microsoft.com/en-us/pricing/details/speech/

## TTS

### Azure

F0:

- 0.5M neural characters/month.

Explicit Egyptian voices exist.

This is the preferred starting TTS benchmark.

---

# 29. Raspberry Pi Resource Policy

The Pi is shared with robot software.

Never benchmark AI components in isolation only.

Always profile under representative load.

Target resource policy:

```text
OS + robot services                   ~1.5–2 GB
Audio/runtime/VAD/turn detection      <0.5 GB target
SQLite/RAG/cache                      ~0.3–0.7 GB target
Local fallback LLM                    ~1.4–3 GB
Safety headroom                       >=1.5 GB
```

These are engineering budgets, not guaranteed measurements.

Rules:

- avoid swap during conversation.
- use active cooling.
- use 64-bit OS.
- prefer NVMe/fast storage for models and event packages if possible.
- monitor temperature.
- monitor memory.
- benchmark while ROS/UI/audio are active.

---

# 30. Production Repository Structure

```text
inno-brain/
│
├── MASTER_PLAN.md
├── README.md
│
├── src/
│   └── innobrain/
│       │
│       ├── audio/
│       │   ├── capture.py
│       │   ├── playback.py
│       │   ├── processing.py
│       │   ├── vad.py
│       │   └── turn_detector.py
│       │
│       ├── voice/
│       │   ├── runtime.py
│       │   ├── state.py
│       │   └── interruption.py
│       │
│       ├── providers/
│       │   ├── stt/
│       │   ├── llm/
│       │   ├── tts/
│       │   └── embeddings/
│       │
│       ├── conversation/
│       │   ├── orchestrator.py
│       │   ├── memory.py
│       │   ├── context.py
│       │   └── persona.py
│       │
│       ├── knowledge/
│       │   ├── ingestion.py
│       │   ├── chunking.py
│       │   ├── normalize.py
│       │   ├── lexical_search.py
│       │   ├── vector_search.py
│       │   ├── hybrid_retriever.py
│       │   ├── reranker.py
│       │   └── evidence.py
│       │
│       ├── event/
│       │   ├── database.py
│       │   ├── schema.py
│       │   ├── package.py
│       │   └── tools.py
│       │
│       ├── robot/
│       │   ├── gateway.py
│       │   └── screen.py
│       │
│       ├── telemetry/
│       │   ├── metrics.py
│       │   └── logging.py
│       │
│       ├── config.py
│       └── main.py
│
├── config/
│   ├── runtime.yaml
│   ├── providers.yaml
│   └── persona.yaml
│
├── events/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── evals/
│   ├── audio/
│   ├── stt/
│   ├── rag/
│   ├── tts/
│   ├── conversation/
│   └── latency/
│
├── scripts/
│   ├── build_event.py
│   ├── benchmark_audio.py
│   ├── benchmark_stt.py
│   ├── benchmark_rag.py
│   └── benchmark_llm.py
│
└── _research/
    ├── sources.yaml
    └── repos/
```

---

# 31. Donor Repository Policy

## 31.1 Workspace Layout

Use one workspace with the production repository separated from cloned research repositories:

```text
InnoBrainWorkspace/
│
├── inno-brain/             # OUR production GitHub repository
│   ├── MASTER_PLAN.md
│   ├── src/
│   ├── tests/
│   ├── evals/
│   └── ...
│
└── donor-repos/            # cloned external repositories for study/reuse
    ├── pipecat/
    ├── smart-turn/
    ├── silero-vad/
    └── ...
```

**Critical rule:** production code must not import code using relative paths from `donor-repos/`.

The coding agent may inspect, adapt or reuse permitted code from donor repositories, but the resulting implementation belongs inside `inno-brain/` with license obligations preserved.

## 31.2 V1 Clone Set — Frozen

The V1 workspace should clone the following repositories.

### Core / Foundation

1. `pipecat-ai/pipecat`
   - Role: realtime voice runtime, frames, streaming and provider patterns.
   - https://github.com/pipecat-ai/pipecat

2. `pipecat-ai/smart-turn`
   - Role: semantic end-of-turn detection.
   - https://github.com/pipecat-ai/smart-turn

3. `snakers4/silero-vad`
   - Role: lightweight speech activity detection.
   - https://github.com/snakers4/silero-vad

4. `asg017/sqlite-vec`
   - Role: local vector search inside SQLite.
   - https://github.com/asg017/sqlite-vec

5. `strands-labs/pywebrtc-audio`
   - Role: optional software AEC / NS / AGC reference and implementation candidate.
   - https://github.com/strands-labs/pywebrtc-audio

6. `ggml-org/llama.cpp`
   - Role: local fallback LLM runtime on ARM/Raspberry Pi.
   - https://github.com/ggml-org/llama.cpp

### Egyptian Speech Candidates

7. `MohammedAly22/metro-asr`
   - Role: lightweight local Egyptian-Arabic STT finalist.
   - https://github.com/MohammedAly22/metro-asr

8. `MohammedAly22/VoiceTuT-TTS`
   - Role: Egyptian-Arabic TTS and Egyptian text-normalization donor/candidate.
   - https://github.com/MohammedAly22/VoiceTuT-TTS

### Architecture / Interaction Donors

9. `sarmakska/voice-agent-starter`
   - Role: clean adapters, state-machine ideas, barge-in cancellation and tests.
   - https://github.com/sarmakska/voice-agent-starter

10. `dnhkng/GLaDOS`
    - Role: low-latency voice interaction, interruption, memory and natural-assistant design reference.
    - https://github.com/dnhkng/GLaDOS

11. `studerus/pepper-android-realtime-chat`
    - Role: physical-robot interaction, perception events, function calling, navigation and HRI lifecycle.
    - https://github.com/studerus/pepper-android-realtime-chat

### RAG / Event Knowledge Donors

12. `araobp/compact-rag`
    - Role: Raspberry-Pi-oriented hybrid RAG using SQLite + sqlite-vec.
    - https://github.com/araobp/compact-rag

13. `docling-project/docling`
    - Role: pre-event document parsing and structured ingestion.
    - https://github.com/docling-project/docling

## 31.3 Repositories NOT Cloned in V1

These are useful research references but are not needed in the initial workspace:

- `MohammedAly22/qwencleo-asr`
  - Keep as an off-board GPU STT reference. Do not clone unless we actually have a GPU deployment path to test.

- `k2-fsa/sherpa-onnx`
  - Strong ARM speech toolkit, but overlaps current V1 needs. Add only if the selected local speech model needs it.

- `FlagOpen/FlagEmbedding`
  - Do not clone just to use an embedding model. Model weights can be pulled directly from Hugging Face when required.

- `protoLabsAI/protoVoice`
  - Useful, but overlaps Pipecat + voice-agent-starter + GLaDOS for our current V1 learning needs.

- Pi-specific benchmark repositories
  - Use published results for pre-selection. Clone only if needed to reproduce a disputed benchmark.

## 31.4 Benchmark Policy

We do **not** clone five model repositories just to benchmark everything.

Use this process:

```text
Published benchmarks / papers / existing Pi results
                  ↓
            pre-filter models
                  ↓
           choose 1–2 finalists
                  ↓
       benchmark finalists on OUR Pi
                  ↓
              choose winner
```

A local benchmark is mandatory only when hardware-specific uncertainty can materially change the decision.

Examples:

- STT: benchmark the best local Egyptian candidate against the best free-tier API.
- Local LLM: benchmark only the top 1–2 small models that fit the Pi memory budget.
- TTS: prefer native-Egyptian API listening tests first; local heavyweight TTS is tested only if there is a credible Pi/off-board deployment path.
- Smart Turn: test on our Egyptian pauses/hesitations because generic Arabic support does not guarantee perfect Egyptian conversational behavior.

## 31.5 Donor Inventory Metadata

Record every cloned donor in `donor-repos/REPOS.md` or a workspace-level manifest with:

```yaml
repo_name:
  url:
  commit:
  license:
  category:
  why_cloned:
  useful_paths:
  production_dependency:
```

This keeps the coding agent from repeatedly re-discovering why a repository exists.

---


# 31.6 Pre-Phase-1 Bootstrap Handoff

Before Phase 1 begins, Codex should perform a one-time workspace bootstrap.

The bootstrap has a strict boundary:

**It prepares the workspace and research material. It does NOT implement the voice pipeline, RAG runtime, STT, TTS, LLM adapters, or robot integration yet.**

Required bootstrap outputs:

1. Create local workspace `InnoBrainWorkspace/`.
2. Create production repository folder `InnoBrainWorkspace/inno-brain/`.
3. Create or connect GitHub repository `inno-brain`.
4. Copy this Master Plan into the production repository as `MASTER_PLAN.md`.
5. Clone the frozen V1 donor repository set into sibling folder `InnoBrainWorkspace/donor-repos/`.
6. Record each donor's exact URL, branch, HEAD commit SHA, license, role and useful paths.
7. Inspect the donor repositories and produce a concise implementation-reuse report.
8. Scaffold the production repository structure without implementing Phase 1 features.
9. Verify donor repositories remain clean and production code has no cross-imports from donor repositories.
10. Commit and push the bootstrap state if GitHub authentication is available.
11. Stop and report readiness for Phase 1.

Bootstrap repository visibility default:

- Prefer a **private** GitHub repository unless the user explicitly requests public visibility.
- Never overwrite or delete an existing remote repository automatically.

The detailed execution handoff is maintained separately in:

`CODEX_PRE_PHASE1_BOOTSTRAP.md`



# 31.7 Bootstrap Execution Status

**Status:** `READY_FOR_PHASE_1`

The pre-Phase-1 bootstrap was executed by Codex and reported complete.

Reported execution details:

- Workspace: `C:\Users\mahmo\Desktop\InnoBrainWorkspace`
- Production repository: `C:\Users\mahmo\Desktop\InnoBrainWorkspace\inno-brain`
- GitHub repository: `https://github.com/MahmoudNagiubX/inno-brain`
- GitHub visibility: Private
- Donor repositories cloned: `13/13`
- Donor inspection report: `docs/research/DONOR_INSPECTION.md`
- Bootstrap report: `docs/bootstrap/BOOTSTRAP_REPORT.md`
- Verification reported by Codex:
  - clean Git state.
  - exact document hashes checked.
  - no secrets detected.
  - no production imports from donor repositories.
  - no Phase 1 implementation started.

License note reported during bootstrap:

- `sqlite-vec` had no root license file in the inspected checkout.
- model, dataset, vendored-code and sample-media licensing concerns are documented separately in the donor inspection materials.
- Any donor marked for license review must not be copied into production code until the relevant license is explicitly confirmed.

**Evidence note:** The status above is recorded from the Codex execution report supplied by the user. It has not been independently re-run or re-verified inside this chat environment.

**Next authorized milestone:** Phase 1 — Foundation + Hardware Validation.


# 32. Six Implementation Phases

The project should remain six major phases.

## PHASE 1 — Foundation + Hardware Validation

Deliver:

- clean repository.
- Master Plan.
- donor repos cloned.
- Pi environment setup.
- S330 detected and tested.
- config system.
- provider interfaces.
- logging baseline.
- initial eval dataset.

Exit criteria:

- Pi captures and plays audio reliably.
- S330 simultaneous record/playback validated.
- repository structure stable.


# 32.1 Phase 1 Execution Contract — Foundation + Laptop Audio Validation

**Execution status:** `PHASE_1_COMPLETE`

Phase 1 is deliberately focused on creating a complete software foundation and validating audio I/O on the current development laptop.

The Raspberry Pi 5 and Anker PowerConf S330 remain the target deployment hardware, but they are NOT required to complete Phase 1.

## Phase 1 locked execution decisions

- Development environment: Windows laptop.
- Development microphone: laptop/default microphone.
- Development output: laptop/default speakers or headphones.
- Work on branch: `phase/1-foundation-laptop-audio`.
- Do not merge the branch automatically.
- Production Python compatibility range: `>=3.11,<3.15`.
- The current Windows development host may use its existing Python 3.14.6.
- Use a project virtual environment; never install project packages globally.
- Phase 1 production dependencies stay small and explicit.
- Phase 1 may add a lightweight cross-platform audio library for laptop device enumeration/capture/playback testing.
- Do **not** install Pipecat, Silero VAD, Smart Turn, STT/TTS/LLM provider SDKs, model runtimes, sqlite-vec or model weights in Phase 1.
- Do **not** use API keys or free-tier API quota in Phase 1.
- Do **not** implement RAG runtime, STT, LLM, TTS or ROS integration yet.
- Build configuration validation, provider contracts, logging, audio-device abstraction, laptop audio probe/capture/playback test tools, and Egyptian-Arabic audio evaluation fixtures.
- Laptop audio device selection must be configuration-driven and must not hard-code a Windows device index.
- Raspberry Pi and S330-specific code must stay behind interfaces/adapters and must not leak into core conversation logic.
- Raspberry Pi/S330 hardware validation is deferred and must not block development.
- Donor repositories stay unchanged and outside the production repository.
- Existing donor inspection reports are the default research reference; do not rescan every donor repo.

## Phase 1 software outputs

The production repository must gain:

```text
pyproject.toml
src/innobrain/config/
src/innobrain/providers/
src/innobrain/telemetry/
src/innobrain/audio/
config/runtime.yaml
config/providers.yaml
config/persona.yaml
evals/audio/phase1_egyptian_phrases.yaml
evals/audio/README.md
scripts/phase1/list_audio_devices.py
scripts/phase1/record_laptop_sample.py
scripts/phase1/play_laptop_sample.py
scripts/phase1/analyze_wav.py
docs/phase1/PHASE1_STATE.md
docs/phase1/PHASE1_REPORT.md
tests/unit/...
```

## Phase 1 laptop audio outputs

Laptop validation must report:

- Windows version.
- Python version.
- available capture devices.
- available playback devices.
- selected/default input device.
- selected/default output device.
- sample rate used.
- one-channel voice capture works.
- playback works.
- repeated short capture/playback works without exceptions.
- Egyptian-Arabic 0.5–1 m natural speech sample is created using the laptop microphone.
- manual listening confirms the development audio path is usable.

## Phase 1 manual acoustic gate

The user must confirm:

1. Laptop-mic recording is clear enough for development.
2. Playback works on the laptop output device.
3. Egyptian speech is intelligible.
4. No severe clipping or corrupted audio is present.

This gate validates the development audio path only.

It does NOT certify Raspberry Pi/S330 production acoustics.

## Deferred deployment validation

Before production/event deployment, a separate deployment validation must test:

- Raspberry Pi 5 8 GB.
- Anker PowerConf S330.
- USB/ALSA enumeration.
- S330 hardware DSP behavior.
- full duplex.
- echo cancellation.
- noise handling.
- distance tests.
- long-duration soak.
- power/thermal stability.

That deployment validation may be performed by another team member.

## Phase 1 allowed final states

Exactly one:

- `PHASE_1_COMPLETE`
- `PHASE_1_WAITING_FOR_AUDIO_CONFIRMATION`
- `PHASE_1_BLOCKED`

No `WAITING_FOR_PI` state exists for current development.

The lack of Raspberry Pi access is NOT a Phase 1 blocker.

Only `PHASE_1_COMPLETE` authorizes Phase 2.

## Phase 1 completion action

On successful completion, the coding agent must:

- update the Phase 1 status and measured laptop-development facts in `MASTER_PLAN.md`;
- bump the Master Plan patch version;
- update `README.md`;
- write `docs/phase1/PHASE1_REPORT.md`;
- run fresh full verification;
- commit and push `phase/1-foundation-laptop-audio`;
- stop without starting Phase 2.



## Phase 1 measured result snapshot

Phase 1 was completed on the Windows laptop and pushed to:

```text
branch: phase/1-foundation-laptop-audio
branch HEAD: 03b46778133ccb5cd8308d8cff739448470c2f1d
implementation finalization commit: aeba88fb956fd017f1c2b57d9c35e49af98919d3
```

Measured/verified development facts:

- OS: Microsoft Windows 11 Home Single Language, version 10.0.26200, build 26200.
- Python: 3.14.6.
- Config: `ar-EG laptop`.
- Input: OS default index 1 — `Microphone Array (Realtek(R) Au`.
- Output: OS default index 3 — `Speakers (Realtek(R) Audio)`.
- Development audio format: 16 kHz, mono.
- Recording: PASS.
- Playback: PASS.
- Repeated I/O smoke: PASS.
- Automated tests: `9 passed`.
- Ruff: PASS.
- Manual Egyptian listening gate: PASS.
- Listening note: Egyptian speech was clear and intelligible enough for development; background noise was acceptable; the slightly low level was not a Phase 1 blocker.
- Raspberry Pi 5 validation: DEFERRED.
- Anker PowerConf S330 validation: DEFERRED.
- No STT/TTS/LLM API was called in Phase 1.
- No Phase 2 implementation was started in the Phase 1 branch.

Phase 1 report:

`docs/phase1/PHASE1_REPORT.md`


# 32.2 Phase 2 Execution Contract — Realtime Conversation Core

**Execution status at v1.7 creation:** `AUTHORIZED_NOT_STARTED`

Phase 2 builds the realtime interaction layer on the current Windows laptop.

It does NOT add speech recognition, an LLM, TTS, RAG, memory, event knowledge, robot navigation, or production hardware validation.

## Phase 2 implementation decisions

- Development remains Windows-laptop-first.
- Branch: `phase/2-realtime-conversation-core`.
- The Phase 2 branch MUST be created from the completed Phase 1 branch, not from stale `main`, because Phase 1 has not been merged.
- Expected Phase 1 source HEAD at planning time: `03b46778133ccb5cd8308d8cff739448470c2f1d`.
- Python remains `>=3.11,<3.15`; current development Python is 3.14.6.
- Pin the stable Pipecat release to `pipecat-ai==1.8.1`.
- Do not use the Pipecat `local`/PyAudio transport in Phase 2.
- Continue using the existing `sounddevice` laptop backend from Phase 1.
- `sounddevice` microphone PCM is converted to Pipecat `InputAudioRawFrame` objects and queued into a Pipecat `PipelineWorker`.
- Runtime VAD uses `pipecat.audio.vad.silero.SileroVADAnalyzer`.
- Runtime semantic turn ending uses `pipecat.audio.turn.smart_turn.local_smart_turn_v3.LocalSmartTurnAnalyzerV3`.
- Runtime uses the models bundled with the pinned Pipecat package; do not download separate Silero or Smart Turn weights.
- Use `VADProcessor` before `UserTurnProcessor`.
- User turn start is VAD-driven with `VADUserTurnStartStrategy`.
- User turn stop is Smart-Turn-driven with `TurnAnalyzerUserTurnStopStrategy`.
- Because Phase 2 intentionally has no STT, configure the stop strategy with `wait_for_transcript=False`.
- Pipecat 1.8.1 default VAD values are the initial baseline: confidence `0.7`, start `0.2 s`, stop `0.2 s`, min volume `0.6`.
- VAD thresholds are configuration-driven. Do not silently tune them without a measured failure.
- The InnoBrain conversation state machine owns the product state: `IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `INTERRUPTED`.
- A small generated non-speech tone is the Phase 2 placeholder for assistant playback. It is NOT TTS.
- The placeholder tone is used to test cancellation and barge-in without letting laptop-speaker speech echo masquerade as user speech.
- Full spoken-output echo/AEC validation remains deferred to later speech/production-hardware testing.
- User speech while state is `THINKING` or `SPEAKING` must cancel active response/playback work.
- Never allow two assistant playback sessions at the same time.
- Phase 2 may provide a text echo/state-machine demo, but it is not an LLM and must not be presented as conversational intelligence.
- Raspberry Pi/S330 absence is not a Phase 2 blocker.

## Phase 2 realtime data path

```text
Laptop Microphone
      │
      ▼
sounddevice RawInputStream
16 kHz / mono / PCM16 / 20 ms blocks
      │
      ▼
async bounded audio queue
      │
      ▼
Pipecat PipelineWorker.queue_frames(...)
      │
      ▼
InputAudioRawFrame
      │
      ▼
VADProcessor
  SileroVADAnalyzer
      │
      ▼
VAD start/stop frames
      │
      ▼
UserTurnProcessor
  start: VADUserTurnStartStrategy
  stop: TurnAnalyzerUserTurnStopStrategy(
          LocalSmartTurnAnalyzerV3,
          wait_for_transcript=False
        )
      │
      ├──────── on_user_turn_started ───────► InterruptionController
      │                                         │
      │                                         └── cancel mock playback/work
      │
      └──────── on_user_turn_stopped ───────► semantic turn complete
                                                │
                                                ▼
                                        Conversation State Machine
```

## Phase 2 software outputs

```text
pyproject.toml                         # add pinned Pipecat + pytest-asyncio
config/runtime.yaml                    # realtime/VAD/Smart Turn settings
src/innobrain/audio/stream.py          # async sounddevice PCM source
src/innobrain/voice/state.py           # strict state machine
src/innobrain/voice/playback.py        # single-session interruptible tone playback
src/innobrain/voice/interruption.py     # cancellation controller + latency result
src/innobrain/voice/turn_events.py      # typed turn-event records
src/innobrain/voice/pipecat_runtime.py  # VAD + Smart Turn Pipecat runtime
src/innobrain/voice/text_echo.py        # non-AI state-machine echo harness
scripts/phase2/dependency_smoke.py
scripts/phase2/offline_vad_probe.py
scripts/phase2/turn_detection_demo.py
scripts/phase2/barge_in_demo.py
scripts/phase2/text_echo_demo.py
evals/conversation/phase2_egyptian_turns.yaml
docs/phase2/PHASE2_STATE.md
docs/phase2/PHASE2_REPORT.md
tests/unit/voice/...
tests/unit/audio/...
tests/integration/voice/...
```

## Phase 2 automated exit checks

- Existing Phase 1 tests still pass.
- New Phase 2 tests pass.
- Ruff passes.
- Pipecat installed version is exactly `1.8.1`.
- `SileroVADAnalyzer` instantiates successfully.
- `LocalSmartTurnAnalyzerV3` instantiates successfully.
- State-machine invalid transitions are rejected.
- Playback controller never overlaps two playback sessions.
- Interruption controller cancels `THINKING`/`SPEAKING` work and returns to `LISTENING`.
- Laptop audio input pump produces 16 kHz mono PCM frames without blocking the sounddevice callback.
- Pipecat pipeline can start, accept synthetic PCM frames, and shut down cleanly.
- No STT/LLM/TTS/RAG provider is imported or called.

## Phase 2 interactive Egyptian checks

### Silence gate

Run the realtime turn detector for 10 seconds without intentionally speaking.

Expected:

- zero user-turn-start events caused by ordinary room background.

### Normal Egyptian turn

Say:

`ممكن تقولي البرنامج بتاع النهارده؟`

Expected:

- one user-turn-start.
- one semantic user-turn-stop after the utterance finishes.

### Hesitation/continuation test

Say naturally:

`بص أنا عايز أعرف...`

Pause approximately 0.8–1.2 seconds, then continue:

`الـsession اللي بعد الضهر فين؟`

Run three trials.

Target:

- at least two of three trials preserve the same user turn through the thinking pause.
- no response placeholder should begin during a preserved incomplete pause.
- final semantic stop should occur after the continuation.

If this target fails repeatedly, do not pretend Smart Turn is validated for the current Egyptian use case. Record the evidence and stop for a turn-detection decision.

### Barge-in test

Use a generated tone as placeholder assistant audio.

While the tone is active, say:

`معلش وقف`

Expected:

- user-turn-start is detected.
- active tone is cancelled.
- state transitions `SPEAKING → INTERRUPTED → LISTENING`.
- there is no second overlapping tone.
- log `event_to_playback_stop_ms`.

Phase 2 engineering target:

`user-turn-start event → playback stop <= 100 ms`

This is an internal software cancellation metric only.

It does NOT claim the full acoustic `speech onset → robot silence` production barge-in target, because laptop speaker echo/AEC and production S330 hardware are not validated here.

## Phase 2 manual gate

The user confirms:

1. normal Egyptian speech creates sensible start/stop events;
2. ordinary silence/background does not constantly false-trigger;
3. the hesitation test is acceptable in at least two of three trials;
4. speaking during the placeholder tone stops it quickly;
5. the runtime returns to listening and can accept another turn afterward.


## Phase 2 validation scheduling override — 2026-09-02

The implementation order has changed.

The primary developer does not want to keep stopping development for repeated live speaking gates during intermediate phases. Therefore:

- Phase 2 live microphone interaction validation is no longer a blocking gate for starting Phase 3.
- Phase 2 implementation must still be finished, tested and documented.
- Human-speaking validation is deferred to a dedicated **Final Voice Acceptance** track near the end of the project.
- Raspberry Pi/S330 validation remains separately deferred to deployment/hardening.
- Current Phase 2 live evidence must be preserved, but it must NOT be used as proof that Smart Turn is good or bad because the attempted interaction was not a controlled acceptance run.
- Do not tune VAD/Smart Turn thresholds from that uncontrolled attempt.
- No automated test may be falsely reported as a human interaction PASS.

Current preserved Phase 2 evidence at the time of this decision:

```text
branch: phase/2-realtime-conversation-core
state commit: 936ad65
automated tests: 22 passed
Ruff: PASS
offline VAD: 12 speech starts, 7 stops
live silence test: 0 false starts
uncontrolled live attempt: 42 events
  - 14 starts
  - 14 inference triggers
  - 14 stops
normal-turn acceptance: NOT VALIDATED
Egyptian hesitation acceptance: NOT VALIDATED
barge-in live acceptance: NOT RUN
```

The 0/3 hesitation result from the uncontrolled attempt is recorded as evidence only. It is not an accepted benchmark result and is not a reason to change thresholds at this stage.

### Progression rule

Phase 3 may start after Phase 2 reaches:

`PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`

This means:

- required Phase 2 code exists;
- automated tests pass;
- lint passes;
- Pipecat/Silero/Smart-Turn runtime initializes;
- automated/synthetic pipeline and cancellation tests pass;
- the live-interaction acceptance suite is explicitly deferred and tracked.

This state is sufficient for **development progression**, but is NOT equivalent to production voice validation.

Before the full project can be considered release/event ready, the deferred Final Voice Acceptance track must pass.

## Phase 2 continuation wrap-up - 2026-09-02

**Phase 2 state:** `PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`

The non-interactive Phase 2 implementation is complete on the Windows laptop branch. The existing Task 12 live evidence was preserved, no human-speaking tests were rerun, and VAD/Smart Turn thresholds were unchanged.

Fresh verification results:

- Dependency smoke: PASS (`pipecat-ai==1.8.1`, Silero initialization, Smart Turn v3 initialization).
- Pytest: `23 passed in 1.71s`.
- Ruff: PASS.
- Realtime configuration: `0.7 0.2 0.2 0.6 False`.
- Phase 3 provider dependency scan: no matches.
- `git ls-files recordings artifacts`: no output.
- Synthetic cancellation harness: PASS; generated placeholder playback was cancelled by a programmatic user-turn-start and the state returned to `LISTENING`.

Preserved live evidence remains diagnostic only: 42 events (14 starts, 14 inference triggers, 14 stops), with normal-turn and hesitation acceptance not validated, correction/Test D not run, and live barge-in acceptance deferred. The exact evidence remains in the ignored `artifacts/phase2/turn_events.jsonl` artifact.

Final Voice Acceptance is tracked in `docs/validation/FINAL_VOICE_ACCEPTANCE.md` and remains required before production/event readiness. Raspberry Pi 5, Anker PowerConf S330, AEC, and full end-to-end voice validation remain deferred.

Phase 3 development is authorized, but Phase 3 has not started.


## Phase 2 allowed final states

Exactly one:

- `PHASE_2_COMPLETE`
- `PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`
- `PHASE_2_BLOCKED`

`PHASE_2_BLOCKED` is now reserved for an implementation/automated-runtime blocker. A missing or intentionally deferred human-speaking test is NOT, by itself, a Phase 2 blocker.

## Phase 2 completion action

For the current laptop development workflow:

1. finish all non-interactive Phase 2 implementation;
2. create the barge-in/live-test harness even if it is not run interactively now;
3. preserve current live JSONL evidence;
4. run the full automated suite, dependency smoke and Ruff fresh;
5. write `docs/phase2/PHASE2_REPORT.md`;
6. set Phase 2 to `PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`;
7. update this Master Plan and bump its patch version;
8. update README;
9. commit and push `phase/2-realtime-conversation-core`;
10. do not merge automatically;
11. stop before Phase 3.

That state authorizes Phase 3 development.

The deferred human-speaking tests move to Final Voice Acceptance.

## PHASE 2 — Realtime Conversation Core summary

Deliver:

- pinned Pipecat runtime.
- Silero VAD.
- Smart Turn v3.
- state machine.
- streaming laptop PCM into Pipecat.
- interruption/cancellation.
- single-session placeholder playback.
- basic text echo/state demo.
- Egyptian turn/pause/barge-in evaluation harness.

Implementation progression criteria:

- Pipecat/Silero/Smart Turn runtime initializes.
- realtime PCM path is implemented.
- state machine and cancellation controller pass automated tests.
- placeholder playback cannot overlap.
- synthetic/offline pipeline smoke shuts down cleanly.
- barge-in/live evaluation harness exists.
- full automated tests and Ruff pass.
- deferred live interaction tests are documented explicitly.
- no Phase 3 provider/brain/RAG work has started before the Phase 2 implementation wrap-up commit.

Human-speaking acceptance criteria are deferred to Final Voice Acceptance and are not deleted.


## PHASE 3 — Speech + Brain + RAG

Deliver:

- STT adapters.
- LLM adapters.
- TTS adapters.
- SQLite.
- FTS5.
- sqlite-vec.
- multilingual E5.
- hybrid retrieval.
- session memory.
- Egyptian persona.

Exit criteria:

- natural Egyptian Q&A.
- code-switch test works.
- RAG answers grounded in event evidence.
- exact event facts use structured data.
- main cloud provider and local fallbacks function.

## PHASE 4 — Dynamic Event Package

Deliver:

- event package schema.
- event versioning.
- document ingestion workflow.
- structured import.
- vector index build.
- event switching.
- validation report.

Exit criteria:

- replace event package without modifying application code.
- old event data does not leak into new event.

## PHASE 5 — Robot + Screen Integration

Deliver:

- semantic tools.
- RobotGateway.
- screen events.
- navigation integration.
- action safety checks.

Exit criteria:

- AI can request approved navigation.
- AI cannot send raw motor commands.
- screen can show event entities.

## PHASE 6 — Event Hardening + Final Voice Acceptance

Deliver:

- noise testing.
- latency benchmark.
- STT/TTS provider bake-off.
- Pi thermal/load testing.
- API outage fallback.
- long-duration testing.
- final golden evaluation set.
- **Final Voice Acceptance** for all deferred human-speaking gates.

### Final Voice Acceptance must include

On the completed system, not an isolated early-phase toy harness:

1. intentional silence/background false-trigger test;
2. normal Egyptian turn start/end;
3. Egyptian thinking-pause/hesitation continuation;
4. correction/afterthought turn;
5. real assistant-output barge-in;
6. post-interruption context continuation;
7. repeated multi-turn Egyptian conversation;
8. code-switching;
9. noisy-room test;
10. final production-hardware revalidation on Pi/S330 before event deployment.

The earlier Phase 2 live JSONL attempt remains diagnostic evidence only and does not replace this acceptance suite.

Exit criteria:

- stable multi-hour run.
- acceptable event-noise recognition.
- interruption reliable.
- deferred Final Voice Acceptance passes.
- no critical event fact hallucinated in golden tests.
- graceful fallback works.

---

# 33. Provider Bake-Off

Do not select winners by marketing.

## STT tests

Compare:

- Deepgram.
- Speechmatics.
- Azure.
- Gemini.
- Metro local.

Dataset:

- Egyptian only.
- English only.
- Egyptian + English nouns.
- English + Arabic nouns.
- speaker names.
- product names.
- room/booth numbers.
- times.
- fast speech.
- hesitation.
- far field.
- crowd noise.
- music.
- robot playback active.

Metrics:

- WER.
- CER.
- proper-name recall.
- number/time accuracy.
- code-switch accuracy.
- partial latency.
- finalization latency.
- CPU/RAM for local models.

## TTS tests

Compare:

- Azure Salma.
- Azure Shakir.
- Gemini Audio.
- ElevenLabs.
- VoiceTut if off-board GPU exists.

Native Egyptian judges score:

1–5:

- Egyptian authenticity.
- naturalness.
- English word pronunciation.
- proper nouns.
- numbers.
- warmth.
- professionalism.
- listener fatigue.
- time to first audio.

## LLM tests

Compare:

- Groq fast Qwen model.
- Gemini Flash.
- Gemma local.
- Qwen local.

Measure:

- Egyptian naturalness.
- tool accuracy.
- grounded answers.
- reference resolution.
- first-token latency.
- complete short-answer latency.

---

# 34. RAG Evaluation

Build 100+ event questions with known evidence.

Categories:

- direct fact.
- paraphrase.
- Egyptian slang.
- Arabic/English code-switch.
- English document / Arabic question.
- proper names.
- ambiguous question.
- conflicting documents.
- expired information.
- unsupported question.

Metrics:

- Recall@K.
- MRR.
- nDCG where useful.
- evidence correctness.
- answer faithfulness.
- unsupported-answer rejection.

RAG success means the correct evidence is retrieved, not merely that the final answer sounds convincing.

---

# 35. Latency Targets

Engineering targets:

## Simple conversational turn

`end of user turn → first useful robot audio`

Target P50:

`~1.0–1.2 s or better`

Target P95:

`<= 1.8 s`

## Barge-in

`user starts speaking → robot playback stops`

Target:

`<= 250 ms`

Stretch:

`<= 150–200 ms`

## Important design rule

Optimize TIME TO FIRST USEFUL AUDIO, not total answer completion.

Responses should stream.

---

# 36. Natural Conversation Behaviors

Required behaviors:

- user can pause briefly while thinking.
- robot does not interrupt every silence.
- robot can be interrupted.
- robot remembers the current topic.
- robot understands references such as "هو", "هناك", "اللي بعدها".
- answers are short by default.
- robot may use brief natural acknowledgements while a slow tool is running.
- acknowledgements should not become repetitive filler.
- robot should ask clarification when event entities are ambiguous.

Example target:

```text
User:
"الـsession بتاعة AI..."

[pause]

"...بتاعة Ahmed يعني."

Robot:
"أيوه، أحمد عنده session الساعة—"

User:
"لا استنى، قصدي Mohamed."

Robot immediately stops.

Robot:
"تمام، محمد. الـsession بتاعته الساعة 5 في Hall B."
```

---

# 37. Failure Modes and Fallbacks

## API outage

```text
primary provider fails
      ↓
secondary provider
      ↓
local fallback
```

## Internet outage

Robot should retain:

- active event DB.
- local RAG.
- session memory.
- basic local LLM.
- navigation tools.
- screen.
- essential FAQ.

## STT unavailable

Possible degraded modes:

- local Metro-ASR.
- touch/text UI if available.

## TTS unavailable

Possible degraded mode:

- local/basic TTS later if added.
- screen text output.

---

# 38. Observability

Log per turn:

- session ID.
- turn ID.
- language.
- STT provider.
- STT partial/final times.
- retrieval duration.
- evidence IDs.
- LLM provider.
- first token time.
- TTS provider.
- first audio time.
- interruption time.
- tool calls.
- tool success/failure.
- total latency.
- CPU.
- RAM.
- temperature.
- network state.

Do not log unlimited raw visitor audio by default.

---

# 39. Security and Grounding

Rules:

- event documents are untrusted data.
- retrieved documents cannot override system instructions.
- tool allowlists only.
- no raw motor control from LLM.
- no unvalidated SQL generated by the model.
- API keys in environment/secrets, never committed.
- every query scoped to active event/version.
- unsupported facts produce an honest fallback.
- do not fabricate schedules, rooms, speakers, prices or safety information.

---

# 40. Immediate Implementation Order

When development begins:

1. Create clean repository.
2. Add this Master Plan.
3. Clone approved donor repos into `_research/repos`.
4. Validate S330 on Raspberry Pi.
5. Measure simultaneous playback/capture.
6. Build minimal Pipecat audio loop.
7. Add Silero VAD.
8. Add Smart Turn.
9. Implement interruption.
10. Add STT adapter.
11. Add Groq LLM adapter.
12. Add Azure TTS adapter.
13. Add SQLite schema.
14. Add FTS5.
15. Add sqlite-vec.
16. Add multilingual-e5-small.
17. Build hybrid retriever.
18. Add memory.
19. Add event tools.
20. Benchmark.
21. Only then choose provider winners.

---

# 40.1 Project Naming Decision

**Project / repository name:** `InnoBrain`

Recommended GitHub repository slug:

`inno-brain`

Recommended local workspace:

`InnoBrainWorkspace`

Reason:

`InnoVoice` is too narrow because the project also contains RAG, memory, event knowledge, tools and robot integration. `InnoBrain` describes the complete AI subsystem without tying the repository to one event or one speech provider.

---

# 41. Architecture Freeze Summary

The architecture is considered sufficiently stable to start implementation.

### Locked

- Raspberry Pi edge controller.
- S330 audio hardware.
- Pipecat.
- Silero + Smart Turn.
- cascaded speech architecture.
- provider adapters.
- main cloud LLM + local fallback.
- SQLite.
- FTS5.
- sqlite-vec.
- hybrid RAG.
- multilingual local embeddings.
- session memory.
- dynamic event packages.
- semantic robot tools.
- simple modular monolith.
- six implementation phases.

### Must be determined empirically

- best STT.
- best Egyptian TTS.
- best main LLM API.
- best local fallback LLM.
- whether S330 needs extra software audio filtering.
- final endpointing thresholds.
- final RAG Top-K.
- whether reranking is necessary.

No provider decision is allowed to destabilize the architecture.

---

# 42. Source Snapshot

Research snapshot used for this architecture includes:

## Hardware

Anker PowerConf S330:
- https://ca.ankerwork.com/products/a3308
- https://uk.ankerwork.com/products/a3308
- https://service.ankerwork.com/article-description/PowerConf-S330-A3308-FAQ

## Realtime voice

Pipecat:
- https://github.com/pipecat-ai/pipecat

Smart Turn:
- https://github.com/pipecat-ai/smart-turn

WebRTC audio Python bindings candidate:
- https://github.com/strands-labs/pywebrtc-audio

## Speech

Metro-ASR:
- https://github.com/MohammedAly22/metro-asr

QwenCleo-ASR:
- https://github.com/MohammedAly22/qwencleo-asr

VoiceTut-TTS:
- https://github.com/MohammedAly22/VoiceTuT-TTS

Azure Speech language support:
- https://learn.microsoft.com/azure/ai-services/speech-service/language-support

## AI APIs

Groq:
- https://console.groq.com/docs/rate-limits

Gemini:
- https://ai.google.dev/gemini-api/docs/pricing

Deepgram:
- https://deepgram.com/pricing

Speechmatics:
- https://www.speechmatics.com/pricing

Azure:
- https://azure.microsoft.com/en-us/pricing/details/speech/

## Raspberry Pi local LLM

Official Raspberry Pi Gemma benchmark:
- https://www.raspberrypi.com/news/mastering-edge-ai-on-raspberry-pi-with-litert-and-gemma/

Pi5-LLM Qwen benchmark:
- https://github.com/Jiaming-Liuu/Pi5-LLM

## Retrieval

sqlite-vec:
- https://github.com/asg017/sqlite-vec

multilingual-e5-small:
- https://huggingface.co/intfloat/multilingual-e5-small

Docling:
- https://github.com/docling-project/docling

FlagEmbedding:
- https://github.com/FlagOpen/FlagEmbedding

## Robot/HRI reference

Pepper realtime AI:
- https://github.com/studerus/pepper-android-realtime-chat

---

# 43. Change Log

## v1.9 — 2026-09-02

- Completed the remaining non-interactive Phase 2 implementation while deferring human-speaking acceptance.
- Added the placeholder-tone barge-in harness and synthetic cancellation coverage without opening the microphone.
- Recorded fresh automated verification: `23 passed in 1.71s`, dependency smoke PASS, and Ruff PASS.
- Set Phase 2 to `PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED`.
- Added `docs/validation/FINAL_VOICE_ACCEPTANCE.md` as the permanent deferred acceptance tracker.
- Preserved the prior 42-event Task 12 evidence as diagnostic/non-acceptance evidence.
- Authorized Phase 3 development without starting Phase 3.

## v1.8 — 2026-09-02

- Changed validation scheduling so intermediate live-speaking gates no longer repeatedly stop development.
- Added `PHASE_2_IMPLEMENTATION_COMPLETE_VALIDATION_DEFERRED` as a valid development-progression state.
- Preserved Phase 2 live evidence from commit `936ad65` as diagnostic evidence rather than an accepted benchmark.
- Explicitly prohibited VAD/Smart Turn threshold tuning based on the uncontrolled Phase 2 speaking attempt.
- Authorized Phase 3 after Phase 2 implementation/automated verification is complete, even when human-speaking validation is deferred.
- Moved normal-turn, Egyptian hesitation, correction and barge-in human acceptance into a dedicated Final Voice Acceptance track.
- Expanded Phase 6 to include Final Voice Acceptance on the completed system.
- Kept Raspberry Pi/S330 production validation deferred to hardening/deployment.

## v1.7 — 2026-09-02

- Authorized Phase 2 — Realtime Conversation Core.
- Locked Phase 2 branch to `phase/2-realtime-conversation-core`, based on the completed Phase 1 branch rather than stale `main`.
- Pinned Pipecat runtime to stable release `1.8.1`.
- Chose the existing `sounddevice` backend for laptop PCM capture instead of Pipecat's PyAudio local transport.
- Locked the Phase 2 Pipecat chain to `VADProcessor(Silero)` followed by `UserTurnProcessor(VAD start + Smart Turn stop)`.
- Explicitly set Smart Turn stop strategy `wait_for_transcript=False` because STT is deferred to Phase 3.
- Chose Pipecat-bundled Silero and Smart Turn model assets; no separate model download in Phase 2.
- Added strict `IDLE/LISTENING/THINKING/SPEAKING/INTERRUPTED` product state machine.
- Added a generated non-speech tone as the Phase 2 assistant-playback placeholder for safe barge-in testing.
- Defined Phase 2 Egyptian silence, normal-turn, hesitation and barge-in manual gates.
- Clarified that Phase 2 cancellation latency is measured from detected user-turn-start event, not acoustic speech onset.
- Kept Raspberry Pi/S330 and full spoken-output AEC validation deferred.

## v1.6 — 2026-09-02

- Recorded Phase 1 as `PHASE_1_COMPLETE`.
- Recorded Windows 11 + Python 3.14.6 as the validated development environment.
- Recorded config validation `ar-EG laptop`.
- Recorded laptop Realtek microphone/output device observations.
- Recorded 16 kHz mono recording/playback/repeated-I/O PASS.
- Recorded `9 passed` and Ruff PASS.
- Recorded the user Egyptian listening gate as PASS, with acceptable background noise and slightly low but usable recording level.
- Kept Raspberry Pi 5 and Anker S330 production validation deferred.
- Authorized Phase 2 without starting it.
- Recorded Phase 1 branch HEAD `03b46778133ccb5cd8308d8cff739448470c2f1d`.

## v1.5 — 2026-09-02

- Changed the active development workflow to **Windows laptop first**.
- Declared the laptop microphone and laptop output device as the current development audio path.
- Reclassified Raspberry Pi 5 + Anker PowerConf S330 as target deployment hardware, not current Phase 1 requirements.
- Removed Raspberry Pi/S330 availability as a Phase 1 blocking condition.
- Deferred Pi/S330 hardware validation to a later deployment-validation track that may be performed by another team member.
- Locked hardware-agnostic audio interfaces so core conversation logic is portable between laptop development and Pi deployment.
- Renamed the Phase 1 branch to `phase/1-foundation-laptop-audio`.
- Replaced Phase 1 hardware validation with laptop audio-device enumeration, capture, playback and Egyptian-Arabic listening validation.
- Kept production readiness dependent on later real Pi/S330 validation before event deployment.

## v1.4 — 2026-09-02

- Authorized Phase 1 execution with a strict Foundation + Hardware Validation scope.
- Added Luna/Codex-friendly deterministic execution boundaries.
- Locked Phase 1 branch name to `phase/1-foundation-hardware`.
- Set Phase 1 Python compatibility to `>=3.11,<3.15` with isolated virtual environments.
- Kept Phase 1 dependencies minimal and deferred Pipecat/Silero/Smart Turn/provider SDK/model installation to later phases.
- Confirmed no API quota or model weights are required in Phase 1.
- Locked the S330 hardware DSP as the Phase 1 audio baseline; software AEC/NS remains disabled pending measurements.
- Prohibited Phase 1 changes to global ALSA default configuration such as `.asoundrc`.
- Defined actual-Pi hardware evidence, S330 full-duplex tests, distance recordings and a five-minute USB/audio soak test.
- Added a mandatory user acoustic-listening gate before Phase 1 can be marked complete.
- Defined explicit intermediate states for missing Pi access or pending acoustic confirmation.
- Required the coding agent to update this Master Plan with measured Phase 1 results before completion.

## v1.3 — 2026-09-02

- Recorded successful Codex pre-Phase-1 bootstrap report.
- Recorded actual local workspace and production repository paths.
- Recorded private GitHub repository `MahmoudNagiubX/inno-brain`.
- Recorded `13/13` donor repositories cloned and inspected.
- Recorded bootstrap final state as `READY_FOR_PHASE_1`.
- Added the `sqlite-vec` license-review note reported during donor inspection.
- Explicitly marked bootstrap verification as Codex-reported rather than independently re-run in this chat.
- Authorized the next milestone: Phase 1 — Foundation + Hardware Validation.

## v1.2 — 2026-09-01

- Added the formal **Pre-Phase-1 Codex Bootstrap** boundary.
- Defined workspace bootstrap outputs and stop condition.
- Defined GitHub repository default as private unless explicitly changed by the user.
- Required donor repository URL/branch/SHA/license inventory and inspection report.
- Clarified that bootstrap scaffolding must not start Phase 1 implementation.
- Added `CODEX_PRE_PHASE1_BOOTSTRAP.md` as the execution handoff companion to this Master Plan.

## v1.1 — 2026-09-01

- Renamed the project/repository from Inno Talk to **InnoBrain** (`inno-brain`).
- Declared **Egyptian Arabic as the primary MVP language**; English is secondary.
- Added mandatory Master Plan change-control rule.
- Moved donor repositories outside the production Git repository into a sibling `donor-repos/` folder.
- Reduced and froze the V1 clone set to **13 high-value repositories**.
- Added GLaDOS as a low-latency/interruption/memory donor.
- Added Compact RAG as a Raspberry-Pi hybrid-RAG donor.
- Removed QwenCleo-ASR, sherpa-onnx, FlagEmbedding and protoVoice from the initial clone set; they remain optional references.
- Changed benchmark policy: use published evidence to pre-filter and benchmark only 1–2 hardware-relevant finalists on the real Raspberry Pi.
- Clarified that donor repositories are code/reference sources, while implementation remains clean inside `inno-brain/`.

## v1.0 — 2026-09-01

- Locked Raspberry Pi 5 8GB as edge controller.
- Confirmed Anker PowerConf S330 A3308 as audio hardware.
- Locked SQLite + FTS5 + sqlite-vec.
- Locked RAG as core architecture.
- Locked hybrid retrieval.
- Locked Pipecat + Silero + Smart Turn.
- Locked API-first main LLM with local fallback.
- Selected Groq as first LLM API to test.
- Selected Azure Egyptian TTS as first TTS baseline.
- Selected Deepgram/Speechmatics/Azure/Gemini/Metro as STT bake-off.
- Selected Gemma 4 E2B and Qwen3.5-2B as local LLM bake-off.
- Defined six implementation phases.
- Defined donor repository policy.
- Defined latency and barge-in targets.

---

**End of Master Plan v1.9**

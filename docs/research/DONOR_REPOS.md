# InnoBrain V1 Donor Repository Index

This index records the 13 shallow-cloned research repositories required by the
pre-Phase-1 bootstrap. Exact URLs, branches, full commit SHAs, license evidence,
and production-dependency status are in `DONOR_REPOS.lock.yaml`.

| Repository | Category | Branch | Inspected commit | License | Production dependency |
|---|---|---:|---|---|---|
| [pipecat](https://github.com/pipecat-ai/pipecat) | foundation | main | `719b580` | BSD-2-Clause | no |
| [smart-turn](https://github.com/pipecat-ai/smart-turn) | foundation | main | `4786657` | BSD-2-Clause | no |
| [silero-vad](https://github.com/snakers4/silero-vad) | foundation | master | `867c2aa` | MIT | no |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | foundation | main | `04d28bd` | REVIEW_REQUIRED | no |
| [pywebrtc-audio](https://github.com/strands-labs/pywebrtc-audio) | foundation | main | `041c3a1` | Apache-2.0 | no |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | foundation | master | `3466812` | MIT | no |
| [metro-asr](https://github.com/MohammedAly22/metro-asr) | egyptian_speech | main | `683dd44` | MIT | no |
| [VoiceTuT-TTS](https://github.com/MohammedAly22/VoiceTuT-TTS) | egyptian_speech | main | `b5302e9` | Apache-2.0 | no |
| [voice-agent-starter](https://github.com/sarmakska/voice-agent-starter) | interaction | main | `123073f` | MIT | no |
| [GLaDOS](https://github.com/dnhkng/GLaDOS) | interaction | main | `09f26d5` | MIT | no |
| [pepper-android-realtime-chat](https://github.com/studerus/pepper-android-realtime-chat) | robot_hri | master | `c83de7b` | MIT | no |
| [compact-rag](https://github.com/araobp/compact-rag) | rag | main | `993f0b3` | MIT | no |
| [docling](https://github.com/docling-project/docling) | ingestion | main | `33e3be2` | MIT | no |

## Bootstrap asset note

No package installation, model registry download, or model-weight download was
run by the bootstrap. Some donor repositories intentionally contain
repository-tracked assets such as ONNX models, vocabulary GGUF files, sample
audio, databases, or native binaries. Those assets remain inside donor clones
only and are not production dependencies.

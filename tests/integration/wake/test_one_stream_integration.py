from pathlib import Path

import pytest

from innobrain.attention.contracts import AttentionPolicyConfig, AttentionState
from innobrain.attention.controller import AttentionController
from innobrain.config import load_all_configs
from innobrain.conversation.memory import SessionMemory
from innobrain.conversation.orchestrator import AnswerRoute, BrainResult
from innobrain.providers import TranscriptEvent
from innobrain.providers.contracts import AudioChunk
from innobrain.voice.brain_runtime import VoiceBrainRuntime
from innobrain.voice.state import ConversationState
from innobrain.wake.bridge import WakeAttentionBridge
from innobrain.wake.contracts import (
    CANONICAL_WAKE_LABEL,
    SAMPLE_RATE_HZ,
    WakeDetection,
    WakeEngineHealth,
    WakeWordEngine,
)
from innobrain.wake.router import WakeAudioRouter

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class FakeEngine(WakeWordEngine):
    def __init__(self) -> None:
        self.trigger_on_next: WakeDetection | None = None
        self.reset_called = False
        self.close_called = False

    @property
    def sample_rate_hz(self) -> int:
        return SAMPLE_RATE_HZ

    @property
    def frame_length(self) -> int:
        return 1280

    @property
    def health(self) -> WakeEngineHealth:
        return WakeEngineHealth(ready=True, engine_name="fake_engine")

    def process(self, pcm16: bytes) -> WakeDetection | None:
        det = self.trigger_on_next
        self.trigger_on_next = None
        return det

    def reset(self) -> None:
        self.reset_called = True

    def close(self) -> None:
        self.close_called = True


class RecordingSTT:
    def __init__(self) -> None:
        self.streamed_chunks: list[bytes] = []
        self.next_text = ""
        self.turn_ids: list[int] = []
        self.final_error: Exception | None = None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def begin_turn(self, turn_id: int) -> None:
        self.turn_ids.append(turn_id)

    async def stream_audio(self, pcm: bytes) -> None:
        self.streamed_chunks.append(pcm)

    async def final_text(self, turn_id: int | None = None) -> TranscriptEvent:
        if self.final_error is not None:
            raise self.final_error
        return TranscriptEvent(text=self.next_text, is_final=True, turn_id=turn_id)


class StubOrchestrator:
    def __init__(self) -> None:
        self.memory = SessionMemory(max_turns=10, ttl_seconds=300.0)

    async def answer(self, text: str) -> BrainResult:
        return BrainResult(
            text="response to " + text,
            route=AnswerRoute.EXACT,
            evidence_ids=(),
            provider="stub",
        )

    def commit_delivered(self, user_text: str, result: BrainResult) -> None:
        pass


class StubTTS:
    async def stream(self, text: str):
        yield AudioChunk(b"\x00\x00" * 320, 16000)


class StubPlayback:
    def __init__(self) -> None:
        self.started = False
        self.finished = False

    async def start(self, sample_rate_hz: int) -> None:
        self.started = True

    async def write(self, data: bytes) -> None:
        pass

    async def finish(self) -> None:
        self.finished = True

    async def cancel(self) -> None:
        pass


@pytest.mark.asyncio
async def test_sleeping_pcm_suppression_and_canonical_wake_handoff() -> None:
    config = load_all_configs(REPOSITORY_ROOT)
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    stt = RecordingSTT()
    orchestrator = StubOrchestrator()
    runtime = VoiceBrainRuntime(
        config.runtime,
        stt=stt,
        orchestrator=orchestrator,
        tts=StubTTS(),
        playback=StubPlayback(),
        audio_gate=bridge,
        attention=attention,
        wake_router=router,
    )

    # 1. Sleeping frames fed through bridge
    assert runtime is not None
    sleeping_chunk_1 = b"\x01\x00" * 640
    sleeping_chunk_2 = b"\x02\x00" * 640

    out_1 = bridge.process_chunk(sleeping_chunk_1)
    out_2 = bridge.process_chunk(sleeping_chunk_2)

    # Bridge suppresses sleeping frames
    assert out_1 == b""
    assert out_2 == b""
    assert attention.state == AttentionState.SLEEPING

    # 2. Canonical wake detected
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL,
        detector="fake",
        detected_at_monotonic=10.0,
    )
    wake_chunk = b"\x03\x00" * 640
    out_wake = bridge.process_chunk(wake_chunk)

    # Attention enters ENGAGED, downstream receives ONLY current chunk
    assert attention.state == AttentionState.ENGAGED
    assert out_wake == wake_chunk
    assert attention.handoff_metadata is not None
    assert attention.handoff_metadata.wake_detection.label == CANONICAL_WAKE_LABEL

    # 3. Subsequent frames while engaged flow downstream
    engaged_chunk = b"\x04\x00" * 640
    out_engaged = bridge.process_chunk(engaged_chunk)
    assert out_engaged == engaged_chunk


@pytest.mark.asyncio
async def test_followup_window_and_rejection_hooks() -> None:
    config = load_all_configs(REPOSITORY_ROOT)
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    policy = AttentionPolicyConfig(
        followup_window_ms=4500.0,
        rejected_background_limit=1,
    )
    attention = AttentionController(policy=policy, router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    stt = RecordingSTT()
    orchestrator = StubOrchestrator()
    playback = StubPlayback()
    runtime = VoiceBrainRuntime(
        config.runtime,
        stt=stt,
        orchestrator=orchestrator,
        tts=StubTTS(),
        playback=playback,
        audio_gate=bridge,
        attention=attention,
        wake_router=router,
    )

    # Enter ENGAGED
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=1.0
    )
    bridge.process_chunk(b"\x01\x00" * 640)
    assert attention.state == AttentionState.ENGAGED

    # Assistant reply completes -> transitions to FOLLOWUP_WINDOW
    runtime.machine.transition(ConversationState.LISTENING, "start")
    runtime.machine.transition(ConversationState.THINKING, "user_stopped")
    await runtime._respond("hello", turn_id=1)
    assert attention.state == AttentionState.FOLLOWUP_WINDOW
    assert router.mode.value == "followup_window"

    # Background / ambiguous speech during follow-up window
    stt.next_text = "just talking to someone else nearby"
    await runtime.handle_user_turn_started(manage_attention=True)
    assert attention.is_utterance_in_progress is True
    assert runtime.is_quiescent is False

    result = await runtime.handle_user_turn_stopped()

    # Ambiguous speech rejected, limit of 1 trips, returns to SLEEPING
    assert result is None
    assert attention.state == AttentionState.SLEEPING
    assert router.mode.value == "sleeping"
    assert attention.health.rejected_background_count == 1
    assert runtime.is_quiescent is True


@pytest.mark.asyncio
async def test_playback_active_suppresses_wake_detection() -> None:
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)

    router.set_playback_active(True)
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=1.0
    )

    # Wake word during robot playback is suppressed
    out = bridge.process_chunk(b"\x01\x00" * 640)
    assert out == b""
    assert attention.state == AttentionState.SLEEPING
    assert router.health.suppressed_detections_playback == 1

    # Playback inactive enables detection
    router.set_playback_active(False)
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=2.0
    )
    out = bridge.process_chunk(b"\x01\x00" * 640)
    assert attention.state == AttentionState.ENGAGED


def _attention_runtime() -> tuple[VoiceBrainRuntime, AttentionController, RecordingSTT]:
    config = load_all_configs(REPOSITORY_ROOT)
    engine = FakeEngine()
    router = WakeAudioRouter(engine)
    attention = AttentionController(router=router)
    bridge = WakeAttentionBridge(router=router, attention=attention)
    stt = RecordingSTT()
    runtime = VoiceBrainRuntime(
        config.runtime,
        stt=stt,
        orchestrator=StubOrchestrator(),
        tts=StubTTS(),
        playback=StubPlayback(),
        audio_gate=bridge,
        attention=attention,
        wake_router=router,
    )
    engine.trigger_on_next = WakeDetection(
        label=CANONICAL_WAKE_LABEL, detector="fake", detected_at_monotonic=1.0
    )
    bridge.process_chunk(b"\x01\x00" * 640)
    return runtime, attention, stt


@pytest.mark.asyncio
async def test_attention_turn_recovers_after_empty_transcript() -> None:
    runtime, attention, _stt = _attention_runtime()

    await runtime.handle_user_turn_started(manage_attention=True)
    assert attention.is_utterance_in_progress is True
    assert await runtime.handle_user_turn_stopped() is None
    assert attention.is_utterance_in_progress is False

@pytest.mark.asyncio
async def test_attention_turn_recovers_after_stt_failure() -> None:
    runtime, attention, stt = _attention_runtime()
    stt.final_error = RuntimeError("offline test STT failure")

    await runtime.handle_user_turn_started(manage_attention=True)
    assert await runtime.handle_user_turn_stopped() is None
    assert attention.is_utterance_in_progress is False

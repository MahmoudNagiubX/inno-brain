import pytest

from innobrain.providers import TranscriptEvent
from innobrain.providers.errors import ProviderUnavailable
from innobrain.providers.stt_failover import FailoverSTTProvider


class FakeSTT:
    def __init__(
        self,
        name: str,
        *,
        fail_start: bool = False,
        fail_send_at: int | None = None,
        fail_final: bool = False,
    ) -> None:
        self.name = name
        self.fail_start = fail_start
        self.fail_send_at = fail_send_at
        self.fail_final = fail_final
        self.calls: list[tuple] = []
        self.send_count = 0
        self.turn_id: int | None = None

    async def start(self) -> None:
        self.calls.append(("start",))
        if self.fail_start:
            raise RuntimeError(f"{self.name} unavailable")

    async def begin_turn(self, turn_id: int) -> None:
        self.turn_id = turn_id
        self.calls.append(("begin", turn_id))

    async def stream_audio(self, pcm: bytes) -> None:
        self.send_count += 1
        self.calls.append(("audio", pcm))
        if self.fail_send_at == self.send_count:
            raise RuntimeError(f"{self.name} send failed")

    async def partial_text(self) -> TranscriptEvent | None:
        return None

    async def final_text(self, turn_id: int | None = None) -> TranscriptEvent:
        self.calls.append(("final", turn_id))
        if self.fail_final:
            raise RuntimeError(f"{self.name} final failed")
        return TranscriptEvent(f"{self.name} text", True, turn_id=turn_id)

    async def stop(self) -> None:
        self.calls.append(("stop",))


@pytest.mark.asyncio
async def test_primary_healthy_serves_the_turn() -> None:
    primary = FakeSTT("speechmatics")
    fallback = FakeSTT("deepgram")
    provider = FailoverSTTProvider(primary, fallback)

    await provider.start()
    await provider.begin_turn(1)
    await provider.stream_audio(b"pcm")
    final = await provider.final_text(1)

    assert final.text == "speechmatics text"
    assert provider.health.active_provider == "speechmatics"
    assert provider.health.degraded is False
    assert fallback.calls == []


@pytest.mark.asyncio
async def test_continuous_pre_turn_audio_reaches_stt_without_opening_a_turn() -> None:
    primary = FakeSTT("speechmatics")
    provider = FailoverSTTProvider(primary, FakeSTT("deepgram"))

    await provider.start()
    await provider.stream_audio(b"pre-turn-silence")
    await provider.begin_turn(1)
    await provider.stream_audio(b"speech")

    assert primary.calls == [
        ("start",),
        ("audio", b"pre-turn-silence"),
        ("begin", 1),
        ("audio", b"speech"),
    ]


@pytest.mark.asyncio
async def test_primary_start_failure_cleans_up_and_starts_fallback() -> None:
    primary = FakeSTT("speechmatics", fail_start=True)
    fallback = FakeSTT("deepgram")
    provider = FailoverSTTProvider(primary, fallback)

    await provider.start()

    assert primary.calls == [("start",), ("stop",)]
    assert fallback.calls == [("start",)]
    assert provider.health.active_provider == "deepgram"
    assert provider.health.degraded is True
    assert provider.health.last_failure == "speechmatics: RuntimeError"


@pytest.mark.asyncio
async def test_failure_before_first_audio_switches_and_sends_only_to_fallback() -> None:
    primary = FakeSTT("speechmatics", fail_send_at=1)
    fallback = FakeSTT("deepgram")
    provider = FailoverSTTProvider(primary, fallback)
    await provider.start()
    await provider.begin_turn(2)

    await provider.stream_audio(b"first")

    assert ("stop",) in primary.calls
    assert fallback.calls == [("start",), ("begin", 2), ("audio", b"first")]
    assert provider.health.active_provider == "deepgram"


@pytest.mark.asyncio
async def test_mid_turn_failure_fails_turn_without_replay_then_uses_fallback_next_turn() -> None:
    primary = FakeSTT("speechmatics", fail_send_at=2)
    fallback = FakeSTT("deepgram")
    provider = FailoverSTTProvider(primary, fallback)
    await provider.start()
    await provider.begin_turn(3)
    await provider.stream_audio(b"accepted")

    with pytest.raises(ProviderUnavailable, match="current STT turn failed"):
        await provider.stream_audio(b"failed")

    assert fallback.calls == []
    await provider.begin_turn(4)
    await provider.stream_audio(b"next")

    assert fallback.calls == [("start",), ("begin", 4), ("audio", b"next")]
    assert ("audio", b"accepted") not in fallback.calls
    assert ("audio", b"failed") not in fallback.calls


@pytest.mark.asyncio
async def test_final_failure_activates_fallback_only_for_next_turn_and_stop_cleans_both() -> None:
    primary = FakeSTT("speechmatics", fail_final=True)
    fallback = FakeSTT("deepgram")
    provider = FailoverSTTProvider(primary, fallback)
    await provider.start()
    await provider.begin_turn(5)
    await provider.stream_audio(b"accepted")

    with pytest.raises(ProviderUnavailable, match="current STT turn failed"):
        await provider.final_text(5)

    assert fallback.calls == []
    await provider.begin_turn(6)
    await provider.stop()

    assert fallback.calls == [("start",), ("begin", 6), ("stop",)]
    assert primary.calls.count(("stop",)) == 1


@pytest.mark.asyncio
async def test_both_start_failures_are_typed_and_health_has_no_secret_message() -> None:
    primary = FakeSTT("speechmatics", fail_start=True)
    fallback = FakeSTT("deepgram", fail_start=True)
    provider = FailoverSTTProvider(primary, fallback)

    with pytest.raises(ProviderUnavailable, match="no STT provider could start"):
        await provider.start()

    assert provider.health.active_provider is None
    assert provider.health.degraded is True
    assert provider.health.last_failure == "deepgram: RuntimeError"

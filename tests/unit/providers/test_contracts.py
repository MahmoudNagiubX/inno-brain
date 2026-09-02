from dataclasses import FrozenInstanceError

import pytest

from innobrain.providers import AudioChunk, ChatMessage, TranscriptEvent


def test_phase1_contract_dataclasses_are_immutable_and_support_arabic() -> None:
    transcript = TranscriptEvent(text="إزيك؟", is_final=True, language="ar-EG", turn_id=7)
    audio = AudioChunk(data=b"pcm", sample_rate_hz=16000, channels=1)
    message = ChatMessage(role="user", content="ممكن تقولّي البرنامج بتاع النهارده؟")

    assert transcript.text == "إزيك؟"
    assert transcript.turn_id == 7
    assert audio.sample_rate_hz == 16000
    assert message.role == "user"

    with pytest.raises(FrozenInstanceError):
        transcript.text = "changed"  # type: ignore[misc]


def test_contract_dataclasses_use_slots() -> None:
    assert not hasattr(TranscriptEvent("text", False), "__dict__")
    assert not hasattr(AudioChunk(b"pcm", 16000), "__dict__")
    assert not hasattr(ChatMessage("user", "hello"), "__dict__")

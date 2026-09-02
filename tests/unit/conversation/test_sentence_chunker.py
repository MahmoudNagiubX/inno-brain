from innobrain.conversation.sentence_chunker import SentenceChunker


def test_chunker_does_not_split_time_or_decimal() -> None:
    chunker = SentenceChunker()

    result = chunker.feed("الSession الساعة 11:00. القيمة 3.14. بعد كده نكمل؟")

    assert result == ["الSession الساعة 11:00.", "القيمة 3.14.", "بعد كده نكمل؟"]


def test_chunker_forces_only_after_minimum_buffer() -> None:
    chunker = SentenceChunker(min_forced_chars=10)

    assert chunker.feed("قصير") == []
    assert chunker.feed(" جداً وممتد") == ["قصير جداً"]
    assert chunker.flush() == ["وممتد"]

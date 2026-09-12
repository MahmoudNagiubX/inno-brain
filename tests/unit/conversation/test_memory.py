from innobrain.conversation.memory import SessionMemory


def test_memory_evicts_oldest_after_eleventh_turn() -> None:
    memory = SessionMemory(max_turns=10, ttl_seconds=300, clock=lambda: 100.0)

    for index in range(11):
        memory.add_turn(f"u{index}", f"a{index}", (f"entity-{index}",))

    assert len(memory.recent_turns()) == 10
    assert memory.recent_turns()[0].user_text == "u1"
    assert "entity-10" in memory.active_entities()


def test_memory_expires_after_301_seconds_and_does_not_store_cancelled_draft() -> None:
    now = [100.0]
    memory = SessionMemory(clock=lambda: now[0])
    memory.add_turn("hello", "hi", ("event",))
    assert memory.add_turn("draft", "never delivered", committed=False) is False
    assert len(memory.recent_turns()) == 1

    now[0] = 401.0
    assert memory.expire_if_idle() is True
    assert memory.recent_turns() == ()
    assert memory.active_entities() == ()


def test_memory_keeps_bounded_language_style_and_event_reset_returns_to_arabic() -> None:
    memory = SessionMemory()
    memory.set_language_style("en")
    assert memory.language_style == "en"

    memory.reset()

    assert memory.language_style == "ar-EG"

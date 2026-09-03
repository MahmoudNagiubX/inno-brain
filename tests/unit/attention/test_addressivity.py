from innobrain.attention.addressivity import AddressivityGate
from innobrain.attention.contracts import AddressivityVerdict
from innobrain.attention.presence import PresenceState


def test_explicit_wake_detection_english() -> None:
    gate = AddressivityGate()

    decision = gate.evaluate("heyino")
    assert decision.verdict == AddressivityVerdict.EXPLICIT_WAKE
    assert decision.is_directed is True
    assert decision.matched_cue == "heyino"
    assert decision.extracted_command == ""
    assert decision.confidence >= 0.95

    # Same-breath command handoff
    decision_cmd = gate.evaluate("Heyino, turn on the living room lights!")
    assert decision_cmd.verdict == AddressivityVerdict.EXPLICIT_WAKE
    assert decision_cmd.is_directed is True
    assert decision_cmd.matched_cue == "heyino"
    assert decision_cmd.extracted_command == "turn on the living room lights"


def test_explicit_wake_detection_arabic() -> None:
    gate = AddressivityGate()

    decision_ar = gate.evaluate("يا هينو")
    assert decision_ar.verdict == AddressivityVerdict.EXPLICIT_WAKE
    assert decision_ar.is_directed is True
    assert decision_ar.confidence >= 0.95

    decision_cmd_ar = gate.evaluate("هينو قولي الأخبار النهاردة")
    assert decision_cmd_ar.verdict == AddressivityVerdict.EXPLICIT_WAKE
    assert decision_cmd_ar.is_directed is True
    assert "قولي الاخبار" in (decision_cmd_ar.extracted_command or "")


def test_directed_cues_english() -> None:
    gate = AddressivityGate()

    test_phrases = [
        ("listen, what is the weather?", "listen"),
        ("tell me a story", "tell me"),
        ("can you help me please?", "can you"),
        ("are you there?", "are you there"),
        ("look at this", "look"),
    ]

    for phrase, expected_cue in test_phrases:
        decision = gate.evaluate(phrase)
        assert decision.verdict == AddressivityVerdict.DIRECTED_CUE
        assert decision.is_directed is True
        assert decision.matched_cue == expected_cue
        assert decision.confidence >= 0.8


def test_directed_cues_egyptian() -> None:
    gate = AddressivityGate()

    test_phrases = [
        ("اسمع يا باشا", "اسمع"),
        ("esma3 ya basha", "esma3"),
        ("شوف ده كده", "شوف"),
        ("shouf keda", "shouf"),
        ("انت معايا يا فندم؟", "انت معايا"),
        ("enta ma3aya", "enta ma3aya"),
        ("كلمني بصوت عالي", "كلمني"),
        ("kallimni", "kallimni"),
        ("boss keda", "boss"),
        ("2ooli el sa3a kam", "2ooli"),
    ]

    for phrase, expected_cue in test_phrases:
        decision = gate.evaluate(phrase)
        assert decision.verdict == AddressivityVerdict.DIRECTED_CUE, f"Failed on {phrase}"
        assert decision.is_directed is True
        assert decision.matched_cue == expected_cue
        assert decision.confidence >= 0.8


def test_conversation_continuity_english() -> None:
    gate = AddressivityGate()

    continuations = [
        "yes",
        "yeah",
        "sure",
        "okay",
        "ok",
        "no",
        "nope",
        "cancel",
        "next",
        "continue",
        "two",
        "repeat",
    ]

    for phrase in continuations:
        decision = gate.evaluate(phrase, expecting_reply=True)
        assert (
            decision.verdict == AddressivityVerdict.CONVERSATION_CONTINUITY
        ), f"Failed on {phrase}"
        assert decision.is_directed is True
        assert decision.confidence >= 0.8


def test_conversation_continuity_egyptian() -> None:
    gate = AddressivityGate()

    continuations = [
        "اه",
        "ah",
        "ايوه",
        "aywa",
        "تمام",
        "tamam",
        "ماشي",
        "mashy",
        "لا",
        "la",
        "خلاص",
        "khalas",
        "أكيد",
        "akeed",
        "صح",
        "sah",
    ]

    for phrase in continuations:
        decision = gate.evaluate(phrase, expecting_reply=True)
        assert (
            decision.verdict == AddressivityVerdict.CONVERSATION_CONTINUITY
        ), f"Failed on {phrase}"
        assert decision.is_directed is True
        assert decision.confidence >= 0.8


def test_background_ambiguous_speech_rejected() -> None:
    gate = AddressivityGate()

    background_samples = [
        "did you see the football match last night?",
        "pass the salt please",
        "my mom said she will arrive at noon",
        "شفت الماتش امبارح كان رهيب",
        "هات المايه يا احمد",
        "the TV news anchor said inflation rose",
        "",
        "   ",
    ]

    for phrase in background_samples:
        decision = gate.evaluate(phrase, expecting_reply=True)
        assert (
            decision.verdict == AddressivityVerdict.BACKGROUND_AMBIGUOUS
        ), f"Expected rejected for: {phrase}"
        assert decision.is_directed is False
        assert decision.confidence < 0.5



def test_presence_signal_influence() -> None:
    gate = AddressivityGate()

    # When user is confirmed absent, non-wake continuity is rejected as ambiguous
    decision_absent = gate.evaluate(
        "tamam",
        expecting_reply=True,
        presence=PresenceState.ABSENT,
    )
    assert decision_absent.verdict == AddressivityVerdict.BACKGROUND_AMBIGUOUS
    assert decision_absent.is_directed is False

    # Wake word still works even if visual sensor says absent (e.g. user speaking around corner)
    decision_wake = gate.evaluate(
        "heyino",
        expecting_reply=True,
        presence=PresenceState.ABSENT,
    )
    assert decision_wake.verdict == AddressivityVerdict.EXPLICIT_WAKE
    assert decision_wake.is_directed is True

    # Safe default (unknown) allows standard continuity
    decision_unknown = gate.evaluate(
        "tamam",
        expecting_reply=True,
        presence=PresenceState.UNKNOWN,
    )
    assert decision_unknown.verdict == AddressivityVerdict.CONVERSATION_CONTINUITY
    assert decision_unknown.is_directed is True

from innobrain.conversation.language import TurnLanguage, decide_turn_language


def test_arabic_turn_selects_egyptian_arabic_response() -> None:
    decision = decide_turn_language("إيه ميعاد الـ Main Stage؟")

    assert decision.detected is TurnLanguage.MIXED
    assert decision.response is TurnLanguage.AR_EG


def test_english_turn_selects_english_response() -> None:
    decision = decide_turn_language("Where is the main stage?")

    assert decision.detected is TurnLanguage.EN
    assert decision.response is TurnLanguage.EN


def test_language_switch_and_explicit_requests_override_prior_style() -> None:
    assert decide_turn_language("Where is the entrance?", prior="ar-EG").response is TurnLanguage.EN
    assert (
        decide_turn_language("answer me in English", prior="ar-EG").response
        is TurnLanguage.EN
    )
    assert (
        decide_turn_language("رد عليا بالعربي", prior="en").response
        is TurnLanguage.AR_EG
    )


def test_provider_metadata_is_preferred_over_script_fallback_when_unambiguous() -> None:
    decision = decide_turn_language(
        "Main Stage",
        provider_language="en-US",
        prior="ar-EG",
    )

    assert decision.detected is TurnLanguage.EN
    assert decision.source == "provider"

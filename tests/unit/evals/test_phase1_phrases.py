from pathlib import Path

import yaml


PHRASES_PATH = (
    Path(__file__).resolve().parents[3] / "evals" / "audio" / "phase1_egyptian_phrases.yaml"
)


def test_phase1_fixture_is_egyptian_arabic_and_has_expected_cases() -> None:
    fixture = yaml.safe_load(PHRASES_PATH.read_text(encoding="utf-8"))

    assert fixture["language"] == "ar-EG"
    assert fixture["purpose"] == "phase1_laptop_audio_validation"
    assert len(fixture["phrases"]) == 8
    assert {phrase["id"] for phrase in fixture["phrases"]} == {
        "greeting",
        "event_schedule",
        "session_time",
        "registration",
        "hesitation",
        "correction",
        "location",
        "long_natural",
    }
    assert all(phrase["text"].strip() for phrase in fixture["phrases"])

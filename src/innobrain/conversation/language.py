import re
from dataclasses import dataclass
from enum import StrEnum


class TurnLanguage(StrEnum):
    AR_EG = "ar-EG"
    EN = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LanguageDecision:
    detected: TurnLanguage
    response: TurnLanguage
    explicit: bool = False
    source: str = "fallback"


_ARABIC_LETTERS = re.compile(r"[\u0600-\u06ff]")
_LATIN_LETTERS = re.compile(r"[A-Za-z]")
_ENGLISH_REQUEST = re.compile(
    r"\b(?:answer|respond|reply|speak|talk)\b.{0,24}\b(?:in\s+)?english\b",
    re.IGNORECASE,
)
_ARABIC_REQUEST = re.compile(
    r"(?:بالعربي|بالعربى|عربي|عربى|بالمصري|بالمصرى|\barabic\b)",
    re.IGNORECASE,
)


def normalize_provider_language(value: str | None) -> TurnLanguage:
    if not value:
        return TurnLanguage.UNKNOWN
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"mixed", "multi", "multilingual"}:
        return TurnLanguage.MIXED
    if normalized.startswith("ar"):
        return TurnLanguage.AR_EG
    if normalized.startswith("en"):
        return TurnLanguage.EN
    return TurnLanguage.UNKNOWN


def decide_turn_language(
    text: str,
    *,
    provider_language: str | None = None,
    prior: str | TurnLanguage = TurnLanguage.AR_EG,
) -> LanguageDecision:
    """Choose a response language using metadata, explicit requests, then text signals.

    Script balance is only a final fallback. Provider metadata and explicit user intent
    take precedence, so the production contract is not an ASCII-vs-Arabic detector.
    """
    if _ENGLISH_REQUEST.search(text):
        return LanguageDecision(TurnLanguage.EN, TurnLanguage.EN, True, "explicit")
    if _ARABIC_REQUEST.search(text):
        return LanguageDecision(TurnLanguage.AR_EG, TurnLanguage.AR_EG, True, "explicit")

    provider = normalize_provider_language(provider_language)
    has_arabic = bool(_ARABIC_LETTERS.search(text))
    has_latin = bool(_LATIN_LETTERS.search(text))
    if provider is TurnLanguage.MIXED or (has_arabic and has_latin):
        return LanguageDecision(TurnLanguage.MIXED, TurnLanguage.AR_EG, False, "mixed")
    if provider in {TurnLanguage.AR_EG, TurnLanguage.EN}:
        return LanguageDecision(provider, provider, False, "provider")
    if has_arabic:
        return LanguageDecision(TurnLanguage.AR_EG, TurnLanguage.AR_EG, False, "script")
    if has_latin:
        return LanguageDecision(TurnLanguage.EN, TurnLanguage.EN, False, "script")

    prior_language = normalize_provider_language(str(prior))
    if prior_language in {TurnLanguage.AR_EG, TurnLanguage.EN}:
        return LanguageDecision(prior_language, prior_language, False, "prior")
    return LanguageDecision(TurnLanguage.UNKNOWN, TurnLanguage.AR_EG, False, "default")


__all__ = [
    "LanguageDecision",
    "TurnLanguage",
    "decide_turn_language",
    "normalize_provider_language",
]

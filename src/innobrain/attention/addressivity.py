import re

from innobrain.attention.contracts import AddressivityDecision, AddressivityVerdict
from innobrain.attention.presence import PresenceState

_WAKE_PATTERNS: tuple[str, ...] = (
    "heyino",
    "hey inno",
    "hey-ino",
    "hayino",
    "heyno",
    "هينو",
    "يا هينو",
    "هاي هينو",
    "هينوو",
)

_DIRECTED_CUES: tuple[str, ...] = (
    # English cues
    "tell me",
    "listen",
    "look here",
    "look",
    "hey",
    "can you",
    "could you",
    "excuse me",
    "are you there",
    "help me",
    "what about",
    "show me",
    "how about",
    # Egyptian Arabic romanized
    "esma3",
    "isma3",
    "shouf",
    "shof",
    "enta ma3aya",
    "enta sam3ni",
    "kallimni",
    "ya basha",
    "boss",
    "2ooli",
    "2oli",
    "fein",
    "eh da",
    "khallik ma3aya",
    "ma3aya",
    "ya fannem",
    # Egyptian Arabic script
    "اسمع",
    "شوف",
    "انت معايا",
    "سامعني",
    "انت سامعني",
    "كلمني",
    "يا باشا",
    "بص",
    "قولي",
    "فين",
    "ايه ده",
    "خليك معايا",
    "معايا",
    "يا فندم",
)

_CONTINUITY_CUES: tuple[str, ...] = (
    # English affirmative / negative / navigational
    "yes",
    "yeah",
    "yep",
    "sure",
    "ok",
    "okay",
    "alright",
    "correct",
    "right",
    "of course",
    "definitely",
    "go ahead",
    "sounds good",
    "please",
    "thanks",
    "thank you",
    "no",
    "nope",
    "cancel",
    "never mind",
    "stop",
    "next",
    "previous",
    "more",
    "repeat",
    "again",
    "continue",
    "what else",
    "one",
    "two",
    "three",
    "four",
    "five",
    "first",
    "second",
    "third",
    # Egyptian Arabic romanized
    "ah",
    "aywa",
    "tamam",
    "mashy",
    "akeed",
    "sah",
    "aywa keda",
    "tab3an",
    "kammel",
    "shukran",
    "la",
    "la2",
    "laa",
    "khalas",
    "balash",
    "kefaya",
    "bas",
    "tany",
    "eh tany",
    "ba3deen",
    "w ba3den",
    "el awel",
    "el tany",
    "wahed",
    "etneen",
    "talata",
    # Egyptian Arabic script
    "اه",
    "ايوه",
    "تمام",
    "ماشي",
    "أكيد",
    "اكيد",
    "صح",
    "طبعا",
    "كمل",
    "شكرا",
    "لا",
    "لأ",
    "خلاص",
    "بلاش",
    "كفاية",
    "بس",
    "تاني",
    "ايه تاني",
    "بعدين",
    "وبعدين",
    "الأول",
    "الاول",
    "التاني",
    "واحد",
    "اتنين",
    "تلاتة",
    "تلاته",
)


def _normalize_text(text: str) -> str:
    """Normalize input text for deterministic cue matching."""
    if not text:
        return ""
    normalized = text.lower().strip()
    # Normalize Arabic alef forms
    normalized = re.sub(r"[إأآٱ]", "ا", normalized)
    # Normalize taa marbuta to haa
    normalized = re.sub(r"ة", "ه", normalized)
    # Normalize alif maqsura to yaa
    normalized = re.sub(r"ى", "ي", normalized)
    # Strip Arabic diacritics (tashkeel)
    normalized = re.sub(r"[\u064B-\u065F\u0670]", "", normalized)
    # Replace non-alphanumeric punctuation with spaces
    normalized = re.sub(r"[^\w\s\d\u0600-\u06FF]", " ", normalized)
    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


class AddressivityGate:
    """Deterministic, testable addressivity evaluation without STT or external provider calls."""

    def evaluate(
        self,
        text: str,
        expecting_reply: bool = False,
        presence: PresenceState | None = None,
    ) -> AddressivityDecision:
        normalized = _normalize_text(text)
        if not normalized:
            return AddressivityDecision(
                verdict=AddressivityVerdict.BACKGROUND_AMBIGUOUS,
                is_directed=False,
                confidence=0.0,
                reason="Empty or noise utterance",
            )

        # 1. Explicit wake detection
        for wake_phrase in _WAKE_PATTERNS:
            norm_wake = _normalize_text(wake_phrase)
            if norm_wake in normalized:
                # Extract command after wake phrase if present
                idx = normalized.find(norm_wake)
                after_wake = normalized[idx + len(norm_wake) :].strip()
                return AddressivityDecision(
                    verdict=AddressivityVerdict.EXPLICIT_WAKE,
                    is_directed=True,
                    confidence=0.98,
                    reason=f"Matched explicit wake phrase: {wake_phrase}",
                    matched_cue=wake_phrase,
                    extracted_command=after_wake,
                )

        # If user is confirmed absent, suppress non-wake cues as unaddressed background noise
        if presence == PresenceState.ABSENT:
            return AddressivityDecision(
                verdict=AddressivityVerdict.BACKGROUND_AMBIGUOUS,
                is_directed=False,
                confidence=0.1,
                reason="Presence signal indicates user is absent; unaddressed background",
            )

        # 2. Directed cues (attention-directing imperatives / addressing tokens)
        words = normalized.split()
        for cue in _DIRECTED_CUES:
            norm_cue = _normalize_text(cue)
            cue_words = norm_cue.split()
            # Check if cue exists as whole words/phrase in normalized text
            if len(cue_words) == 1:
                if cue_words[0] in words:
                    return AddressivityDecision(
                        verdict=AddressivityVerdict.DIRECTED_CUE,
                        is_directed=True,
                        confidence=0.9,
                        reason=f"Matched directed cue: {cue}",
                        matched_cue=cue,
                        extracted_command=normalized,
                    )
            else:
                if norm_cue in normalized:
                    return AddressivityDecision(
                        verdict=AddressivityVerdict.DIRECTED_CUE,
                        is_directed=True,
                        confidence=0.9,
                        reason=f"Matched multi-word directed cue: {cue}",
                        matched_cue=cue,
                        extracted_command=normalized,
                    )

        # 3. Conversation continuity / direct responses (answers, confirmations, selections)
        # Direct responses are concise (<= 3 words) or lead with a continuity cue.
        for cue in _CONTINUITY_CUES:
            norm_cue = _normalize_text(cue)
            cue_words = norm_cue.split()
            if len(cue_words) == 1:
                cue_word = cue_words[0]
                if cue_word in words:
                    # If sentence is short (<= 3 words) or starts with the continuity word
                    if len(words) <= 3 or words[0] == cue_word:
                        return AddressivityDecision(
                            verdict=AddressivityVerdict.CONVERSATION_CONTINUITY,
                            is_directed=True,
                            confidence=0.85,
                            reason=f"Matched conversation continuity cue: {cue}",
                            matched_cue=cue,
                            extracted_command=normalized,
                        )
            else:
                if norm_cue in normalized:
                    # Multi-word cue matches if utterance is short or starts with cue
                    if len(words) <= len(cue_words) + 2 or normalized.startswith(norm_cue):
                        return AddressivityDecision(
                            verdict=AddressivityVerdict.CONVERSATION_CONTINUITY,
                            is_directed=True,
                            confidence=0.85,
                            reason=f"Matched multi-word conversation continuity cue: {cue}",
                            matched_cue=cue,
                            extracted_command=normalized,
                        )

        # 4. Background / Ambiguous speech
        return AddressivityDecision(
            verdict=AddressivityVerdict.BACKGROUND_AMBIGUOUS,
            is_directed=False,
            confidence=0.2,
            reason="Unaddressed background speech or side conversation",
        )

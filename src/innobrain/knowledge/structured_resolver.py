import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from .normalize import normalize_arabic_retrieval
from .repository import EventRepository


class ExactIntent(StrEnum):
    EVENT_DATE = "event_date"
    SESSION_TIME = "session_time"
    SESSION_LOCATION = "session_location"
    SPEAKER_SESSIONS = "speaker_sessions"
    BOOTH_LOCATION = "booth_location"


@dataclass(frozen=True, slots=True)
class ExactAnswer:
    intent: ExactIntent
    text: str
    evidence_ids: tuple[str, ...]
    entities: tuple[str, ...]


def _has_any(query: str, terms: tuple[str, ...]) -> bool:
    return any(term in query for term in terms)


def _format_time(value: str, language: str = "ar-EG") -> str:
    time = datetime.fromisoformat(value).strftime("%H:%M")
    if language.startswith("en"):
        return time
    hour = int(time[:2])
    period = "صباحًا" if hour < 12 else "مساءً"
    return f"{time} {period}"


class StructuredResolver:
    def __init__(self, repository: EventRepository, *, event_id: str) -> None:
        self.repository = repository
        self.event_id = event_id

    def resolve(
        self,
        query: str,
        *,
        active_entities: Sequence[str] = (),
    ) -> ExactAnswer | None:
        normalized_query = normalize_arabic_retrieval(query)
        if not normalized_query:
            return None

        booth = self._unique_entity("booths", "normalized_name", normalized_query)
        if booth is None and _has_any(
            normalized_query,
            ("\u0628\u0648\u062b", "booth"),
        ):
            booth = self._one_active_row("booths", active_entities)
        if booth is not None and _has_any(
            normalized_query,
            ("بوث", "booth", "فين", "مكان", "where", "located"),
        ):
            location = self.repository.get_location(booth["location_id"])
            if location is None:
                return None
            return ExactAnswer(
                intent=ExactIntent.BOOTH_LOCATION,
                text=f"{booth['name']} موجود في {location['name']}.",
                evidence_ids=(f"booth:{booth['id']}", f"location:{location['id']}"),
                entities=(str(booth["id"]), str(location["id"])),
            )

        session = self._unique_entity("sessions", "normalized_title", normalized_query)
        speaker = self._unique_entity("speakers", "normalized_name", normalized_query)
        asks_time = _has_any(
            normalized_query,
            (
                "\u0627\u0644\u0633\u0627\u0639\u0629",
                "\u0645\u064a\u0639\u0627\u062f",
                "\u0645\u0639\u0627\u062f",
                "\u0627\u0645\u062a\u0649",
                "\u0645\u062a\u0649",
                "\u0648\u0642\u062a",
                "when",
                "time",
                "starts",
            ),
        )
        asks_location = _has_any(
            normalized_query,
            (
                "\u0641\u064a\u0646",
                "\u0645\u0643\u0627\u0646",
                "location",
                "\u0642\u0627\u0639\u0629",
                "where",
                "located",
            ),
        )
        if session is None and (asks_time or asks_location):
            candidates = self._active_rows("sessions", active_entities)
            if len(candidates) == 1:
                session = candidates[0]
        if speaker is None and _has_any(
            normalized_query,
            (
                "\u0628\u064a\u062a\u0643\u0644\u0645",
                "\u0628\u062a\u062a\u0643\u0644\u0645",
                "session",
                "sessions",
                "speaks",
                "speaking",
                "talks",
                "when",
                "where",
            ),
        ):
            speaker = self._one_active_row("speakers", active_entities)
        if speaker is not None and _has_any(
            normalized_query,
            (
                "بيتكلم",
                "بتتكلم",
                "بيتكل",
                "جلس",
                "session",
                "sessions",
                "speaks",
                "speaking",
                "talks",
                "when",
                "where",
                "امتى",
                "متى",
                "فين",
            ),
        ):
            sessions = self.repository.sessions_for_speaker(speaker["id"])
            if not sessions:
                return None
            parts: list[str] = []
            evidence_ids = [f"speaker:{speaker['id']}"]
            entities = [str(speaker["id"])]
            for item in sessions:
                location = self.repository.get_location(item["location_id"])
                if location is None:
                    return None
                parts.append(
                    f"{item['title']} الساعة {_format_time(item['starts_at'])} "
                    f"في {location['name']}"
                )
                evidence_ids.extend((f"session:{item['id']}", f"location:{location['id']}"))
                entities.extend((str(item["id"]), str(location["id"])))
            return ExactAnswer(
                intent=ExactIntent.SPEAKER_SESSIONS,
                text=f"{speaker['name']} بيتكلم في " + "؛ ".join(parts) + ".",
                evidence_ids=tuple(evidence_ids),
                entities=tuple(entities),
            )

        if session is not None:
            location = self.repository.get_location(session["location_id"])
            if location is None:
                return None
            if _has_any(
                normalized_query,
                ("فين", "مكان", "location", "قاعة", "where", "located"),
            ):
                return ExactAnswer(
                    intent=ExactIntent.SESSION_LOCATION,
                    text=f"Session {session['title']} موجودة في {location['name']}.",
                    evidence_ids=(f"session:{session['id']}", f"location:{location['id']}"),
                    entities=(str(session["id"]), str(location["id"])),
                )
            if _has_any(
                normalized_query,
                (
                    "الساعة",
                    "ميعاد",
                    "معاد",
                    "امتى",
                    "متى",
                    "وقت",
                    "when",
                    "time",
                    "starts",
                ),
            ):
                return ExactAnswer(
                    intent=ExactIntent.SESSION_TIME,
                    text=f"Session {session['title']} الساعة {_format_time(session['starts_at'])}.",
                    evidence_ids=(f"session:{session['id']}",),
                    entities=(str(session["id"]),),
                )

        if _has_any(normalized_query, ("الايفنت", "الحدث", "event")) and _has_any(
            normalized_query,
            ("امتى", "متى", "تاريخ", "date", "يوم", "when"),
        ):
            event = self.repository.get_event_meta(self.event_id)
            if event is None:
                return None
            return ExactAnswer(
                intent=ExactIntent.EVENT_DATE,
                text=f"الـevent يوم {event['event_date']} في {event['venue_name']}.",
                evidence_ids=(f"event:{event['id']}",),
                entities=(str(event["id"]),),
            )
        return None

    def localize(self, answer: ExactAnswer, language: str) -> ExactAnswer:
        """Render the same structured fact in the requested response language."""
        if not language.startswith("en"):
            return answer

        if answer.intent is ExactIntent.EVENT_DATE:
            event = self.repository.get_event_meta(self.event_id)
            if event is not None:
                return replace(
                    answer,
                    text=f"The event is on {event['event_date']} at {event['venue_name']}.",
                )

        if answer.intent is ExactIntent.BOOTH_LOCATION and len(answer.entities) >= 2:
            booth = self._row("booths", answer.entities[0])
            location = self.repository.get_location(answer.entities[1])
            if booth is not None and location is not None:
                return replace(
                    answer,
                    text=f"{booth['name']} is located at {location['name']}.",
                )

        if answer.intent in {ExactIntent.SESSION_LOCATION, ExactIntent.SESSION_TIME}:
            session = self._row("sessions", answer.entities[0]) if answer.entities else None
            if session is not None:
                if answer.intent is ExactIntent.SESSION_LOCATION:
                    location = self.repository.get_location(session["location_id"])
                    if location is not None:
                        return replace(
                            answer,
                            text=f"Session {session['title']} is located at {location['name']}.",
                        )
                return replace(
                    answer,
                    text=(
                        f"Session {session['title']} starts at "
                        f"{_format_time(session['starts_at'], 'en')}."
                    ),
                )

        if answer.intent is ExactIntent.SPEAKER_SESSIONS and answer.entities:
            speaker = self._row("speakers", answer.entities[0])
            if speaker is not None:
                sessions = self.repository.sessions_for_speaker(speaker["id"])
                parts: list[str] = []
                for session in sessions:
                    location = self.repository.get_location(session["location_id"])
                    if location is None:
                        return answer
                    parts.append(
                        f"{session['title']} at {_format_time(session['starts_at'], 'en')} "
                        f"at {location['name']}"
                    )
                if parts:
                    return replace(
                        answer,
                        text=f"{speaker['name']} is speaking at " + "; ".join(parts) + ".",
                    )

        return answer

    def _row(self, table: str, row_id: str):
        return self.repository.conn.execute(
            f"SELECT * FROM {table} WHERE event_id = ? AND id = ?",
            (self.event_id, row_id),
        ).fetchone()

    def _unique_entity(self, table: str, column: str, normalized_query: str):
        rows = self.repository.conn.execute(
            f"SELECT * FROM {table} WHERE event_id = ? ORDER BY id",
            (self.event_id,),
        ).fetchall()
        query_tokens = set(re.findall(r"[^\W_]+", normalized_query, flags=re.UNICODE))
        generic_tokens = {"dr", "the", "session", "booth"}
        matches = []
        for row in rows:
            candidate = row[column]
            candidate_tokens = set(re.findall(r"[^\W_]+", candidate, flags=re.UNICODE))
            meaningful_tokens = candidate_tokens - generic_tokens
            if candidate in normalized_query or meaningful_tokens <= query_tokens:
                matches.append(row)
        return matches[0] if len(matches) == 1 else None

    def _active_rows(self, table: str, active_entities: Sequence[str]):
        entity_ids = tuple(dict.fromkeys(str(entity) for entity in active_entities))
        if not entity_ids:
            return []
        placeholders = ",".join("?" for _ in entity_ids)
        return self.repository.conn.execute(
            f"SELECT * FROM {table} WHERE event_id = ? AND id IN ({placeholders}) ORDER BY id",
            (self.event_id, *entity_ids),
        ).fetchall()

    def _one_active_row(self, table: str, active_entities: Sequence[str]):
        rows = self._active_rows(table, active_entities)
        return rows[0] if len(rows) == 1 else None

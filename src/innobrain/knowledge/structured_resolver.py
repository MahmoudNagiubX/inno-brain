import re
from dataclasses import dataclass
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


def _format_time(value: str) -> str:
    time = datetime.fromisoformat(value).strftime("%H:%M")
    hour = int(time[:2])
    period = "صباحًا" if hour < 12 else "مساءً"
    return f"{time} {period}"


class StructuredResolver:
    def __init__(self, repository: EventRepository, *, event_id: str) -> None:
        self.repository = repository
        self.event_id = event_id

    def resolve(self, query: str) -> ExactAnswer | None:
        normalized_query = normalize_arabic_retrieval(query)
        if not normalized_query:
            return None

        booth = self._unique_entity("booths", "normalized_name", normalized_query)
        if booth is not None and _has_any(normalized_query, ("بوث", "booth", "فين", "مكان")):
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
        if speaker is not None and _has_any(
            normalized_query,
            ("بيتكلم", "بتتكلم", "بيتكل", "جلس", "session", "امتى", "متى", "فين"),
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
            if _has_any(normalized_query, ("فين", "مكان", "location", "قاعة")):
                return ExactAnswer(
                    intent=ExactIntent.SESSION_LOCATION,
                    text=f"Session {session['title']} موجودة في {location['name']}.",
                    evidence_ids=(f"session:{session['id']}", f"location:{location['id']}"),
                    entities=(str(session["id"]), str(location["id"])),
                )
            if _has_any(normalized_query, ("الساعة", "ميعاد", "معاد", "امتى", "متى", "وقت")):
                return ExactAnswer(
                    intent=ExactIntent.SESSION_TIME,
                    text=f"Session {session['title']} الساعة {_format_time(session['starts_at'])}.",
                    evidence_ids=(f"session:{session['id']}",),
                    entities=(str(session["id"]),),
                )

        if _has_any(normalized_query, ("الايفنت", "الحدث", "event")) and _has_any(
            normalized_query, ("امتى", "متى", "تاريخ", "date", "يوم")
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

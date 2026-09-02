import re
import sqlite3
from collections.abc import Sequence
from datetime import datetime

_RETRIEVAL_STOPWORDS = frozenset(
    {
        "and",
        "event",
        "the",
        "what",
        "where",
        "when",
        "is",
        "الايفنت",
        "الحدث",
        "امتى",
        "متى",
        "فين",
        "منين",
        "مين",
        "ايه",
        "هو",
        "هي",
    }
)


def _safe_fts_query(query: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[^\W_]+", query, flags=re.UNICODE)
        if token.casefold() not in {"and", "or", "not", "near"}
        and token.casefold() not in _RETRIEVAL_STOPWORDS
    ]
    expressions = []
    for token in tokens:
        escaped = token.replace(chr(34), chr(34) * 2)
        variants = [f'"{escaped}"']
        if not token.startswith("ال"):
            variants.append(f'"ال{escaped}"')
        expressions.append(f"({' OR '.join(variants)})")
    return " AND ".join(expressions)


class EventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_event_meta(self, event_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM event_meta WHERE id = ?",
            (event_id,),
        ).fetchone()

    def find_session_by_name(self, event_id: str, normalized_query: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM sessions
                WHERE event_id = ?
                  AND (normalized_title = ? OR instr(normalized_title, ?) > 0)
                ORDER BY id
                """,
                (event_id, normalized_query, normalized_query),
            )
        )

    def find_speaker_by_name(self, event_id: str, normalized_query: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM speakers
                WHERE event_id = ?
                  AND (normalized_name = ? OR instr(normalized_name, ?) > 0)
                ORDER BY id
                """,
                (event_id, normalized_query, normalized_query),
            )
        )

    def find_booth_by_name(self, event_id: str, normalized_query: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM booths
                WHERE event_id = ?
                  AND (normalized_name = ? OR instr(normalized_name, ?) > 0)
                ORDER BY id
                """,
                (event_id, normalized_query, normalized_query),
            )
        )

    def sessions_for_speaker(self, speaker_id: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT sessions.*
                FROM sessions
                JOIN session_speakers ON session_speakers.session_id = sessions.id
                WHERE session_speakers.speaker_id = ?
                ORDER BY sessions.starts_at, sessions.id
                """,
                (speaker_id,),
            )
        )

    def speakers_for_session(self, session_id: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT speakers.*
                FROM speakers
                JOIN session_speakers ON session_speakers.speaker_id = speakers.id
                WHERE session_speakers.session_id = ?
                ORDER BY speakers.id
                """,
                (session_id,),
            )
        )

    def get_location(self, location_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM locations WHERE id = ?",
            (location_id,),
        ).fetchone()

    def lexical_search(
        self,
        event_id: str,
        normalized_query: str,
        limit: int,
        reference_time: datetime | str | None = None,
    ) -> list[sqlite3.Row]:
        if limit < 1:
            return []
        safe_query = _safe_fts_query(normalized_query)
        if not safe_query:
            return []
        query = """
            SELECT chunks.*, bm25(chunks_fts) AS lexical_rank_score
            FROM chunks_fts
            JOIN chunks ON chunks.id = chunks_fts.rowid
            WHERE chunks.event_id = ? AND chunks_fts MATCH ?
        """
        parameters: list[object] = [event_id, safe_query]
        if reference_time is not None:
            reference_value = (
                reference_time.isoformat()
                if isinstance(reference_time, datetime)
                else reference_time
            )
            query += """
              AND (chunks.valid_from IS NULL OR chunks.valid_from <= ?)
              AND (chunks.valid_until IS NULL OR chunks.valid_until > ?)
            """
            parameters.extend([reference_value, reference_value])
        query += """
            ORDER BY lexical_rank_score,
                CASE chunks.authority_level
                    WHEN 'official' THEN 0
                    WHEN 'approved' THEN 1
                    WHEN 'reference' THEN 2
                    WHEN 'marketing' THEN 3
                    ELSE 4
                END,
                chunks.id
            LIMIT ?
        """
        parameters.append(limit)
        return list(self.conn.execute(query, tuple(parameters)))

    def chunks_by_ids(
        self,
        chunk_ids: Sequence[int],
        reference_time: datetime | str | None = None,
    ) -> list[sqlite3.Row]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        query = f"SELECT * FROM chunks WHERE id IN ({placeholders})"
        parameters: list[object] = list(chunk_ids)
        if reference_time is not None:
            reference_value = (
                reference_time.isoformat()
                if isinstance(reference_time, datetime)
                else reference_time
            )
            query += (
                " AND (valid_from IS NULL OR valid_from <= ?)"
                " AND (valid_until IS NULL OR valid_until > ?)"
            )
            parameters.extend([reference_value, reference_value])
        rows = self.conn.execute(
            query,
            tuple(parameters),
        ).fetchall()
        by_id = {row["id"]: row for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

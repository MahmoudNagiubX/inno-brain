"""Rebuildable sqlite-vec storage; canonical chunk text remains in SQLite tables.

The vec0 index is derived and must be rebuilt on the target platform instead of
being copied across Windows and later Raspberry Pi deployments.
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .database import load_sqlite_vec


@dataclass(frozen=True, slots=True)
class VectorHit:
    rowid: int
    distance: float


def serialize_f32(vector: Sequence[float], *, dimension: int = 384) -> bytes:
    arr = np.asarray(vector, dtype=np.float32)
    if arr.shape != (dimension,):
        raise ValueError(f"expected an embedding with shape ({dimension},), got {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError("embedding contains non-finite values")
    return arr.tobytes()


class VectorStore:
    def __init__(self, conn: sqlite3.Connection, *, dimension: int = 384) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        self.conn = conn
        self.dimension = dimension
        load_sqlite_vec(conn)
        version = conn.execute("SELECT vec_version()").fetchone()[0]
        if version not in {"0.1.9", "v0.1.9"}:
            raise RuntimeError(f"sqlite-vec 0.1.9 is required, found {version}")
        self._create_table()

    def _create_table(self) -> None:
        self.conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
            f"USING vec0(embedding float[{self.dimension}])"
        )
        self.conn.commit()

    def rebuild(self, rows: Sequence[tuple[int, Sequence[float]]]) -> None:
        """Drop and recreate only the derived index inside one transaction."""

        with self.conn:
            self.conn.execute("DROP TABLE IF EXISTS vec_chunks")
            self._create_table_without_commit()
            self.conn.executemany(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                [
                    (rowid, serialize_f32(vector, dimension=self.dimension))
                    for rowid, vector in rows
                ],
            )

    def _create_table_without_commit(self) -> None:
        self.conn.execute(
            f"CREATE VIRTUAL TABLE vec_chunks USING vec0(embedding float[{self.dimension}])"
        )

    def search(self, vector: Sequence[float], limit: int) -> list[VectorHit]:
        if limit < 1:
            return []
        rows = self.conn.execute(
            """
            SELECT rowid, distance
            FROM vec_chunks
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (serialize_f32(vector, dimension=self.dimension), limit),
        )
        return [VectorHit(rowid=int(row[0]), distance=float(row[1])) for row in rows]

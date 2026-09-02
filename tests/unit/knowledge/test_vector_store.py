import sqlite3

import pytest

from innobrain.knowledge.vector_store import VectorStore, serialize_f32


def test_serialize_f32_validates_dimension() -> None:
    assert len(serialize_f32([1, 2, 3, 4], dimension=4)) == 16
    with pytest.raises(ValueError):
        serialize_f32([1, 2], dimension=4)


def test_vector_store_rebuilds_derived_index_and_searches_nearest() -> None:
    conn = sqlite3.connect(":memory:")
    store = VectorStore(conn, dimension=4)
    conn.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, text TEXT)")
    conn.executemany("INSERT INTO chunks(id, text) VALUES (?, ?)", [(1, "near"), (2, "far")])
    conn.commit()

    store.rebuild([(1, [1, 0, 0, 0]), (2, [0, 1, 0, 0])])
    hits = store.search([1, 0, 0, 0], 2)

    assert [hit.rowid for hit in hits] == [1, 2]
    assert hits[0].distance == pytest.approx(0.0)
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 2

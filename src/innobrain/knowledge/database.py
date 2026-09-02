import sqlite3
from pathlib import Path


def connect_event_db(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def ensure_sqlite_features(conn: sqlite3.Connection) -> None:
    """Verify the runtime can create and query the FTS5 feature we require."""

    options = {row[0] for row in conn.execute("PRAGMA compile_options")}
    if any("ENABLE_FTS5" in item for item in options):
        return
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._innobrain_fts_probe USING fts5(value)")
        conn.execute("DROP TABLE temp._innobrain_fts_probe")
    except sqlite3.OperationalError as exc:
        raise RuntimeError("SQLite FTS5 is required for event retrieval") from exc


def load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load the pinned sqlite-vec extension for derived vector-index tables."""

    import sqlite_vec

    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)


def initialize_schema(conn: sqlite3.Connection) -> None:
    ensure_sqlite_features(conn)
    load_sqlite_vec(conn)
    schema_path = Path(__file__).with_name("schema.sql")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()

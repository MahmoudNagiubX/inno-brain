CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_meta (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    venue_name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT '0.0.0',
    client_id TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    level TEXT,
    zone TEXT,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS speakers (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS session_speakers (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    speaker_id TEXT NOT NULL REFERENCES speakers(id),
    PRIMARY KEY (session_id, speaker_id)
);

CREATE TABLE IF NOT EXISTS booths (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    checksum TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT '0.0.0',
    client_id TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    authority_level TEXT NOT NULL DEFAULT 'reference',
    valid_from TEXT,
    valid_until TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    event_id TEXT NOT NULL REFERENCES event_meta(id),
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    event_version TEXT NOT NULL DEFAULT '0.0.0',
    client_id TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    authority_level TEXT NOT NULL DEFAULT 'reference',
    valid_from TEXT,
    valid_until TEXT,
    UNIQUE(document_id, chunk_index)
);

INSERT OR IGNORE INTO schema_meta(key, value)
VALUES ('database_schema_version', '2');

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    normalized_text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, normalized_text) VALUES (new.id, new.normalized_text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, normalized_text)
    VALUES ('delete', old.id, old.normalized_text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE OF normalized_text ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, normalized_text)
    VALUES ('delete', old.id, old.normalized_text);
    INSERT INTO chunks_fts(rowid, normalized_text) VALUES (new.id, new.normalized_text);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
    embedding float[384]
);

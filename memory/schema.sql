CREATE TABLE IF NOT EXISTS persons(
    id TEXT PRIMARY KEY,
    name TEXT,
    embedding BLOB NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT REFERENCES persons(id),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    transcript TEXT,
    vision_emotion TEXT,
    vision_confidence REAL,
    text_emotion TEXT,
    text_confidence REAL,
    voice_emotion TEXT,
    voice_confidence REAL
);
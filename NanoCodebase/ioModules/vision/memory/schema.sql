-- embedding is NOT NULL for schema simplicity even though the current
-- identity backend (facial_recognition/, YuNet+SFace) doesn't use this
-- column -- its embeddings live in facial_recognition/cache/embeddings.npz
-- instead. identity_backend.py's enroll() stores b'' as a placeholder.
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
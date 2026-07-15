CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  transcript TEXT,
  vision_emotion TEXT,
  text_emotion TEXT,
  voice_emotion TEXT
);
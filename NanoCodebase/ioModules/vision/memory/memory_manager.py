from memory.database import get_connection


def save_session(person_id, transcript, vision_emotion, vision_confidence, text_emotion, text_confidence, voice_emotion, voice_confidence):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessions
        (person_id, transcript, vision_emotion, vision_confidence, text_emotion,text_confidence, voice_emotion, voice_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (person_id, transcript, vision_emotion, vision_confidence, text_emotion, text_confidence, voice_emotion, voice_confidence))

    conn.commit()
    conn.close()


def get_recent_sessions(person_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, transcript, vision_emotion, vision_confidence, text_emotion, text_confidence, voice_emotion, voice_confidence
        FROM sessions
        WHERE person_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """,
    (person_id, limit))

    results = cursor.fetchall()
    conn.close()

    return results
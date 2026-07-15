from memory.database import get_connection


def save_session(person_id, transcript, vision_emotion, text_emotion, voice_emotion):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessions
        (person_id, transcript, vision_emotion, text_emotion, voice_emotion)
        VALUES (?, ?, ?, ?, ?)
    """,
    (person_id, transcript, vision_emotion, text_emotion, voice_emotion))

    conn.commit()
    conn.close()


def get_recent_sessions(person_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, transcript, vision_emotion, text_emotion, voice_emotion
        FROM sessions
        WHERE person_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """,
    (person_id, limit))

    results = cursor.fetchall()
    conn.close()

    return results
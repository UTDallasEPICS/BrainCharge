from memory.memory_manager import save_session, get_recent_sessions
from memory.session_summary import record_session, summarize_session, summarize_recent_sessions


session_readings = []

record_session(session_readings, "Positive", 0.72, "vision")
record_session(session_readings, "Neutral", 0.60, "vision")
record_session(session_readings, "Sad", 0.65, "text")
record_session(session_readings, "Anxious", 0.99, "voice")
record_session(session_readings, "Anxious", 0.71, "voice")

# --- when the conversation/session ends ---
summary = summarize_session(session_readings)
print("summary: ", summary)
print("recent history:", summarize_recent_sessions("user1"))


save_session(
    "user1",
    "I had a had a horrible day",
    summary["vision_emotion"],
    summary["vision_confidence"],
    summary["text_emotion"],
    summary["text_confidence"],
    summary["voice_emotion"],
    summary["voice_confidence"],
)

print(get_recent_sessions("user1"))
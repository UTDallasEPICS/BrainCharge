from memory.memory_manager import save_session, get_recent_sessions
from memory.session_summary import record_session, summarize_session

session_readings = []

record_session(session_readings, "Positive", 0.72, "vision")
record_session(session_readings, "Neutral", 0.60, "vision")
record_session(session_readings, "Sad", 0.65, "text")
record_session(session_readings, "Anxious", 0.58, "speech")
record_session(session_readings, "Anxious", 0.71, "speech")

# --- when the conversation/session ends ---
summary = summarize_session(session_readings)
print("summary: ", summary)

save_session(
    "user1",
    "I had a had a good day",
    summary["vision_emotion"],
    summary["text_emotion"],
    summary["speech_emotion"],
)

print(get_recent_sessions("user1"))
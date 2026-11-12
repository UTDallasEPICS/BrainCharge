from collections import Counter
from memory.memory_manager import get_recent_sessions


def record_session(sessions_readings, emotion_labels, confidence, modality):
    sessions_readings.append({
        "emotion": emotion_labels,
        "confidence": confidence,
        "modality": modality,
    })

def sessions_to_readings(saved_sessions):
    readings = []
    for session in saved_sessions:
        timestamp, transcript, vision_emotion, vision_confidence, text_emotion, text_confidence, voice_emotion, voice_confidence = session
        if vision_emotion is not None:
            readings.append({"emotion": vision_emotion, "confidence": vision_confidence, "modality": "vision"})
        if text_emotion is not None:
            readings.append({"emotion": text_emotion, "confidence": text_confidence, "modality": "text"})
        if voice_emotion is not None:
            readings.append({"emotion": voice_emotion, "confidence": voice_confidence, "modality": "voice"})
    return readings

def summarize_recent_sessions(person_id, limit = 10):
    sessions = get_recent_sessions(person_id, limit)
    sessions = sessions_to_readings(sessions)
    return summarize_session(sessions)

def summarize_modality(sessions_readings, modality):
    readings = [r for r in sessions_readings if r["modality"] == modality]
    if not readings:
        return (None, None)
    labels = [r["emotion"]for r in readings]
    common = Counter(labels).most_common(1)[0][0]#top confidence
    confidences = [r["confidence"] for r in readings if r["emotion"] == common]#list of same emotion as the top confidence emotion to find the average confidence
    average_confidence = sum(confidences) / len(confidences)#calculation for the avg confidence of top emotion

    return (common, average_confidence)

def summarize_session(sessions_readings):
    vision_emotion, vision_confidence = summarize_modality(sessions_readings, modality="vision")
    voice_emotion, voice_confidence = summarize_modality(sessions_readings, modality="voice")
    text_emotion, text_confidence = summarize_modality(sessions_readings, modality="text")
    return{
        "vision_emotion": vision_emotion,
        "vision_confidence": vision_confidence,
        "voice_emotion" : voice_emotion,
        "voice_confidence": voice_confidence,
        "text_emotion" : text_emotion,
        "text_confidence": text_confidence,
    }


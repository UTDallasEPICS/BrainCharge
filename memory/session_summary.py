from collections import Counter

def record_session(sessions_readings, emotion_labels, confidence, modality):
    sessions_readings.append({
        "emotion": emotion_labels,
        "confidence": confidence,
        "modality": modality,
    })

def summarize_modality(sessions_readings, modality):
    readings = [r for r in sessions_readings if r["modality"] == modality]
    if not readings:
        return "there is no reading data"
    labels = [r["emotion"]for r in readings]
    common = Counter(labels).most_common(1)[0][0]

    return common

def summarize_session(sessions_readings):
    return{
        "vision_emotion": summarize_modality(sessions_readings, modality="vision"),
        "text_emotion" : summarize_modality(sessions_readings, modality="text"),
        "speech_emotion" : summarize_modality(sessions_readings, modality="speech"),
    }


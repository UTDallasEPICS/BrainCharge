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


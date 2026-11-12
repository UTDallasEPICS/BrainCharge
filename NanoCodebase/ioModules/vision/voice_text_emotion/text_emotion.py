import json
import requests

from ollama_client import call_ollama

OLLAMA_MODEL = "gemma3:1b"

EMOTION_LABELS = [
    "Happy", "Sad", "Angry", "Anxious", "Overwhelmed",
    "Exhausted", "Lonely", "Frustrated", "Grief", "Guilty",
    "Hopeful", "Grateful", "Relieved", "Content", "Neutral",
]

def detect_text_emotion(transcript):
    """
       Classify the emotional content of a transcript using Ollama.
       Returns (label, confidence, description) -- all None if detection
       fails or the model's response can't be parsed/validated.
       """
    prompt = (
        "Classify the primary emotion expressed in the following statement, spoken by "
        "a caregiver to a companion robot. "
        f"Choose exactly one label from this list: {EMOTION_LABELS}\n\n"
        "Respond ONLY with valid JSON in this exact format:\n"
        '{"emotion": "<one label from the list>", "confidence": <number between 0 and 1>, '
        '"description": "<a short phrase capturing the specific nuance>"}\n\n'
        f"Statement: {transcript}"
    )

    try:
        summary_text = call_ollama(prompt, model=OLLAMA_MODEL, json_mode=True, timeout=90)
        parsed_summary = json.loads(summary_text)
        summary_emotion = parsed_summary.get("emotion")
        summary_description = parsed_summary.get("description", "")

        # json_mode only guarantees valid JSON syntax, not that the fields we
        # asked for actually show up -- on junk input (e.g. whisper's
        # "[BLANK_AUDIO]" placeholder) the model sometimes omits "confidence"
        # entirely, or writes it as a quoted string ("0.9") instead of a
        # number. Either way, treat that as a failed detection rather than
        # crashing or fabricating a default.
        raw_confidence = parsed_summary.get("confidence")
        if raw_confidence is None:
            return (None, None, None)
        summary_confidence = float(raw_confidence)

        if summary_emotion in EMOTION_LABELS:
            return (summary_emotion, summary_confidence, summary_description)
        else:
            return (None, None, None)
    except requests.exceptions.Timeout:
        print("Text emotion detection timed out")
        return (None, None, None)
    except json.JSONDecodeError as e:
        print(f"Failed to parse text emotion JSON: {e}")
        return (None, None, None)
    except (ValueError, TypeError) as e:
        print(f"Text emotion response had an unusable confidence value: {e}")
        return (None, None, None)
    except Exception as e:
        print(f"Error detecting text emotion: {e}")
        return (None, None, None)

import json
import subprocess

OLLAMA_MODEL = "gemma3:4b"

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
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL, prompt], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
        summary_text = result.stdout.strip()
        if "```json" in summary_text:
            summary_text = summary_text.split("```json")[1].split("```")[0].strip()
        elif "```" in summary_text:
            summary_text = summary_text.split("```")[1].split("```")[0].strip()
        parsed_summary = json.loads(summary_text)
        summary_emotion = parsed_summary["emotion"]
        summary_confidence = parsed_summary["confidence"]
        summary_description = parsed_summary["description"]
        if summary_emotion in EMOTION_LABELS:
            return (summary_emotion, summary_confidence, summary_description)
        else:
            return (None, None, None)
    except subprocess.TimeoutExpired:
        print("Text emotion detection timed out")
        return (None, None, None)
    except json.JSONDecodeError as e:
        print(f"Failed to parse summary JSON: {e}")
        return (None, None, None)
    except Exception as e:
        print(f"Error generating summary: {e}")
        return (None, None, None)

from transformers import pipeline

# ehcalabres/wav2vec2-emotion-recognition (tried first) has a transformers
# version mismatch that leaves its classifier head unloaded -- confirmed via
# near-uniform (~12.5%) scores and non-deterministic output across identical
# runs. This model loads cleanly and gives deterministic, confident output.
MODEL_NAME = "Dpngtm/wav2vec2-emotion-recognition"

_classifier = None

def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = pipeline("audio-classification", MODEL_NAME)

    return _classifier

def detect_voice_emotion(audio_path):
    """
        Classify the tone of voice in an audio file using a pretrained
        speech-emotion-recognition model.
        Returns (label, confidence) -- (None, None) if detection fails.
        """
    try:
        classifier = _get_classifier()
        results = classifier(audio_path)
        top = results[0]
        return (top["label"], top["score"])
        
    except Exception as e:
        print(f"Error detecting voice tone: {e}")
        return (None, None)

if __name__ == "__main__":
    print(detect_voice_emotion("input.wav"))
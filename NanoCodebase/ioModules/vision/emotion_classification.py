import numpy as np
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

class EmotionClassifier:
    def __init__(self, model = "enet_b2_8"):
        self.model = HSEmotionRecognizer(model)
        self.emotion_labels = self.model.idx_to_class

    def predict_emotions(self, face, num_top_emotions: int = 3, confidence_threshold: float = 0.1):
        _, scores = self.model.predict_emotions(face, False)
        score_indices = np.argsort(scores)[::-1][:min(num_top_emotions, len(self.emotion_labels))]

        predictions = [
            {
                "emotion": self.emotion_labels[i],
                "confidence": round(float(scores[i]), 2)
            }
            for i in score_indices if scores[i] > confidence_threshold
        ]

        return predictions
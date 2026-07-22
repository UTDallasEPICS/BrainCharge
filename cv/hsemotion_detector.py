#Using hsemotion_onnx instead of just hsemotion to avoid timm version mismatch when unpickling old model checkpoint
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

class EmotionDetector:
    #initialize hsemotion detector
    def __init__(self):
        self.model = HSEmotionRecognizer(model_name="enet_b2_8")
        
    def predict(self, face):
        #model will predict emotion and the confidence of the emotion
        emotion, confidence = self.model.predict_emotions(face, logits=False)
        return emotion, confidence
"""
Facial recognition module for BrainCharge.

Standalone
----------
    python -m facial_recognition
    python -m facial_recognition.enroll --capture Alice --rebuild

Pipeline (shared frames)
------------------------
    from facial_recognition import FaceRecognitionEngine, FRConfig

    engine = FaceRecognitionEngine(FRConfig())
    engine.initialize()
    results = engine.recognize(frame_bgr)
"""

from facial_recognition.config import FRConfig
from facial_recognition.engine import FaceRecognitionEngine, Recognition

__all__ = ["FRConfig", "FaceRecognitionEngine", "Recognition"]

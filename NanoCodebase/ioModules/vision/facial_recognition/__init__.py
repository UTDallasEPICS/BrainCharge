"""
Facial recognition module for BrainCharge.

Standalone
----------
    python -m ioModules.vision.facial_recognition
    python -m ioModules.vision.facial_recognition.enroll --capture Alice --rebuild

Pipeline (shared frames)
------------------------
    from ioModules.vision.facial_recognition import FaceRecognitionEngine, FRConfig

    engine = FaceRecognitionEngine(FRConfig())
    engine.initialize()
    results = engine.recognize(frame_bgr)
"""

from .config import FRConfig
from .engine import FaceRecognitionEngine, Recognition

__all__ = ["FRConfig", "FaceRecognitionEngine", "Recognition"]

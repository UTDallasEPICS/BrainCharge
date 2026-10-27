"""
High-level vision services.
"""

import cv2
from pathlib import Path
from warnings import warn
from typing import Any

from .facial_recognition.camera import open_camera, read_latest_frame
from .facial_recognition.engine import FaceRecognitionEngine
from .emotion_classification import EmotionClassifier

FRAMES_PER_SECOND = 10
NUM_TOP_EMOTIONS = 3
EMOTIONS_CONFIDENCE_THRESHOLD = 0.1

class VisionService:
    """
    Capture and manage vision for the robot.
    """
    def __init__(self, config: dict[str, Any], opencv_models_path: Path, test_mode: bool):
        if (opencv_models_path):
            try:
                if not opencv_models_path.is_dir():
                    warn(f"""OpenCV models directory was not found: {opencv_models_path}.""")
                    return
            except ImportError:
                warn(
                    "OpenCV is not installed."
                    "Install it with: pip install opencv-python."
                )
            except Exception as error:
                warn(f"Could not initialize the OpenCV models: {error}")

        self.frames_per_second = float(config.get("frames_per_second", FRAMES_PER_SECOND))
        self.num_top_emotions = int(config.get("top_emotions", NUM_TOP_EMOTIONS))
        self.emotions_confidence_threshold = float(config.get("emotions_confidence_threshold", EMOTIONS_CONFIDENCE_THRESHOLD))

        self.engine = FaceRecognitionEngine()
        self.engine.initialize()

        self.emotion_classifier = EmotionClassifier()
        self.current_emotions = None

        self.test_mode = test_mode
        if test_mode:
            self.window = "Vision Service Test"

    """
    Start vision capture using the robot's camera.
    """
    def start_capture(self):
        try:
            self.capture = open_camera(width=1920, height=1080)
        except:
            print("Could not open camera")

        if self.test_mode:
            cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)

    """
    Capture a frame using the robot's camera, and store its inference.
    """
    def capture_frame(self, user: str = ""):
        status, bgr_frame = read_latest_frame(self.capture)
        if not status or bgr_frame is None:
            raise RuntimeError("Could not read camera capture")

        if user == "":
            if self.test_mode:
                cv2.imshow(self.window, bgr_frame)

            return

        results = self.engine.recognize(bgr_frame)
        recognition = None
        for result in results:
            if result.name == user:
                recognition = result
                break

        if recognition is None:
            return
        
        x1, y1, x2, y2 = recognition.bbox
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        face = rgb_frame[y1:y2, x1:x2]

        emotions = self.emotion_classifier.predict_emotions(
            face,
            self.num_top_emotions,
            self.emotions_confidence_threshold
        )
        self.current_emotions = emotions

        if self.test_mode:
            display = self.engine.annotate_face(bgr_frame, 
                recognition.bbox, f"{user} ({recognition.confidence:.2f}) - {emotions[0]["emotion"]}")
            cv2.imshow(self.window, display)

    """
    Return the inference of the last frame captured by the robot's camera.
    """
    def get_latest_inference(self):
        return self.current_emotions

    def delay_capture(self, delay: int):
        cv2.waitKey(delay)

    """
    Stop vision capture by the robot's camera.
    """
    def stop_capture(self):
        self.capture.release()

        if self.test_mode:
            cv2.destroyAllWindows()
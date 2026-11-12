"""
High-level vision services.
"""

import cv2
from pathlib import Path
from warnings import warn
from typing import Any, Tuple

from .facial_recognition.camera import open_camera, read_latest_frame
from .facial_recognition.engine import FaceRecognitionEngine
from .emotion_classification import EmotionClassifier
from .movement_detection.movement_controller import MovementController

from . import backend

RESOLUTION_WIDTH = 1280
RESOLUTION_HEIGHT = 720

CAPTURE_DELAY = 100
NUM_TOP_EMOTIONS = 3
EMOTIONS_CONFIDENCE_THRESHOLD = 0.1

class VisionService:
    """
    Capture and manage vision for the robot.
    """
    def __init__(self, system: str, config: dict[str, Any], opencv_models_path: Path, test_mode: bool):
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

        self._backend = backend.get(system)

        camera_config: dict[str, Any] = config.get("camera")
        emotion_classification_config: dict[str, Any] = config.get("emotion_classification")

        self.resolution_width = int(camera_config.get("resolution_width", RESOLUTION_WIDTH))
        self.resolution_height = int(camera_config.get("resolution_height", RESOLUTION_HEIGHT))
        self.capture_delay = int(camera_config.get("capture_delay", CAPTURE_DELAY))

        self.num_top_emotions = int(emotion_classification_config.get("top_emotions", NUM_TOP_EMOTIONS))
        self.emotions_confidence_threshold = float(
            emotion_classification_config.get("emotions_confidence_threshold", EMOTIONS_CONFIDENCE_THRESHOLD)
        )

        self.engine = FaceRecognitionEngine()
        self.engine.initialize()

        self.emotion_classifier = EmotionClassifier()
        self.current_emotions = None

        self.movement_controller = MovementController()
        self.current_distance = None

        self.test_mode = test_mode
        if test_mode:
            self.window = "Vision Service Test"

    """
    Start vision capture using the robot's camera.
    """
    def start_capture(self):
        try:
            self.capture = open_camera(width = self.resolution_width, height = self.resolution_height)
        except:
            print("Could not open camera")

        if self.test_mode:
            cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)

    """
    Capture a frame using the robot's camera, and store its inference.
    """
    def capture_frame(
        self,
        emotion_inference: bool = False,
        movement_inference: bool = False,
        user: str = ""
    ):
        status, bgr_frame = read_latest_frame(self.capture)
        if not status or bgr_frame is None:
            raise RuntimeError("Could not read camera capture")

        if len(user) == 0:
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

        if emotion_inference:
            self.current_emotions = self.emotion_classifier.predict_emotions(
                face,
                self.num_top_emotions,
                self.emotions_confidence_threshold
            )

        if movement_inference:
            self.current_distance = self.movement_controller.estimate_distance(
                recognition.bbox,
                bgr_frame
            )

        if self.test_mode:
            label = f"Subject: {user} ({recognition.confidence:.2f})"
            if emotion_inference:
                label += f"\nEmotion: {self.current_emotions[0]["emotion"]} ({self.current_emotions[0]["confidence"]:.2f})"
            if movement_inference:
                label += f"\nDistance: ({self.current_distance[0]:.2f} m, {self.current_distance[1]:.2f} m, {self.current_distance[2]:.2f} m)"

            display = self.engine.annotate_face(bgr_frame, recognition.bbox, label)
            cv2.imshow(self.window, display)

        cv2.waitKey(self.capture_delay)

    """
    Return the emotion inference of the last frame captured by the robot's camera.
    """
    def get_emotion_inference(self):
        return self.current_emotions

    """
    Return the movement inference of the last frame captured by the robot's camera.
    """
    def get_movement_inference(self):
        return self.current_distance

    """
    Stop vision capture by the robot's camera.
    """
    def stop_capture(self):
        self.capture.release()

        if self.test_mode:
            cv2.destroyAllWindows()
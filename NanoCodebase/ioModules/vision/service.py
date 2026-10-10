"""
High-level vision services.
"""

import cv2
from pathlib import Path
from warnings import warn

from facial_recognition.camera import open_camera, read_latest_frame
from facial_recognition.engine import FaceRecognitionEngine

class VisionService:
    """
    Capture and manage vision for the robot.
    """
    def __init__(self, opencv_models_path: Path, test_mode: bool):
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

        self.engine = FaceRecognitionEngine()
        self.engine.initialize()

        self.test_mode = test_mode
        if test_mode:
            self.window = "Vision Service Test"

    """
    Start vision capture using the robot's camera.
    """
    def start_capture(self):
        self.capture = open_camera()

        cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)

    """
    Capture and store a frame and its inference using the robot's camera.
    """
    def capture_frame(self):
        status, frame = read_latest_frame(self.capture)
        if not status or frame is None:
            raise RuntimeError("Could not read camera capture")

        results = self.engine.recognize(frame)

        if self.test_mode:
            display = self.engine.annotate(frame, results)

            cv2.putText(
                display,
                f"faces={len(results)}",
                (10, display.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow(self.window, display)

    """
    Return the last frame's inference captured by the robot's camera.
    """
    def get_latest_inference(self):
        pass

    def stop_capture(self):
        self.capture.release()

        if self.test_mode:
            cv2.destroyAllWindows()
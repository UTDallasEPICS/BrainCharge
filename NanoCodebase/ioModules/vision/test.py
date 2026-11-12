import cv2
from pathlib import Path

from .service import VisionService

models_path = Path(__file__).resolve().parent / "facial_recognition" / "models"
vision_service = VisionService({}, models_path, True)
vision_service.start_capture()

for i in range(100):
    vision_service.capture_frame("Test")
    inference = vision_service.get_latest_inference()
    print(inference)
    cv2.waitKey(100)

vision_service.stop_capture()
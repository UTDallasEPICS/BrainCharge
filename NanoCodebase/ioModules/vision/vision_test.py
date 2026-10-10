import cv2
from pathlib import Path

from service import VisionService

models_path = Path("facial_recognition", "models")
vision_service = VisionService(models_path, True)
vision_service.start_capture()

for i in range(10):
    vision_service.capture_frame()
    cv2.waitKey(1000)

vision_service.stop_capture()
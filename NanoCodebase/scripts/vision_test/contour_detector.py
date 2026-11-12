from pathlib import Path
import json
import platform

from ioModules.vision.service import VisionService

project_root = Path(__file__).resolve().parents[2]
models_path = project_root / "ioModules" / "vision" / "facial_recognition" / "models"
config_path = project_root / "userConfig.json"
with config_path.open("r", encoding="utf-8") as file:
    config = json.load(file)

vision_service = VisionService(platform.system(), config.get("vision"), models_path, True)
vision_service.start_capture()

distances = []
for i in range(100):
    vision_service.capture_frame(movement_inference = True, user = "Test")
    inference = vision_service.get_movement_inference()
    distances.append(inference)

vision_service.stop_capture()
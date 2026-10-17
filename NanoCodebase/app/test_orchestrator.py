# Component imports
from ioModules.audio import AudioService
from ioModules.vision import VisionService

# Python imports
import time
import threading
from enum import Enum
from typing import Any

class TestOrchestrator:
    def __init__(
        self,
        language: dict[str, Any],
        audio_service: AudioService,
        vision_service: VisionService,
    ) -> None:
        self.audio_service = audio_service
        self.language = language

        self.vision_service = vision_service
        self.vision_thread = None
        self.vision_thread_stop_event = threading.Event()

    def vision_thread_task(self, user: str, frames_per_second: float):
        self.vision_service.start_capture()

        if frames_per_second is None:
            interval = 1 / self.vision_service.frames_per_second
        else:
            interval = 1 / frames_per_second

        while not self.vision_thread_stop_event.is_set():
            self.vision_service.capture_frame(user)
            print(self.vision_service.get_latest_inference())

            self.vision_service.delay_capture(int(interval * 1000))

        self.vision_service.stop_capture()
        self.vision_thread_stop_event.clear()

    """
    Main control loop
    """
    def startup(self):
        self.vision_thread = threading.Thread(target = self.vision_thread_task, args = ("Test", 2))
        self.vision_thread.start()

        timer = 20
        while timer > 0:
            print(f"Time remaining: {timer} seconds")
            time.sleep(1)
            timer = timer - 1

        self.vision_thread_stop_event.set()
        self.vision_thread.join()
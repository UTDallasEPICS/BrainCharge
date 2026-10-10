"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""

# Component imports
from ioModules.audio import AudioService
from ioModules.vision import VisionService

# Python imports
import time
import threading
from enum import Enum
from typing import Any

class State(Enum):
    EXIT = -1
    SLEEPING = 0
    ACTIVE = 1

class Orchestrator:
    """Coordinate services and state transitions.

    The orchestrator owns the robot's state machine and determines when
    services should perform work. Business logic should remain within the
    individual services.
    """

    def __init__(self, language: dict[str, Any], audio_service: AudioService, vision_service: VisionService) -> None:
        self.audio_service = audio_service
        self.state = State.SLEEPING
        self.language = language

        self.wakeWord = language["wake_word"]
        self.sleepWord = language["sleep_word"]

        self.vision_service = vision_service

    def audio_service_loop(self):
        while self.state != State.EXIT:
            match self.state:
                case State.SLEEPING:
                    print("[Orchestrator-Sleep] Listening for wake word...")
                    transcript = self.audio_service.listen()

                    if transcript == "[BLANK_AUDIO]":
                        continue

                    if self.wakeWord in transcript.casefold():
                        print(f'[Orchestrator-Sleep] "{self.wakeWord}" detected.')

                        self.state = State.ACTIVE
                        self.audio_service.speak(self.language["greeting"], True)

                case State.ACTIVE:
                    print(f"\n[Orchestrator-wake] Listening")
                    transcript = self.audio_service.listen()

                    if transcript == "[BLANK_AUDIO]":
                        self.audio_service.speak(self.language["empty_response"])
                    elif self.sleepWord in transcript.casefold():
                        print(f"\n[Orchestrator-wake] Sleep word detected — ending session.")

                        self.state = State.SLEEPING
                        self.audio_service.speak(self.language["shutdown"], True)
                    else:
                        print(f"[Orchestrator-wake] Placeholder print")

    def vision_service_loop(self):
        self.vision_service.start_capture()

        while self.state != State.EXIT:
            if self.state == State.ACTIVE:
                print("Vision service running")

    def startup(self):
        """Main control loop."""
        audio_service_thread = threading.Thread(target=self.audio_service_loop)
        vision_service_thread = threading.Thread(target=self.vision_service_loop)

        audio_service_thread.start()
        vision_service_thread.start()
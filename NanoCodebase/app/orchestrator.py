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
from ioModules.webapp import DisabledWebAppEvents, Expression, RobotState, WebAppEvents

# Python imports
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

    def __init__(
        self,
        language: dict[str, Any],
        audio_service: AudioService,
        vision_service: VisionService,
        webapp: WebAppEvents | DisabledWebAppEvents,
    ) -> None:
        self.audio_service = audio_service
        self.vision_service = vision_service
        self.webapp = webapp
        self.state = State.SLEEPING
        self.language = language

        self.wakeWord = language["wake_word"]
        # Language files list several phrasings ("bye, companion" / "bye companion"); accept a single string too.
        sleep_words = language["sleep_word"]
        self.sleepWords = [sleep_words] if isinstance(sleep_words, str) else list(sleep_words)

    def _change_state(self, new_state: State) -> None:
        """Switch state and mirror it on the web app's face screen."""
        self.state = new_state
        self.webapp.send_state(RobotState.ACTIVE if new_state == State.ACTIVE else RobotState.SLEEPING)

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

                        self._change_state(State.ACTIVE)
                        self.webapp.send_expression(Expression.HAPPY)
                        self.audio_service.speak(self.language["greeting"], True)

                case State.ACTIVE:
                    print(f"\n[Orchestrator-wake] Listening")
                    self.webapp.send_expression(Expression.NEUTRAL)
                    transcript = self.audio_service.listen()

                    if transcript == "[BLANK_AUDIO]":
                        self.audio_service.speak(self.language["empty_response"])
                    elif any(word in transcript.casefold() for word in self.sleepWords):
                        print(f"\n[Orchestrator-wake] Sleep word detected — ending session.")

                        # Goodbye is said with the awake face; the face goes idle once it's done.
                        self.audio_service.speak(self.language["shutdown"], True)
                        self._change_state(State.SLEEPING)
                    else:
                        self.webapp.send_expression(Expression.THINKING)
                        print(f"[Orchestrator-wake] Placeholder print")

    def vision_service_loop(self):
        self.vision_service.start_capture()

        while self.state != State.EXIT:
            if self.state == State.ACTIVE:
                print("Vision service running")

    def startup(self):
        """Main control loop."""
        self._change_state(State.SLEEPING)

        audio_service_thread = threading.Thread(target=self.audio_service_loop, daemon=True)
        vision_service_thread = threading.Thread(target=self.vision_service_loop, daemon=True)

        audio_service_thread.start()
        vision_service_thread.start()

        # Block until the audio loop exits (Ctrl+C or State.EXIT).
        audio_service_thread.join()

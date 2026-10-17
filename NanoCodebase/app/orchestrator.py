"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""
# Component imports
from app.webapp import DisabledWebAppEvents, Expression, RobotState, WebAppEvents
from ioModules.audio import AudioService
from ioModules.vision import VisionService

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

        self.vision_thread = None
        self.vision_thread_stop_event = threading.Event()

    def _change_state(self, new_state: State) -> None:
        """Switch state and mirror it on the web app's face screen."""
        self.state = new_state
        self.webapp.send_state(RobotState.ACTIVE if new_state == State.ACTIVE else RobotState.SLEEPING)

    def vision_thread_task(self, user: str, frames_per_second: float | None = None):
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

    def startup(self):
        """Main control loop."""
        self._change_state(State.SLEEPING)

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

                        if self.vision_thread is None:
                            self.vision_thread = threading.Thread(
                                target=self.vision_thread_task,
                                args=("Test", 2),
                                daemon=True,
                            )
                            self.vision_thread.start()

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

                        if self.vision_thread is not None:
                            self.vision_thread_stop_event.set()
                            self.vision_thread.join()
                            self.vision_thread = None

                        self._change_state(State.SLEEPING)
                    else:
                        self.webapp.send_expression(Expression.THINKING)
                        print(f"[Orchestrator-wake] Placeholder print")

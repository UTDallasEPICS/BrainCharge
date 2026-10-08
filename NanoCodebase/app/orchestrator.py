"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""
import time
from typing import Any

# Component import
from ioModules.audio import AudioService
from ioModules.webapp import DisabledWebAppEvents, Expression, RobotState, WebAppEvents

# Python imports
from enum import Enum

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
        webapp: WebAppEvents | DisabledWebAppEvents,
    ) -> None:
        self.audio_service = audio_service
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

    def startup(self):
        """Main control loop."""
        # This is somewhat ugly, need to come in and remove some indenting to make this look cleaner but that's
        # aesthetics stuff
        self._change_state(State.SLEEPING)

        while self.state != State.EXIT:

            # (This segment is long and rambly and would probs be better served in a documentation document rather than a random comment)
            # Move each state into their own static class?
            # If we move each state into their own class, we could define a method like state_enter()/state_exit()
            # which each state can run their own specific state code. With current approach, expanding to more states
            # would be difficult as we would need to hardcode the exit & entry for each one on change, rather than
            # one consolidated place.
            # For now this is fine but if we expand to more states then we should consider a better approach.

            # viable alt: change_state_enter(state) & change_state_exit(state)
            #   function which just has a switch for each state and the code they want to do when starting.
            #   Not the cleanest but cleaner then current

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
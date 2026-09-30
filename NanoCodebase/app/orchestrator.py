"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""
from typing import Any
from ConversationModules.LLM.module import LLMModule
# Component import
from ioModules.audio import AudioService

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

    def __init__(self, language: dict[str, Any], audio_service: AudioService) -> None:
        self.audio_service = audio_service
        self.state = State.SLEEPING
        self.language = language

        self.llm = LLMModule()

        self.wakeWord = language["wake_word"]
        self.sleepWord = language["sleep_word"]

    def startup(self):
        """Main control loop."""
        # This is somewhat ugly, need to come in and remove some indenting to make this look cleaner but that's
        # aesthetics stuff
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

                        self.state = State.ACTIVE
                        self.llm.startup()
                        self.audio_service.speak(self.language["greeting"], True)

                case State.ACTIVE:
                    print(f"\n[Orchestrator-wake] Listening")
                    transcript = self.audio_service.listen()    # TODO: Look into streaming this into the LLM/sleep detection
                    transcript = transcript.casefold()

                    if transcript == "[BLANK_AUDIO]":
                        self.audio_service.speak(self.language["empty_response"])
                    elif any(word.casefold() in transcript.casefold() for word in self.sleepWord):
                        print(f"\n[Orchestrator-wake] Sleep word detected — ending session.")

                        self.state = State.SLEEPING
                        self.audio_service.speak(self.language["shutdown"], True)
                        self.llm.shutdown()
                    else:
                        # print(f"[Orchestrator-wake] Placeholder print")
                        reply = self.llm.generate(transcript)
                        print(f"[Orchestrator-wake] LLM response: {reply}")
                        self.audio_service.speak(reply)
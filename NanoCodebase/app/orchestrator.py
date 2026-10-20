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
from conversationModules.llm.module import LLMModule

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

    def __init__(
        self,
        language: dict[str, Any],
        audio_service: AudioService,
        vision_service: VisionService
    ) -> None:
        self.audio_service = audio_service
        self.audio_thread = None
        self.state = State.SLEEPING
        self.language = language

        self.llm = LLMModule()

        self.wakeWord = language["wake_word"]
        self.sleepWord = language["sleep_word"]

        self.vision_service = vision_service
        self.vision_thread = None
        self.vision_thread_stop_event = threading.Event()

    def audio_service_loop(self):
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
                    if self.state == State.EXIT:
                        break

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
                    if self.state == State.EXIT:
                        break
                    
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

    def vision_service_loop(self, user: str, frames_per_second: float):
        self.vision_service.start_capture()

        if frames_per_second is None:
            interval = 1 / self.vision_service.frames_per_second
        else:
            interval = 1 / frames_per_second

        while not self.vision_thread_stop_event.is_set():
            self.vision_service.capture_frame(user)
            self.vision_service.delay_capture(int(interval * 1000))

        self.vision_service.stop_capture()
        self.vision_thread_stop_event.clear()
    
    """
    Main control loop
    """
    def startup(self):
        self.audio_thread = threading.Thread(target=self.audio_service_loop)
        self.vision_thread = threading.Thread(target=self.vision_service_loop, args = ("Test", 2))

        self.audio_thread.start()
        self.vision_thread.start()

    def shutdown(self):
        self.shutdown_vision_service()
        self.shutdown_audio_service()

    def shutdown_audio_service(self):
        self.state = State.EXIT

        if self.audio_thread is not None and self.audio_thread.is_alive():
            self.audio_thread.join()

        self.llm.shutdown()
        self.audio_service.cleanup()

    def shutdown_vision_service(self):
        self.vision_thread_stop_event.set()

        if self.vision_thread is not None and self.vision_thread.is_alive():
            self.vision_thread.join()
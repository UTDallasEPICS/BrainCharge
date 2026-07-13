"""
    Owner of application state to conduct each service at a high level on what to do
"""
from dataclasses import dataclass

# Component import
from ioServices.audio import AudioService

# Python imports
from enum import Enum

class State(Enum):
    SLEEPING = 1
    ACTIVE = 2

class Orchestrator:
    def __init__(self, audio: AudioService):
        self.audio = audio
        self.state = State.SLEEPING

    def startup(self):
        # Control the high level loop for the program controlling overall state
        self.audio.await_wake_word()



    def active(self):

        print("Robot is active!")

        while self.state == State.ACTIVE:

            text = self.audio.listen()

            if text == "bye":
                print("Returning to sleep.")
                self.state = State.SLEEPING
                return

            self.audio.speak(f"You said: {text}")
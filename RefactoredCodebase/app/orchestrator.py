"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""
import time

from app.Types import LanguagePhrases
# Component import
from ioServices.audio import AudioService

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

    def __init__(self, language:LanguagePhrases, audio_service: AudioService):
        self.audio_service = audio_service
        self.state = State.SLEEPING
        self.lang = language

        self.wake_word = "companion"
        self.wake_listen_duration = 5

    def startup(self):
        """Main control loop."""
        while self.state != State.EXIT:
            self.await_wake_word()
            # Awaken
            self.state = State.ACTIVE
            self.audio_service.speak(self.lang["Greeting"])

            # Back to sleep
            self.state = State.SLEEPING


    def await_wake_word(self):
        """Block until the configured wake word is detected."""
        while True:
            print("[Sleep] Listening for wake word...")

            transcript = self.audio_service.listen(
                duration=self.wake_listen_duration,
            )

            if not transcript:
                time.sleep(0.3)
                continue

            print(f"[Sleep] Heard: {transcript}")

            if self.wake_word in transcript.casefold():
                print(f'[Wake] "{self.wake_word}" detected.')
                return

            # await loop
            # while True:
            #     print("\n[Sleep] Listening for wake word...")
            #     if not self._listen(listenDuration, use_vad=False):
            #         # time.sleep(1) # Delay between starting listening where it will be doing nothing.
            #         continue
            #
            #     if transcription := self._transcribe_audio(self.audio_output_path):
            #         print(f"[Sleep] Heard: {transcription}")
            #         wakeWord = self.config["wake_word"]
            #         if wakeWord in transcription.lower():
            #             print(f"\n[Wake] \"{wakeWord}\" detected! Starting active mode...\n")
            #             return
            #         # if check_for_wake_word(transcription):
            #         #     print(f"\n[Wake] \"{WAKE_WORD}\" detected! Starting active mode...\n")
            #         #     start_active_mode(context)
            #         #     print("[Sleep] Returning to sleep mode...")
            #         #     time.sleep(1)
            #     time.sleep(0.3)

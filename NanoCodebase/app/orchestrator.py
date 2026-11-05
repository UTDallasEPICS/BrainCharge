"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""

# Component imports
from inspect import trace
from time import monotonic

from ioModules.audio import AudioService
from ioModules.vision import VisionService
# from conversationModules.llm.module import LLMModule

# Python imports
from threading import Thread, Event, Condition
from dataclasses import dataclass
from queue import Queue
from enum import Enum
from typing import Any, final
from abc import ABC, abstractmethod

class State(Enum):
    EXIT = -1
    SLEEPING = 0
    ACTIVE = 1

#region Worker implementation
#TODO: Move this into its own file, or require services to define there own worker which we just grab
@dataclass(frozen=True, slots=True)
class Message:
    """Message structure used to send messages to & from worker threads back to main orchestration"""
    type: str           # Defines what this message is
    payload:Any = None  # Data associated with it

class Worker(ABC):
    """Worker base class to encapsulate services"""
    def __init__(self, event_queue: Queue[Message], shutdown_event: Event):
        self._event_queue = event_queue         # Worker -> Main thread
        self.command_queue = Queue[Message]()   # Main thread -> Worker
        self._shutdown_event = shutdown_event

        self._thread = Thread(
            target=self._run,
        )
        self._thread.start()

    @abstractmethod
    def _run(self):
        """Represents the running logic for the worker"""
        ...

    def enable(self) -> None:
        """Activates the worker"""
        pass

    def disable(self) -> None:
        """Deactivates the worker and releases resources"""
        pass

    @final  # Sealing this as you should implement the cleanup using the que message/
    def cleanup(self) -> None:
        """Shutdown worker thread & release all resources"""
        self.command_queue.put(Message("EXIT"))
        self._thread.join(10)
        if self._thread.is_alive():
            raise TimeoutError(f"{type(self).__name__} failed to terminate")

class VisionWorker(Worker):
    def __init__(self, event_queue: Queue[Message], shutdown_event: Event, vision_service: VisionService,
                 frames_per_second:float | None = None) -> None:
        self._vision_service = vision_service
        self.frames_per_second = frames_per_second or vision_service.frames_per_second
        super().__init__(event_queue, shutdown_event)

    def _run(self):
        import cv2  # TODO: remove this import after pollKey has been implemented in vision to update the UI
        next_frame = monotonic()    # Timer variable https://salivity.github.io/python/article/python-time-time-vs-monotonic-vs-perf-counter

        try:
            self._vision_service.start_capture()

            while not self._shutdown_event.is_set():
                interval = 1 / self.frames_per_second
                self._vision_service.capture_frame()
                cv2.pollKey()
                next_frame += interval

                # If we have already missed this frame deadline then just do another
                if next_frame < monotonic():
                    next_frame = monotonic()

                timeUntilNextFrame = max(0.0, next_frame - monotonic())
                self._shutdown_event.wait(timeUntilNextFrame)
        except Exception as exc:
            self._event_queue.put(Message("error", f"vision: {exc}"))
        finally:
            self._vision_service.stop_capture() # This should be a cleanup function and also made safe

# class AudioWorker(Worker):
#     def start(self):
#         pass
#
#     def __init__(self, event_queue: Queue[Message], stop_event: Event, audio_service:AudioService):
#         super().__init__(event_queue, stop_event)
#         self._audio_service = audio_service
#endregion

# Python multi-threading: https://www.geeksforgeeks.org/python/python-communicating-between-threads-set-1/
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
        self.state = State.SLEEPING
        self.language = language

        # self.llm = LLMModule()
        # self.audio_service = audio_service
        # self.vision_service = vision_service

        self.event_queue = Queue[Message]()
        self.stop_event = Event()
        self.vision_worker = VisionWorker(
            event_queue=self.event_queue,
            shutdown_event=self.stop_event,
            vision_service=vision_service,
            frames_per_second=5)

        self.wakeWord = language["wake_word"].casefold()
        self.sleepWord = language["sleep_word"].casefold()

    def startup(self):
        """Starts the main state machine"""
        self.change_state(State.ACTIVE)

        while self.state != State.EXIT:
            event = self.event_queue.get()

            if event.type == "error":
                print(f"Worker failure: {event.payload}")
                self.state = State.EXIT
                return

            match self.state:
                case State.SLEEPING:
                    pass
                case State.ACTIVE:
                    pass


    def change_state(self, new_state: State)-> bool:
        """Changes the currently active state
        Args:
            new_state (State): State to change to
        Returns:
            bool: True if the state was changed, False otherwise
        """

        if self.state == new_state: # Throw away changes to state we are already in
            return False

        self.state = new_state

        match new_state:
            case State.ACTIVE:
                print("Entering ACTIVE state")
                self.vision_worker.start()
            case State.SLEEPING:
                print("Entering SLEEPING state")
                self.vision_worker.shutdown()
        return False






    # def audio_service_loop(self):
    #     # This is somewhat ugly, need to come in and remove some indenting to make this look cleaner but that's
    #     # aesthetics stuff
    #     while self.state != State.EXIT:
    #         match self.state:
    #             case State.SLEEPING:
    #                 print("[Orchestrator-Sleep] Listening for wake word...")
    #                 transcript = self.audio_service.listen()
    #                 if self.state == State.EXIT:
    #                     break
    #
    #                 if transcript == "[BLANK_AUDIO]":
    #                     continue
    #
    #                 if self.wakeWord in transcript.casefold():
    #                     print(f'[Orchestrator-Sleep] "{self.wakeWord}" detected.')
    #
    #                     self.state = State.ACTIVE
    #                     # self.llm.startup()
    #                     self.audio_service.speak(self.language["greeting"], True)
    #
    #             case State.ACTIVE:
    #                 print(f"\n[Orchestrator-wake] Listening")
    #                 transcript = self.audio_service.listen()    # TODO: Look into streaming this into the LLM/sleep detection
    #                 if self.state == State.EXIT:
    #                     break
    #
    #                 transcript = transcript.casefold()
    #
    #                 if transcript == "[BLANK_AUDIO]":
    #                     self.audio_service.speak(self.language["empty_response"])
    #                 elif self.sleepWord in transcript.casefold():
    #                     print(f"\n[Orchestrator-wake] Sleep word detected — ending session.")
    #
    #                     self.state = State.SLEEPING
    #                     self.audio_service.speak(self.language["shutdown"], True)
    #                     # self.llm.shutdown()
    #                 # else:
    #                 #     # print(f"[Orchestrator-wake] Placeholder print")
    #                 #     reply = self.llm.generate(transcript)
    #                 #     print(f"[Orchestrator-wake] LLM response: {reply}")
    #                 #     self.audio_service.speak(reply)
    #
    # def vision_service_loop(self, user: str, frames_per_second: float):
    #     self.vision_service.start_capture()
    #
    #     if frames_per_second is None:
    #         interval = 1 / self.vision_service.frames_per_second
    #     else:
    #         interval = 1 / frames_per_second
    #
    #     while not self.vision_thread_stop_event.is_set():
    #         self.vision_service.capture_frame(user)
    #         self.vision_service.delay_capture(int(interval * 1000))
    #
    #     self.vision_service.stop_capture()
    #     self.vision_thread_stop_event.clear()
    #
    # """
    # Main control loop
    # """
    # def startup(self):
    #     self.audio_thread = Thread(target=self.audio_service_loop)
    #     self.vision_thread = Thread(target=self.vision_service_loop, args = ("Test", 2))
    #
    #     self.audio_thread.start()
    #     self.vision_thread.start()
    #
    # def shutdown(self):
    #     self.shutdown_vision_service()
    #     self.shutdown_audio_service()
    #
    # def shutdown_audio_service(self):
    #     self.state = State.EXIT
    #
    #     if self.audio_thread is not None and self.audio_thread.is_alive():
    #         self.audio_thread.join()
    #
    #     # self.llm.shutdown()
    #     self.audio_service.cleanup()
    #
    # def shutdown_vision_service(self):
    #     self.vision_thread_stop_event.set()
    #
    #     if self.vision_thread is not None and self.vision_thread.is_alive():
    #         self.vision_thread.join()

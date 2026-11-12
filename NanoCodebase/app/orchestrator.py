"""
Application coordinator.

The orchestrator owns the application's state machine and coordinates
communication between independent services.

It should contain as little implementation logic as possible.
Services perform work while the orchestrator decides when that work should occur.
"""

# Python imports
from time import monotonic
from threading import Thread
from dataclasses import dataclass
from queue import Queue, ShutDown, Empty
from enum import Enum
from typing import Any, final
from abc import ABC, abstractmethod

# Component imports
from ioModules.audio import AudioService
from ioModules.vision import VisionService
# from conversationModules.llm.module import LLMModule

class State(Enum):
    EXIT = -1
    SLEEPING = 0
    ACTIVE = 1

#region Worker implementations
#TODO: Move this into its own file, or require services to define there own worker which we just grab
@dataclass(frozen=True, slots=True)
class Message:
    """Message structure used to send messages to & from worker threads back to main orchestration"""
    type: str           # Defines what this message is
    payload:Any = None  # Data associated with it

class Worker(ABC):
    """
    Worker base class to encapsulate services
    """
    def __init__(self, event_queue: Queue[Message]):
        self._event_queue = event_queue         # Worker -> Main thread
        self._command_queue = Queue[Message]()   # Main thread -> Worker

        self._thread = Thread(
            target=self._run,
        )
        self._thread.start()

    @abstractmethod
    def _run(self):
        """Represents the threaded running logic for the worker"""
        ...

    def enable(self) -> None:
        """Activates the worker"""
        self._command_queue.put(Message("ENABLE"))

    def disable(self) -> None:
        """Warm shutdown: Release temporary resources while preserving initialized services for a fast restart."""
        self._command_queue.put(Message("DISABLE"))

    @final  # Sealing this as you should implement the cleanup using the que message
    def cleanup(self) -> None:
        """Cold shutdown - Terminate the worker and release all resources.
        Notes:
            Restarting requires creating a new worker instance.
        """
        self._command_queue.shutdown(immediate=True)
        self._thread.join(10)
        if self._thread.is_alive():
            raise TimeoutError(f"{type(self).__name__} failed to terminate")

class VisionWorker(Worker):
    """
        Worker setup as an internal loop to manage the CV timings.
        Reason internal loop was done is because this is essentially a background task. While we care when it runs we don't
        specifically need
    """
    def __init__(self, event_queue: Queue[Message], vision_service: VisionService,
                 frames_per_second:float|None = None) -> None:

        self._vision_service = vision_service
        self.frames_per_second = frames_per_second or vision_service.frames_per_second
        super().__init__(event_queue)

    def set_interval(self, new_fps: float):
        """Changes the capture rate for the vision service"""
        self._command_queue.put(Message("SET INTERVAL", new_fps))

    def get_last_inference(self):
        """Changes the capture rate for the vision service"""
        self._command_queue.put(Message("GET"))

    def _run(self):
        import cv2  # TODO: remove this import after pollKey has been implemented in vision to update the UI
        enabled = False
        next_frame = monotonic()    # https://salivity.github.io/python/article/python-time-time-vs-monotonic-vs-perf-counter
        interval = 1 / self.frames_per_second

        while True:
            # Get command from orcastrator
            try:
                if enabled:
                    # Wait until next frame OR a command arrives
                    timeout = max(0, next_frame - monotonic())
                    command = self._command_queue.get(timeout=timeout)
                else:
                    # Blocks until a command arrives
                    command = self._command_queue.get()
            except Empty:
                # If we get empty, that means timeout has occurred & we need to capture a new frame
                self._vision_service.capture_frame()
                cv2.pollKey()
                self._event_queue.put(Message("EMOTION", self._vision_service.get_latest_inference()))

                next_frame = max(
                    next_frame + interval,
                    monotonic()
                )
                continue
            except ShutDown:
                self._vision_service.stop_capture()
                break

            # Processing command
            match command.type:
                case "ENABLE":
                    if not enabled:
                        self._vision_service.start_capture()
                        enabled = True
                        next_frame = monotonic()

                case "DISABLE":
                    if enabled:
                        self._vision_service.stop_capture()
                        enabled = False

                case "SET INTERVAL":
                    fps = float(command.payload)

                    if fps <= 0:
                        raise ValueError("FPS must be greater than zero")

                    self.frames_per_second = fps
                    interval = 1 / fps

                    if enabled:
                        next_frame = monotonic() + interval

class AudioWorker(Worker):
    """
        Implements the event structure for the audio serv.
        Notes:

    """
    def __init__(self, event_queue: Queue[Message], audio_service: AudioService) -> None:
        self._audio_service = audio_service
        super().__init__(event_queue)

    def listen(self):
        self._command_queue.put(Message("LISTEN_ONCE"))

    def speak(self, sentence:str):
        self._command_queue.put(Message("SPEAK", sentence))

    def _run(self):
        while True:
            try:
                command = self._command_queue.get()
            except ShutDown:
                # TODO add audio service shutdown
                break

            match command.type:
                case "LISTEN_ONCE":
                    transcript = self._audio_service.listen()
                    self._event_queue.put(Message("TRANSCRIPT", transcript))

                case "SPEAK":
                    self._audio_service.speak(command.payload)
                    self._event_queue.put(Message("SPEECH_FINISHED"))

            # # Get command from orcastrator
            # try:
            #     if enabled:
            #         command = self._command_queue.get_nowait()  # Polls to see if there's a command ready
            #         # We don't need to use the same implementation as Vision worker as audio service will block the thread as it waits for IO
            #     else:
            #         command = self._command_queue.get()         # Wait until command
            # except Empty:
            #     command = None  #Get_nowait throws empty exception if it doesnt find anything
            # except ShutDown:
            #     # Cleanup audio
            #     break
            #
            # # Processing command
            # if command is not None:
            #     match command.type:
            #         case "ENABLE":
            #             enabled = True
            #         case "DISABLE":
            #             enabled = False
            #         case "SPEAK":
            #             # TODO Fix blocking audio service
            #             # Theres a problem that since .listen() blocks, after getting and sending the transcript down
            #             # it will start another one, this is a problem with wake & shutdown words as it cant be interrupted
            #             self._audio_service.speak(command.payload)
            #     continue
            #
            # # Main audio loop
            # if enabled:
            #     try:
            #         transcript = self._audio_service.listen()
            #         if transcript.strip() != "[BLANK_AUDIO]":
            #             self._event_queue.put(Message("TRANSCRIPT", transcript.casefold() ))
            #
            #     except Exception as exc:
            #         self._event_queue.put(Message("ERR", exc))
            #         break
# endregion

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
        # self.state = State.SLEEPING
        self.state = None
        self.language = language
        self.wakeWords = {
            word.strip().casefold()
            for word in language["wake_word"]
        }

        self.sleepWords = {
            word.strip().casefold()
            for word in language["sleep_word"]
        }
        # self.llm = LLMModule()
        # self.audio_service = audio_service
        # self.vision_service = vision_service

        self.event_queue = Queue[Message]()
        self.vision_worker = VisionWorker(
            event_queue=self.event_queue,
            vision_service=vision_service,
            frames_per_second=5)

        self.audio_worker = AudioWorker(
            event_queue=self.event_queue,
            audio_service=audio_service,
        )

    def startup(self):
        """Starts the runtime loop for the orchestrator"""
        self.change_state(State.SLEEPING)

        try:
            while self.state != State.EXIT:
                event = self.event_queue.get()

                match (self.state, event.type):
                    case (_, "ERR"):
                        print(f"Worker failure: {event.payload}")
                        self.change_state(State.EXIT)
                        return

                    # region Sleep
                    case (State.SLEEPING, "TRANSCRIPT"):
                        print(event.payload.strip().casefold(), self.wakeWords)
                        if event.payload.strip(" .,!?").casefold() in self.wakeWords:
                            # Speak greeting (which will trigger speach finished and then trigger state change)
                            self.audio_worker.speak(self.language["greeting"])
                        else:
                            self.audio_worker.listen()
                    case (State.SLEEPING, "SPEECH_FINISHED"):
                        self.change_state(State.ACTIVE)
                    # endregion

                    # region Active
                    case (State.ACTIVE, "TRANSCRIPT"):
                        # TODO: Process transcript with LLM
                        # Resume listening
                        if event.payload.strip(" .,!?").casefold() in self.sleepWords:
                            # Speak greeting (which will trigger speach finished and then trigger state change)
                            self.audio_worker.speak(self.language["greeting"])
                        self.audio_worker.listen()

                    case (State.ACTIVE, "EMOTION"):
                        # TODO: Forward emotion
                        pass
                    # endregion

                    case _:  # Unhandled events
                        raise RuntimeError(f"Unexpected message\n{self.state} | {event.type}: {event.payload}")
        finally:
            self.vision_worker.cleanup()
            self.audio_worker.cleanup()

            # if event.type == "ERR":
            #     print(f"Worker failure: {event.payload}")
            #     self.change_state(State.EXIT)
            #     return
            #
            # # Ugly af switch statements go
            # match self.state:
            #     case State.SLEEPING:
            #         match event.type:
            #             case "TRANSCRIPT":
            #                 if event.payload == self.wakeWord:
            #                     # Already queues the greeting in your implementation.
            #                     self.audio_worker.speak(self.language["greeting"])
            #                 else:
            #                     self.audio_worker.listen()
            #
            #             case "SPEECH_FINISHED":
            #                 self.change_state(State.ACTIVE)
            #
            #     case State.ACTIVE:
            #         match event.type:
            #             case "TRANSCRIPT":
            #                 # Pass transcript to LLM
            #                 pass
            #             case "EMOTION":
            #                 # Forward emotion to relevant services
            #                 pass


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
                print("[Orchestrator] Entering ACTIVE state")
                self.vision_worker.enable()
                self.audio_worker.listen()
            case State.SLEEPING:
                print("[Orchestrator] Entering SLEEPING state")
                self.vision_worker.disable()
                print("[Orchestrator-Sleep] Awaiting wake word...")
                self.audio_worker.listen()
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

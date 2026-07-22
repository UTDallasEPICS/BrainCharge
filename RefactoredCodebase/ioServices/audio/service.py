"""High-level audio services.

Provides audio functionality independent of the underlying operating system by
delegating platform-specific behavior to an ``AudioBackend`` implementation.
"""
import threading
from enum import Enum
from pathlib import Path
from subprocess import Popen
from typing import Any, Literal
import subprocess

from . import backend

class AudioService:
    """Capture and manage audio for the robot.

    Uses a platform-specific ``AudioBackend`` to configure audio peripherals.
    """
    def __init__(self,
                 system: str,
                 temp_directory: Path,
                 config: dict[str, Any],
                 ):
        self._backend = backend.get(system, config)
        self._config = config

        self.interrupt_event = threading.Event()

        self.audio_output_path = temp_directory / "audio.wav"
        self.transcript_output_path = temp_directory / "transcript"

    def listen(self, duration: int) -> str:
        """Record microphone audio for a fixed duration.
        Audio is captured using ``FFmpeg`` and saved as a 16 kHz mono WAV file.

        Args:
            duration:
                Recording duration in seconds.

        Returns:
            The transcribed text, or an empty string if recording or
            transcription fails.
        """
        try:
            subprocess.run([
                "ffmpeg",
                *self._backend.ffmpeg_input_args(),
                "-t", str(duration),
                "-ar", "16000",
                "-ac", "1",
                str(self.audio_output_path),
                "-y",
                "-loglevel", "error",
            ], check=True, capture_output=True)

            return self._transcribe_audio(self.audio_output_path)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
            print(f"[Audio] FFmpeg error: {stderr}")
            return ""
        except Exception as e:
            print(f"[Audio] Error: {e}")
            return ""

    def speak(self, sentence: str, monitor:Literal["VOSK", "VOLUME"] | None=None) -> Popen[bytes]:
        """Outputs spoken audio.
        Audio output is done via given TTS engine from current backend.

        Args:
            sentence: Text to be spoken
            monitor: What monitor engine to be used in order to cancel TTS if speach is detected
            ``VOSK`` -
            ``VOLUME`` -
        Returns:
            Popen[bytes]: TTS subprocess
        """
        self.interrupt_event.clear()
        print(f"{self._backend.get_speak_command() + [sentence]}")
        process = subprocess.Popen(
            self._backend.get_speak_command() + [sentence],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        thread: threading.Thread | None = None # Thread used in respective monitor processes
        match monitor:
            case "VOSK":
                thread = threading.Thread(
                    target=lambda tts_process, spoken_text: None,
                    args=(process, sentence),
                    daemon=True,
                )
            case "VOLUME":
                thread = threading.Thread(
                    target= lambda tts_process: None,
                    args=(process,),
                    daemon=True,
                )

        if thread is not None:
            thread.start()

        return process

    def _transcribe_audio(self, audio_file: Path) -> str:
        try:
            whisper_config = self._config.get("whisper")

            subprocess.run([
                whisper_config["binary"],
                "-m", whisper_config["model"],
                "-f", audio_file,
                "-of", str(self.transcript_output_path),
                "-otxt",
                "-l", "en",
            ], check=True, capture_output=True)
            transcript_file = Path(self.transcript_output_path).with_suffix(".txt")

            if transcript_file.exists():
                return transcript_file.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).strip()

            return ""
        except subprocess.CalledProcessError as e:
            print(f"[Whisper] Error: {e}")
            return ""

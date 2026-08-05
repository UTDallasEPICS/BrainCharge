"""High-level audio services.

Provides audio functionality independent of the underlying operating system by
delegating platform-specific behavior to an ``AudioBackend`` implementation.
"""
import threading
import warnings
import json
from enum import Enum
from pathlib import Path
from subprocess import Popen
from typing import Any
import subprocess

import pyaudio
from . import backend

class AudioService:
    """Capture and manage audio for the robot.

    Uses a platform-specific ``AudioBackend`` to configure audio peripherals.
    """
    def __init__(self,
                 system: str,
                 config: dict[str, Any],
                 temp_directory: Path,
                 vosk_model_path: Path,
                 language: str = "en",
    ):
        self._config = config
        self._backend = backend.get(system, config)
        self._language = language

        self.audio_output_path = temp_directory / "audio.wav"
        self.transcript_output_path = temp_directory / "transcript"

        # If we have a valid vosk model then preform the setup for it
        if vosk_model_path:
            self.interrupt_event = threading.Event()

            interrupt_config = config.get("interrupt", {})
            self._sample_rate = int(interrupt_config.get("sample_rate", 16000))
            self._chunk_size = int(interrupt_config.get("chunk_size", 1024))
            self._min_words = int(interrupt_config.get("minimum_words", 2))
            self._warmup_seconds = float(interrupt_config.get("warmup_seconds", 0.4))
            self._echo_similarity_threshold = float(interrupt_config.get("echo_similarity_threshold", 0.55))

            try:
                from vosk import KaldiRecognizer, Model

                if not vosk_model_path.is_dir():
                    warnings.warn(
                        f"""Vosk model directory was not found: {vosk_model_path}.
                        Echo-aware interruption is disabled."""
                    )
                    return

                self._vosk_model = Model(str(vosk_model_path))
                self._kaldi_recognizer = KaldiRecognizer

            except ImportError:
                warnings.warn(
                    "Vosk is not installed; echo-aware TTS interruption is disabled. "
                    "Install it with: pip install vosk"
                )
            except Exception as error:
                warnings.warn(
                    f"Could not initialize the Vosk model: {error}"
                )

    # TODO: Look into swapping to VOSK for sleeping wake word detection instead of whisper. Use whisper when accuracy is required for LLM input
    # The main problem with doing this is the current architectural split. A clean way to do this might be an event driven approach?
    # Otherwise having the audio service might be necessary
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

    def speak(self, sentence: str, ignore_interrupt:bool = False) -> Popen[bytes]:
        """Outputs spoken audio.
        Audio output is done via given TTS engine from current backend.

        Args:
            sentence: Text to be spoken
            ignore_interrupt: If user interruption is allowed for this phrase.
                Typically enabled for short preset phrases such as the greeting
        Returns:
            Popen[bytes]: TTS subprocess
        """
        self.interrupt_event.clear()
        process = subprocess.Popen(
            self._backend.get_speak_command() + [sentence],
            #stdout=subprocess.DEVNULL,
            #stderr=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
        )

        # VOSK interrupt thread
        if not ignore_interrupt and self._vosk_model and self._kaldi_recognizer:
            threading.Thread(
                target=self._vosk_echo_monitor,
                args=(process, sentence),
                daemon=True,
            ).start()

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
                "-l", self._language,
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

    def _vosk_echo_monitor(self, tts_process, expected_sentence: str):
        """Monitor microphone input while TTS is playing and interrupt on user speech.

        Args:
            tts_process:
                Running TTS subprocess to monitor and terminate when an interruption
                is detected.
            expected_sentence:
                Text currently being spoken by the TTS engine and used for echo
                comparison.

        Returns:
            None.

        Notes:
            A new ``KaldiRecognizer`` is created for each monitoring session, while
            the heavier Vosk model is reused from ``self._vosk_model``.
        """
        try:
            recognizer = self._kaldi_recognizer(self._vosk_model, self._sample_rate)
            recognizer.SetWords(False)

            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16, channels=1, rate=self._sample_rate,
                input=True, frames_per_buffer=self._chunk_size
            )

            warmup_chunks = int(self._sample_rate * self._warmup_seconds / self._chunk_size)
            for _ in range(warmup_chunks):
                if tts_process.poll() is not None:
                    break
                try:
                    stream.read(self._chunk_size, exception_on_overflow=False)
                except Exception:
                    break

            while tts_process.poll() is None and not self.interrupt_event.is_set():
                try:
                    chunk = stream.read(self._chunk_size, exception_on_overflow=False)
                except Exception:
                    break

                if recognizer.AcceptWaveform(chunk):
                    heard = json.loads(recognizer.Result()).get("text", "").strip()
                else:
                    heard = json.loads(recognizer.PartialResult()).get("partial", "").strip()

                if len(heard.split()) < self._min_words:
                    continue

                # _mic_content_matches_expected()
                if heard.strip():
                    heard_words = set(heard.lower().split())
                    expected_words = set(expected_sentence.lower().split())
                    overlap = len(heard_words & expected_words) / len(heard_words)
                    print(f"  [echo-check] heard={heard!r:.60}  overlap={overlap:.2f}", flush=True)

                    if overlap < 0.4:
                        print("  [echo-check] Content diverged — interrupting TTS.")
                        tts_process.terminate()
                        self.interrupt_event.set()
                        break

        except Exception as e:
            print(f"[Vosk] Monitor error: {e}")
        finally:
            try:
                stream.stop_stream()
                stream.close()
                pa.terminate()
            except Exception:
                pass
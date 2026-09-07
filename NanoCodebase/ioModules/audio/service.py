"""High-level audio services.

Provides audio functionality independent of the underlying operating system by
delegating platform-specific behavior to an ``AudioBackend`` implementation.

Requires:
    piper - https://github.com/OHF-Voice/piper1-gpl
        For GPU support you need onnxruntime-gpu, but you MUST HAVE A CUDA COMPATIBLE GPU
        If you simply install the piper-tts it will give a warning stating that it couldn't find it and will default to CPU (Slower)
            python -m pip install piper-tts
            python -m pip install onnxruntime-gpu

        To get voices for piper it has its own command (Remember to put voice files in their respective languageFolder
            python -m piper.download_voices
"""
import math
import subprocess
import threading    # vosk
import json
import wave
import struct
from pathlib import Path
from typing import Any
from time import time
from warnings import warn

from pyaudio import PyAudio, paInt16
from piper import PiperVoice

from . import backend

# Audio internal configs
VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 1024

DEFAULT_VAD_MIN_RECORDING  = 0.5
DEFAULT_VAD_MAX_RECORDING  = 30.0
DEFAULT_VAD_SILENCE_THRESHOLD_DB = -30
DEFAULT_VAD_SILENCE_DURATION = 1.2

class AudioService:
    """Capture and manage audio for the robot.
    Uses a platform-specific ``AudioBackend`` to configure audio peripherals.

    Right now, code should be expected to be synchronous but there should become a point where speak() and listen() are async.
    """
    def __init__(self,
                 config: dict[str, Any],
                 temp_directory: Path,
                 vosk_model_path: Path,
                 piper_model_path: Path,
    ):
        self._language = config.get("language", "en")       # Currently selected user language

        # This might be unnecessary as piper has smoothed over much of the OS specific issues that we were having for audio output
        # self._backend = backend.get(system, config, language)   # The backend which abstracts OS specific functionality

        # Using the CLI it must start a separate process and in that case new model every time. https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md
        # Instead we load piper directly through the python API. This also allowed implementation of streaming and GPU support
        # TODO Only make this initialized when we are awake. Awake/Sleep event?
        self._voice = PiperVoice.load(piper_model_path, None, True)
        # https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md

        self.audio_input_path = str(temp_directory / "audioUserInput.wav")      # User's voice input
        self.audio_output_path = str(temp_directory / "audioSpeachOutput.wav")  # TTS Output
        self.transcript_output_path = temp_directory / "transcript"             # STT Output

        whisper_config = config["whisper"]
        self.whisper_binary = whisper_config["binary"]
        self.whisper_model = whisper_config["model"]

        # If we have a vosk model specified then preform the setup for it
        if vosk_model_path:
            self.interrupt_event = threading.Event()

            interrupt_config = config.get("interrupt", {})
            self._min_words = int(interrupt_config.get("minimum_words", 2))
            self._warmup_seconds = float(interrupt_config.get("warmup_seconds", 0.4))
            self._echo_similarity_threshold = float(interrupt_config.get("echo_similarity_threshold", 0.55))

            try:
                from vosk import KaldiRecognizer, Model

                if not vosk_model_path.is_dir():
                    warn(
                        f"""Vosk model directory was not found: {vosk_model_path}.
                        Echo-aware interruption is disabled."""
                    )
                    return

                self._vosk_model = Model(str(vosk_model_path))
                self._kaldi_recognizer = KaldiRecognizer

            except ImportError:
                warn(
                    "Vosk is not installed; echo-aware TTS interruption is disabled. "
                    "Install it with: pip install vosk"
                )
            except Exception as error:
                warn(
                    f"Could not initialize the Vosk model: {error}"
                )

    # TODO: Look into swapping to VOSK for sleeping wake word detection instead of whisper.
    def listen(self,
               min_duration:float=DEFAULT_VAD_MIN_RECORDING,
               max_duration:float=DEFAULT_VAD_MAX_RECORDING,
               silence_threshold_db:int=DEFAULT_VAD_SILENCE_THRESHOLD_DB,
               silence_duration:float=DEFAULT_VAD_SILENCE_DURATION,
    ) -> str:
        """Record microphone audio until speech ends and transcribe it.

        Recording stops after the configured duration of silence following detected
        speech, or when max_duration is reached.

        Returns:
            The transcribed text, or an empty string if recording or transcription fails.
        """
        pa = None
        stream = None

        try:
            pa, stream = self._get_audio_input_stream()

            frames = []
            silence_start = None
            recording_start = time()
            speech_detected = False

            while True:
                elapsed = time() - recording_start

                # Hard cap
                if elapsed >= max_duration:
                    print(f"\n  [Audio] VAD Max duration ({max_duration}s) reached, stopping.")
                    break

                try:
                    chunk = stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
                except Exception:
                    break

                frames.append(chunk)
                db = self._calculate_rms_db(chunk)
                is_speech = db > silence_threshold_db

                if is_speech:
                    status = "SPEECH"
                    speech_detected = True
                    silence_start = None
                else:
                    if elapsed >= min_duration and speech_detected:
                        if silence_start is None:
                            silence_start = time()
                        sil_elapsed = time() - silence_start
                        status = f"silence {sil_elapsed:.1f}/{silence_duration:.1f}s"
                    else:
                        status = "waiting..."

                print(f"\r {db:6.1f} dBFS  |  {status:<22} | {elapsed:.1f}s", end="", flush=True)

                if not is_speech and elapsed >= min_duration and speech_detected:
                    if silence_start and time() - silence_start >= silence_duration:
                        print(f"\n  [Audio] VAD Silence threshold reached, stopping.")
                        break

            if not frames:
                return ""

            # Save as WAV
            with wave.open(str(self.audio_input_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(VAD_SAMPLE_RATE)
                wf.writeframes(b"".join(frames))

            total_duration = len(frames) * VAD_CHUNK_SIZE / VAD_SAMPLE_RATE
            print(f"  [Audio] VAD Recorded {total_duration:.1f}s of audio")
            return self._transcribe_audio()

        except Exception as e:
            print(f"[Audio] VAD recording error: {e}")
            return ""
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()

            if pa is not None:
                pa.terminate()

        # Old ffmpeg code that we no longer use
        # try:
        #     # Maybe look into removing ffmpeg? Unsure why we use both pyaudio and ffmpeg
        #     # Moved to a streamed version of this so that there's less delay between audio input and output
        #     subprocess.run([
        #         "ffmpeg",
        #         *self._backend.ffmpeg_input_args(),
        #         "-t", str(duration),
        #         "-ar", "16000",
        #         "-ac", "1",
        #         str(self.audio_output_path),
        #         "-y",
        #         "-loglevel", "error",
        #     ], check=True, capture_output=True)
        #
        #     audioTranscript = self._transcribe_audio(self.audio_output_path)
        #     print(f"[Audio] Heard: {audioTranscript}")
        #     return audioTranscript
        # except subprocess.CalledProcessError as e:
        #     stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        #     print(f"[Audio] FFmpeg error: {stderr}")
        #     return ""
        # except Exception as e:
        #     print(f"[Audio] Error: {e}")
        #     return ""

    def speak(self, sentence: str, ignore_interrupt:bool = False):
        """Outputs spoken audio.
        Audio output is done via given TTS engine from current backend.

        Args:
            sentence: Text to be spoken
            ignore_interrupt: If user interruption is allowed for this phrase.
                Typically enabled for short preset phrases such as the greeting
        Returns:
            Popen[bytes]: TTS subprocess
        """
        # look at streaming in piper doc (posted above where we init model)
        pa = PyAudio()
        stream = None

        try:
            for chunk in self._voice.synthesize(sentence):
                if stream is None:  # We only want to open 1 stream, but we want the data from chunk
                    stream = pa.open(
                        format=pa.get_format_from_width(chunk.sample_width),
                        channels=chunk.sample_channels,
                        rate=chunk.sample_rate,
                        output=True,
                    )

                stream.write(chunk.audio_int16_bytes)
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()

        # self.interrupt_event.clear()
        # speakCommand = [
        #     sys.executable,
        #     "-m",
        #     "piper",
        #     "-m",
        #     self._voice,
        #     "-f",
        #     self.audio_output_path,
        #     "--",
        #     sentence,
        # ]
        #
        # process = subprocess.Popen(
        #     speakCommand,
        #     #stdout=subprocess.DEVNULL,
        #     #stderr=subprocess.DEVNULL,
        #     stdout=None,
        #     stderr=None,
        # )
        #
        # winsound.PlaySound(
        #     self.audio_output_path,
        #     winsound.SND_FILENAME,
        # )

        # VOSK interrupt thread
        # if not ignore_interrupt and self._vosk_model and self._kaldi_recognizer:
        #     threading.Thread(
        #         target=self._vosk_echo_monitor,
        #         args=(process, sentence),
        #         daemon=True,
        #     ).start()

        #return process

    def _transcribe_audio(self, audio_file: str|None=None) -> str:
        print("  [Audio] Beginning transcription")
        transcription_start = time()

        if audio_file is None:
            audio_file = str(self.audio_input_path)

        try:

            # https://thomasthelliez.com/blog/run-whisper-cpp-with-cuda-on-jetson-orin-nano-super/
            subprocess.run([
                self.whisper_binary,
                "-m", self.whisper_model,
                "-f", audio_file,
                "-of", str(self.transcript_output_path),
                "-otxt",
                "-l", self._language,
            ], check=True, capture_output=True)

            transcript = self.transcript_output_path.with_suffix(".txt").read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()

            print(
                f"  [Audio] Transcription took {time() - transcription_start:.1f}s\n"
                f"      Heard: \"{transcript}\""
            )
            return transcript
        except subprocess.CalledProcessError as e:
            print(f"[Audio] Whisper Error: {e}")
            return ""
        except FileNotFoundError as e:
            print(f"[Audio] Transcript file not found: {e}")
            return ""

    @staticmethod
    def _get_audio_input_stream(chunk_size = VAD_CHUNK_SIZE, sample_rate = VAD_SAMPLE_RATE):
        py_audio = PyAudio()
        stream = py_audio.open(
            format=paInt16, channels=1, rate=sample_rate,
            input=True, frames_per_buffer=chunk_size
        )
        return py_audio, stream

    @staticmethod
    def _calculate_rms_db(audio_chunk) -> float:
        """
        Calculate the RMS volume of an audio chunk in dBFS.
        Returns -inf for silence (all zeros), otherwise a negative dB value
        where 0 dBFS is the maximum possible level.
        """
        count = len(audio_chunk) // 2  # 16-bit = 2 bytes per sample
        if count == 0:
            return -100.0

        shorts = struct.unpack(f"{count}h", audio_chunk)
        sum_squares = sum(s * s for s in shorts)
        rms = math.sqrt(sum_squares / count)

        if rms == 0:
            return -100.0

        # Normalize to 16-bit range (max 32768) and convert to dB
        db = 20 * math.log10(rms / 32768.0)
        return db

    def _vosk_echo_monitor(self, tts_process, expected_sentence: str):
        """Monitor microphone input while TTS is playing and interrupt on speech.
        Decided to keep vosk so that if user started speaking, it would stop talking but left out volume based interrupt
        as it seemed redundant to stop speaking if it was just loud

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
        pa = None
        stream = None
        try:
            recognizer = self._kaldi_recognizer(self._vosk_model, VAD_SAMPLE_RATE)
            recognizer.SetWords(False)

            pa, stream = self._get_audio_input_stream()

            warmup_chunks = int(VAD_SAMPLE_RATE * self._warmup_seconds / VAD_CHUNK_SIZE)
            for _ in range(warmup_chunks):
                if tts_process.poll() is not None:
                    break
                try:
                    stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
                except Exception:
                    break

            while tts_process.poll() is None and not self.interrupt_event.is_set():
                try:
                    chunk = stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
                except Exception:
                    break

                if recognizer.AcceptWaveform(chunk):
                    heard = json.loads(recognizer.Result()).get("text", "").strip()
                else:
                    heard = json.loads(recognizer.PartialResult()).get("partial", "").strip()

                heard_words = set(heard.casefold().split())
                if len(heard_words) < self._min_words:
                    continue

                # If there are more then the minimum amount of words then intersect the set of heard & expected
                # Turn the number of this intersection to % and if there not overlapping then we are not hearing ourself
                expected_words = set(expected_sentence.casefold().split())
                overlap = len(heard_words & expected_words) / len(heard_words)
                print(f"  [echo-check] heard={heard!r:.60}  overlap={overlap:.2f}", flush=True)
                if overlap < 0.4:
                    print("  [echo-check] Content diverged — interrupting TTS.")
                    tts_process.terminate()
                    self.interrupt_event.set()
                    break

        # if len(heard.split()) < self._min_words:
        #     continue
        #
        # # _mic_content_matches_expected()
        # if heard.strip():
        #     heard_words = set(heard.lower().split())
        #     expected_words = set(expected_sentence.lower().split())
        #     overlap = len(heard_words & expected_words) / len(heard_words)
        #     print(f"  [echo-check] heard={heard!r:.60}  overlap={overlap:.2f}", flush=True)
        #
        #     if overlap < 0.4:
        #         print("  [echo-check] Content diverged — interrupting TTS.")
        #         tts_process.terminate()
        #         self.interrupt_event.set()
        #         break

        except Exception as e:
            print(f"[Vosk] Monitor error: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            if pa:
                pa.terminate()
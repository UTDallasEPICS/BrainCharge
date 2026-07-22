import time
import subprocess
import os
from typing import Any


class AudioService:
    def __init__(self, system:str, temp_directory_path:str, audio_config: dict[str, Any]) -> None:
        self.config = audio_config
        self.audio_output_path = os.path.join(temp_directory_path, "audio.wav")
        self.transcript_output_path = os.path.join(temp_directory_path, "transcript")

        # Getting pyaudio
        try:
            import pyaudio
            self.pyaudio = pyaudio
        except ImportError:
            self.pyaudio = None

        # OS specific configuration
        if system == "Darwin":
            self.ffmpeg_input_args = ["-f", "avfoundation", "-i", ":1"]
        elif system == "Windows":
            # region Windows Mic input setup
            configured = audio_config.get("windows_mic_name", "").strip()
            try:
                result = subprocess.run(
                    ["ffmpeg", "-f", "dshow", "-list_devices", "true", "-i", "dummy"],
                    capture_output=True,
                    text=True,
                    errors="replace",
                )

                available = [
                    line.split('"')[1].strip()
                    for line in (result.stderr + result.stdout).splitlines()
                    if "(audio)" in line and '"' in line
                ]

            except Exception:
                available = []

            if configured and (not available or configured in available):
                selected_mic = configured
            elif available:
                if configured:
                    print(f"[Audio] Configured mic not found: {configured!r}")
                    print("[Audio] Available microphones:")
                    for device in available:
                        print(f"  - {device}")
                    print(f"[Audio] Using: {available[0]!r}")
                selected_mic = available[0]
            else:
                selected_mic = configured or "Microphone (Realtek Audio)"
            # endregion
            self.ffmpeg_input_args = ["-f", "dshow", "-i", f"audio={selected_mic}"]
        else:
            # region Linux Mic input setup

            backend = audio_config.get("linux_audio_backend", "alsa")
            device = audio_config.get("linux_audio_device", "default")

            if backend == "pulse" and not (
                    os.path.exists("/usr/bin/pulseaudio")
                    or os.path.exists("/usr/bin/pactl")
            ):
                backend = "alsa"
            # endregion
            self.ffmpeg_input_args = ["-f", backend, "-i", device]

    # region Public functions
    # Make this async and generic word?
    def await_wake_word(self) -> None:
        """
            Yields current code until it receives wake word
        """
        # loading config options from storage
        listenDuration:int = self.config["wake_word_listen_duration"]

        # await loop
        while True:
            print("\n[Sleep] Listening for wake word...")
            if not self.listen(listenDuration, use_vad=False):
                # time.sleep(1) # Delay between starting listening where it will be doing nothing.
                continue

            if transcription := self._transcribe_audio(self.audio_output_path):
                print(f"[Sleep] Heard: {transcription}")
                wakeWord = self.config["wake_word"]
                if wakeWord in transcription.lower():
                    print(f"\n[Wake] \"{wakeWord}\" detected! Starting active mode...\n")
                    return
                # if check_for_wake_word(transcription):
                #     print(f"\n[Wake] \"{WAKE_WORD}\" detected! Starting active mode...\n")
                #     start_active_mode(context)
                #     print("[Sleep] Returning to sleep mode...")
                #     time.sleep(1)
            time.sleep(0.3)

    # 2 listen types with diffrent functionality
    # First listen type is fixed duration the other is VAD
    # Fixed duration is syncronous

    def listen(self, duration:int,use_vad:bool=False):
        """Records audio from the microphone configured in init

        Args:
            duration: Length of time that will be recorded and processed
            use_vad: Whether to use voice activity detection
        Returns:
            True if recording succeeded, otherwise False
        """
        if use_vad and self.pyaudio:
            # VAD code
            pass

        try:
            subprocess.run([
                "ffmpeg",
                *self.ffmpeg_input_args,
                "-t", str(duration),
                "-ar", "16000",
                "-ac", "1",
                self.audio_output_path,
                "-y",
                "-loglevel", "error",
            ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
            print(f"[Audio] FFmpeg error: {stderr}")
            return False
        except Exception as e:
            print(f"[Audio] Error: {e}")
            return False
    # endregion

    # region Internal private code
    # def listen(self, duration:int,use_vad:bool=False):
    #     """Records audio from the microphone configured in init
    #
    #     Args:
    #         duration: Length of time that will be recorded and processed
    #         use_vad: Whether to use voice activity detection
    #     Returns:
    #         True if recording succeeded, otherwise False
    #     """
    #     if use_vad and self.pyaudio:
    #         # VAD code
    #         pass
    #
    #     try:
    #         subprocess.run([
    #             "ffmpeg",
    #             *self.ffmpeg_input_args,
    #             "-t", str(duration),
    #             "-ar", "16000",
    #             "-ac", "1",
    #             self.audio_output_path,
    #             "-y",
    #             "-loglevel", "error",
    #         ], check=True, capture_output=True)
    #         return True
    #     except subprocess.CalledProcessError as e:
    #         stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
    #         print(f"[Audio] FFmpeg error: {stderr}")
    #         return False
    #     except Exception as e:
    #         print(f"[Audio] Error: {e}")
    #         return False

    # def _transcribe_audio(self, audio_file:str) -> str:
    #     try:
    #         whisperConfig = self.config.get("whisper")
    #
    #         subprocess.run([
    #             whisperConfig["binary"],
    #             "-m", whisperConfig["model"],
    #             "-f", audio_file,
    #             "-of", self.transcript_output_path,
    #             "-otxt",
    #             "-l", "en",
    #         ], check=True, capture_output=True)
    #
    #         transcript_file = self.transcript_output_path + ".txt"
    #         if os.path.exists(transcript_file):
    #             with open(transcript_file, "r", encoding="utf-8", errors="replace") as f:
    #                 return f.read().strip()
    #         return ""
    #     except subprocess.CalledProcessError as e:
    #         print(f"[Whisper] Error: {e}")
    #         return ""
    # endregion

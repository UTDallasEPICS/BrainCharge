"""macOS implementation of the AudioBackend protocol.

Configures FFmpeg audio input using the AVFoundation backend.
"""
from typing import Any

from . import AudioBackend

class MacOSAudioBackend(AudioBackend):
    def __init__(self, config: dict[str, Any], language:str = "en") -> None:
        """Configure FFmpeg microphone input on Windows.

        Supported configuration keys:
            ``macos_audio_device``:
                Preferred microphone name.

                Defaults to first available microphone.
        """
        self._device = config.get("macos_audio_device", ":0")

    def ffmpeg_input_args(self) -> list[str]:
        return ["-f", "avfoundation", "-i", self._device]
"""Linux implementation of the AudioBackend protocol.

Configures FFmpeg audio input using a selectable Linux backend and device.
ALSA with the default input device is used when no configuration is provided.
"""
from typing import Any

from . import AudioBackend

class LinuxAudioBackend(AudioBackend):
    """
    Supported configuration keys:
        ``linux_audio_backend``:
            ``FFmpeg`` input format, such as ``"alsa"`` or ``"pulse"``.

            Defaults to ``"alsa"``.
        ``linux_audio_device``:
            Input device understood by the selected backend.

            Defaults to ``"default"``.
    """
    def __init__(self, config: dict[str, Any], language:str = "en") -> None:
        self._device = config.get("input_device", "default")
        self.language = language

    def get_speak_command(self,) -> list[str]:
        return ["espeak", "-v", self.language, "-s", "145"]

    def ffmpeg_input_args(self) -> list[str]:
        return ["-f", "alsa", "-i", self._device]
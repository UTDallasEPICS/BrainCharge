"""Windows implementation of the AudioBackend protocol.

Configures FFmpeg audio input using the DirectShow backend and selects a
microphone from the devices reported by FFmpeg.
"""
from textwrap import dedent
from typing import Any
import subprocess

import pyaudio

from . import AudioBackend

class WindowsAudioBackend(AudioBackend):
    def __init__(self, config: dict[str, Any], language:str = "en") -> None:
        """
        Supported configuration keys:
            ``windows_mic_name``:
                Preferred DirectShow microphone name.

                If the configured microphone is unavailable, the first microphone
                reported by ``FFmpeg`` is used.
        """
        self.language = language
        self._voice = self._select_voice(language)

        configured_microphone = str(config.get("input_device") or "").strip()
        self._microphone = configured_microphone or self._default_microphone()

    def get_speak_command(self) -> list[str]:
        # TODO add language support to windows
        ps_script = """
        Add-Type -AssemblyName System.Speech

        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $s.SelectVoice($args[0])
        $s.Rate = 0
        $s.Speak($args[1])
        """

        return [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-CommandWithArgs",
            ps_script,
            self._voice,
        ]

    def ffmpeg_input_args(self) -> list[str]:
        return ["-f","dshow","-i",
            f"audio={self._microphone}",
        ]

    @staticmethod
    def _default_microphone() -> str:
        """Using pyaudio to get the default device, only because windows is windows"""
        audio = pyaudio.PyAudio()

        try:
            device = audio.get_default_input_device_info()
            return str(device["name"])
        finally:
            audio.terminate()

    @staticmethod
    def _select_voice(language: str) -> str:
        ps_script = """
        Add-Type -AssemblyName System.Speech

        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $lang = $args[0]

        $voice = $s.GetInstalledVoices() |
            Where-Object {
                $_.Enabled -and
                $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $lang
            } |
            Select-Object -First 1

        if (-not $voice) {
            Write-Error "No installed voice found for language '$lang'"
            exit 1
        }

        $voice.VoiceInfo.Name
        """

        result = subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-CommandWithArgs",
                ps_script,
                language,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()
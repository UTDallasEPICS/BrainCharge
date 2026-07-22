"""Windows implementation of the AudioBackend protocol.

Configures FFmpeg audio input using the DirectShow backend and selects a
microphone from the devices reported by FFmpeg.
"""
from textwrap import dedent
from typing import Any
import subprocess

from . import AudioBackend

class WindowsAudioBackend(AudioBackend):
    def __init__(self, config: dict[str, Any]) -> None:
        """
        Supported configuration keys:
            ``windows_mic_name``:
                Preferred DirectShow microphone name.

                If the configured microphone is unavailable, the first microphone
                reported by ``FFmpeg`` is used.
        """
        self._microphone = self._select_microphone(config)

    def get_speak_command(self) -> list[str]:
        # TODO add language support to windows
        ps_script = """
        Add-Type -AssemblyName System.Speech;
        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer;
        $s.Rate = 0;
        $s.Speak($args[0])
        """

        return [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-CommandWithArgs",
            ps_script,
        ]

    def ffmpeg_input_args(self) -> list[str]:
        return ["-f","dshow","-i",
            f"audio={self._microphone}",
        ]

    @staticmethod
    def _select_microphone(config: dict[str, Any]) -> str:
        """Select the microphone to use for recording.

        Selection order:
        1. Configured microphone, if present.
        2. First microphone reported by FFmpeg.
        3. Built-in fallback.
        """
        configured = config.get("input_device", "").strip()

        result = subprocess.run(
            [
                "ffmpeg",
                "-f",
                "dshow",
                "-list_devices",
                "true",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )

        available = [
            line.split('"')[1].strip()
            for line in (result.stderr + result.stdout).splitlines()
            if "(audio)" in line and '"' in line
        ]

        # Use the configured microphone if FFmpeg found it, or if device
        # enumeration failed and it cannot be verified.
        if configured and (not available or configured in available):
            return configured

        # First available
        if selected := available[0]:
            if configured:
                print(
                    f"[Audio] Configured microphone not found: {configured!r}"
                )
                print("[Audio] Available microphones:")

                for microphone in available:
                    print(f"  - {microphone}")

                print(f"[Audio] Using: {selected!r}")

            return selected

        # Hardcoded fallback
        return "Microphone (Realtek Audio)"
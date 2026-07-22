"""Platform-specific audio backend selection.

This module defines the interface implemented by each operating-system-specific
audio backend and provides a factory for getting the correct implementation.
"""

from typing import Any, Protocol

class AudioBackend(Protocol):
    """Interface snub implemented by platform-specific audio backends."""

    def get_speak_command(self)-> list[str]:
        """
        Returns:
            Command-line arguments that run text to speach.
        """
        ...

    def ffmpeg_input_args(self) -> list[str]:
        """
        Returns:
            Command-line arguments that configure FFmpeg's input format and
            input device.
        """
        ...

def get(
    system: str,
    config: dict[str, Any],
)-> AudioBackend:
    """Creates the audio backend for the given operating system.

    Args:
        system:
            Operating-system name.
            Supported values are ``"Windows"``, ``"Linux"``, and ``"Darwin"``.
        config:
            Audio configuration values used by the selected backend.

    Returns:
        The audio backend for given operating system.
    Raises:
        RuntimeError:
            If the operating system is not supported.
    """
    match system:
        case "Windows":
            from .Windows import WindowsAudioBackend
            return WindowsAudioBackend(config)

        case "Linux":
            from .Linux import LinuxAudioBackend
            return LinuxAudioBackend(config)

        case "Darwin":
            from .macOS import MacOSAudioBackend
            return MacOSAudioBackend(config)
        case _:
            raise RuntimeError("Unsported OS")

__all__ = ["get"]
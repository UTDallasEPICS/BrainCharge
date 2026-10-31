"""Platform-specific vision backend selection.

This module defines the interface implemented by each operating-system-specific
vision backend and provides a factory for getting the correct implementation.
"""
from typing import Protocol

class VisionBackend(Protocol):
    """Interface snub implemented by platform-specific vision backends."""

def get(system: str) -> VisionBackend:
    """Creates the vision backend for the given operating system.

    Args:

        system:
            Operating-system name.
            Supported values are ``"Windows"``, ``"Linux"``, and ``"Darwin"``.

    Returns:
        The vision backend for given operating system.
    Raises:
        RuntimeError:
            If the operating system is not supported.
    """
    match system:
        case "Windows":
            from .Windows import WindowsVisionBackend
            return WindowsVisionBackend()

        case "Linux":
            from .Linux import LinuxVisionBackend
            return LinuxVisionBackend()

        case "Darwin":
            from .macOS import MacOSVisionBackend
            return MacOSVisionBackend()
        case _:
            raise RuntimeError("Unsported OS")

__all__ = ["get"]
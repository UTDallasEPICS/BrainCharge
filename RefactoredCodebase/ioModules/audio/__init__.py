"""Public interface for the audio subsystem.

Provides shared audio functionality while abstracting platform-specific
implementations behind a common interface.

Example:
    from audio import AudioService
"""

#~~ DEVELOPER NOTE ~~#
# The main reason this file exists is to make
# from audio import AudioService
# instead of having to do
# from audio.service import AudioService

# Otherwise this file can be ignored

from .service import AudioService
__all__ = ["AudioService"]
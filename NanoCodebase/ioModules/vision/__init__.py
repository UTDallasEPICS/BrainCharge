"""Public interface for the vision subsystem.

Provides shared vision functionality while abstracting platform-specific
implementations behind a common interface.

Example:
    from vision import VisionService
"""

#~~ DEVELOPER NOTE ~~#
# The main reason this file exists is to make
# from vision import VisionService
# instead of having to do
# from vision.service import VisionService

# Otherwise this file can be ignored

from .service import VisionService
__all__ = ["VisionService"]
"""Windows implementation of the AudioBackend protocol."""

from pathlib import Path
from typing import Any
import shutil
import sys

from . import AudioBackend


class WindowsAudioBackend(AudioBackend):
    def __init__(
        self,
        config: dict[str, Any],
        language: str = "en",
    ) -> None:
        """Windows audio backend.

        Args:
            config:
                Audio configuration dictionary.

            piper_model_path:
                Path to the Piper .onnx voice model.

            language:
                Current language identifier, such as "en" or "es".
        """

        self.language = language
        # self._validate_piper(self._voice)
        #
        # print(
        #     "[Audio-Backend] Selecting Piper voice: "
        #     f"{self._voice}"
        # )

    # Todo | Move to main or languge helper to validate
    @staticmethod
    def _validate_piper(model_path: Path) -> None:
        """Validate that Piper is able to run on this machine."""

        if not model_path.is_file():
            raise FileNotFoundError(
                f"Piper model not found: {model_path}\n"
                "Are you sure you downloaded a model?\n"
                f'"{sys.executable}" -m piper.download_voices '
                "en_US-mike-medium"
            )

        piper_config_path = Path(f"{model_path}.json")
        if not piper_config_path.is_file():
            raise FileNotFoundError(
                f"Piper model config not found: "
                f"{piper_config_path}"
            )

        if shutil.which("ffplay") is None:
            raise RuntimeError(
                "ffplay was not found. Piper uses ffplay "
                "for audio playback when no output file is "
                "specified."
            )
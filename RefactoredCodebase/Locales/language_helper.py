from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

def load_locale_config(
    language: str,
    locales_directory: Path = Path("Locales"),
) -> tuple[Any, Path]:
    """Load language-specific resources for the application.

    Locates the directory for the requested language, loads its phrase
    configuration from ``config.json``, and provides the path to the
    associated Vosk speech-recognition model.

    Args:
        language:
            Language identifier used to select the locale directory,
            such as ``"en"`` or ``"es"``.
        locales_directory:
            Root directory containing the available language directories.
            Defaults to ``Locales``.

    Returns:
        LocaleConfig:
            A locale configuration containing the loaded phrase data and
            the path to the language's Vosk model directory.

    Raises:
        FileNotFoundError:
            If the requested locale directory or its ``config.json`` file
            does not exist.
        json.JSONDecodeError:
            If ``config.json`` contains invalid JSON.
    """

    locale_directory = locales_directory / language

    if not locale_directory.is_dir():
        raise FileNotFoundError(
            f"Locale directory not found: {locale_directory}"
        )

    phrases_path = locale_directory / "config.json"
    if not phrases_path.is_file():
        raise FileNotFoundError(
            f"Locale phrases file not found: {phrases_path}"
        )

    with phrases_path.open("r", encoding="utf-8") as file:
        phrases = json.load(file)

    vosk_model_path = locale_directory / "voskModel"

    return phrases, vosk_model_path,
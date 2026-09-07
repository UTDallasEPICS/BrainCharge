from pathlib import Path
from typing import Any
import json


def load_locale_config(
    language: str,
    locales_directory: Path = Path("languageFiles"),
) -> tuple[Any, Path, Path]:
    """Load language-specific resources for the application.

    Returns:
        tuple containing:
            - phrase configuration
            - Vosk model directory
            - Piper ONNX voice model
    """

    locale_directory = locales_directory / language

    if not locale_directory.is_dir():
        raise FileNotFoundError(
            f"Locale directory not found: {locale_directory}"
        )

    # Language file
    phrases_path = locale_directory / "config.json"
    print(phrases_path)

    if not phrases_path.is_file():
        raise FileNotFoundError(
            f"Locale phrases file not found: {phrases_path}"
        )

    with phrases_path.open("r", encoding="utf-8") as file:
        phrases = json.load(file)

    # Vosk
    vosk_model_path = locale_directory / "voskModel"

    if not vosk_model_path.is_dir():
        raise FileNotFoundError(
            f"Vosk model directory not found: {vosk_model_path}"
        )

    # Piper
    piper_models = list(locale_directory.glob("*.onnx"))

    if not piper_models:
        raise FileNotFoundError(
            f"No Piper .onnx model found in: {locale_directory}"
        )

    if len(piper_models) > 1:
        raise RuntimeError(
            f"Multiple Piper models found in {locale_directory}: "
            f"{[model.name for model in piper_models]}"
        )

    piper_model_path = piper_models[0]

    # Make sure the corresponding Piper JSON exists
    piper_config_path = Path(
        str(piper_model_path) + ".json"
    )

    if not piper_config_path.is_file():
        raise FileNotFoundError(
            f"Piper config file not found: {piper_config_path}"
        )

    return (
        phrases,
        vosk_model_path,
        piper_model_path,
    )
from pathlib import Path
import json
import os
import platform
import tempfile
import shutil

from Locales.language_helper import load_locale_config
from app.orchestrator import Orchestrator
from ioServices.audio import AudioService


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    """
        Composition root to init & pass components required data and configurations
    """
    system = platform.system()

    config = Path("config.json")
    if not config.is_file():
        shutil.copy2(Path(f"app/defaultConfigs/{system.lower()}.json"), config)
        print(f"[MAIN] Config not found: Creating default config for {system}")

    config = load_json(config)
    audio_config = config.get("audio", {})

    language = config.get("language", "en")
    languagePhrases, vosk_model_path  = load_locale_config(language)

    temp_parent = (
        "/dev/shm"
        if system == "Linux" and os.path.isdir("/dev/shm")
        else None
    )

    with tempfile.TemporaryDirectory(
        prefix="companion_robot_",
        dir=temp_parent,
    ) as temporary_directory:
        audio = AudioService(
            system=system,
            language=config["language"],
            temp_directory=Path(temporary_directory),
            config=audio_config,
            vosk_model_path=vosk_model_path,
        )

        orchestrator = Orchestrator(
            language=languagePhrases,
            audio_service=audio,
        )

        orchestrator.startup()


if __name__ == "__main__":
    main()
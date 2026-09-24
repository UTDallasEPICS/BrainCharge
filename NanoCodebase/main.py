from pathlib import Path
import json
import os
import platform
from tempfile import TemporaryDirectory
import shutil

from app.orchestrator import Orchestrator
from ioModules.audio import AudioService

def main() -> None:
    """
        Composition root to init & pass components required data and configurations
    """
    system = platform.system()

    config = Path("userConfig.json")
    if not config.is_file():
        shutil.copy2(Path(f"./app/defaultConfigs/{system.lower()}.json"), config)
        print(f"[MAIN] Config not found: Creating default config for {system}")


    with config.open("r", encoding="utf-8") as file:
        config = json.load(file)

    audio_config = config.get("audio", {})

    language_dir = Path("languageFiles") / config.get("language", "en")
    with (language_dir / "config.json").open("r", encoding="utf-8") as file:
        language_phrases = json.load(file)
    piper_model_path:Path = next(language_dir.glob("*.onnx"))
    vosk_model_path:Path = next(language_dir.glob("vosk*"))

    temp_parent = (
        "/dev/shm"
        if system == "Linux" and os.path.isdir("/dev/shm")
        else None
    )

    with TemporaryDirectory(
        prefix="companion_robot_",
        dir=temp_parent,
    ) as temporary_directory:
        audio = AudioService(
            config=audio_config,
            temp_directory=Path(temporary_directory),
            vosk_model_path=vosk_model_path,
            piper_model_path=piper_model_path,
        )

        orchestrator = Orchestrator(
            language=language_phrases,
            audio_service=audio,
        )

        orchestrator.startup()

if __name__ == "__main__":
    main()
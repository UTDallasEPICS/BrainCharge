from pathlib import Path
import json
import os
import platform
from tempfile import TemporaryDirectory
import shutil

from app.orchestrator import Orchestrator
from ioModules.audio import AudioService
from ioModules.vision import VisionService

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

    # TODO: Move CV models from "NanoCodebase\ioModules\vision\facial_recognition\models"
    #       to "NanoCodebase\visionFiles" and change "opencv_models_path" below to use "visionFiles" path
    # opencv_models_path:Path = Path("visionFiles")
    opencv_models_path:Path = Path("ioModules", "vision", "facial_recognition", "models")

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

        vision = VisionService(opencv_models_path=opencv_models_path)

        orchestrator = Orchestrator(
            language=language_phrases,
            audio_service=audio,
            vision_service=vision,
        )

        orchestrator.startup()

if __name__ == "__main__":
    main()
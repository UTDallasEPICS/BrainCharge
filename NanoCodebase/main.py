from pathlib import Path
import json
import os
import platform
from tempfile import TemporaryDirectory
import shutil

from app.orchestrator import Orchestrator
from app.webapp import DisabledWebAppEvents, RobotState, WebAppEvents
from ioModules.audio import AudioService
from ioModules.vision import VisionService

# Web app backend on the same machine (reactApp/backend, default port 3001).
DEFAULT_WEBAPP_URL = "http://127.0.0.1:3001/api/nano/event"


def create_webapp_events(webapp_config: dict | None) -> WebAppEvents | DisabledWebAppEvents:
    """Build the web app link from the "webapp" config section (disabled if missing or off)."""
    if not webapp_config or not webapp_config.get("enabled", False):
        print('[MAIN] Web app face link disabled (enable it in the "webapp" section of userConfig.json)')
        return DisabledWebAppEvents()

    # NANO_TOKEN env var wins so the token can stay out of config files; must match backend/.env.
    token = os.environ.get("NANO_TOKEN") or webapp_config.get("token", "")
    if not token or token == "change-me":
        print("[MAIN] Web app token is not set; face events will be rejected until it matches NANO_TOKEN in backend/.env")

    return WebAppEvents(url=webapp_config.get("url") or DEFAULT_WEBAPP_URL, token=token)

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
        webapp = create_webapp_events(config.get("webapp"))

        orchestrator = Orchestrator(
            language=language_phrases,
            audio_service=audio,
            vision_service=vision,
            webapp=webapp,
        )

        try:
            orchestrator.startup()
        finally:
            # Return the face to idle when the robot stops (including Ctrl+C).
            webapp.send_state(RobotState.SLEEPING)
            webapp.close()

if __name__ == "__main__":
    main()

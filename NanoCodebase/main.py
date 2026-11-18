from pathlib import Path
import json
import os
import platform
from tempfile import gettempdir
import shutil

from app.orchestrator import Orchestrator
from app.webapp import DisabledWebAppEvents, WebAppEvents
from ioModules.audio import AudioService
from ioModules.vision import VisionService


def _build_webapp_link(config: dict):
    """Start the Nano ↔ webapp HTTP bridge when ``webapp.enabled`` is true.

    Outbound: face ``robot.state`` / ``robot.expression`` → POST /api/nano/event
    Inbound:  poll GET /api/nano/inbox for ``ui.settings`` (and future ui.*)

    ``token`` must match the backend ``NANO_TOKEN``. If urls for inbox/settings
    are omitted, they are derived from the event ``url``.
    """
    webapp_cfg = config.get("webapp") or {}
    if not webapp_cfg.get("enabled"):
        return DisabledWebAppEvents()

    url = str(webapp_cfg.get("url") or "").strip()
    token = str(webapp_cfg.get("token") or "").strip()
    if not url or not token:
        print("[MAIN] webapp.enabled but url/token missing; webapp link disabled")
        return DisabledWebAppEvents()

    # Default inbox/settings to the same host as the face event endpoint.
    base = url.rsplit("/api/nano/event", 1)[0] if "/api/nano/event" in url else url.rstrip("/")
    inbox_url = str(webapp_cfg.get("inbox_url") or f"{base}/api/nano/inbox").strip()
    settings_url = str(webapp_cfg.get("settings_url") or f"{base}/api/settings").strip()
    poll_interval_s = float(webapp_cfg.get("poll_interval_s") or 2.0)

    link = WebAppEvents(
        url=url,
        token=token,
        inbox_url=inbox_url,
        settings_url=settings_url,
        poll_interval_s=poll_interval_s,
        # Used only to warn when UI language differs; no hot language reload.
        initial_language=str(config.get("language") or "en"),
    )
    # Pull any settings already saved in the webapp before the first inbox poll.
    link.sync_settings_from_server()
    print(f"[MAIN] Webapp link enabled (polling inbox every {poll_interval_s}s)")
    return link


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
    vision_config = config.get("vision", {})

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
        else gettempdir()
    )

    # Daemon threads inside WebAppEvents keep polling/sending while the robot runs.
    webapp = _build_webapp_link(config)

    audio = AudioService(
        config=audio_config,
        temp_directory={
            "name": "companion_robot_temp",
            "parent": temp_parent
        },
        vosk_model_path=vosk_model_path,
        piper_model_path=piper_model_path,
    )
    vision = VisionService(
        config=vision_config,
        opencv_models_path=opencv_models_path,
        test_mode=False,
    )

    orchestrator = Orchestrator(
        language=language_phrases,
        audio_service=audio,
        vision_service=vision,
    )

    # Hold the link on the orchestrator so it isn't GC'd and is easy to use later
    # (e.g. send_state / read webapp.settings).
    orchestrator.webapp = webapp
    orchestrator.startup()

if __name__ == "__main__":
    main()

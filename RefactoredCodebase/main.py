from pathlib import Path

from ioServices.audio import AudioService
from app.orchestrator import Orchestrator
import platform
import os
import json
import tempfile

def main():
    """
        Composition root to init & pass components required data and configurations
    """
    system = platform.system()

    config_path = Path("config.json")
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}"
        )

    with config_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = json.load(file)
    audio_config = config.get("audio", {})

    lang = config.get("language", "en")
    lang_path = Path("Locales/" + lang + ".json")
    if not lang_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {lang_path}"
        )
    with config_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        lang_file = json.load(file)

    # Getting the temp directory for the OS
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # if system == "Linux" and os.path.isdir("/dev/shm"):
    #     # Linux uses a different system as /dev/shm is stored in memory rather than disk. This is primarily for the json orion nano
    #     # https://linuxvox.com/blog/devshm-in-linux/
    #     temp_directory = tempfile.TemporaryDirectory(
    #         prefix=f"companion_robot_{timestamp}",
    #         dir="/dev/shm",
    #     )
    #
    #     #temp_directory = f"/dev/shm/companion_robot_{time.ctime()}"
    #     #os.makedirs(temp_directory, exist_ok=True)
    # else:
    #     temp_directory = tempfile.TemporaryDirectory(prefix=f"companion_robot_{timestamp}_")

    # Init
    with tempfile.TemporaryDirectory(
        prefix="companion_robot_",
        dir= "/dev/shm" if system == "Linux" and os.path.isdir("/dev/shm") else None,
    ) as temp_directory:
        temp_directory = Path(temp_directory)
        # Temp directory for outputs, For linux specifically /dev/shm is kept in RAM so we dont need to use main bus storage

        audio = AudioService(
            system,
            temp_directory,
            audio_config,
        )

        Orchestrator(
            language=lang_file,
            audio_service=audio,
        ).startup()


if __name__ == "__main__":
    main()
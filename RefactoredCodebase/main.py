"""
    Main acting as composition root to init & pass components required data and configurations
    Should also rectify any issues with differing OS
"""
from datetime import datetime

from ioServices.audio import AudioService
from app.orchestrator import Orchestrator
import time
import platform
import os
import json
import tempfile


def main():
    system = platform.system()

    # getting configs
    CONFIG_PATH = "config.json"
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Config file not found: {CONFIG_PATH}\n"
            "Create one based on the project README or JETSON_SETUP.md."
        )
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    # Getting the temp directory for the OS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if system == "Linux" and os.path.isdir("/dev/shm"):
        # Linux uses a different system as /dev/shm is stored in memory rather than disk. This is primarily for the json orion nano
        # https://linuxvox.com/blog/devshm-in-linux/
        temp_directory = tempfile.TemporaryDirectory(
            prefix=f"companion_robot_{timestamp}",
            dir="/dev/shm",
        )

        #temp_directory = f"/dev/shm/companion_robot_{time.ctime()}"
        #os.makedirs(temp_directory, exist_ok=True)
    else:
        temp_directory = tempfile.TemporaryDirectory(prefix=f"companion_robot_{timestamp}_")

    # Init each service
    audio = AudioService(system, temp_directory.name, config.get("audio"))
    Orchestrator(
        audio
    ).startup()


if __name__ == "__main__":
    main()
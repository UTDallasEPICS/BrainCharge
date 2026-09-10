from pathlib import Path
import platform
import subprocess
import sys
import urllib.request
from shutil import unpack_archive

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = platform.system()
ARCH = platform.machine().lower()

VOSK_URL = "https://alphacephei.com/vosk/models"

WHISPER_DIR = ROOT / "whisper.cpp"
WHISPER_MODEL = "ggml-base.bin"
WHISPER_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/" + WHISPER_MODEL

LANGUAGE_FILE_DIR = ROOT / "languageFiles"
LANGUAGE_MODELS = [
    (
        "en",                           # Language
        "en_US-mike-medium",            # Piper model
        "vosk-model-small-en-us-0.15",  # Vosk model name
    ),
    (
        "es",  # Language
        "es_MX-ald-medium",  # Piper model
        "vosk-model-small-es-0.42",  # Vosk model name
    )
]

def run(*args):
    print("+", " ".join(map(str, args)))
    subprocess.run(args, check=True)

def setup_whisper():
    if WHISPER_DIR.exists():
        print("whisper.cpp already installed.")
        return
    WHISPER_DIR.mkdir(parents=True, exist_ok=True)

    whisper_bin = {
        "Windows":"whisper-bin-x64.zip",
        "Linux": "whisper-bin-ubuntu-arm64.tar.gz" if ARCH in ("arm64", "aarch64")
            else "whisper-bin-ubuntu-x64.tar.gz",
    }[SYSTEM]
    # If ^ keyerror, it means system not supported (MacOS)
    # Linux doesn't have any compatible prebuilt version that supports arm64 + cuda so we will need to compile from source

    archive_path = WHISPER_DIR / whisper_bin

    print("Downloading whisper.cpp...")
    run(
        "gh",
        "release",
        "download",
        "--repo",
        "ggml-org/whisper.cpp",
        "--pattern",
        whisper_bin,
        "--dir",
        WHISPER_DIR,
    )

    print("Extracting whisper.cpp...")

    try:
        unpack_archive(archive_path, WHISPER_DIR)   # Could have problems with other diff installs of whisper.cpp not having the binary file named "Release"
    finally:
        archive_path.unlink()

    print("whisper.cpp installed.")

    if (WHISPER_DIR/ WHISPER_MODEL).exists():
        print("Whisper model already installed.")
        return
    print("Downloading Whisper model...")
    urllib.request.urlretrieve(
        WHISPER_MODEL_URL,
        WHISPER_DIR / WHISPER_MODEL,
    )

    print("Whisper model installed.")


def setup_languages():
    for language, piperModel, voskModel in LANGUAGE_MODELS:
        language_dir = LANGUAGE_FILE_DIR / language

        # region PiperInstall
        model_file = language_dir / f"{piperModel}.onnx"
        config_file = language_dir / f"{piperModel}.onnx.json"
        if not model_file.exists() or not config_file.exists():
            print(f"Downloading Piper voice '{piperModel}'...")

            run(
                sys.executable,
                "-m",
                "piper.download_voices",
                "--data-dir",
                language_dir,
                piperModel,
            )
        else:
            print(f"Piper voice for'{language}' already installed.")
        # endregion

        # region VoskInstall
        model_file = next(language_dir.glob("vosk*"), None)
        if not model_file:
            print(f"Downloading Vosk model {voskModel} for '{language}'...")
            archive_path,_ = urllib.request.urlretrieve(f"{VOSK_URL}/{voskModel}.zip")
            archive_path = Path(archive_path)

            try:
                print(f"Extracting Vosk model...")
                unpack_archive(archive_path, language_dir, "zip")
                # (language_dir/voskModel).rename(language_dir/"voskModel")
            finally:
                archive_path.unlink()
            print(f"Vosk model for '{language}' installed.")
        else:
            print(f"Vosk model for '{language}' already installed.")
        # endregion

def setup_ollama():
    try:
        run("ollama", "pull", "gemma3n:e4b")
    except FileNotFoundError:
        print(
            "Ollama is not installed or is not on PATH.\n"
            "Install Ollama and run this setup again."
        )


def main():
    setup_whisper()
    setup_languages()
    setup_ollama()

    print("\nPC setup complete.")


if __name__ == "__main__":
    main()
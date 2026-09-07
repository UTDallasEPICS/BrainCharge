from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = platform.system()
ARCH = platform.machine().lower()

WHISPER_DIR = ROOT / "whisper.cpp"
WHISPER_MODEL = WHISPER_DIR / "ggml-base.bin"

WHISPER_MODEL_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
)

LANGUAGE_FILE_DIR = ROOT / "LanguageFiles"

PIPER_VOICES = [
    ("en", "en_US-mike-medium"),
    ("es", "es_MX-ald-medium"),
]

VOSK_MODELS = [
    (
        "en",
        "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        "vosk-model-small-en-us-0.15",
    ),
    (
        "es",
        "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
        "vosk-model-small-es-0.42",
    ),
]


def run(*args):
    print("+", " ".join(map(str, args)))
    subprocess.run(args, check=True)


def get_whisper_release():
    if SYSTEM == "Windows":
        return "whisper-bin-x64.zip", "whisper-cli.exe"

    if SYSTEM == "Linux":
        if ARCH in ("arm64", "aarch64"):
            return "whisper-bin-ubuntu-arm64.tar.gz", "whisper-cli"

        return "whisper-bin-ubuntu-x64.tar.gz", "whisper-cli"

    raise RuntimeError(
        f"Automatic whisper.cpp installation is not supported on {SYSTEM}."
    )


def extract_archive(archive_path: Path, destination: Path):
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)

    elif archive_path.name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(destination)

    else:
        raise RuntimeError(f"Unsupported archive format: {archive_path}")


def install_whisper():
    whisper_bin, executable_name = get_whisper_release()

    archive_path = WHISPER_DIR / whisper_bin
    executable_path = WHISPER_DIR / executable_name

    WHISPER_DIR.mkdir(parents=True, exist_ok=True)

    if executable_path.exists():
        print("whisper.cpp already installed.")
        return

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
        str(WHISPER_DIR),
    )

    print("Extracting whisper.cpp...")

    extract_archive(archive_path, WHISPER_DIR)

    archive_path.unlink()

    print("whisper.cpp installed.")


def install_whisper_model():
    if WHISPER_MODEL.exists():
        print("Whisper model already installed.")
        return

    print("Downloading Whisper model...")

    WHISPER_DIR.mkdir(parents=True, exist_ok=True)

    urllib.request.urlretrieve(
        WHISPER_MODEL_URL,
        WHISPER_MODEL,
    )

    print("Whisper model installed.")


def install_piper_voices():
    for language, voice in PIPER_VOICES:
        voice_dir = LANGUAGE_FILE_DIR / language
        model_file = voice_dir / f"{voice}.onnx"
        config_file = voice_dir / f"{voice}.onnx.json"

        if model_file.exists() and config_file.exists():
            print(f"Piper voice '{voice}' already installed.")
            continue

        voice_dir.mkdir(parents=True, exist_ok=True)

        print(f"Downloading Piper voice '{voice}'...")

        run(
            sys.executable,
            "-m",
            "piper.download_voices",
            "--data-dir",
            str(voice_dir),
            voice,
        )


def install_vosk_models():
    for language, url, extracted_name in VOSK_MODELS:
        language_dir = LANGUAGE_FILE_DIR / language
        model_dir = language_dir / "voskModel"
        zip_path = language_dir / "vosk-model.zip"

        if model_dir.exists() and any(model_dir.iterdir()):
            print(f"Vosk model for '{language}' already installed.")
            continue

        language_dir.mkdir(parents=True, exist_ok=True)

        print(f"Downloading Vosk model for '{language}'...")

        urllib.request.urlretrieve(url, zip_path)

        print(f"Extracting Vosk model for '{language}'...")

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(language_dir)

        extracted_dir = language_dir / extracted_name
        extracted_dir.rename(model_dir)

        zip_path.unlink()

        print(f"Vosk model for '{language}' installed.")


def setup_ollama():
    try:
        run("ollama", "pull", "gemma3n:e4b")
    except FileNotFoundError:
        print(
            "Ollama is not installed or is not on PATH.\n"
            "Install Ollama and run this setup again."
        )


def main():
    install_whisper()
    install_whisper_model()
    install_piper_voices()
    install_vosk_models()
    setup_ollama()

    print("\nPC setup complete.")


if __name__ == "__main__":
    main()
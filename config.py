import os
import platform
import subprocess
import re


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SYSTEM = platform.system()
def _load_dotenv_if_present():
    """Lightweight .env loader (no external deps)."""
    env_path = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Don't override already-set env vars
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        # Silently ignore .env errors
        pass


# Load .env very early so env overrides apply
_load_dotenv_if_present()


def _default_whisper_path() -> str:
    # Allow override from environment
    env = os.getenv("WHISPER_PATH")
    if env:
        return env

    if SYSTEM == "Windows":
        return os.path.join(REPO_ROOT, "whisper.cpp", "build", "bin", "Release", "whisper-cli.exe")
    # macOS or Linux
    return os.path.join(REPO_ROOT, "whisper.cpp", "build", "bin", "whisper-cli")


def _default_whisper_model() -> str:
    return os.getenv(
        "WHISPER_MODEL",
        os.path.join(REPO_ROOT, "whisper.cpp", "models", "ggml-base.en.bin"),
    )


def _detect_windows_dshow_device() -> str | None:
    try:
        # ffmpeg prints device list to stderr; 'dummy' input is intentional
        proc = subprocess.run(
            ["ffmpeg", "-f", "dshow", "-list_devices", "true", "-i", "dummy"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stderr or "") + "\n" + (proc.stdout or "")
        # Look for quoted device names that include 'Microphone'
        candidates = re.findall(r'"([^"]*Microphone[^"]*)"', output, flags=re.IGNORECASE)
        if candidates:
            return f"audio={candidates[0]}"
        # Fallback: look for any audio device lines
        m = re.search(r'"([^"]+)"\s*\(audio\)', output, flags=re.IGNORECASE)
        if m:
            return f"audio={m.group(1)}"
    except Exception:
        pass
    return None


def _default_ffmpeg_format_and_device():
    fmt = os.getenv("FFMPEG_FORMAT")
    dev = os.getenv("FFMPEG_DEVICE")
    if fmt and dev:
        return fmt, dev

    if SYSTEM == "Windows":
        # Prefer WASAPI default device which works on most modern Windows setups
        # Users can override via FFMPEG_FORMAT/FFMPEG_DEVICE.
        # If WASAPI isn't available in this ffmpeg build, fall back to dshow detection.
        try:
            proc = subprocess.run(
                ["ffmpeg", "-f", "wasapi", "-i", "default", "-t", "0.1", "-f", "null", "-"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 or "Input #0, wasapi" in (proc.stderr or ""):
                return "wasapi", "default"
        except Exception:
            pass

        detected = _detect_windows_dshow_device()
        return "dshow", (detected or "audio=default")
    if SYSTEM == "Darwin":
        # avfoundation uses ":<audio_index>"; 0 is common default
        return "avfoundation", ":0"
    # Linux defaults (may vary by distro). Try ALSA default device.
    return "alsa", "default"


# Public config values
WHISPER_PATH = _default_whisper_path()
WHISPER_MODEL = _default_whisper_model()
FFMPEG_FORMAT, FFMPEG_DEVICE = _default_ffmpeg_format_and_device()
RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", "5"))
TEMP_AUDIO = os.getenv("TEMP_AUDIO", "input.wav")
TEMP_TRANSCRIPT = os.getenv("TEMP_TRANSCRIPT", "transcript")
TEMP_RESPONSE = os.getenv("TEMP_RESPONSE", "response.wav")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


def ffmpeg_record_command(output_wav: str) -> list[str]:
    return [
        "ffmpeg",
        "-f",
        FFMPEG_FORMAT,
        "-i",
        FFMPEG_DEVICE,
        "-t",
        str(RECORD_SECONDS),
        output_wav,
        "-y",
    ]

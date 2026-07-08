import os
import platform
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent
SYSTEM = platform.system()


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode, out


def list_windows_devices() -> list[tuple[str, str]]:
    # Return list of (format, device) pairs to choose from
    devices: list[tuple[str, str]] = []

    # WASAPI default option (usually works out of the box)
    rc, out = run(["ffmpeg", "-f", "wasapi", "-list_devices", "true", "-i", "dummy"])  # not all builds support
    if "wasapi" in out.lower():
        devices.append(("wasapi", "default"))

    # DShow: enumerate microphones
    rc, out = run(["ffmpeg", "-f", "dshow", "-list_devices", "true", "-i", "dummy"])  # prints to stderr
    # Look for lines like: "Microphone ..." (audio)
    for m in re.finditer(r"\"([^\"]+)\"\s*\(audio\)", out, flags=re.IGNORECASE):
        name = m.group(1)
        devices.append(("dshow", f"audio={name}"))

    # De-duplicate while preserving order
    seen = set()
    uniq: list[tuple[str, str]] = []
    for fmt, dev in devices:
        key = (fmt, dev)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((fmt, dev))
    return uniq


def list_macos_devices() -> list[tuple[str, str]]:
    # avfoundation index listing
    rc, out = run(["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""])  # prints to stderr
    # Build some common candidates: default :0 (audio index)
    devices = [("avfoundation", ":0")]
    return devices


def list_linux_devices() -> list[tuple[str, str]]:
    # Try ALSA default
    devices = [("alsa", "default")]
    return devices


def choose(items: list[tuple[str, str]]):
    if not items:
        print("No audio devices found. Ensure ffmpeg is installed and supports your OS input.")
        return None
    print("Select an input device:")
    for i, (fmt, dev) in enumerate(items):
        print(f"  [{i}] {fmt} :: {dev}")
    while True:
        sel = input("Enter number (or press Enter to cancel): ").strip()
        if sel == "":
            return None
        if sel.isdigit():
            idx = int(sel)
            if 0 <= idx < len(items):
                return items[idx]
        print("Invalid selection. Try again.")


def write_env(fmt: str, dev: str):
    env_path = REPO_ROOT / ".env"
    # Preserve existing lines, update or append keys
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    existing["FFMPEG_FORMAT"] = fmt
    existing["FFMPEG_DEVICE"] = dev
    content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    env_path.write_text(content, encoding="utf-8")
    print(f"Saved to {env_path}:")
    print(f"  FFMPEG_FORMAT={fmt}")
    print(f"  FFMPEG_DEVICE={dev}")


def main():
    if SYSTEM == "Windows":
        items = list_windows_devices()
    elif SYSTEM == "Darwin":
        items = list_macos_devices()
    else:
        items = list_linux_devices()

    choice = choose(items)
    if not choice:
        print("No changes made.")
        return
    fmt, dev = choice
    write_env(fmt, dev)


if __name__ == "__main__":
    main()

"""Download OpenCV Zoo ONNX models required by the facial recognition engine."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from facial_recognition.config import (
    DEFAULT_MODELS_DIR,
    SFACE_FILENAME,
    SFACE_URL,
    YUNET_FILENAME,
    YUNET_URL,
)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[FR] Model already present: {dest.name}")
        return
    print(f"[FR] Downloading {dest.name} ...")
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    print(f"[FR] Saved {dest} ({dest.stat().st_size:,} bytes)")


def ensure_models(models_dir: Path | None = None) -> tuple[Path, Path]:
    """
    Ensure YuNet + SFace ONNX files exist under models_dir.
    Returns (yunet_path, sface_path).
    """
    root = Path(models_dir) if models_dir is not None else DEFAULT_MODELS_DIR
    root.mkdir(parents=True, exist_ok=True)
    yunet = root / YUNET_FILENAME
    sface = root / SFACE_FILENAME
    _download(YUNET_URL, yunet)
    _download(SFACE_URL, sface)
    return yunet, sface


if __name__ == "__main__":
    ensure_models()

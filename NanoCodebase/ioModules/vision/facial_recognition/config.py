"""Configuration for the facial recognition module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import platform

# Package root: facial_recognition/
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

# Enrollment: one subfolder per person, any number of images inside
#   known_faces/
#     Alice/img1.jpg, img2.png
#     Bob/photo.jpg
DEFAULT_KNOWN_FACES_DIR = PACKAGE_ROOT / "known_faces"
DEFAULT_MODELS_DIR = PACKAGE_ROOT / "models"
DEFAULT_CACHE_DIR = PACKAGE_ROOT / "cache"
DEFAULT_EMBEDDINGS_CACHE = DEFAULT_CACHE_DIR / "embeddings.npz"

# OpenCV Zoo ONNX models (YuNet detector + SFace embedder)
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
SFACE_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx"
)
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"

# Image extensions accepted for enrollment
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# SFace cosine-similarity threshold (OpenCV docs recommend ~0.363)
DEFAULT_MATCH_THRESHOLD = 0.363

# Detector input size — smaller = faster, slightly less accurate
DEFAULT_DET_WIDTH = 320
DEFAULT_DET_HEIGHT = 320
DEFAULT_SCORE_THRESHOLD = 0.7
DEFAULT_NMS_THRESHOLD = 0.3
DEFAULT_TOP_K = 5000

# Camera defaults (match cv_pipeline platform backends)
DEFAULT_CAMERA_INDEX = 0
DEFAULT_FRAME_WIDTH = 640
DEFAULT_FRAME_HEIGHT = 480


def system_name() -> str:
    return platform.system()


@dataclass
class FRConfig:
    """Runtime configuration for FaceRecognitionEngine / app."""

    known_faces_dir: Path = field(default_factory=lambda: DEFAULT_KNOWN_FACES_DIR)
    models_dir: Path = field(default_factory=lambda: DEFAULT_MODELS_DIR)
    cache_path: Path = field(default_factory=lambda: DEFAULT_EMBEDDINGS_CACHE)

    match_threshold: float = DEFAULT_MATCH_THRESHOLD
    det_width: int = DEFAULT_DET_WIDTH
    det_height: int = DEFAULT_DET_HEIGHT
    score_threshold: float = DEFAULT_SCORE_THRESHOLD
    nms_threshold: float = DEFAULT_NMS_THRESHOLD
    top_k: int = DEFAULT_TOP_K

    camera_index: int = DEFAULT_CAMERA_INDEX
    frame_width: int = DEFAULT_FRAME_WIDTH
    frame_height: int = DEFAULT_FRAME_HEIGHT

    # Skip identity matching every N-1 frames (detection still runs when True)
    # 1 = recognize every frame (lowest lag for identity labels that update often)
    recognize_every_n_frames: int = 1

    # Reuse last label for same track-like bbox IoU if we skip recognition frames
    show_fps: bool = True
    mirror_preview: bool = True

    unknown_label: str = "Unknown"

    def yunet_path(self) -> Path:
        return self.models_dir / YUNET_FILENAME

    def sface_path(self) -> Path:
        return self.models_dir / SFACE_FILENAME

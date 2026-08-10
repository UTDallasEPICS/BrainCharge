"""SFace embedding extraction (OpenCV FaceRecognizerSF)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from facial_recognition.detector import FaceBox


class FaceEncoder:
    """
    Align + extract 128-D SFace feature vectors.
    Cosine similarity is used for matching (see OpenCV FaceRecognizerSF docs).
    """

    def __init__(self, model_path: Path | str) -> None:
        path = str(model_path)
        if not Path(path).is_file():
            raise FileNotFoundError(f"SFace model not found: {path}")
        self._sf = cv2.FaceRecognizerSF.create(path, "")

    def align_crop(self, bgr: np.ndarray, face: FaceBox) -> Optional[np.ndarray]:
        """
        Align face using 5 landmarks from YuNet (OpenCV expects 1x15 detect row).
        Falls back to tight bbox crop if align fails.
        """
        # Reconstruct a FaceDetectorYN-style face row (1 x 15) for alignCrop
        x, y = float(face.x1), float(face.y1)
        w, h = float(face.x2 - face.x1), float(face.y2 - face.y1)
        row = np.zeros(15, dtype=np.float32)
        row[0:4] = (x, y, w, h)
        for i, (lx, ly) in enumerate(face.landmarks):
            row[4 + 2 * i] = lx
            row[5 + 2 * i] = ly
        row[14] = face.score

        try:
            aligned = self._sf.alignCrop(bgr, row)
            if aligned is None or aligned.size == 0:
                return None
            return aligned
        except cv2.error:
            # Fallback: naive crop with padding
            pad = 0.15
            fh, fw = bgr.shape[:2]
            bw, bh = face.x2 - face.x1, face.y2 - face.y1
            cx, cy = (face.x1 + face.x2) / 2, (face.y1 + face.y2) / 2
            side = max(bw, bh) * (1 + pad)
            x1 = max(0, int(cx - side / 2))
            y1 = max(0, int(cy - side / 2))
            x2 = min(fw, int(cx + side / 2))
            y2 = min(fh, int(cy + side / 2))
            crop = bgr[y1:y2, x1:x2]
            return crop if crop.size else None

    def encode_aligned(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """Return L2-ready feature vector for an aligned face crop (float32)."""
        feat = self._sf.feature(aligned_bgr)
        return np.asarray(feat, dtype=np.float32).reshape(-1)

    def encode(self, bgr: np.ndarray, face: FaceBox) -> Optional[np.ndarray]:
        aligned = self.align_crop(bgr, face)
        if aligned is None:
            return None
        return self.encode_aligned(aligned)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity in [ -1, 1 ]. Higher = more similar."""
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        b = np.asarray(b, dtype=np.float32).reshape(-1)
        # Prefer OpenCV match if shapes match SF output
        try:
            return float(
                self._sf.match(
                    a.reshape(1, -1),
                    b.reshape(1, -1),
                    cv2.FaceRecognizerSF_FR_COSINE,
                )
            )
        except Exception:
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na < 1e-8 or nb < 1e-8:
                return 0.0
            return float(np.dot(a, b) / (na * nb))

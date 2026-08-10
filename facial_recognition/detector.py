"""YuNet face detection wrapper (OpenCV FaceDetectorYN)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class FaceBox:
    """Detected face in image coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int
    score: float
    # 5 landmarks: right_eye, left_eye, nose, right_mouth, left_mouth (x,y)
    landmarks: Tuple[Tuple[float, float], ...]

    @property
    def xyxy(self) -> Tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2, self.y2

    def as_int_rect(self) -> Tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2 - self.x1, self.y2 - self.y1


class FaceDetector:
    """Thin wrapper around cv2.FaceDetectorYN for low-latency face boxes."""

    def __init__(
        self,
        model_path: Path | str,
        det_width: int = 320,
        det_height: int = 320,
        score_threshold: float = 0.7,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> None:
        path = str(model_path)
        if not Path(path).is_file():
            raise FileNotFoundError(f"YuNet model not found: {path}")

        self._det_size = (det_width, det_height)
        self._detector = cv2.FaceDetectorYN.create(
            path,
            "",
            self._det_size,
            score_threshold,
            nms_threshold,
            top_k,
        )

    def set_input_size(self, width: int, height: int) -> None:
        """Update detector input size when frame resolution changes."""
        size = (int(width), int(height))
        if size != self._det_size:
            self._det_size = size
            self._detector.setInputSize(size)

    def detect(self, bgr: np.ndarray) -> List[FaceBox]:
        if bgr is None or bgr.size == 0:
            return []

        h, w = bgr.shape[:2]
        self.set_input_size(w, h)

        _, faces = self._detector.detect(bgr)
        if faces is None or len(faces) == 0:
            return []

        results: List[FaceBox] = []
        for row in faces:
            x, y, bw, bh = row[0:4]
            score = float(row[14])
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(w - 1, int(x + bw))
            y2 = min(h - 1, int(y + bh))
            landmarks = tuple(
                (float(row[i]), float(row[i + 1])) for i in range(4, 14, 2)
            )
            results.append(
                FaceBox(x1=x1, y1=y1, x2=x2, y2=y2, score=score, landmarks=landmarks)
            )
        return results

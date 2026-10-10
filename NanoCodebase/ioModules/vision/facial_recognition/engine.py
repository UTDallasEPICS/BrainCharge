"""
Core facial recognition engine.

Designed for:
  - Standalone real-time use (see app.py / __main__.py)
  - In-pipeline use: call `recognize(frame)` on frames from a shared camera
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from facial_recognition.config import FRConfig
from facial_recognition.detector import FaceBox, FaceDetector
from facial_recognition.encoder import FaceEncoder
from facial_recognition.gallery import Gallery, load_or_build_gallery
from facial_recognition.models_setup import ensure_models


@dataclass(frozen=True)
class Recognition:
    """One recognized face in a frame."""

    name: str
    confidence: float  # cosine similarity [~0..1] for SFace
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    score: float  # detector confidence
    is_known: bool

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "confidence": round(float(self.confidence), 4),
            "bbox": list(self.bbox),
            "detector_score": round(float(self.score), 4),
            "is_known": self.is_known,
        }


class FaceRecognitionEngine:
    """
    Modular face recognition service.

    Typical standalone use
    ----------------------
        engine = FaceRecognitionEngine()
        engine.initialize()
        results = engine.recognize(frame)

    Pipeline use (shared frames)
    ----------------------------
        engine = FaceRecognitionEngine(config)
        engine.initialize()
        # inside your existing camera loop:
        results = engine.recognize(frame)
    """

    def __init__(self, config: Optional[FRConfig] = None) -> None:
        self.config = config or FRConfig()
        self.detector: Optional[FaceDetector] = None
        self.encoder: Optional[FaceEncoder] = None
        self.gallery: Gallery = Gallery()
        self._ready = False
        self._frame_idx = 0
        self._last_results: List[Recognition] = []

    @property
    def ready(self) -> bool:
        return self._ready

    def initialize(self, force_rebuild_gallery: bool = False) -> None:
        """Download models if needed, build detectors, load known-face gallery."""
        cfg = self.config
        cfg.known_faces_dir = Path(cfg.known_faces_dir)
        cfg.models_dir = Path(cfg.models_dir)
        cfg.cache_path = Path(cfg.cache_path)

        cfg.known_faces_dir.mkdir(parents=True, exist_ok=True)
        yunet, sface = ensure_models(cfg.models_dir)

        self.detector = FaceDetector(
            yunet,
            det_width=cfg.det_width,
            det_height=cfg.det_height,
            score_threshold=cfg.score_threshold,
            nms_threshold=cfg.nms_threshold,
            top_k=cfg.top_k,
        )
        self.encoder = FaceEncoder(sface)
        self.gallery = load_or_build_gallery(
            cfg.known_faces_dir,
            self.detector,
            self.encoder,
            cfg.cache_path,
            force_rebuild=force_rebuild_gallery,
        )
        self._ready = True
        print("[FR] Engine ready.")

    def reload_gallery(self, force_rebuild: bool = True) -> None:
        """Re-scan known_faces/ after you add or remove enrollment photos."""
        if not self.detector or not self.encoder:
            raise RuntimeError("Call initialize() before reload_gallery().")
        self.gallery = load_or_build_gallery(
            self.config.known_faces_dir,
            self.detector,
            self.encoder,
            self.config.cache_path,
            force_rebuild=force_rebuild,
        )

    def detect_faces(self, frame_bgr: np.ndarray) -> List[FaceBox]:
        if not self.detector:
            raise RuntimeError("Call initialize() first.")
        return self.detector.detect(frame_bgr)

    def recognize(
        self,
        frame_bgr: np.ndarray,
        threshold: Optional[float] = None,
    ) -> List[Recognition]:
        """
        Detect faces and match against the gallery.
        Returns one Recognition per face (largest-first not required).

        Low-latency tip: set config.recognize_every_n_frames > 1 to skip
        embedding extraction on some frames (labels may lag slightly).
        """
        if not self._ready or not self.detector or not self.encoder:
            raise RuntimeError("Call initialize() first.")

        thr = self.config.match_threshold if threshold is None else threshold
        self._frame_idx += 1
        n = max(1, int(self.config.recognize_every_n_frames))

        faces = self.detector.detect(frame_bgr)
        if not faces:
            self._last_results = []
            return []

        # Detection-only frames: keep last identities if bbox count matches, else unknown boxes only
        if n > 1 and (self._frame_idx % n) != 0 and self._last_results:
            if len(self._last_results) == len(faces):
                # Update boxes only; keep names
                updated: List[Recognition] = []
                for face, prev in zip(faces, self._last_results):
                    updated.append(
                        Recognition(
                            name=prev.name,
                            confidence=prev.confidence,
                            bbox=face.xyxy,
                            score=face.score,
                            is_known=prev.is_known,
                        )
                    )
                self._last_results = updated
                return updated

        results: List[Recognition] = []
        for face in faces:
            emb = self.encoder.encode(frame_bgr, face)
            if emb is None:
                results.append(
                    Recognition(
                        name=self.config.unknown_label,
                        confidence=0.0,
                        bbox=face.xyxy,
                        score=face.score,
                        is_known=False,
                    )
                )
                continue
            name, conf = self.gallery.match(emb, self.encoder, thr)
            known = bool(name)
            results.append(
                Recognition(
                    name=name if known else self.config.unknown_label,
                    confidence=conf,
                    bbox=face.xyxy,
                    score=face.score,
                    is_known=known,
                )
            )

        self._last_results = results
        return results

    def annotate(
        self,
        frame_bgr: np.ndarray,
        results: Sequence[Recognition],
        fps: Optional[float] = None,
    ) -> np.ndarray:
        """Draw boxes + labels on a BGR frame (returns a copy)."""
        out = frame_bgr.copy()
        for r in results:
            x1, y1, x2, y2 = r.bbox
            color = (40, 180, 60) if r.is_known else (40, 40, 220)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{r.name} {r.confidence:.2f}" if r.is_known else r.name
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(out, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), color, -1)
            cv2.putText(
                out,
                label,
                (x1 + 3, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        if fps is not None and self.config.show_fps:
            cv2.putText(
                out,
                f"{fps:.1f} FPS",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 220, 255),
                2,
                cv2.LINE_AA,
            )
        return out

    def known_names(self) -> List[str]:
        return list(self.gallery.names)

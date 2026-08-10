"""
Known-face gallery: load enrollment photos from folder structure and cache embeddings.

Layout
------
known_faces/
  Alice/
    photo1.jpg
    photo2.png
  Bob/
    face.jpg

Each immediate subdirectory name is the identity label.
Images placed directly under known_faces/ (no person folder) are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from facial_recognition.config import IMAGE_EXTENSIONS
from facial_recognition.detector import FaceDetector
from facial_recognition.encoder import FaceEncoder


@dataclass
class GalleryEntry:
    name: str
    embedding: np.ndarray
    source_images: List[str] = field(default_factory=list)


@dataclass
class Gallery:
    entries: List[GalleryEntry] = field(default_factory=list)

    @property
    def names(self) -> List[str]:
        return [e.name for e in self.entries]

    def is_empty(self) -> bool:
        return len(self.entries) == 0

    def match(
        self,
        query: np.ndarray,
        encoder: FaceEncoder,
        threshold: float,
    ) -> Tuple[str, float]:
        """
        Return (best_name, best_score). If best_score < threshold, name is "" .
        """
        if self.is_empty():
            return "", 0.0

        best_name = ""
        best_score = -1.0
        for entry in self.entries:
            score = encoder.cosine_similarity(query, entry.embedding)
            if score > best_score:
                best_score = score
                best_name = entry.name

        if best_score >= threshold:
            return best_name, float(best_score)
        return "", float(best_score)


def _list_person_images(person_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(person_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            files.append(p)
    return files


def scan_known_faces_dir(known_faces_dir: Path) -> Dict[str, List[Path]]:
    """Map person name -> list of image paths."""
    root = Path(known_faces_dir)
    if not root.is_dir():
        root.mkdir(parents=True, exist_ok=True)
        return {}

    mapping: Dict[str, List[Path]] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name.startswith("_"):
            continue
        imgs = _list_person_images(child)
        if imgs:
            mapping[child.name] = imgs
    return mapping


def _mean_unit_embeddings(vectors: Sequence[np.ndarray]) -> Optional[np.ndarray]:
    if not vectors:
        return None
    stacked = np.stack([np.asarray(v, dtype=np.float32).reshape(-1) for v in vectors], axis=0)
    mean = stacked.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm < 1e-8:
        return None
    return (mean / norm).astype(np.float32)


def build_gallery(
    known_faces_dir: Path,
    detector: FaceDetector,
    encoder: FaceEncoder,
) -> Gallery:
    """
    Encode every enrollment image. For each person, average L2-normalized
    embeddings into one prototype vector (robust with a few photos).
    """
    mapping = scan_known_faces_dir(known_faces_dir)
    entries: List[GalleryEntry] = []

    if not mapping:
        print(
            f"[FR] No enrolled subjects under {known_faces_dir}.\n"
            f"     Create a folder per person and drop photos inside, e.g.\n"
            f"       {known_faces_dir / 'Alice' / 'photo1.jpg'}"
        )
        return Gallery(entries=[])

    for name, images in mapping.items():
        vectors: List[np.ndarray] = []
        used: List[str] = []
        for img_path in images:
            bgr = cv2.imread(str(img_path))
            if bgr is None:
                print(f"[FR] Warning: could not read {img_path}")
                continue
            faces = detector.detect(bgr)
            if not faces:
                print(f"[FR] Warning: no face in {img_path.name} ({name}) — skipped")
                continue
            # Largest face if multiple
            face = max(faces, key=lambda f: (f.x2 - f.x1) * (f.y2 - f.y1))
            emb = encoder.encode(bgr, face)
            if emb is None:
                print(f"[FR] Warning: failed to encode {img_path.name} ({name})")
                continue
            # L2-normalize each sample before averaging
            n = np.linalg.norm(emb)
            if n > 1e-8:
                emb = emb / n
            vectors.append(emb.astype(np.float32))
            used.append(str(img_path))

        prototype = _mean_unit_embeddings(vectors)
        if prototype is None:
            print(f"[FR] Warning: no valid embeddings for '{name}' — not enrolled")
            continue
        entries.append(GalleryEntry(name=name, embedding=prototype, source_images=used))
        print(f"[FR] Enrolled '{name}' from {len(used)} image(s)")

    print(f"[FR] Gallery ready: {len(entries)} subject(s)")
    return Gallery(entries=entries)


def save_gallery_cache(gallery: Gallery, cache_path: Path) -> None:
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if gallery.is_empty():
        if cache_path.exists():
            cache_path.unlink()
        return
    names = np.array([e.name for e in gallery.entries], dtype=object)
    embeddings = np.stack([e.embedding for e in gallery.entries], axis=0)
    np.savez_compressed(cache_path, names=names, embeddings=embeddings)
    print(f"[FR] Cached embeddings -> {cache_path}")


def load_gallery_cache(cache_path: Path) -> Optional[Gallery]:
    cache_path = Path(cache_path)
    if not cache_path.is_file():
        return None
    try:
        data = np.load(cache_path, allow_pickle=True)
        names = data["names"]
        embeddings = data["embeddings"]
        entries = [
            GalleryEntry(name=str(n), embedding=np.asarray(embeddings[i], dtype=np.float32))
            for i, n in enumerate(names)
        ]
        print(f"[FR] Loaded embedding cache ({len(entries)} subject(s)) from {cache_path}")
        return Gallery(entries=entries)
    except Exception as e:
        print(f"[FR] Cache load failed ({e}); will rebuild.")
        return None


def gallery_fingerprint(known_faces_dir: Path) -> str:
    """Cheap mtime/size signature so we can invalidate embedding cache."""
    mapping = scan_known_faces_dir(known_faces_dir)
    parts: List[str] = []
    for name, imgs in sorted(mapping.items()):
        for p in imgs:
            try:
                st = p.stat()
                parts.append(f"{name}:{p.name}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                parts.append(f"{name}:{p.name}:missing")
    return "|".join(parts)


def load_or_build_gallery(
    known_faces_dir: Path,
    detector: FaceDetector,
    encoder: FaceEncoder,
    cache_path: Path,
    force_rebuild: bool = False,
) -> Gallery:
    """
    Use NPZ cache when the known_faces folder has not changed; otherwise rebuild.
    """
    cache_path = Path(cache_path)
    sig = gallery_fingerprint(known_faces_dir)
    sig_file = cache_path.with_suffix(".sig")

    if not force_rebuild and cache_path.is_file() and sig_file.is_file():
        if sig_file.read_text(encoding="utf-8").strip() == sig:
            cached = load_gallery_cache(cache_path)
            if cached is not None:
                return cached

    gallery = build_gallery(known_faces_dir, detector, encoder)
    save_gallery_cache(gallery, cache_path)
    sig_file.write_text(sig, encoding="utf-8")
    return gallery

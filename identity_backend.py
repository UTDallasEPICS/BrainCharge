"""
Identity recognition backed by the YuNet+SFace facial recognition system.

Identity IS a name for this system -- there is no id until a name exists,
because enrollment works by saving a labeled photo under known_faces/<name>/
and rebuilding the gallery. So person_id and name are literally the same
string.
"""
import time
from pathlib import Path

import cv2

from memory.database import get_connection

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from facial_recognition import FaceRecognitionEngine, FRConfig
        _engine = FaceRecognitionEngine(FRConfig())
        _engine.initialize()
    return _engine


def _ensure_person_row(person_id, name):
    """Real embeddings live in the engine's own gallery cache, not our DB,
    but the embedding column is NOT NULL -- store an empty placeholder."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO persons (id, name, embedding) VALUES (?, ?, ?)",
        (person_id, name, b""),
    )
    connection.commit()
    connection.close()


class IdentityResult:
    def __init__(self, person_id, is_new_person):
        self.person_id = person_id
        self.is_new_person = is_new_person


def recognize(cv_pipeline):
    """Grabs a raw BGR frame and matches it against the known faces gallery.
    then returns IdentityResult. unknown faces get person_id=None since no id can
    exist without a name yet."""
    if cv_pipeline.camera is None:
        return IdentityResult(None, False)
    cv_pipeline.flush_buffer()
    success, frame_bgr = cv_pipeline.camera.read()
    if not success:
        return IdentityResult(None, False)

    engine = _get_engine()
    results = engine.recognize(frame_bgr)
    if not results:
        return IdentityResult(None, False)

    # Largest face = closest/most likely the person actually talking
    best = max(results, key=lambda r: (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1]))
    if best.is_known:
        return IdentityResult(best.name, False)
    return IdentityResult(None, True)


def enroll(name, cv_pipeline):
    """Called once a name has been captured for a person that isnt known yet.
    Returns the resulting person_id (== name), or None if enrollment failed."""
    if cv_pipeline.camera is None:
        return None
    cv_pipeline.flush_buffer()
    success, frame_bgr = cv_pipeline.camera.read()
    if not success:
        return None

    engine = _get_engine()
    person_dir = Path(engine.config.known_faces_dir) / name
    person_dir.mkdir(parents=True, exist_ok=True)
    photo_path = person_dir / f"enroll_{int(time.time())}.jpg"
    cv2.imwrite(str(photo_path), frame_bgr)
    engine.reload_gallery(force_rebuild=True)
    _ensure_person_row(name, name)
    return name


def get_name(person_id):
    return person_id

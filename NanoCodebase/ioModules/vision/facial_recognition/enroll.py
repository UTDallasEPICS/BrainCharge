"""
Helpers for enrollment (known-face folder layout).

Examples
--------
  # Print status / how to enroll
  python -m facial_recognition.enroll

  # Rebuild embedding cache after adding photos
  python -m facial_recognition.enroll --rebuild

  # Capture one enrollment photo from webcam into known_faces/<name>/
  python -m facial_recognition.enroll --capture Alice
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from facial_recognition.camera import open_camera
from facial_recognition.config import DEFAULT_KNOWN_FACES_DIR, FRConfig
from facial_recognition.engine import FaceRecognitionEngine
from facial_recognition.gallery import scan_known_faces_dir


def print_status(known_faces_dir: Path) -> None:
    mapping = scan_known_faces_dir(known_faces_dir)
    print(f"Enrollment directory: {known_faces_dir.resolve()}")
    if not mapping:
        print("  (empty)")
        print()
        print("To enroll a person:")
        print(f"  1. Create folder:  {known_faces_dir / 'PersonName'}")
        print("  2. Drop 3–8 clear face photos (jpg/png) into that folder")
        print("  3. Run:  python -m facial_recognition.enroll --rebuild")
        print("  4. Start live: python -m facial_recognition")
        return
    print(f"Subjects: {len(mapping)}")
    for name, imgs in mapping.items():
        print(f"  - {name}: {len(imgs)} image(s)")
        for p in imgs[:5]:
            print(f"      {p.name}")
        if len(imgs) > 5:
            print(f"      ... +{len(imgs) - 5} more")


def capture_enrollment(
    name: str,
    known_faces_dir: Path,
    camera_index: int = 0,
    count: int = 5,
) -> None:
    """Interactive webcam capture for a new subject."""
    person_dir = Path(known_faces_dir) / name
    person_dir.mkdir(parents=True, exist_ok=True)
    cap = open_camera(camera_index)
    window = f"Enroll {name} — SPACE capture, q done"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    saved = 0
    print(f"[FR] Capturing for '{name}' into {person_dir}")
    print("     SPACE = save frame | q = finish")

    try:
        while saved < count:
            ok, frame = cap.read()
            if not ok:
                continue
            preview = cv2.flip(frame, 1)
            cv2.putText(
                preview,
                f"{name}: {saved}/{count}  (SPACE save)",
                (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 180),
                2,
            )
            cv2.imshow(window, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                # save non-mirrored original for better consistency
                out = person_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                cv2.imwrite(str(out), frame)
                saved += 1
                print(f"[FR] Saved {out.name} ({saved}/{count})")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    print(f"[FR] Captured {saved} image(s) for '{name}'. Run with --rebuild to update cache.")


def rebuild_gallery(known_faces_dir: Path) -> None:
    cfg = FRConfig(known_faces_dir=Path(known_faces_dir))
    engine = FaceRecognitionEngine(cfg)
    engine.initialize(force_rebuild_gallery=True)
    print(f"[FR] Gallery subjects: {engine.known_names() or '(none)'}")


def main(argv: Optional[list] = None) -> None:
    p = argparse.ArgumentParser(description="Enroll known faces for recognition.")
    p.add_argument(
        "--faces-dir",
        type=Path,
        default=DEFAULT_KNOWN_FACES_DIR,
        help="Root enrollment directory",
    )
    p.add_argument(
        "--rebuild",
        action="store_true",
        help="Re-encode all enrollment photos into the embedding cache",
    )
    p.add_argument(
        "--capture",
        metavar="NAME",
        help="Capture enrollment photos from webcam for this person name",
    )
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--count", type=int, default=5, help="Photos to capture (default 5)")
    args = p.parse_args(argv)

    faces_dir = Path(args.faces_dir)
    faces_dir.mkdir(parents=True, exist_ok=True)

    if args.capture:
        capture_enrollment(args.capture, faces_dir, args.camera, args.count)
        if args.rebuild:
            rebuild_gallery(faces_dir)
        return

    if args.rebuild:
        rebuild_gallery(faces_dir)
        return

    print_status(faces_dir)


if __name__ == "__main__":
    main()

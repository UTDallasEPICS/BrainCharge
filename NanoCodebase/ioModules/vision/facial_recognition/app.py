"""
Standalone real-time facial recognition application.

Keys
----
  q / ESC  quit
  r        rebuild gallery from known_faces/ (after adding photos)
  s        save a still of the current annotated frame
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from facial_recognition.camera import open_camera, read_latest_frame
from facial_recognition.config import DEFAULT_KNOWN_FACES_DIR, FRConfig
from facial_recognition.engine import FaceRecognitionEngine


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Real-time facial recognition (standalone).",
    )
    p.add_argument(
        "--faces-dir",
        type=Path,
        default=DEFAULT_KNOWN_FACES_DIR,
        help=f"Enrollment folder (default: {DEFAULT_KNOWN_FACES_DIR})",
    )
    p.add_argument("--camera", type=int, default=0, help="Camera index (default 0)")
    p.add_argument("--width", type=int, default=640, help="Capture width")
    p.add_argument("--height", type=int, default=480, help="Capture height")
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Cosine match threshold (default from config ~0.363)",
    )
    p.add_argument(
        "--every-n",
        type=int,
        default=1,
        help="Run embedding match every N frames (1=every frame)",
    )
    p.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild of embedding cache on startup",
    )
    p.add_argument(
        "--no-mirror",
        action="store_true",
        help="Do not mirror the preview (selfie view off)",
    )
    return p


def run_realtime(config: FRConfig, force_rebuild: bool = False) -> None:
    engine = FaceRecognitionEngine(config)
    engine.initialize(force_rebuild_gallery=force_rebuild)

    if engine.gallery.is_empty():
        print(
            "\n[FR] Gallery is empty — everyone will show as Unknown.\n"
            f"    Add photos under: {config.known_faces_dir}/<PersonName>/photo.jpg\n"
            "    Then press 'r' in the window to reload, or restart.\n"
        )
    else:
        print(f"[FR] Known subjects: {', '.join(engine.known_names())}")

    cap = open_camera(config.camera_index, config.frame_width, config.frame_height)
    window = "Facial Recognition — BrainCharge"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    t0 = time.perf_counter()
    frames = 0
    fps: Optional[float] = None
    thr = config.match_threshold

    print("[FR] Live. Keys: q quit | r reload gallery | s save frame")

    try:
        while True:
            ok, frame = read_latest_frame(cap)
            if not ok or frame is None:
                print("[FR] Frame grab failed; retrying...")
                time.sleep(0.02)
                continue

            if config.mirror_preview:
                frame = cv2.flip(frame, 1)

            results = engine.recognize(frame, threshold=thr)
            display = engine.annotate(frame, results, fps=fps)

            # Footer status
            known = sum(1 for r in results if r.is_known)
            status = f"faces={len(results)} known={known}"
            cv2.putText(
                display,
                status,
                (10, display.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (220, 220, 220),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window, display)

            frames += 1
            elapsed = time.perf_counter() - t0
            if elapsed >= 0.5:
                fps = frames / elapsed
                frames = 0
                t0 = time.perf_counter()

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                print("[FR] Reloading gallery from disk...")
                engine.reload_gallery(force_rebuild=True)
                print(f"[FR] Subjects: {engine.known_names() or '(none)'}")
            if key == ord("s"):
                out = Path("facial_recognition") / "cache" / (
                    f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )
                out.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(out), display)
                print(f"[FR] Saved {out}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[FR] Stopped.")


def main(argv: Optional[list] = None) -> None:
    args = build_arg_parser().parse_args(argv)
    cfg = FRConfig(
        known_faces_dir=Path(args.faces_dir),
        camera_index=args.camera,
        frame_width=args.width,
        frame_height=args.height,
        recognize_every_n_frames=max(1, args.every_n),
        mirror_preview=not args.no_mirror,
    )
    if args.threshold is not None:
        cfg.match_threshold = float(args.threshold)
    run_realtime(cfg, force_rebuild=args.rebuild)


if __name__ == "__main__":
    main()

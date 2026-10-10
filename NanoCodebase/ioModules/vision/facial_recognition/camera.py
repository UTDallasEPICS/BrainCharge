"""Cross-platform camera helpers (aligned with cv_pipeline backends)."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2

from facial_recognition.config import system_name


def open_camera(
    index: int = 0,
    width: int = 640,
    height: int = 480,
) -> cv2.VideoCapture:
    """
    Open a webcam with the platform-appropriate backend.
    Sets a small buffer to cut capture latency.
    """
    system = system_name()
    cap: Optional[cv2.VideoCapture] = None

    if system == "Windows":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            for i in range(0, 3):
                if i == index:
                    continue
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    print(f"[FR] Camera opened with DirectShow at index {i}.")
                    break
                cap.release()
        else:
            print(f"[FR] Camera opened with DirectShow at index {index}.")
    elif system == "Darwin":
        cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap.release()
            for i in range(0, 3):
                cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
                if cap.isOpened():
                    print(f"[FR] Camera opened with AVFoundation at index {i}.")
                    break
                cap.release()
        else:
            print(f"[FR] Camera opened with AVFoundation at index {index}.")
    else:
        # Linux / Jetson
        for i in (index, 0, 1, 2):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"[FR] Camera opened at /dev/video{i}.")
                break
            cap.release()

    if cap is None or not cap.isOpened():
        raise RuntimeError(
            "[FR] Could not open any webcam. Check cable, permissions, "
            "and that no other app is using the camera."
        )

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Warm up sensor
    for _ in range(8):
        cap.read()
    print("[FR] Camera ready.")
    return cap


def read_latest_frame(cap: cv2.VideoCapture) -> Tuple[bool, Optional[object]]:
    """
    Grab+retrieve to discard buffered stale frames when possible.
    Reduces perceived lag on multi-buffer backends.
    """
    if not cap.grab():
        return False, None
    # Extra grab once if buffer might still hold an older frame
    cap.grab()
    ok, frame = cap.retrieve()
    return ok, frame if ok else None

"""Cross-platform camera helpers (aligned with cv_pipeline backends)."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2

from .config import system_name


def _get_camera_index(
    width: int,
    height: int,
    cameraAPI: int,
    total_indices: int
) -> int:
    """
    Gets the camera index for the camera with resolution (width, height).
    Scans total_indices camera ports and uses cameraAPI for capture.
    """
    index = 0
    while index < total_indices:
        # Capture a frame at resolution (width, height)
        # and another at resolution (width + 1, height + 1)
        capture = cv2.VideoCapture(index, cameraAPI)
        if not capture.isOpened():
            capture.release()
            index += 1
            continue

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        status1, frame1 = capture.read()
        if (not status1) or (frame1 is None):
            continue

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width + 1)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height + 1)

        status2, frame2 = capture.read()
        if (not status2) or (frame2 is None):
            continue

        # Check if the effective frame resolution matches (width, height)
        capture.release()
        frame_height, frame_width = frame2.shape[:2]
        if (frame_width, frame_height) == (width, height):
            return index

        index += 1

    return -1

def open_camera(
    width: int = 640,
    height: int = 480,
    total_indices: int = 3
) -> cv2.VideoCapture:
    """
    Open a webcam with the platform-appropriate backend.
    Sets a small buffer to cut capture latency.
    """
    system = system_name()
    cap: Optional[cv2.VideoCapture] = None

    cameraAPI = 0
    log = ""
    if system == "Windows":
        cameraAPI = cv2.CAP_DSHOW
        log = "[FR] Camera opened with DirectShow at index "
    elif system == "Darwin":
        cameraAPI = cv2.CAP_AVFOUNDATION
        log = "[FR] Camera opened with AVFoundation at index "
    else:
        cameraAPI = cv2.CAP_V4L2
        log = "[FR] Camera opened at /dev/video"

    index = _get_camera_index(
        width,
        height,
        cameraAPI,
        total_indices
    )
    error = RuntimeError(
        "[FR] Could not open any webcam. Check cable, permissions, "
        "and that no other app is using the camera."
    )

    if index == -1:
        raise error
    else:
        cap = cv2.VideoCapture(
            index,
            cameraAPI
        )
        if cap is None or not cap.isOpened():
            raise error

    print(f"{log}{index}.")

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

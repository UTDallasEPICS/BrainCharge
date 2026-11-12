from typing import Tuple
from pathlib import Path

from math import tan, atan
import numpy as np
from ultralytics import YOLO
from cv2 import resize, INTER_LINEAR

class MovementController:
    def __init__(
        self,
        depth_model = "yolo26n-depth-calibrated.pt",
        focal_calibration = "camera_calibration.npz"
    ):
        depth_model_path = Path(__file__).resolve().parent / "models" / depth_model
        self.depth_model = YOLO(depth_model_path)

        calibration_path = Path(__file__).resolve().parent / "camera_calibration" / "focal_calibration" / focal_calibration
        camera_matrix = (np.load(calibration_path))["camera_matrix"]
        self.camera_calibration = {
            "fx": camera_matrix[0, 0],  # Horizontal focal point
            "fy": camera_matrix[1, 1],  # Vertical focal point
            "cx": camera_matrix[0, 2],  # Horizontal principal point
            "cy": camera_matrix[1, 2],  # Vertical principal point
        }

    def estimate_distance(
        self,
        bbox: Tuple[int, int, int, int],
        frame: np.ndarray
    ) -> Tuple[float, float, float]:
        y_depth = self._estimate_depth(bbox, frame)
        bearing = self._estimate_bearing(bbox)

        x_depth = tan(bearing[0]) * y_depth
        z_depth = -tan(bearing[1]) * y_depth
        return (x_depth, y_depth, z_depth)

    def _estimate_depth(
        self,
        bbox: Tuple[int, int, int, int],
        frame: np.ndarray
    ) -> float:
        """
        bbox: (x1, y1, x2, y2) bounding box
        frame: BGR camera frame
        """
        frame_height, frame_width = frame.shape[:2]

        # Keep bounding-box coordinates inside the frame
        x1 = max(0, min(bbox[0], frame_width - 1))
        x2 = max(0, min(bbox[2], frame_width))
        y1 = max(0, min(bbox[1], frame_height - 1))
        y2 = max(0, min(bbox[3], frame_height))

        # Predict the depth map
        result = self.depth_model.predict(
            frame,
            imgsz=768,
            verbose=False
        )[0]
        depth_map = result.depth.data.squeeze().cpu().numpy()

        # Ensure depth map coordinates match the camera frame
        if depth_map.shape != (frame_height, frame_width):
            depth_map = resize(
                depth_map,
                (frame_width, frame_height),
                interpolation=INTER_LINEAR
            )

        # Use the central 60% of the face box to reduce background
        face_width = x2 - x1
        face_height = y2 - y1

        left = x1 + int(0.20 * face_width)
        right = x2 - int(0.20 * face_width)
        top = y1 + int(0.20 * face_height)
        bottom = y2 - int(0.20 * face_height)

        face_depth = depth_map[top:bottom, left:right]

        # Filter only valid depth values
        valid_depth = face_depth[
            np.isfinite(face_depth) & (face_depth > 0)
        ]
        if valid_depth.size == 0:
            return None

        # Robust estimate of the visible face region's depth
        return float(np.median(valid_depth))

    def _estimate_bearing(
        self,
        bbox: Tuple[int, int, int, int]
    ) -> float:
        """
        bbox: (x1, y1, x2, y2) bounding box
        frame_size: (width, height) size of BGR camera frame
        """
        face_center = (
            (bbox[0] + bbox[2]) / 2.0,
            (bbox[1] + bbox[3]) / 2.0
        )
        bearing = (
            atan((face_center[0] - self.camera_calibration["cx"]) / self.camera_calibration["fx"]),
            atan((face_center[1] - self.camera_calibration["cy"]) / self.camera_calibration["fy"])
        )

        return bearing
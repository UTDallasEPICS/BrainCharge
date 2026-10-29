from typing import Tuple

class FaceTracker:
    def __init__(self):
        pass

    def estimate_distance(
        bbox: Tuple[int, int, int, int],
        frame_width: int,
        focal_length: float
    ) -> Tuple[int, int]:
        """
        bbox: (x1, y1, x2, y2)
        frame_width: width of camera frame (in pixels)
        focal_length: focal length of camera (in pixels)
        """
        return (0, 0)
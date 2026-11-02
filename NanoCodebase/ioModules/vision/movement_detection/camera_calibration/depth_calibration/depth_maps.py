import csv
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent / "face_depth_dataset"
IMAGE_DIR = ROOT / "images" / "validation"
DEPTH_DIR = ROOT / "depth" / "validation"
CSV_PATH = ROOT / "points.csv"

# Load the focal calibration camera matrix.
calibration = np.load(Path(__file__).resolve().parent.parent / "focal_calibration" / "camera_calibration.npz")
camera_matrix = calibration["camera_matrix"]

fx = camera_matrix[0, 0]
fy = camera_matrix[1, 1]
cx = camera_matrix[0, 2]
cy = camera_matrix[1, 2]

DEPTH_DIR.mkdir(parents=True, exist_ok=True)

# Group measured points by image.
points_by_image = {}

with open(CSV_PATH, newline="") as f:
    reader = csv.DictReader(f)

    for row in reader:
        filename = row["image"]
        x = int(row["x"])
        y = int(row["y"])
        distance = float(row["meters"])

        points_by_image.setdefault(filename, []).append(
            (x, y, distance)
        )

for filename, points in points_by_image.items():

    image_path = IMAGE_DIR / filename
    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Skipping missing image: {filename}")
        continue

    height, width = image.shape[:2]

    # 0 means unknown/invalid depth.
    depth_map = np.zeros((height, width), dtype=np.float32)

    for x, y, distance in points:

        if not (0 <= x < width and 0 <= y < height):
            print(f"Invalid point in {filename}: {(x, y)}")
            continue

        # Convert Euclidean range to optical-axis depth.
        ray_factor = np.sqrt(
            1.0
            + ((x - cx) / fx) ** 2
            + ((y - cy) / fy) ** 2
        )

        z_depth = distance / ray_factor

        # A small labeled patch helps preserve the point
        # when the image is resized during calibration.
        radius = 6

        x1 = max(0, x - radius)
        x2 = min(width, x + radius + 1)
        y1 = max(0, y - radius)
        y2 = min(height, y + radius + 1)

        depth_map[y1:y2, x1:x2] = z_depth

    output_path = DEPTH_DIR / (
        Path(filename).stem + ".npy"
    )

    np.save(output_path, depth_map)

    print(
        f"Generated {output_path.name}; "
        f"labeled pixels: {np.count_nonzero(depth_map)}"
    )

print("Depth-map generation complete.")
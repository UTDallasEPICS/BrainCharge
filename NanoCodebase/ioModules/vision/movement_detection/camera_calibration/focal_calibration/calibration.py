import cv2
import numpy as np
from pathlib import Path

# Number of INNER corners, not number of squares
CHECKERBOARD = (9, 6)

# Physical width of one checkerboard square, in millimeters
SQUARE_SIZE_MM = 25.0

# Create the 3D coordinates of the checkerboard corners.
# The checkerboard lies on the Z=0 plane.
objp = np.zeros(
    (CHECKERBOARD[0] * CHECKERBOARD[1], 3),
    np.float32
)

objp[:, :2] = np.mgrid[
    0:CHECKERBOARD[0],
    0:CHECKERBOARD[1]
].T.reshape(-1, 2)

objp *= SQUARE_SIZE_MM

# Corresponding 3D and 2D corner coordinates
object_points = []
image_points = []

image_size = None

ROOT = Path(__file__).resolve().parent
calibration_images_dir = ROOT / "images"
images = sorted(calibration_images_dir.glob("*"))

for filename in images:
    image = cv2.imread(str(filename))

    if image is None:
        continue

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if image_size is None:
        image_size = (gray.shape[1], gray.shape[0])

    found, corners = cv2.findChessboardCorners(
        gray,
        CHECKERBOARD,
        cv2.CALIB_CB_ADAPTIVE_THRESH
        + cv2.CALIB_CB_NORMALIZE_IMAGE
    )

    if not found:
        print(f"Checkerboard not found: {filename}")
        continue

    # Improve corner accuracy
    corners = cv2.cornerSubPix(
        gray,
        corners,
        (11, 11),
        (-1, -1),
        (
            cv2.TERM_CRITERIA_EPS
            + cv2.TERM_CRITERIA_MAX_ITER,
            30,
            0.001
        )
    )

    object_points.append(objp.copy())
    image_points.append(corners)

    print(f"Used calibration image: {filename}")

if len(object_points) < 10:
    raise RuntimeError(
        f"Only {len(object_points)} usable images found. "
        "Capture at least 10 varied checkerboard images."
    )

# Estimate camera intrinsics and lens distortion
rms_error, camera_matrix, dist_coeffs, rvecs, tvecs = (
    cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None
    )
)

fx = camera_matrix[0, 0]
fy = camera_matrix[1, 1]
cx = camera_matrix[0, 2]
cy = camera_matrix[1, 2]

print("\nCamera matrix:")
print(camera_matrix)

print(f"\nFocal length fx: {fx:.2f} pixels")
print(f"Focal length fy: {fy:.2f} pixels")
print(f"Principal point: ({cx:.2f}, {cy:.2f})")
print(f"RMS reprojection error: {rms_error:.4f} pixels")

# Save calibration for later use
np.savez(
    ROOT / "camera_calibration.npz",
    camera_matrix=camera_matrix,
    dist_coeffs=dist_coeffs,
    image_size=np.array(image_size)
)

print("\nSaved calibration to camera_calibration.npz")
import cv2
import csv
import time
from pathlib import Path

# Camera configuration
CAMERA_INDEX = 0
WIDTH = 1280
HEIGHT = 720

# Dataset configuration
ROOT = Path(__file__).resolve().parent / "face_depth_dataset"
IMAGE_DIR = ROOT / "images" / "validation"
CSV_PATH = ROOT / "points.csv"

FRAMES_PER_RUN = 25
START_DELAY = 5
FRAME_INTERVAL = 0.1  # Seconds between captures

IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Initialize CSV if necessary, including an existing empty file.
if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "x", "y", "meters"])

selected_point = None


def mouse_callback(event, x, y, flags, param):
    global selected_point

    if event == cv2.EVENT_LBUTTONDOWN:
        selected_point = (x, y)


def get_next_image_number():
    existing_numbers = []

    for path in IMAGE_DIR.glob("face_*.jpg"):
        try:
            number = int(path.stem.split("_")[1])
            existing_numbers.append(number)
        except (IndexError, ValueError):
            pass

    return max(existing_numbers, default=0) + 1


# Ask for the distance before starting the camera.
while True:
    try:
        distance = float(
            input("Enter actual camera-to-face distance (meters): ")
        )

        if distance <= 0:
            raise ValueError

        break

    except ValueError:
        print("Please enter a valid positive distance.")


# Open camera
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

if not cap.isOpened():
    raise RuntimeError("Could not open camera")

cv2.namedWindow("Dataset Capture")
cv2.setMouseCallback("Dataset Capture", mouse_callback)

image_number = get_next_image_number()

print("\nCamera ready.")
print("Click the center of your face in the preview.")
print("Press S when you are ready to begin the capture sequence.")
print("Press Q to quit.\n")

# Wait for user to select face center.
while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to receive frame.")
        break

    display = frame.copy()

    if selected_point is not None:
        cv2.circle(display, selected_point, 7, (0, 255, 0), -1)

    cv2.imshow("Dataset Capture", display)

    key = cv2.waitKey(1) & 0xFF

    if key in (ord("s"), ord("S")):
        if selected_point is None:
            print("Click the center of your face first.")
            continue

        break

    elif key in (ord("q"), ord("Q")):
        cap.release()
        cv2.destroyAllWindows()
        raise SystemExit


# Start countdown.
print(f"\nCapturing {FRAMES_PER_RUN} frames in {START_DELAY} seconds...")

for remaining in range(START_DELAY, 0, -1):
    print(f"{remaining}...")
    time.sleep(1)

print("Capture started!\n")

x, y = selected_point
captured_count = 0

with open(CSV_PATH, "a", newline="") as f:
    writer = csv.writer(f)

    for i in range(FRAMES_PER_RUN):

        ret, frame = cap.read()

        if not ret:
            print(f"Frame {i + 1}: camera read failed.")
            continue

        filename = f"face_{image_number:04d}.jpg"
        image_path = IMAGE_DIR / filename

        if not cv2.imwrite(str(image_path), frame):
            print(f"Frame {i + 1}: image save failed.")
            continue

        writer.writerow([filename, x, y, distance])
        f.flush()

        print(
            f"Captured {i + 1}/{FRAMES_PER_RUN}: "
            f"{filename}, distance={distance:.3f} m"
        )

        image_number += 1
        captured_count += 1

        time.sleep(FRAME_INTERVAL)

print(f"\nRun complete: {captured_count}/{FRAMES_PER_RUN} frames saved.")
print(f"Distance: {distance:.3f} m")
print(f"CSV updated: {CSV_PATH}")

cap.release()
cv2.destroyAllWindows()
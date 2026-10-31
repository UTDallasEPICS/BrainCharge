import cv2
from ioModules.vision.facial_recognition.camera import open_camera

resolution = {
    "width": 1280,
    "height": 720
}

cap = open_camera(resolution["width"], resolution["height"])

if not cap.isOpened():
    raise RuntimeError("Could not open camera")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution["width"])
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution["height"])
cap.set(cv2.CAP_PROP_FPS, 5)

try:
    for i in range(10):
        ret, frame = cap.read()

        if not ret or frame is None:
            print("Frame capture failed")
            continue

        print(
            f"Frame {i + 1}: "
            f"mean={frame.mean():.3f}, "
            f"min={frame.min()}, max={frame.max()}"
        )

        cv2.imshow("Camera Test", frame)

        if cv2.waitKey(200) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
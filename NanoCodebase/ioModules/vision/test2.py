
import cv2

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

if not cap.isOpened():
    raise RuntimeError("Could not open camera")

# Explicitly request YUY2, the format reported by FFmpeg
fourcc = cv2.VideoWriter_fourcc(*"YUY2")
print("Set YUY2:", cap.set(cv2.CAP_PROP_FOURCC, fourcc))

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 5)

print("Reported FOURCC:", int(cap.get(cv2.CAP_PROP_FOURCC)))

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

        if i == 0:
            cv2.imwrite("hiwonder_yuy2_test.png", frame)

        cv2.imshow("YUY2 Camera Test", frame)

        if cv2.waitKey(200) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
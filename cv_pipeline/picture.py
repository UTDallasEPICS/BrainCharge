# cv_pipeline/picture.py
#
# Refactored for integrated operation:
#   - Arduino serial connection is INJECTED via __init__(arduino=...)
#     instead of being created internally. This means main.py owns the
#     single serial port — no duplicate connections.
#   - CONNECT_ARDUINO_FLAG and SERIAL_PORT constants are kept as
#     fallbacks for standalone testing only (e.g. python -m cv_pipeline.picture)
#   - shutdown() method added for clean teardown from the tracking thread.

from typing import Optional
from ultralytics import YOLO
import cv2
from cv2.typing import MatLike
from pathlib import Path
import platform
import torch
from torch import nn
from torch import device, cuda, Tensor
from torchvision.transforms import v2
from torchvision.models import EfficientNet, efficientnet_b2
from PIL import Image
import time

_SYSTEM = platform.system()

# ---------------------------------------------------------------------------
# Standalone / fallback constants
# (only used when CVPipeline is run directly, not from main.py)
# ---------------------------------------------------------------------------

# Set to False to run CV pipeline without Arduino in standalone mode
CONNECT_ARDUINO_FLAG: bool = True

# Change to '/dev/ttyUSB0' or '/dev/ttyACM0' for Jetson
SERIAL_PORT = '/dev/tty.usbmodem21101'  # macOS default; change for Jetson: /dev/ttyUSB0 or /dev/ttyACM0
BAUD_RATE   = 115200

# ---------------------------------------------------------------------------
# Global model paths
# ---------------------------------------------------------------------------

DEVICE: device                = "cuda" if cuda.is_available() else "cpu"
PERSON_DETECTOR_FILEPATH      = "yolov8n.pt"
FACE_DETECTOR_FILEPATH        = "./cv_pipeline/yolov8n-face-lindevs.pt"
EMOTION_CLASSIFIER_FILEPATH   = "./cv_pipeline/emotions_model.pt"
AVAILABLE_EMOTIONS            = ["Angry", "Fear", "Happy", "Neutral", "Sad"]
NUM_TOP_EMOTIONS              = 2

# Ensure image output directory exists
try:
    DIRECTORY_NAME = "./picturefile"
    DIRECTORY_PATH = Path(DIRECTORY_NAME)
    DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    print(f"[CV] Image folder ready at: {DIRECTORY_NAME}")
except Exception as e:
    raise Exception("Error finding or creating image output directory: ", e)


class CVPipeline:
    def __init__(self, arduino=None):
        """
        Parameters
        ----------
        arduino : serial.Serial | None
            An already-opened pyserial Serial object, shared from main.py.
            If None AND CONNECT_ARDUINO_FLAG is True, the pipeline will open
            its own connection (standalone / legacy mode only).
        """
        self.camera: Optional[cv2.VideoCapture] = None
        self.target: Optional[int] = None

        # --- Load models ---
        self.person_detector    = self._init_detector(PERSON_DETECTOR_FILEPATH, DEVICE)
        self.face_detector      = self._init_detector(FACE_DETECTOR_FILEPATH, DEVICE)
        self.emotion_classifier = self._init_emotion_classifier(EMOTION_CLASSIFIER_FILEPATH, DEVICE)
        self.emotion_classifier.eval()

        # --- Arduino connection ---
        if arduino is not None:
            # Integrated mode: use the shared connection from main.py
            self.arduino = arduino
            self._owns_arduino = False   # main.py will close it
            print("[CV] Using shared Arduino connection from main.")
        elif CONNECT_ARDUINO_FLAG:
            # Standalone / legacy mode: open our own connection
            try:
                import serial
                self.arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
                time.sleep(2)   # Wait for Arduino reset
                self._owns_arduino = True
                print(f"[CV] Opened own Arduino connection on {SERIAL_PORT}.")
            except Exception as e:
                print(f"[CV] Could not open Arduino: {e}")
                self.arduino = None
                self._owns_arduino = False
        else:
            self.arduino = None
            self._owns_arduino = False


    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _init_detector(self, filepath: str, device) -> YOLO:
        return YOLO(filepath).to(device)

    def _init_emotion_classifier(self, filepath: str, device: device) -> EfficientNet:
        efficientnet = efficientnet_b2()
        efficientnet.classifier = nn.Sequential(
            nn.Linear(1408, 512, bias=True),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(512, 5, bias=True)
        )
        efficientnet.load_state_dict(torch.load(filepath, map_location=device))
        return efficientnet.to(device)

    def _convert_to_tensor(self, image: MatLike, device: device) -> Tensor:
        modified = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        modified = Image.fromarray(modified)
        transform = v2.Compose([
            v2.Lambda(lambda x: x.convert("L").convert("RGB")),
            v2.Resize([288, 288]),
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        return transform(modified).unsqueeze(0).to(device)


    # -----------------------------------------------------------------------
    # Camera control
    # -----------------------------------------------------------------------

    def camera_on(self) -> bool:
        return self.camera is not None

    def camera_off(self) -> bool:
        return self.camera is None

    def turn_on_camera(self) -> None:
        print("[CV] Opening camera...")
        camera_found = False

        if _SYSTEM == "Darwin":
            # macOS — AVFoundation backend, index 2 (external / virtual camera)
            self.camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
            if self.camera.isOpened():
                camera_found = True
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("[CV] Camera opened with AVFoundation backend (index 2).")
            else:
                self.camera.release()
                print("[CV] AVFoundation index 2 failed. Trying indices 0 and 1...")
                for i in range(2):
                    self.camera = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
                    if self.camera.isOpened():
                        camera_found = True
                        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        print(f"[CV] Camera opened with AVFoundation at index {i}.")
                        break

        elif _SYSTEM == "Windows":
            # Windows — DirectShow backend
            self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if self.camera.isOpened():
                camera_found = True
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("[CV] Camera opened with DirectShow backend.")
            else:
                self.camera.release()
                print("[CV] DirectShow index 0 failed. Trying indices 1 and 2...")
                for i in range(1, 3):
                    self.camera = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if self.camera.isOpened():
                        camera_found = True
                        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        print(f"[CV] Camera opened with DirectShow at index {i}.")
                        break

        else:
            # Linux / Jetson — default backend, try indices 0-2
            for i in range(3):
                self.camera = cv2.VideoCapture(i)
                if self.camera.isOpened():
                    camera_found = True
                    print(f"[CV] Camera opened at /dev/video{i}.")
                    break
                self.camera.release()

        if not camera_found:
            print("[CV] ERROR: Could not open any webcam.")
            print("  Check: cable connected, camera permissions granted,")
            print("  no other app is using the camera.")
            exit(1)

        # Warm up — discard the first several frames so the sensor stabilises
        for _ in range(10):
            self.camera.read()
        print("[CV] Camera ready.")

    def turn_off_camera(self) -> None:
        if self.camera is not None:
            self.camera.release()
            cv2.destroyAllWindows()
            self.camera = None
            print("[CV] Camera closed.")

    def shutdown(self) -> None:
        """
        Clean shutdown: turn off camera. If we opened our own Arduino
        connection (standalone mode), close that too.
        """
        self.turn_off_camera()
        if self._owns_arduino and self.arduino is not None and self.arduino.is_open:
            try:
                self.arduino.write(b"s")   # stop motors
                time.sleep(0.1)
            except Exception:
                pass
            self.arduino.close()
            print("[CV] Closed own Arduino connection.")


    # -----------------------------------------------------------------------
    # Movement logic
    # -----------------------------------------------------------------------

    def _get_turn_signal(self, w: int, h: int, x1: int, x2: int,
                         y1: int, y2: int) -> str:
        """Return 'L', 'R', or 'S' based on where the target is horizontally."""
        center_dist = (x1 + x2 - w) / 2
        threshold   = w / 4
        region_area = (y2 - y1) * (x2 - x1)
        camera_area = h * w

        if not (region_area >= camera_area / 2 or
                (region_area <= camera_area / 4 and region_area >= camera_area / 10)):
            if center_dist >= threshold:
                return "R"
            elif center_dist <= -threshold:
                return "L"
        return "S"

    def _get_move_signal(self, w: int, h: int, x1: int, x2: int,
                         y1: int, y2: int) -> str:
        """Return 'F', 'B', or 'S' based on how large the target is in frame."""
        region_area = (y2 - y1) * (x2 - x1)
        camera_area = h * w

        if region_area >= camera_area / 2:
            return "B"
        elif region_area <= camera_area / 4 and region_area >= camera_area / 10:
            return "F"
        return "S"

    def _send_command(self, move: str, turn: str) -> None:
        """Send a single-byte movement command to the Arduino."""
        if self.arduino is None:
            return
        try:
            if move == "B":
                self.arduino.write(b'b')
            elif turn == "L":
                self.arduino.write(b'l')
            elif turn == "R":
                self.arduino.write(b'r')
            elif move == "F":
                self.arduino.write(b'f')
            else:
                self.arduino.write(b's')
        except Exception as e:
            print(f"[CV] Serial write error: {e}")


    # -----------------------------------------------------------------------
    # Tracking loop (used for standalone mode)
    # In integrated mode, CVTrackingThread in main.py runs its own loop
    # so it can also check the stop_event.
    # -----------------------------------------------------------------------

    def track_movement(self) -> None:
        """
        Blocking person-tracking loop. Locks onto the first person detected
        and sends movement commands to the Arduino to follow them.

        Press Q in the camera window to stop.

        NOTE: When running under main.py, CVTrackingThread runs an equivalent
        loop directly so it can exit cleanly on request_stop(). This method
        is kept for standalone / testing use.
        """
        if not self.camera:
            raise Exception("[CV] Camera is not open. Call turn_on_camera() first.")

        prev_turn, prev_move = "", ""

        while True:
            success, image = self.camera.read()
            if not success:
                raise ValueError("[CV] Failed to capture camera frame.")

            analysis = self.person_detector.track(
                image, persist=True, tracker="bytetrack.yaml"
            )[0].boxes

            if analysis.id is None:
                cv2.imshow("Realtime Personal Tracking", image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            boxes     = analysis.xyxy.cpu().numpy()
            classes   = analysis.cls.cpu().numpy()
            track_ids = analysis.id.cpu().numpy()

            if (self.target is not None and
                    self.target not in [int(tid) for tid in track_ids]):
                self.target = None

            for box, class_id, track_id in zip(boxes, classes, track_ids):
                if int(class_id) == 0 and self.target is None:
                    self.target = int(track_id)

                if self.target == int(track_id):
                    h, w, _ = image.shape
                    x1, y1, x2, y2 = map(int, box)

                    new_turn = self._get_turn_signal(w, h, x1, x2, y1, y2)
                    new_move = self._get_move_signal(w, h, x1, x2, y1, y2)

                    if new_turn != prev_turn or new_move != prev_move:
                        prev_turn, prev_move = new_turn, new_move
                        self._send_command(prev_move, prev_turn)

                    cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 3)
                    cv2.putText(
                        image,
                        f"Turn {prev_turn}, move {prev_move}",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5
                    )

            cv2.imshow("Realtime Personal Tracking", image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break


    # -----------------------------------------------------------------------
    # Emotion analysis
    # -----------------------------------------------------------------------

    def _expand_face(self, w: int, h: int, x1: int, y1: int,
                     x2: int, y2: int) -> tuple:
        box_w = x2 - x1
        box_h = y2 - y1
        side  = int(max(box_w, box_h) * 1.2)   # 20% padding
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        _x1 = max(0, cx - side // 2)
        _y1 = max(0, cy - side // 2)
        _x2 = min(w, cx + side // 2)
        _y2 = min(h, cy + side // 2)
        return _x1, _y1, _x2, _y2

    def execute(self) -> list:
        """Capture one frame and return a list of detected emotions."""
        emotions = []
        if not self.camera:
            return emotions

        success, image = self.camera.read()
        if not success:
            return emotions

        try:
            analysis = self.face_detector(image)[0].boxes
            boxes    = analysis.xyxy.cpu().numpy()

            if boxes is not None and len(boxes):
                h, w, _ = image.shape
                x1, y1, x2, y2 = map(int, boxes[0])
                x1, y1, x2, y2 = self._expand_face(w, h, x1, y1, x2, y2)
                face_region: MatLike = image[y1:y2, x1:x2]

                with torch.no_grad():
                    tensor = self._convert_to_tensor(face_region, DEVICE)
                    output = torch.softmax(self.emotion_classifier(tensor), dim=1)
                    probs, labels = torch.topk(output, NUM_TOP_EMOTIONS)
                    emotions = [
                        {
                            "emotion":     AVAILABLE_EMOTIONS[l],
                            "confidence":  round(probs[0][i].item(), 2)
                        }
                        for i, l in enumerate(labels[0].cpu().numpy())
                        if probs[0][i].item() > 0.1
                    ]

                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(
                    image,
                    ", ".join(e["emotion"] for e in emotions),
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5
                )
                image_path = DIRECTORY_PATH / "analyzed_image.jpg"
                if not cv2.imwrite(str(image_path), image):
                    raise Exception("Error saving analyzed image.")
                print(f"[CV] Analyzed image saved to: {image_path}")
            else:
                cv2.putText(image, "No face detected",
                            (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5)
        except Exception as e:
            cv2.putText(image, f"Error: {e}",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5)

        return emotions


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pipeline = CVPipeline()   # opens its own Arduino in standalone mode
    pipeline.turn_on_camera()
    pipeline.track_movement()
    pipeline.shutdown()
from typing import Optional
from ultralytics import YOLO
import cv2
from cv2.typing import MatLike
from pathlib import Path
from torch import device, cuda
import time
from .hsemotion_detector import EmotionDetector
import numpy as np
import os

# FEATURE FLAG (Sort of)
CONNECT_ARDUINO_FLAG: bool = False

# GLOBAL
DEVICE: device = "cuda" if cuda.is_available() else "cpu"
CV_DIR = os.path.dirname(os.path.abspath(__file__))
PERSON_DETECTOR_FILEPATH = os.path.join(CV_DIR, "yolov8n.pt")
FACE_DETECTOR_FILEPATH = os.path.join(CV_DIR, "./yolov8n-face-lindevs.pt")
EMOTION_CLASSIFIER_FILEPATH = "./hsemotion_detector.py"
NUM_TOP_EMOTIONS = 3

# Check and create if needed the file needed for the file
try:
    DIRECTORY_NAME = os.path.join(CV_DIR, "./picturefile")
    DIRECTORY_PATH = Path(DIRECTORY_NAME)

    DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Image folder ready at: {DIRECTORY_NAME}")#file directory where the picture taken will be stored
except Exception as e:
    raise Exception("Error finding or creating directory to store images: ", e)

class CVPipeline:
    def __init__(self):#initiate detectors
        self.camera: Optional[cv2.VideoCapture] = None
        self.person_detector = self._init_detector(
            PERSON_DETECTOR_FILEPATH, 
            DEVICE
        )
        self.face_detector = self._init_detector(
            FACE_DETECTOR_FILEPATH, 
            DEVICE
        )
        self.emotion_classifier = self._init_emotion_classifier(
            EMOTION_CLASSIFIER_FILEPATH,
        )
        self.emotion_labels = self.emotion_classifier.model.idx_to_class

        # For person tracking
        self.target: Optional[int] = None
        if CONNECT_ARDUINO_FLAG:
            import serial # type: ignore
            self.arduino = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
            time.sleep(2)  # Wait for Arduino reset


    def _init_detector(self, filepath: str, device) -> YOLO:
        """Helper method: Get the YOLO-based detection model"""
        detector = YOLO(filepath).to(device)
        return detector
    

    def _init_emotion_classifier(self, filepath: str):
        """Helper method: Initialize the emotional classification model"""
        return EmotionDetector()


    def camera_on(self) -> bool:
        """Check if the camera is on"""
        return self.camera is not None
    

    def turn_on_camera(self) -> None:
        """Attempts to turn on the camera"""
        print("Trying DirectShow backend...")
        camera_found = False
        self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        if self.camera.isOpened():
            camera_found = True
            print("Cam found with DirectShow!")
        else:
            self.camera.release()
            print("Trying different backend with different camera indices...")
            for i in range(3):
                print(f"Trying camera index [i]...")
                self.camera = cv2.VideoCapture(i)
                if self.camera.isOpened():
                    camera_found = True
                    print(f"Camera found at index {i}!")
                    break

        if not camera_found: 
            print("Error: could not open any webcam.")
            print("Please check: ")
            print("1. Is connected")
            print("2. Camera permissions are enabled with Windows Settings")
            print("3. No other application is using camera")
            exit()

        # Warm up the camera to prevent it from crashing when reopening
        for _ in range(7):
            self.camera.read()
        print("Turn on the camera successfully!")


    def camera_off(self) -> bool:
        """Check if the camera is off"""
        return self.camera is None


    def turn_off_camera(self) -> None:
        """Turn off the camera if there is an opened one"""
        if self.camera is not None:
            self.camera.release()
            cv2.destroyAllWindows()
            self.camera = None
            print("Turn off the camera successfully!")


    def flush_buffer(self, n: int = 5) -> None:
        """
        Discard whatever frames are sitting in the camera's internal buffer.

        cv2.VideoCapture keeps capturing into a buffer even when nothing calls
        read() -- if the camera goes untouched for a while (e.g. during a long
        VAD recording), the next read() can return a stale buffered frame
        instead of what the camera is seeing right now. grab() is cheap (no
        decode) so a handful of them quickly catches the buffer up to live.
        """
        if self.camera is None:
            return
        for _ in range(n):
            self.camera.grab()


    def _get_turn_signal(self, w: int, x1: int, x2: int) -> str:
        """Helper method: Determine if the robot turns left or right"""
        center_dist = (x1 + x2 - w) / 2
        threshold = w / 8

        if center_dist >= threshold:
            return "R"
        elif center_dist <= -threshold:
            return "L"
        
        return "S" #stop


    def _get_move_signal(self, 
        w: int, h: int, x1: int, x2: int, y1: int, y2: int
    ) -> str:
        """Helper method: Determine if the robot moves forward or backward"""
        region_area = (y2 - y1) * (x2 - x1)
        camera_area = h * w

        if region_area >= camera_area / 2:
            return "B"
        elif region_area <= camera_area / 4:
            return "F"
        
        return "S" #stop


    def _send_command(self, move: str, turn: str):
        """Helper method: Send the new movement command to the adruino"""
        #It'll be a lot faster to just send a character instead of string
        if move == "B":
            cmd = 'b'  # Back up if too close
        elif turn == "L":
            cmd = 'l' #turn towards
        elif turn == "R":
            cmd = 'r' #turn towards
        elif move == "F":
            cmd = 'f' #go forwards
        else:
            cmd = 's'

        self.arduino.write(cmd.encode())

        #return self.arduino.readline().decode().strip() - as of now, I don't think we'll need


    def track_movement(self) -> tuple[int]:
        """
        Person-tracking system for robot movement.
        It captures the first person to get in the frame and lock in that person as target to follow.
        If the target gets out of frame before the robot's reaction, it will automatically choose
        the next person it captures as the target.
        
        To adjust the target, clear the camera's frame and be the first person to be in the frame.
        """
        prev_turn, prev_move = "", ""

        if not self.camera: 
            raise Exception("Unable to open the camera")

        while True:
            success, image = self.camera.read()
            if not success:
                raise ValueError("Failed to capture the image of the user")
            
            # The object-detection model but uses bytetrack algorithm to assign id to each detected obj
            analysis = self.person_detector.track(
                image, 
                persist=True, 
                tracker="bytetrack.yaml"
            )[0].boxes
            if analysis.id is None:
                # No persons or objects to track, send the empty image
                cv2.imshow("Realtime Personal Tracking", image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    # Hit q to stop the movement tracking (For DEMO)
                    break
                continue

            boxes = analysis.xyxy.cpu().numpy()
            classes = analysis.cls.cpu().numpy()
            track_ids = analysis.id.cpu().numpy()

            if (
                self.target is not None and 
                self.target not in [int(id) for id in track_ids]
            ):
                # Clear the target if the target is out of the frame
                self.target = None

            for box, class_id, track_id in zip(boxes, classes, track_ids):
                # YOLOv8 can actually detect more than just a person, but person's class_id is 0
                if int(class_id) == 0 and self.target is None:
                    # Lock in the new target if there is no previous targets
                    # or the previous target is out
                    self.target = int(track_id)

                if self.target == int(track_id):
                    # For the target, compute the geometric of the target compared with the image
                    # and get the instruction
                    h, w, _ = image.shape
                    x1, y1, x2, y2 = map(int, box)

                    # Determine the signal
                    new_turn = self._get_turn_signal(w, x1, x2)
                    new_move = self._get_move_signal(w, h, x1, x2, y1, y2)

                    if new_turn != prev_turn or new_move != prev_move:
                        # If the instruction changes, send the new instruction to Arduino
                        prev_turn = new_turn
                        prev_move = new_move
                        if CONNECT_ARDUINO_FLAG:
                            self._send_command(prev_move, prev_turn)

                    cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 3)
                    cv2.putText(
                        image, 
                        f"Turn {prev_turn}, move {prev_move}", 
                        (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5
                    )

            cv2.imshow("Realtime Personal Tracking", image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                # Hit q to stop the movement tracking (For DEMO)
                break


    def _expand_face(self, 
        w: int, h: int, x1: int, y1: int, x2: int, y2: int
    ) -> tuple[int]:
        """Helper method: Expand the box a little bit to match the training images"""
        box_w = x2 - x1
        box_h = y2 - y1
        side = max(box_w, box_h)

        # Add padding to the box around the face
        padding = 0.2
        side = int(side * (1 + padding)) 

        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        _x1 = max(0, cx - side // 2)
        _y1 = max(0, cy - side // 2)
        _x2 = min(w, cx + side // 2)
        _y2 = min(h, cy + side // 2)

        return _x1, _y1, _x2, _y2


    def execute(self) -> list:
        emotions = []

        # Take the picture of the user with the opened camera
        if not self.camera:
            return emotions, None
        self.flush_buffer()
        success, image = self.camera.read()
        if not success: 
            return emotions, None

        face_rgb = None
        try: 
            # The face detector captures only one image at the time
            analysis = self.face_detector(image)[0].boxes
            boxes = analysis.xyxy.cpu().numpy()

            # len() check, not `is not None` -- YOLO returns an empty ndarray
            # (never None) when no face is found, so `is not None` was always
            # true and this branch silently ran on empty detections for a
            # long time before it got caught.
            if len(boxes) > 0:
                # The face the YOLO is most confident, which is often the closest face
                h, w, _ = image.shape
                x1, y1, x2, y2 = map(int, boxes[0])
                x1, y1, x2, y2 = self._expand_face(w, h, x1, y1, x2, y2)
                face_region: MatLike = image[y1:y2, x1:x2]

                #change cv2 from BGR to RGB since hsemotion expects RGB
                face_rgb = cv2.cvtColor(face_region, cv2.COLOR_BGR2RGB)


                _, scores = self.emotion_classifier.predict(face_rgb)

                top_indices = np.argsort(scores)[::-1][:NUM_TOP_EMOTIONS]
                emotions = [
                    {
                        "emotion": self.emotion_labels[i],
                        "confidence": round(float(scores[i]), 2)
                    }
                    for i in top_indices if scores[i] > 0.1
                ]
                    
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
                for i, e in enumerate(emotions):
                    label = f"{e['emotion']}: {e['confidence']:.2f}"
                    cv2.putText(
                        image,
                        label,
                        (10, 50 + i * 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3
                    )
                image_path = DIRECTORY_PATH / "analyzed_image.jpg"
                image_saved = cv2.imwrite(str(image_path), image)
                if not image_saved:
                    raise Exception("Error saving the image to the file")

                print(f"Final analyzed image saved to: {image_path}")
            else:
                face_rgb = None
                cv2.putText(
                    image, 
                    "No emotions determined", 
                    (10, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5
                )
        except Exception as e:
            face_rgb = None
            import traceback
            traceback.print_exc()
            cv2.putText(
                image, 
                f"Error during emotional analysis {e}", 
                (10, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5
            )

        return emotions, face_rgb


if __name__ == "__main__": 
    # This is to test the workflow of the pipeline when integrated into workflow
    cv_pipeline = CVPipeline()
    conversation_mode = False

    cv_pipeline.turn_on_camera()
    # will take a picture and give the top three emotions detected by confidence
    emotions, face_rgb = cv_pipeline.execute()
    print(emotions)
    print(face_rgb)
    #cv_pipeline.track_movement()
    cv_pipeline.turn_off_camera()
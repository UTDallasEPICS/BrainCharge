from typing import Optional
from ultralytics import YOLO
import cv2
from cv2.typing import MatLike
import os
import warnings
from pathlib import Path
import torch
from torch import device, cuda, Tensor, float32
from torchvision.models import ResNet
from torchvision.transforms import v2
from cv.cv_model import get_resnet

DEVICE: device = "cuda" if cuda.is_available() else "cpu"
FILEPATH = "./yolov8n-face-lindevs.pt"
AVAILABLE_EMOTIONS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]
TEXT_COLOR = cv2.FONT_HERSHEY_SIMPLEX
NUM_TOP_EMOTIONS = 3


#os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=INFO, 2=WARNING, 3=ERROR
#os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN messages
#warnings.filterwarnings('ignore')


PARENT_NAME = r"C:\Users\sahot\OneDrive\Desktop\textbooks+Slides\EPICS\spring26\code\BrainCharge_Update\BrainCharge"
DIRECTORY_NAME = "picturefile"

parent_path = Path(PARENT_NAME)
child_path = parent_path / DIRECTORY_NAME

child_path.mkdir(parents=True, exist_ok=True)
print(f"Image folder ready at: {child_path}")

class CVPipeline:
    def __init__(self):
        self.camera: Optional[cv2.VideoCapture] = None
        self.face_detector = self._init_face_detector(FILEPATH, DEVICE)
        self.emotion_classifier = get_resnet().to(DEVICE).eval()


    def _init_face_detector(self, filepath: str, device) -> YOLO:
        """Get the YOLO-based detection model"""
        detector = YOLO(filepath).to(device)
        return detector
    

    def _convert_to_tensor(image: MatLike, device: device) -> Tensor:
        """Convert the cv2 image to torch tensor"""
        # Convert img to 1-dim grayscale first, then 3-dim grayscale
        grayscale = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        # Scale, normalize the tensorized img
        transform = v2.Compose([
            v2.Resize(224),
            v2.ToImage(),
            v2.ToDtype(float32, scale=True),
            v2.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            )
        ])
        return transform(grayscale).unsqueeze(0).to(device)
    

    def get_camera(self):
        """Get the camera (OOP 101)"""
        return self.camera
    

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

        for _ in range(7):
            # Warm up the camera to prevent it from crashing when reopening
            self.camera.read()


    def turn_off_camera(self) -> None:
        """Turn off the camera if there is an opened one"""
        if self.camera is not None:
            self.camera.release()
            self.camera.destroyAllWindows() 
            self.camera = None
            print("Turn off the camera successfully!")


    def execute(self) -> list:
        emotions = []

        # Take the picture of the user with the opened camera
        if not self.camera: 
            return
        success, image = self.camera.read()
        if not success: 
            return

        try: 
            # Only one image, so generally only one analysis returned
            analysis = self.face_detector(image)[0]

            boxes = analysis[0].boxes.xyxy.cpu().numpy()
            if boxes and isinstance(boxes, list) and len(boxes) > 0:
                # The face the YOLO is most confident, which I think is often the closest face
                x1, y1, x2, y2 = map(int, boxes[0])

                # Feed to emotion classifier
                face_region = image[y1:y2, x1:x2]
                with torch.no_grad():
                    output = self.emotion_classifier(self._convert_to_tensor(face_region, DEVICE))
                    _, top_labels = torch.topk(output, NUM_TOP_EMOTIONS)

                emotions = [AVAILABLE_EMOTIONS[label] for label in top_labels[0].cpu().numpy()]
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(image, emotions, (10, 30), TEXT_COLOR, 0.9, (0, 255, 0), 2)

            else: 
                emotions = ["No face/emotion detected/determined"]
                cv2.putText(image, emotions, (10, 30), TEXT_COLOR, 0.7, (0, 0, 255), 2)
                
        except Exception as e:
            emotions = [f"Error during emotional analysis {e}"]
            cv2.putText(image, emotions, (10, 30), TEXT_COLOR, 0.7, (0, 0, 255), 2)

        image_path = child_path / "analyzed_image.jpg"
        cv2.imwrite(str(image_path), image)

        print(f"Final analyzed image saved to: {image_path}")
        return emotions


def main():
    # This is to test the workflow of the pipeline
    cv_pipeline = CVPipeline()

    cv_pipeline.turn_on_camera()
    cv_pipeline.execute()
    cv_pipeline.turn_off_camera()

if __name__ == "__main__": 
    main()
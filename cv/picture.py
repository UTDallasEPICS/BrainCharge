from typing import Optional
from ultralytics import YOLO
import cv2
from cv2.typing import MatLike
from pathlib import Path
import torch
from torch import nn
from torch import device, cuda, Tensor, float32
from torchvision.transforms import v2
from torchvision.models import EfficientNet, efficientnet_b2
from PIL import Image

DEVICE: device = "cuda" if cuda.is_available() else "cpu"
DETECTOR_FILEPATH = "./yolov8n-face-lindevs.pt"
CLASSIFIER_FILEPATH = "./emotions_model.pth"

AVAILABLE_EMOTIONS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]
NUM_TOP_EMOTIONS = 3

# Maybe a better way of handling these constants rather than CONSTANT
PARENT_NAME = r"C:\Users\sahot\OneDrive\Desktop\textbooks+Slides\EPICS\spring26\code\BrainCharge_Update\BrainCharge"
DIRECTORY_NAME = "picturefile"

PARENT_PATH = Path(PARENT_NAME)
CHILD_PATH = PARENT_PATH / DIRECTORY_NAME

CHILD_PATH.mkdir(parents=True, exist_ok=True)
print(f"Image folder ready at: {CHILD_PATH}")

class CVPipeline:
    def __init__(self):
        self.camera: Optional[cv2.VideoCapture] = None
        self.face_detector = self._init_face_detector(DETECTOR_FILEPATH, DEVICE)
        self.emotion_classifier = self._init_emotion_classifier(CLASSIFIER_FILEPATH, DEVICE)

    def _init_face_detector(self, filepath: str, device) -> YOLO:
        """Get the YOLO-based detection model"""
        detector = YOLO(filepath).to(device)
        return detector
    
    def _init_emotion_detector(self, filepath: str, device: device) -> EfficientNet:
        """Helper method: Initialize the emotional classification model"""
        efficientnet = efficientnet_b2()
        # Modify the linear head
        efficientnet.classifier = nn.Sequential(
            nn.Linear(1408, 2048, bias=True),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(2048, 512, bias=True),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(512, 7, bias=True)
        )

        efficientnet.load_state_dict(torch.load(filepath, map_location=device))
        return efficientnet.to(device)


    def _convert_to_tensor(image: MatLike, device: device) -> Tensor:
        """Convert the cv2 image to torch tensor"""
        modified = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  
        modified = Image.fromarray(modified)

        transform = v2.Compose([
            v2.Lambda(lambda x: x.convert("L").convert("RGB")),
            v2.Resize([224, 224]),
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225])
        ])

        return transform(modified).unsqueeze(0).to(device)
    

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
        print("Turn on the camera successfully!")


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
                h, w, _ = image.shape
                x1, y1, x2, y2 = map(int, boxes[0])
                box_w = x2 - x1
                box_h = y2 - y1
                side = max(box_w, box_h)

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                x1 = max(0, cx - side // 2)
                y1 = max(0, cy - side // 2)
                x2 = min(w, cx + side // 2)
                y2 = min(h, cy + side // 2)
                face_region: MatLike = image[y1:y2, x1:x2]

                # Feed to emotion classifier
                face_region = image[y1:y2, x1:x2]
                with torch.no_grad():
                    output = self.emotion_classifier(self._convert_to_tensor(face_region, DEVICE))
                    _, top_labels = torch.topk(output, NUM_TOP_EMOTIONS)

                emotions = [AVAILABLE_EMOTIONS[l] for l in top_labels[0].cpu().numpy()]
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    image, emotions, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            else: 
                emotions = ["No emotion determined"]
                cv2.putText(
                    image, emotions, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
        except Exception as e:
            emotions = [f"Error during emotional analysis {e}"]
            cv2.putText(image, emotions, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        image_path = CHILD_PATH / "analyzed_image.jpg"
        cv2.imwrite(str(image_path), image)

        print(f"Final analyzed image saved to: {image_path}")
        return emotions


if __name__ == "__main__": 
    # This is to test the workflow of the pipeline when integrated into workflow
    cv_pipeline = CVPipeline()
    conversation_mode = False

    while True:
        prompt = input("Enter: ")
        if "hello" in prompt.lower():
            conversation_mode = True
            cv_pipeline.turn_on_camera()

        if conversation_mode:
            detected_emotions = cv_pipeline.execute()
            print(f"LLM will response based on these emotions: {", ".join(detected_emotions)}")

        if "bye" in prompt.lower():
            conversation_mode = False
            cv_pipeline.turn_off_camera()
            break
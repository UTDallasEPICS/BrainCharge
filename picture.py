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
from cv_model import get_resnet

DEVICE: device = "cuda" if cuda.is_available() else "cpu"
FILEPATH = "./yolov8n-face-lindevs.pt"
AVAILABLE_EMOTIONS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]
TEXT_COLOR = cv2.FONT_HERSHEY_SIMPLEX


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=INFO, 2=WARNING, 3=ERROR
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN messages
warnings.filterwarnings('ignore')

parent_name = r"C:\Users\sahot\OneDrive\Desktop\textbooks+Slides\EPICS\spring26\code\BrainCharge_Update\BrainCharge"
directory_name = "picturefile"

parent_path = Path(parent_name)
child_path = parent_path / directory_name

child_path.mkdir(parents=True, exist_ok=True)
print(f"Image folder ready at: {child_path}")


def turn_on_camera() -> cv2.VideoCapture:
    """Attempts to turn on the camera"""
    print("Trying DirectShow backend...")
    camera_found = False
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if camera.isOpened():
        camera_found = True
        print("Cam found with DirectShow.")
    else:
        camera.release()
        print("Trying different backend with different camera indices")
        for i in range(3):
            print(f"Trying camera index [i]...")
            camera = cv2.VideoCapture(i)
            if camera.isOpened():
                camera_found = True
                print(f"Camera found at index {i}")
                break

    if not camera_found: 
        print("Error: could not open any webcam.")
        print("Please check: ")
        print("1. Is connected")
        print("2. Camera permissions are enabled with Windows Settings")
        print("3. No other application is using camera")
        exit()

    return camera


def turn_off_camera(camera: cv2.VideoCapture) -> None:
    """Turn off the camera if there is an opened one"""
    if camera:
        camera.release()
        camera.destroyAllWindows()


def get_face_detector(filepath: str, device) -> YOLO:
    """Get the YOLO-based detection model"""
    detector = YOLO(filepath).to(device)
    return detector


def convert_to_tensor(image: MatLike, device: device) -> Tensor:
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


def cv_pipeline(camera: cv2.VideoCapture, face_detector: YOLO, emotion_classifier: ResNet) -> None:
    # Take the picture of the user with the opened camera
    if not camera: return
    success, image = camera.read()
    if not success: 
        return

    try: 
        # Only one image, so generally only one analysis returned
        analysis = face_detector(image)[0]

        boxes = analysis[0].boxes.xyxy.cpu().numpy()
        if boxes and isinstance(boxes, list) and len(boxes) > 0:
            # The face the YOLO is most confident, which I think is often the closest face
            x1, y1, x2, y2 = map(int, boxes[0])
            emotion = analysis[0]['dominant_emotion']

            # Feed to emotion classifier
            face_region = image[y1:y2, x1:x2]
            output = emotion_classifier(convert_to_tensor(face_region, DEVICE))
            _, label = torch.max(output, dim=1)
            emotion = AVAILABLE_EMOTIONS[label.numpy()[0]]

            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(image, emotion, (10, 30), TEXT_COLOR, 0.9, (0, 255, 0), 2)
        else: 
            emotion = "No face/emotion detected/determined"
            cv2.putText(image, emotion, (10, 30), TEXT_COLOR, 0.7, (0, 0, 255), 2)
            
    except Exception as e:
        emotion = f"Error during emotional analysis {e}"
        cv2.putText(image, emotion, (10, 30), TEXT_COLOR, 0.7, (0, 0, 255), 2)

    image_path = child_path / "analyzed_image.jpg"
    cv2.imwrite(str(image_path), image)

    print(f"Final analyzed image saved to: {image_path}")


def main():
    # This is to test the workflow
    face_detector = get_face_detector(FILEPATH, DEVICE)
    animal_classifier = get_resnet().to(DEVICE).eval()

    camera = turn_on_camera()
    cv_pipeline(camera, face_detector, animal_classifier)
    turn_off_camera(camera)

if __name__ == "__main__": 
    main()
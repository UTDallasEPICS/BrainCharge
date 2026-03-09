from deepface import DeepFace
import cv2
import os
import warnings
from pathlib import Path

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


def cv_pipeline(camera: cv2.VideoCapture) -> None:
    # Take the picture of the user with the opened camera
    if not camera:
        return
    success, image = camera.read()
    if not success:
        return

    try: 
        analysis = DeepFace.analyze(image, actions=['emotion'], enforce_detection=False)

        if analysis and isinstance(analysis, list) and len(analysis) > 0:
            emotion = analysis[0]['dominant_emotion']
            face_region = analysis[0]['region']

            x,y,w,h = face_region['x'], face_region['y'], face_region['w'], face_region['h']
            cv2.rectangle(image, (x,y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(image, emotion, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        else: 
            emotion = "No face/emotion detected/determined"
            cv2.putText(image, emotion, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    except Exception as e:
        emotion = f"Error during emotional analysis {e}"
        cv2.putText(image, emotion, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    image_path = child_path / "analyzed_image.jpg"
    cv2.imwrite(str(image_path), image)

    print(f"Final analyzed image saved to: {image_path}")

if __name__ == "__main__":
    camera = turn_on_camera()
    cv_pipeline(camera)
    turn_off_camera(camera)
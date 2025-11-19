from deepface import DeepFace
import cv2
import os
import warnings

# Suppress TensorFlow messages
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=INFO, 2=WARNING, 3=ERROR
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN messages

# Suppress Python warnings
warnings.filterwarnings('ignore')

# Now import TensorFlow and other libraries
import tensorflow as tf




# Initialize the webcam (0 for default webcam)
cap = None
camera_found = False
print("Trying DirectShow backend...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if cap.isOpened():
    camera_found = True
    print("Cam found with DirectShow.")
else:
    cap.release()

    print("Trying different backend with different camera indices")
    for i in range(3):
        print(f"Trying camera index [i]...")
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            camera_found = True
            print(f"Camera found at index {i}")
            break
        cap.release()

if not camera_found: 
    print("Error: could not open any webcam")
    print("please check: ")
    print("1. Is connected")
    print("2. Camera permissions are enabled with Windows Settings")
    print("3. No other application is using camera")
    exit()
    
# Capture a single frame
ret, frame = cap.read()

if ret:
    # Save the captured frame as an image file
    cv2.imwrite("captured_image.jpg", frame)
    print("Image captured and saved as 'captured_image.jpg'")
else:
    print("Error: Could not read frame from webcam.")

# Release the webcam
cap.release()
cv2.destroyAllWindows()

img = cv2.imread("captured_image.jpg")

gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

try: 
    analysis = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)

    if analysis and isinstance(analysis, list) and len(analysis) > 0:
        dominant_emotion = analysis[0]['dominant_emotion']
        face_region = analysis[0]['region']

        x,y,w,h = face_region['x'], face_region['y'], face_region['w'], face_region['h']
        cv2.rectangle(frame, (x,y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, dominant_emotion, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)
    
    else: 
        dominant_emotion = "No face/emotion detected/determined"
        cv2.putText(frame, dominant_emotion, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
except Exception as e:
    
    dominant_emotion = f"Error during emotional analysis {e}"
    cv2.putText(frame, dominant_emotion, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
cv2.imshow('Captured Image with emotion', frame)
cv2.waitKey(0)
cv2.destroyAllWindows()
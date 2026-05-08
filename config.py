# config.py
# Central configuration for the Companion Robot.
# Change SERIAL_PORT here and it propagates everywhere.

import platform

# --- Serial / Arduino ---
# On Windows: "COM3"
# On Jetson / Linux: "/dev/ttyUSB0" or "/dev/ttyACM0"
if platform.system() == "Windows":
    SERIAL_PORT = "COM3"
else:
    SERIAL_PORT = "/dev/tty.usbmodem21101"

BAUD_RATE = 115200
SERIAL_TIMEOUT = 2          # seconds

# --- Feature Flags ---
CONNECT_ARDUINO = True      # Set False to run CV-only without hardware

# --- Wake Word ---
WAKE_WORD = "companion"

# --- CV Pipeline ---
PERSON_DETECTOR_PATH   = "yolov8n.pt"
FACE_DETECTOR_PATH     = "./cv_pipeline/yolov8n-face-lindevs.pt"
EMOTION_MODEL_PATH     = "./cv_pipeline/emotions_model.pt"
AVAILABLE_EMOTIONS     = ["Angry", "Fear", "Happy", "Neutral", "Sad"]
NUM_TOP_EMOTIONS       = 2
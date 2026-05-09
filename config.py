# config.py
# Central configuration for the Companion Robot.
# Jetson Orin Nano edition — updated serial port detection and model paths.

import platform
import os

_system = platform.system()

# --- Serial / Arduino ---
# On Windows  : "COM3"
# On macOS    : "/dev/tty.usbmodem21101"
# On Jetson / Linux :
#   USB-serial adapters (FTDI, CH340) → /dev/ttyUSB0
#   Arduino Uno/Mega (CDC ACM)        → /dev/ttyACM0
#   Check with: ls /dev/tty{USB,ACM}* after plugging in

if _system == "Windows":
    SERIAL_PORT = "COM3"
elif _system == "Darwin":
    SERIAL_PORT = "/dev/tty.usbmodem21101"
else:  # Linux / Jetson
    # Auto-detect: prefer ACM0, fall back to USB0
    if os.path.exists("/dev/ttyACM0"):
        SERIAL_PORT = "/dev/ttyACM0"
    elif os.path.exists("/dev/ttyUSB0"):
        SERIAL_PORT = "/dev/ttyUSB0"
    else:
        SERIAL_PORT = "/dev/ttyACM0"   # default; override in config.json if needed

BAUD_RATE      = 115200
SERIAL_TIMEOUT = 2          # seconds

# --- Feature Flags ---
CONNECT_ARDUINO = True      # Set False to run CV-only without hardware

# --- Wake Word ---
WAKE_WORD = "companion"

# --- CV Pipeline ---
PERSON_DETECTOR_PATH  = "yolov8n.pt"
FACE_DETECTOR_PATH    = "./cv_pipeline/yolov8n-face-lindevs.pt"
EMOTION_MODEL_PATH    = "./cv_pipeline/emotions_model.pt"
AVAILABLE_EMOTIONS    = ["Angry", "Fear", "Happy", "Neutral", "Sad"]
NUM_TOP_EMOTIONS      = 2

# --- Jetson / CUDA info (informational) ---
try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
    CUDA_DEVICE    = torch.cuda.get_device_name(0) if CUDA_AVAILABLE else "N/A"
except ImportError:
    CUDA_AVAILABLE = False
    CUDA_DEVICE    = "torch not installed"

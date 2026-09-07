# BrainCharge — Jetson Orin Nano Setup Guide

Fresh-out-of-the-box walkthrough. Follow every step in order.

---

## What You Need Before Starting

- Jetson Orin Nano Developer Kit (4 GB or 8 GB)
- microSD card **≥ 64 GB** (A2-rated recommended) **or** NVMe SSD
- USB-C power supply (≥ 5 V / 4 A)
- USB keyboard, mouse, HDMI monitor (for first boot only)
- Internet connection (Ethernet recommended for first setup)
- USB microphone
- USB camera (or CSI camera)
- Arduino Mega/Uno connected via USB

---

## Part 1 — Flash the Jetson

### 1.1  Download and flash JetPack 6

1. On a separate PC, download **NVIDIA SDK Manager** from:
   https://developer.nvidia.com/sdk-manager

2. Flash **JetPack 6.0** (or newer) to your Jetson:
   - Connect the Jetson in recovery mode (hold REC button, then plug power)
   - In SDK Manager, select "Jetson Orin Nano" → JetPack 6.x → Flash

   **OR** use the simpler SD-card method if you have an Orin Nano Dev Kit:
   - Download the SD card image: https://developer.nvidia.com/embedded/downloads
   - Flash with **Balena Etcher** → insert card → power on

3. Complete the first-boot Ubuntu setup wizard (username, password, timezone).

### 1.2  Verify CUDA is working

Open a terminal and run:

```bash
nvcc --version
# Should show: Cuda compilation tools, release 12.x
```

---

## Part 2 — System Dependencies

Run all of these in a terminal on the Jetson (one block at a time).

### 2.1  System update

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2  Essential build tools

```bash
sudo apt install -y \
    git cmake build-essential \
    python3-pip python3-dev python3-venv \
    curl wget nano htop
```

### 2.3  Audio stack

```bash
sudo apt install -y \
    ffmpeg \
    alsa-utils \
    portaudio19-dev \
    python3-pyaudio \
    espeak
```

Test your microphone:

```bash
# List audio capture devices
arecord -l

# Record 3 seconds to verify mic works (use the card number from above)
# If your mic is card 2, device 0:
arecord -D hw:2,0 -d 3 -f S16_LE -r 16000 test.wav
aplay test.wav
```

> **Note your mic's card number** — you'll need it for `config.json` later.
> Set `"linux_audio_device": "hw:2,0"` (replace 2,0 with your values).

### 2.4  OpenCV system libraries

```bash
sudo apt install -y \
    libopencv-dev \
    python3-opencv \
    v4l-utils
```

Test your camera:

```bash
# List video devices
ls /dev/video*
v4l2-ctl --list-devices

# Quick camera preview (press q to quit)
python3 -c "import cv2; cap=cv2.VideoCapture(0); ret,f=cap.read(); print('Camera OK' if ret else 'Camera FAILED')"
```

### 2.5  Arduino serial permissions

```bash
# Add yourself to dialout group so you can access /dev/ttyACM0 without sudo
sudo usermod -aG dialout $USER

# Verify Arduino is detected (plug it in first)
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

> **You must log out and back in** (or reboot) for the group change to take effect.

---

## Part 3 — Python Environment

### 3.1  Create a virtual environment

```bash
cd ~
python3 -m venv braincharge-env
source ~/braincharge-env/bin/activate

# You should see (braincharge-env) in your prompt from now on.
# Add activation to your shell startup so it's always active:
echo "source ~/braincharge-env/bin/activate" >> ~/.bashrc
```

### 3.2  Install PyTorch for JetPack 6 (NVIDIA wheel — NOT from PyPI)

NVIDIA provides pre-built PyTorch wheels with CUDA support for Jetson.
These are different from the standard pip packages.

```bash
# Install pip build tools first
pip install --upgrade pip setuptools wheel

# Download NVIDIA's PyTorch wheel for JetPack 6 / Python 3.10
# Check https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/
# for the exact filename; the command below covers JetPack 6.0:

wget https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/torch-2.3.0a0+ebedce2-cp310-cp310-linux_aarch64.whl

pip install torch-2.3.0a0+ebedce2-cp310-cp310-linux_aarch64.whl
```

> If the URL above is outdated, go to:
> https://developer.nvidia.com/embedded/downloads#?search=pytorch
> and grab the latest JP6-compatible wheel for Python 3.10.

### 3.3  Build and install torchvision

torchvision must be built from source on Jetson (no pre-built wheel exists).

```bash
# Install build deps
sudo apt install -y libjpeg-dev zlib1g-dev libpython3-dev

# Clone and build torchvision (match the torch version above)
cd ~
git clone --branch v0.18.0 https://github.com/pytorch/vision.git
cd vision

# Set CUDA arch for Jetson Orin (SM 87)
export TORCH_CUDA_ARCH_LIST="8.7"
export FORCE_CUDA=1

pip install -e .
cd ~
```

This takes 10–20 minutes. Go get a coffee.

### 3.4  Verify PyTorch + CUDA

```bash
python3 -c "
import torch
print('PyTorch:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')
"
```

Expected output:
```
PyTorch: 2.3.0a0+ebedce2
CUDA available: True
GPU: Orin
```

---

## Part 4 — Ollama (LLM)

### 4.1  Install Ollama

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 4.2  Pull the model

```bash
# Start Ollama service
ollama serve &

# Pull the model (downloads ~3 GB — Jetson 4 GB RAM can run this)
ollama pull gemma3:4b

# Test it
ollama run gemma3:4b "Hello! Are you working?"
```

### 4.3  Make Ollama start on boot (optional but recommended)

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

---

## Part 5 — Clone and Configure BrainCharge

### 5.1  Clone the repo

```bash
cd ~
git clone https://github.com/UTDallasEPICS/BrainCharge.git
cd BrainCharge
```

### 5.2  Install Python packages

```bash
# Make sure your venv is active
source ~/braincharge-env/bin/activate

pip install -r requirements.txt
```

### 5.3  Install Whisper.cpp (clone, build, download model)

**Not included when you clone BrainCharge** — each Jetson must do this once (`whisper.cpp/` is gitignored). See also [PC_TESTING.md §2](PC_TESTING.md#2-install-whispercpp-clone-build-download-model) for the same steps on Windows.

```bash
cd ~/BrainCharge
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp

# Build with CUDA support for Jetson
cmake -B build \
    -DWHISPER_CUDA=ON \
    -DCMAKE_CUDA_ARCHITECTURES=87

cmake --build build --config Release -j$(nproc)

# Download the English base model (~150 MB)
cd models
bash download-ggml-model.sh base.en
cd ~/BrainCharge
```

Test Whisper:

```bash
# Record a quick test clip and transcribe
ffmpeg -f alsa -i default -t 3 -ar 16000 -ac 1 test_whisper.wav -y
./whisper.cpp/build/bin/whisper-cli \
    -m whisper.cpp/models/ggml-base.en.bin \
    -f test_whisper.wav
```

### 5.4  Download Vosk model (for echo-aware TTS interrupt)

```bash
cd ~/BrainCharge
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
rm vosk-model-small-en-us-0.15.zip
```

Install vosk Python package:

```bash
pip install vosk
```

### 5.5  Download YOLO and emotion model weights

```bash
cd ~/BrainCharge

# YOLOv8n (person detector) — auto-downloads on first run, but you can pre-fetch:
python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Face detector — download from the project's release assets or team drive:
# Place as: cv_pipeline/yolov8n-face-lindevs.pt

# Emotion classifier — from project assets:
# Place as: cv_pipeline/emotions_model.pt
```

> Ask your team lead for the `yolov8n-face-lindevs.pt` and `emotions_model.pt` files
> if they are not already in the repo. These are large binary files typically shared
> via Google Drive or a release attachment.

---

## Part 6 — Configure BrainCharge

### 6.1  Create your config.json

```bash
cd ~/BrainCharge
cp config.json.example config.json   # or use the Jetson-specific config.json from this guide
```

Edit `config.json` and check these fields:

```json
{
  "whisper_path_linux":  "whisper.cpp/build/bin/whisper-cli",
  "whisper_model":       "whisper.cpp/models/ggml-base.en.bin",

  "connect_arduino":     true,
  "serial_port_linux":   "/dev/ttyACM0",

  "linux_audio_backend": "alsa",
  "linux_audio_device":  "hw:2,0",

  "vosk_model_path":     "vosk-model-small-en-us-0.15",
  "vosk_interrupt_enabled": true,

  "ollama_model":        "gemma3:4b",
  "wake_word":           "companion",
  "sleep_word":          "bye companion"
}
```

**Finding your audio device:**

```bash
arecord -l
# Look for your USB mic, e.g.:
# card 2: Device [USB Audio Device], device 0: USB Audio [USB Audio]
# → use "hw:2,0"
```

**Finding your Arduino serial port:**

```bash
# Plug in Arduino, then:
ls /dev/ttyACM* /dev/ttyUSB*
# Usually /dev/ttyACM0 for Uno/Mega
```

---

## Part 7 — First Run

### 7.1  Run a system check

```bash
cd ~/BrainCharge
source ~/braincharge-env/bin/activate

python3 -c "
import torch, cv2, serial, pyaudio, vosk
print('torch:', torch.__version__, '| CUDA:', torch.cuda.is_available())
print('opencv:', cv2.__version__)
print('pyserial: OK')
print('pyaudio: OK')
print('vosk: OK')
from cv_pipeline import CVPipeline
print('CVPipeline: OK')
"
```

### 7.2  Start the robot

```bash
cd ~/BrainCharge
source ~/braincharge-env/bin/activate
python3 main.py
```

You should see the startup banner:
```
============================================================
  BrainCharge Companion Robot — Caregiver Compassion Bot
  Wake word : "companion"
  Sleep word: "bye companion"
  ...
[Sleep] Listening for wake word...
```

Say **"companion"** → the robot wakes up, greets you, and starts tracking.

Say **"bye companion"** → it generates a session summary and returns to sleep.

Press **Ctrl-C** → graceful shutdown.

---

## Part 8 — Auto-Start on Boot (Optional)

If you want BrainCharge to start automatically when the Jetson powers on:

```bash
sudo nano /etc/systemd/system/braincharge.service
```

Paste:

```ini
[Unit]
Description=BrainCharge Companion Robot
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/BrainCharge
ExecStart=/home/YOUR_USERNAME/braincharge-env/bin/python3 main.py
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_USERNAME` with your actual username, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable braincharge
sudo systemctl start braincharge

# Check logs:
journalctl -u braincharge -f
```

---

## Troubleshooting

### "CUDA not available" in PyTorch
- Make sure you installed the NVIDIA wheel (Step 3.2), not the generic PyPI version.
- Run `pip show torch` — the version string should end in `+cuda` or contain `ebedce2`.
- Re-flash JetPack if CUDA libraries are missing.

### "No module named pyaudio"
```bash
sudo apt install portaudio19-dev
pip install pyaudio
```

### Arduino: "Permission denied /dev/ttyACM0"
```bash
sudo usermod -aG dialout $USER
# Then log out and back in, or:
sudo chmod 666 /dev/ttyACM0   # temporary fix until reboot
```

### Arduino: wrong port / not detected
```bash
ls /dev/ttyACM* /dev/ttyUSB*     # see what ports exist
dmesg | tail -20                  # shows USB events when you plug in
```
Update `serial_port_linux` in `config.json` to match.

### FFmpeg can't find audio device
```bash
# List ALSA capture devices
arecord -l

# Test a specific device (replace 2,0 with your values)
ffmpeg -f alsa -i hw:2,0 -t 3 -ar 16000 test.wav -y && aplay test.wav
```
Update `linux_audio_device` in `config.json`.

### Whisper binary not found
```bash
ls whisper.cpp/build/bin/
# If empty, rebuild:
cd whisper.cpp
cmake -B build -DWHISPER_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build -j$(nproc)
```

### Whisper very slow (no GPU)
Check CUDA was enabled at build time:
```bash
./whisper.cpp/build/bin/whisper-cli --help 2>&1 | grep -i cuda
```
If no CUDA output, rebuild with `-DWHISPER_CUDA=ON`.

### Ollama model errors
```bash
ollama list                   # see installed models
ollama pull gemma3:4b         # re-pull if missing
systemctl status ollama       # check service is running
```

### Camera not found
```bash
ls /dev/video*
v4l2-ctl --list-devices
# Try different indices (0, 1, 2) in cv_pipeline/picture.py
```

### "ImportError: cv_pipeline" 
Make sure you're in the `BrainCharge` directory and the venv is active:
```bash
cd ~/BrainCharge
source ~/braincharge-env/bin/activate
python3 main.py
```

### Out of memory during inference
- Use `gemma3:1b` instead of `4b` (edit `ollama_model` in `config.json`)
- Disable YOLO tracking (`CV_AVAILABLE` will be False if the import fails)
- Close other GPU-heavy processes

---

## Quick Reference — Daily Use

```bash
# Activate environment
source ~/braincharge-env/bin/activate

# Start the robot
cd ~/BrainCharge && python3 main.py

# Check Arduino port
ls /dev/ttyACM* /dev/ttyUSB*

# Check mic
arecord -l

# Check Ollama
ollama list

# Test whisper manually
./whisper.cpp/build/bin/whisper-cli -m whisper.cpp/models/ggml-base.en.bin -f input.wav
```

---

## File Map (what goes where after setup)

```
BrainCharge/
├── main.py                          ← main entry point (updated for Jetson)
├── config.py                        ← serial port / path constants (updated)
├── config.json                      ← your local settings (never commit this)
├── requirements.txt                 ← Python packages (updated for ARM64)
├── serial_movements_jetson.py       ← manual serial test script (updated)
├── Hardware/
│   └── serial_movements_arduino.ino ← Arduino firmware (unchanged)
├── cv_pipeline/
│   ├── picture.py                   ← CV pipeline (unchanged)
│   ├── yolov8n-face-lindevs.pt      ← face detector weights (from team)
│   └── emotions_model.pt            ← emotion classifier weights (from team)
├── whisper.cpp/                     ← built locally (gitignored)
│   ├── build/bin/whisper-cli        ← compiled binary
│   └── models/ggml-base.en.bin      ← downloaded model
├── vosk-model-small-en-us-0.15/     ← vosk STT model (gitignored)
└── yolov8n.pt                       ← YOLO person detector (auto-downloaded)
```

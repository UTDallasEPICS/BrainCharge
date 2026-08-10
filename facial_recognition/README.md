# Facial Recognition — Setup & Run Guide

Low-latency, real-time face recognition for BrainCharge. Uses OpenCV **YuNet** (detect) + **SFace** (embed). ONNX models download automatically the first time you run enrollment or live recognition.

This module runs **standalone** today and is **pipeline-ready** (same `FaceRecognitionEngine` API for later integration with `main.py` / `cv_pipeline`).

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | Same as the main BrainCharge project |
| **Webcam** | Built-in or USB camera |
| **Internet (first run only)** | Downloads ~39 MB of ONNX models into `facial_recognition/models/` |
| **Windows / macOS / Linux** | PC and Jetson supported |

OpenCV must include face APIs (`FaceDetectorYN`, `FaceRecognizerSF`) — **OpenCV ≥ 4.5.4**. Desktop live preview needs a GUI OpenCV build (not headless only).

---

## 1. Project setup

Open a terminal in the **BrainCharge project root** (the folder that contains `main.py` and `facial_recognition/`).

### Create / activate a virtual environment (recommended)

**Windows (PowerShell):**

```powershell
cd C:\path\to\BrainCharge-summer26-rewrite
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
cd /path/to/BrainCharge-summer26-rewrite
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

**PC (live window + camera):**

```powershell
pip install --upgrade pip
pip install opencv-python numpy
```

**Jetson / headless server** (no local GUI window; use headless OpenCV if JetPack already provides GUI OpenCV with face modules, skip the pip OpenCV install):

```bash
pip install numpy
# only if system OpenCV is missing:
# pip install opencv-python-headless
```

If you already installed the full project `requirements.txt`, you still need **GUI** OpenCV for the live preview on Windows:

```powershell
pip install opencv-python
```

(`opencv-python` and `opencv-python-headless` conflict — use one. Prefer `opencv-python` for this app on PC.)

---

## 2. Enroll people (training photos)

Recognition compares live faces to a **gallery** built from photos you provide.  
Folder name = **display name**.

### Layout

```text
facial_recognition/known_faces/
  Alice/
    photo1.jpg
    photo2.png
  Bob/
    face.jpg
```

| Rule | Detail |
|------|--------|
| One subfolder per person | Name of the folder is what appears on screen |
| 3–8 photos work best | Clear, front-facing, different lighting if possible |
| Formats | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp` |
| Ignored | Folders starting with `_` or `.` |

### Option A — Drop photos manually

1. Create `facial_recognition/known_faces/<PersonName>/`
2. Copy 3–8 face photos into that folder
3. Build the embedding cache:

```powershell
python -m facial_recognition.enroll --rebuild
```

### Option B — Capture from webcam

```powershell
# Captures up to 5 frames (SPACE to capture, q when done), then rebuilds cache
python -m facial_recognition.enroll --capture Alice --count 5 --rebuild
```

| Flag | Meaning |
|------|---------|
| `--capture NAME` | Person folder name (e.g. `Alice`) |
| `--count N` | Max photos to capture (default `5`) |
| `--camera 0` | Camera index if you have multiple webcams |
| `--rebuild` | Re-encode all enrollment photos into the cache |

### Check who is enrolled

```powershell
python -m facial_recognition.enroll
```

Prints the enrollment directory and each subject’s image count.

---

## 3. Run live facial recognition

From the **project root**, with the venv active:

```powershell
python -m facial_recognition
```

**First run:** YuNet + SFace ONNX files download into `facial_recognition/models/`.  
A window opens with the live feed; known people are labeled with name + confidence, others as `Unknown`.

### Live window keys

| Key | Action |
|-----|--------|
| `q` or `Esc` | Quit |
| `r` | Reload gallery from disk (after adding new photos) |
| `s` | Save annotated snapshot to `facial_recognition/cache/` |

### Common run options

```powershell
# Default camera, 640x480
python -m facial_recognition

# Second camera, custom resolution
python -m facial_recognition --camera 1 --width 1280 --height 720

# Stricter matching (fewer false IDs)
python -m facial_recognition --threshold 0.40

# Skip embedding every other frame (slightly higher FPS; labels may lag)
python -m facial_recognition --every-n 2

# Force rebuild cache on startup
python -m facial_recognition --rebuild

# Do not mirror preview (default is mirrored selfie view)
python -m facial_recognition --no-mirror

# Custom enrollment folder
python -m facial_recognition --faces-dir path\to\my_faces
```

| Flag | Default | Description |
|------|---------|-------------|
| `--faces-dir` | `facial_recognition/known_faces` | Enrollment root |
| `--camera` | `0` | Webcam index |
| `--width` / `--height` | `640` / `480` | Capture size |
| `--threshold` | `~0.363` | Cosine match gate (SFace) |
| `--every-n` | `1` | Run identity matching every N frames |
| `--rebuild` | off | Rebuild embedding cache at start |
| `--no-mirror` | off | Disable horizontal flip of preview |

---

## 4. Typical workflow (copy-paste)

```powershell
# Once per machine
cd C:\path\to\BrainCharge-summer26-rewrite
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install opencv-python numpy

# Enroll
python -m facial_recognition.enroll --capture YourName --count 5 --rebuild

# Run
python -m facial_recognition
```

Add another person later:

```powershell
# Drop photos into known_faces/Bob/  OR:
python -m facial_recognition.enroll --capture Bob --count 5 --rebuild

# Or while live is open: add photos, then press r
python -m facial_recognition
```

---

## 5. Use from Python (pipeline / scripts)

```python
from facial_recognition import FaceRecognitionEngine, FRConfig

engine = FaceRecognitionEngine(FRConfig())
engine.initialize()

# After you grab a BGR frame (OpenCV or cv_pipeline camera):
results = engine.recognize(frame_bgr)
for r in results:
    print(r.name, r.confidence, r.bbox, r.is_known)

# Optional: draw boxes
annotated = engine.annotate(frame_bgr, results)
```

Reload gallery without restarting the process:

```python
engine.reload_gallery(force_rebuild=True)
```

Camera ownership can stay in `main.py` / `cv_pipeline` — only pass frames into `recognize()`.

---

## 6. Troubleshooting

| Problem | What to try |
|---------|-------------|
| `Could not open any webcam` | Close other apps using the camera; try `--camera 1` |
| Everyone shows `Unknown` | Enroll photos, then `python -m facial_recognition.enroll --rebuild` (or press `r` live) |
| Wrong person tagged | Add more clear photos; raise `--threshold` (e.g. `0.40`) |
| Models fail to download | Check internet; manually place ONNX files under `facial_recognition/models/` (see below) |
| No window / GUI error | Install `opencv-python` (not only headless) on PC |
| Import errors | Run commands from **project root**, with venv active |

### Manual model files (optional)

If auto-download fails, place these in `facial_recognition/models/`:

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

Source: [OpenCV Zoo](https://github.com/opencv/opencv_zoo) (`face_detection_yunet`, `face_recognition_sface`).

Or from project root:

```powershell
python -m facial_recognition.models_setup
```

---

## Project layout

| Path | Role |
|------|------|
| `engine.py` | Core API (`recognize`, `annotate`, gallery reload) |
| `app.py` | Standalone live loop |
| `enroll.py` | Status / webcam capture / cache rebuild |
| `detector.py` | YuNet face boxes |
| `encoder.py` | SFace embeddings |
| `gallery.py` | Folder enrollment + NPZ cache |
| `camera.py` | Platform camera open (Windows DirectShow, etc.) |
| `models/` | Auto-downloaded ONNX weights |
| `known_faces/` | Your enrollment photos (gitignored except docs) |
| `cache/` | Embedding cache + snapshots |

---

## Dependencies

- **opencv-python** ≥ 4.5.4 (GUI on PC; or system/JetPack OpenCV on Jetson)
- **numpy**

No dlib or torch required for this module.

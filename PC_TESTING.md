# BrainCharge — PC Testing Guide

Run `main.py` on a Windows (or desktop) PC to test the **voice pipeline** without Jetson hardware. Arduino and camera tracking are disabled by default in PC mode.

For full robot deployment on NVIDIA Jetson Orin Nano, see [JETSON_SETUP.md](JETSON_SETUP.md).

---

## What works on PC

| Feature | PC testing | Jetson robot |
|---------|------------|--------------|
| Wake word (`companion`) | Yes | Yes |
| Speech-to-text (Whisper.cpp) | Yes | Yes |
| LLM replies (Ollama) | Yes | Yes |
| Text-to-speech (Windows SAPI) | Yes | Yes (eSpeak) |
| VAD recording | Yes (with PyAudio) | Yes |
| Arduino motors | Off by default | On by default |
| Camera / person tracking | Off by default (enable in config) | On by default |

> **Jetson code is unchanged.** PC mode only changes defaults via `runtime_platform.py` and `config.json`. The same `cv_pipeline/` code runs on both; `picture.py` already picks DirectShow on Windows and ALSA/V4L on Jetson.

---

## Prerequisites

Install these before starting:

| Tool | Purpose | Windows install |
|------|---------|-----------------|
| **Python 3.10+** | Runs `main.py` | [python.org](https://www.python.org/downloads/) — enable **Add to PATH** |
| **FFmpeg** | Microphone recording | `winget install ffmpeg` |
| **CMake** | Build Whisper.cpp | `winget install Kitware.CMake` |
| **Visual Studio Build Tools** | C++ compiler for Whisper | Install with **Desktop development with C++** workload |
| **Ollama** | Local LLM | [ollama.ai](https://ollama.ai) — restart terminal after install |
| **Git** | Clone whisper.cpp | `winget install Git.Git` |

---

## 1. Project setup

Open PowerShell in the project folder:

```powershell
cd C:\path\to\BrainCharge-integrated-code
```

### Python virtual environment (recommended)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install pyaudio requests PyYAML python-dateutil packaging
```

**Required for PC voice testing:** `pyaudio` (enables VAD recording during conversation).

**Optional** (not needed for basic voice testing):

```powershell
pip install vosk      # echo-aware TTS interrupt
pip install pyserial  # Arduino (only if testing serial on PC)
```

> **Note:** `requirements.txt` includes Jetson/CV packages (torch, ultralytics, opencv). You do **not** need the full file for PC voice testing.

---

## 2. Install Whisper.cpp (clone, build, download model)

**Not included when you clone BrainCharge** — each PC must do this once (`whisper.cpp/` is gitignored).

The `whisper.cpp` directory must contain the full repository (with `CMakeLists.txt`). If the folder is empty, remove it and clone again.

```powershell
# From project root
Remove-Item whisper.cpp -Recurse -Force -ErrorAction SilentlyContinue
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp

cmake -B build
cmake --build build --config Release

cd models
.\download-ggml-model.cmd base.en
cd ..\..
```

Verify the build:

```powershell
.\whisper.cpp\build\bin\Release\whisper-cli.exe --help
Test-Path .\whisper.cpp\models\ggml-base.en.bin
```

Both should succeed.

---

## 3. Install Ollama and pull a model

1. Download and install from [https://ollama.ai](https://ollama.ai)
2. **Close and reopen PowerShell** so `ollama` is on your PATH
3. Pull the model:

```powershell
ollama pull gemma3:4b
```

For lower RAM usage:

```powershell
ollama pull gemma3:1b
```

Verify:

```powershell
ollama list
ollama run gemma3:4b "Hello, are you working?"
```

---

## 4. Configure `config.json`

```powershell
Copy-Item config.json.example config.json
```

Recommended settings for PC testing:

```json
{
  "runtime_mode": "pc",

  "whisper_path_windows": "whisper.cpp/build/bin/Release/whisper-cli.exe",
  "whisper_model": "whisper.cpp/models/ggml-base.en.bin",

  "ollama_model": "gemma3:4b",

  "wake_word": "companion",
  "sleep_word": "bye companion",

  "windows_mic_name": "Microphone Array (Realtek(R) Audio)"
}
```

### Runtime mode

| Value | Behavior |
|-------|----------|
| `"pc"` | Force PC testing mode (Arduino + CV off) |
| `"auto"` | Detect hardware: PC on Windows/desktop, Jetson on robot |
| `"jetson"` | Force full robot mode (Arduino + CV on) |

You can also set an environment variable:

```powershell
$env:BRAINCHARGE_RUNTIME = "pc"
python main.py
```

### Microphone name

List DirectShow audio devices:

```powershell
ffmpeg -f dshow -list_devices true -i dummy
```

Copy the exact name from the `(audio)` line into `windows_mic_name`. If the name is wrong or omitted, the app will try to auto-detect the first available microphone.

### Override hardware on PC

By default, PC mode disables Arduino and camera. To enable them explicitly:

```json
{
  "runtime_mode": "pc",
  "connect_arduino": true,
  "serial_port_windows": "COM3",
  "enable_cv": true
}
```

CV also requires `cv_pipeline` dependencies and model weights (see [JETSON_SETUP.md](JETSON_SETUP.md) Part 5.5).

---

## 5. Run

```powershell
python main.py
```

### Expected startup banner

```
============================================================
  BrainCharge Companion Robot — Caregiver Compassion Bot
  Wake word : "companion"
  Sleep word: "bye companion"
  ...
  Runtime   : PC testing (runtime_mode='pc')
  TTS       : Windows SAPI (System.Speech)
  Audio     : dshow device='Microphone Array (Realtek(R) Audio)'
  CV        : Disabled
  Arduino   : Disabled
============================================================

[Sleep] Listening for wake word...
```

### Usage

1. Say **"companion"** — robot wakes and greets you
2. Speak your question — VAD records until you pause (~1.5s silence)
3. Listen to the spoken reply (Whisper → Ollama → Windows TTS)
4. Say **"bye companion"** — ends session, saves summary, returns to sleep
5. Press **Ctrl+C** — exit anytime

---

## 6. CV pipeline on PC (optional)

Use this after the voice pipeline works ([Steps 1–5](#5-run)). Camera tracking uses **YOLO** (person) + **face detection** + **emotion classifier** via PyTorch. On PC it runs on **CPU or NVIDIA GPU** (standard PyTorch)—**do not** install Jetson-specific NVIDIA wheels from [JETSON_SETUP.md](JETSON_SETUP.md).

### What the CV pipeline does

| Component | File | Role |
|-----------|------|------|
| Person tracker | `yolov8n.pt` (project root) | Finds person, drives turn/move signals |
| Face detector | `cv_pipeline/yolov8n-face-lindevs.pt` | Face bounding box |
| Emotion model | `cv_pipeline/emotions_model.pt` | Classifies Angry / Fear / Happy / Neutral / Sad |
| Camera | `cv_pipeline/picture.py` | Windows: DirectShow (`CAP_DSHOW`); Jetson: `/dev/video*` |

When integrated in `main.py`, CV runs in a **background thread** after the wake word. A window **"Companion — Tracking"** shows the feed; press **q** to end the session.

### Step A — Install CV Python packages (PC)

From project root with venv active:

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

For **CPU-only** (no NVIDIA GPU):

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Then install the rest (same packages as Jetson, but from normal PyPI—not Jetson wheels):

```powershell
pip install ultralytics opencv-python-headless numpy pillow scipy matplotlib
pip install pyserial
```

Verify imports:

```powershell
python -c "import torch, cv2; from ultralytics import YOLO; from cv_pipeline import CVPipeline; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('opencv', cv2.__version__); print('CVPipeline OK')"
```

### Step B — Model weight files

Place files exactly here (paths are hardcoded in `cv_pipeline/picture.py` for Jetson compatibility—do not move them):

```
BrainCharge/
├── yolov8n.pt                              ← person detector (auto-downloads on first YOLO use if missing)
└── cv_pipeline/
    ├── yolov8n-face-lindevs.pt             ← face detector (from team / release)
    └── emotions_model.pt                   ← emotion classifier (from team / release)
```

Per [JETSON_SETUP.md](JETSON_SETUP.md) §5.5, pre-fetch the person model:

```powershell
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

If `yolov8n-face-lindevs.pt` or `emotions_model.pt` are missing, get them from your team lead (large binaries, often on Google Drive).

### Step C — Enable CV in `config.json` (no code edits)

Keep `runtime_mode` as `"pc"` and **turn on CV only**:

```json
{
  "runtime_mode": "pc",
  "enable_cv": true,
  "connect_arduino": false
}
```

| Setting | PC recommendation | Why |
|---------|---------------------|-----|
| `runtime_mode` | `"pc"` | Voice + CV without forcing Jetson serial defaults |
| `enable_cv` | `true` | Starts camera thread on wake word |
| `connect_arduino` | `false` | Skip motors unless you have Arduino on COM port |

To test **Arduino + CV** on PC, set `"connect_arduino": true` and `"serial_port_windows": "COM3"` (your port from Device Manager).

### Step D — Run integrated (recommended)

```powershell
python main.py
```

Say **"companion"**. You should see:

```
[CV] Person-tracking running in background.
```

and a tracking window. Arduino lines stay skipped if `connect_arduino` is `false`.

### Step E — Test CV standalone (optional)

Runs only the camera/tracking loop without voice or Ollama:

```powershell
python -m cv_pipeline.picture
```

By default this tries to open Arduino on `SERIAL_PORT` in `picture.py` (macOS-style path). For **PC without Arduino**, either:

- Plug in Arduino and set `SERIAL_PORT` in `picture.py` to your `COM3`, **or**
- Temporarily set `CONNECT_ARDUINO_FLAG = False` at the top of `picture.py` for standalone tests only (integrated `main.py` does not need this).

### Camera tips on Windows

List cameras (FFmpeg also shows video devices):

```powershell
ffmpeg -f dshow -list_devices true -i dummy
```

`picture.py` tries camera index **0**, then **1** and **2** with DirectShow. If the wrong camera opens (e.g. OBS Virtual Camera), close other apps using the camera or adjust indices in `cv_pipeline/picture.py` (Windows block only—Jetson Linux block is separate and unchanged).

### CV troubleshooting on PC

| Issue | Fix |
|-------|-----|
| `[!] cv_pipeline not found` on startup | Install packages in [Step A](#step-a--install-cv-python-packages-pc); fix import errors shown above |
| `FileNotFoundError` for `.pt` files | Place weights per [Step B](#step-b--model-weight-files) |
| `Could not open any webcam` | Permissions, close Zoom/Teams, try another USB port |
| Very slow tracking | Normal on CPU; use GPU PyTorch wheel if you have NVIDIA |
| Accidentally installed Jetson torch | On PC uninstall and reinstall from [pytorch.org](https://pytorch.org) CPU/CUDA wheel—not `JETSON_SETUP.md` §3.2 |
| Want CV off again | Set `"enable_cv": false` or remove the key (PC default is off) |

---

## Troubleshooting

### `CMakeLists.txt` not found / empty `whisper.cpp` folder

The repo does not include whisper.cpp source. Clone, build, and download the model (see [Step 2](#2-install-whispercpp-clone-build-download-model)).

### FFmpeg: Could not find audio device

```powershell
ffmpeg -f dshow -list_devices true -i dummy
```

Update `windows_mic_name` in `config.json` with the exact device name. The app can fall back to the first detected mic if the configured name is missing.

### `[Ollama] Error: [WinError 2] The system cannot find the file specified`

Ollama is not installed or not on PATH.

1. Install from [ollama.ai](https://ollama.ai)
2. Restart PowerShell
3. Run `ollama pull gemma3:4b` (or your `ollama_model` from config)
4. Test with `ollama list`

### Whisper binary or model not found

- Rebuild: `cmake -B build` and `cmake --build build --config Release` inside `whisper.cpp`
- Confirm paths in `config.json` match:
  - `whisper.cpp/build/bin/Release/whisper-cli.exe`
  - `whisper.cpp/models/ggml-base.en.bin`

### `[!] pyaudio not installed`

```powershell
pip install pyaudio
```

If install fails, try a prebuilt wheel or install from [PyAudio wheels](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio).

### No speech from the assistant

TTS uses Windows **System.Speech** via PowerShell. It should work without extra installs. If TTS fails, check that PowerShell is available (`where.exe powershell`).

### `[!] vosk not installed` / `[!] cv_pipeline not found`

These are **warnings**, not blockers. Voice testing works without them.

- **vosk** — optional echo-aware interrupt during TTS
- **cv_pipeline** — optional camera tracking (off in PC mode by default)

### Unicode / transcript errors on Windows

The project reads Whisper output as UTF-8 with error replacement. If issues persist, ensure `config.json` is saved as UTF-8.

---

## Optional: echo-aware interrupt (Vosk)

```powershell
pip install vosk
```

Download the model:

```powershell
# From project root
Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" -OutFile vosk.zip
Expand-Archive vosk.zip -DestinationPath .
Remove-Item vosk.zip
```

Ensure `config.json` has:

```json
"vosk_model_path": "vosk-model-small-en-us-0.15",
"vosk_interrupt_enabled": true
```

---

## PC vs Jetson quick reference

| | **PC testing** | **Jetson robot** |
|--|----------------|------------------|
| Guide | This file | [JETSON_SETUP.md](JETSON_SETUP.md) |
| `runtime_mode` | `"pc"` or `"auto"` | `"auto"` or `"jetson"` |
| Whisper build | CPU (default CMake) | CUDA recommended |
| TTS | Windows SAPI | eSpeak |
| Audio | FFmpeg DirectShow | ALSA (`hw:X,Y`) |
| Arduino / CV | Off by default | On by default |

---

## Minimal checklist

**Voice only**

- [ ] Python 3.10+ with `pyaudio` installed
- [ ] FFmpeg on PATH
- [ ] `whisper.cpp` cloned, built, model downloaded
- [ ] Ollama installed, model pulled, `ollama list` works
- [ ] `config.json` created with `runtime_mode: "pc"` and correct mic name
- [ ] `python main.py` — hear wake word, get LLM reply with speech

**+ CV pipeline**

- [ ] `torch`, `torchvision`, `ultralytics`, `opencv-python-headless` installed (PC PyTorch, not Jetson wheel)
- [ ] `yolov8n.pt`, `cv_pipeline/yolov8n-face-lindevs.pt`, `cv_pipeline/emotions_model.pt` present
- [ ] `config.json`: `"enable_cv": true`, `"connect_arduino": false` (unless testing motors)
- [ ] `python -c "from cv_pipeline import CVPipeline"` succeeds
- [ ] `python main.py` → wake word → tracking window appears

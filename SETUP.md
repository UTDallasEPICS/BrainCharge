# BrainCharge — Setup & Run Guide

A voice-activated companion robot for caregivers. Say a wake word, it recognizes who's talking to it by face, has a natural back-and-forth conversation, reads your mood from your face/voice/words, replies out loud with a locally-run LLM, and remembers how you've been feeling across sessions.

<!-- ![BrainCharge conversation pipeline](braincharge%20robot%20pipeline.png) -->


This guide covers the **`emotional_memory_system`** branch specifically. If you're setting up a different branch, its own README may describe different pieces (e.g. the web app or Jetson-specific branches).

---

## 1. What it does

1. **Sleeps**, listening for the wake word ("companion").
2. On hearing it, **turns the camera on** and checks who's in frame — recognized faces are greeted by name; a new face gets asked for one and enrolled.
3. **Has a conversation**: each turn, it records until you stop talking (voice-activity detection, not a fixed timer), transcribes it, reads your face/voice/word tone, and replies out loud — grounded in what you actually said, not a canned script.
4. Its **on-screen face** changes expression to match the tone of its own reply.
5. On hearing the sleep word ("bye companion"), it **saves a summary of the conversation's emotional tone** to that person's history and goes back to sleep.

---

## 2. Prerequisites

| Requirement | Why | Notes |
|---|---|---|
| **Python 3.10+** | Runs everything | |
| **A webcam** | Face recognition + vision emotion | |
| **A microphone** | Speech input | |
| **[Ollama](https://ollama.ai)** | Runs the LLM locally | Install, then `ollama pull gemma3:4b` **and** `ollama pull gemma3:1b` — both are used (4b for replies, 1b for faster classification tasks) |
| **[eSpeak NG](https://github.com/espeak-ng/espeak-ng)** | Text-to-speech | Windows: `winget install eSpeak-NG.eSpeak-NG`. The Windows installer does **not** add it to PATH — you point `config.json` at the real install path instead (see below) |
| **CMake** | Builds whisper.cpp | Windows: `winget install Kitware.CMake` · macOS: `brew install cmake` · Linux: `sudo apt install cmake` |
| **A C++ toolchain** | Builds whisper.cpp | Windows: Visual Studio Build Tools (MSVC) · macOS: Xcode Command Line Tools · Linux: `build-essential` |
| **PyTorch** | YOLO detection, ONNX runtime deps | Install yourself for your platform: https://pytorch.org/get-started/locally/ (pick CPU or CUDA build) |
| **PyAudio** *(recommended)* | Natural, VAD-based recording | Optional — without it, recording falls back to a fixed-duration ffmpeg capture, which is a noticeably worse conversational experience |
| **FFmpeg** *(optional)* | Only needed as the PyAudio fallback | Windows: `winget install ffmpeg` · macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg` |

---

## 3. Installation

### Clone and set up a virtual environment

```bash
git clone https://github.com/UTDallasEPICS/BrainCharge.git
cd BrainCharge
git checkout emotional_memory_system
python -m venv .venv
```

Activate it — **Windows (PowerShell)**: `.\.venv\Scripts\Activate.ps1` · **macOS/Linux**: `source .venv/bin/activate`

### Install PyTorch, then everything else

```bash
# Follow https://pytorch.org/get-started/locally/ for your platform first, e.g. CPU-only:
pip install torch torchvision

pip install -r requirements.txt
```

### Build whisper.cpp and download the model

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release
cd models
```
Windows (PowerShell): `.\download-ggml-model.cmd base-q5_1`
macOS/Linux: `./download-ggml-model.sh base-q5_1`
```bash
cd ../..
```

### Set up your config

```bash
cp config.json.example config.json
```
Open it and check `espeak_path_windows` matches where eSpeak NG actually installed (default is usually right). Every other path auto-detects by OS.

### Initialize the database

```bash
python -m memory.database
```
This creates `data/braincharge.db` with the `persons`/`sessions` tables. Only needs to run once — it's a fresh, empty per-machine file (gitignored), not something you pull from git.

### First run

```bash
python main.py
```
The facial recognition models (~38MB) auto-download on first use. Say "companion" to start talking to it.

---

## 4. Configuration reference

All settings live in `config.json` (copied from `config.json.example`, itself gitignored since paths are machine-specific). The example file has inline comments for every key; the ones worth knowing about:

| Key | Default | What it does |
|---|---|---|
| `wake_word` / `sleep_word` | `"companion"` / `"bye companion"` | What starts/ends a conversation |
| `emotion_confidence_threshold` | `0.4` | Below this, a vision/voice emotion reading is withheld from the LLM instead of stated as fact |
| `vad_silence_duration` | `1.5` (seconds) | How long you need to pause before it decides you're done talking |
| `vad_silence_threshold_db` | `-40` | How quiet counts as "silence" — raise it (e.g. `-35`) in a noisy room |

---

## 5. Project structure

```
BrainCharge/
├── main.py                      # Wake/sleep word loop, conversation turns, orchestrates everything below
├── ollama_client.py              # Ollama HTTP API wrapper (not the CLI -- see comment in the file for why)
├── identity_backend.py           # Bridges facial_recognition/'s name-based identity to the persons/sessions DB
│
├── facial_recognition/           # Face detection + recognition (YuNet + SFace, OpenCV, no torch needed)
│   ├── known_faces/               #   enrollment photos, one folder per person (gitignored -- personal data)
│   ├── cache/                     #   embedding gallery cache (gitignored)
│   └── models/                    #   ONNX model weights, auto-downloaded (gitignored)
│
├── cv/                           # Person/face detection (YOLO) + facial emotion classification (hsemotion)
├── voice_text_emotion/           # Voice tone (wav2vec2) and spoken-word (Ollama) emotion detection
├── display/                      # robot_face.py -- the animated on-screen face (pygame, its own thread)
├── memory/                       # SQLite-backed per-person conversation/emotion history
│   ├── schema.sql                 #   persons + sessions tables
│   ├── database.py                #   connection + one-time schema init
│   ├── memory_manager.py          #   save_session
│   └── session_summary.py         #   record_session / summarize_session (averages readings per turn)
│
├── whisper.cpp/                  # Speech-to-text (external, gitignored, built locally per machine)
├── config.json.example           # Copy to config.json
├── requirements.txt
└── test_conversation_flow.py     # Layer 2 integration test -- see below
```

Legacy fallback path (kept working, not the primary one tested): `config.py` + `select_audio_device.py` provide fixed-duration ffmpeg-based recording for machines without PyAudio.

---

## 6. Testing without the physical robot

```bash
python test_conversation_flow.py
```

Fakes only the hardware boundary (mic recording, transcription, speaker output are scripted) — everything else runs for real: the actual camera, real face recognition, real emotion models, real Ollama calls, real database. It backs up your actual `persons`/`sessions` data and your facial recognition gallery before running, runs two scripted conversations against a clean slate, then restores everything you had before, no matter how the test ends.

Useful when iterating on prompt/logic changes without needing to physically talk to it each time.

---

## 7. Troubleshooting

| Problem | Try this |
|---|---|
| `Could not open any webcam` | Close other apps using the camera; check Windows camera privacy settings |
| Assistant never speaks | Check `espeak_path_windows` in `config.json` actually points at `espeak-ng.exe` |
| Whisper binary not found | Confirm `cmake --build build --config Release` finished without errors inside `whisper.cpp/` |
| Ollama errors / long pauses | `ollama list` to confirm both `gemma3:4b` and `gemma3:1b` are pulled; a cold model load is genuinely slow the first time |
| Everyone shows up as a new person | Lighting/angle affects face matching more than you'd expect — enroll again, or check `facial_recognition/known_faces/<name>/` has a clear photo |
| `sqlite3.OperationalError: no such table` | Run `python -m memory.database` once to create the schema |
| VAD never stops recording | Room is likely quieter/louder than the `-40` dBFS default — adjust `vad_silence_threshold_db` in `config.json` |

---

## 8. What's gitignored, and why

`config.json` (machine-specific paths), `data/*.db` (personal conversation history), `whisper.cpp/` (built locally, ~large), `facial_recognition/models/*.onnx` (auto-downloaded weights), `facial_recognition/known_faces/*/` and `cache/*` (enrollment photos and embeddings are personal data — don't commit anyone's face), `conversation_context.json`/`conversation_summary.json` (scratch state, cleared every conversation anyway), and the usual `__pycache__/`/`.venv/`/IDE files.

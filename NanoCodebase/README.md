# BrainCharge — PC Testing Guide

Run `main.py` on a Windows (or desktop) PC to test the **voice pipeline** without Jetson hardware. Arduino and camera tracking are disabled by default in PC mode.

For full robot deployment on NVIDIA Jetson Orin Nano, see [JETSON_SETUP.md](docs/old/JETSON_SETUP.md).

---

## What works on PC

| Feature                      | PC testing         | Jetson robot |
|------------------------------|--------------------|--------------|
| Wake word (`companion`)      | Yes                | Yes          |
| Speech-to-text (Whisper.cpp) | Yes                | Yes          |
| Text-to-speech (PiperTTS)    | Yes                | Yes          |
| VAD recording                | Yes (with PyAudio) | Yes          |
| LLM replies (Ollama)         | No                 | No           |
| Arduino motors               | No                 | No           |
| Camera / person tracking     | No                 | No           |

> **Jetson code is unchanged.** PC mode only changes defaults via `runtime_platform.py` and `config.json`. The same `cv_pipeline/` code runs on both; `picture.py` already picks DirectShow on Windows and ALSA/V4L on Jetson.

---

## Prerequisites

Install these before starting:

| Tool        | Purpose                        | Windows install                                                                                          |
|-------------|--------------------------------|----------------------------------------------------------------------------------------------------------|
| **uv**      | Installs python & dependencies | [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) — restart terminal after install |
| **Git CLI** | gh release download            | `winget install --id GitHub.cli`                                                                         |
| **Ollama**  | Installs local LLM             | [ollama.com](https://ollama.ai) — restart terminal after install                                         |

---
# Automated Project setup
```powershell
cd C:\path\to\BrainCharge\NanoCodebase
uv sync
uv run python3 scripts/setup.py
```
Will install whisper.cpp & model, Piper model, LLM from Ollama, and vosk model 

---

# Manual Project setup

Open PowerShell in the project folder and install python version & dependincies:
```powershell
cd C:\path\to\BrainCharge\NanoCodebase
uv sync
```

---

## 2. Install Whisper.cpp (clone, build, download model)

**Not included when you clone BrainCharge** — each PC must do this once (`whisper.cpp/` is gitignored).

The `whisper.cpp` directory must contain the full repository (with `CMakeLists.txt`). If the folder is empty, remove it and clone again.

To use GPU instead of CPU change `whisper-bin-x64.zip` to `whisper-cublas-12.4.0-bin-x64.zip`

```powershell
# From project root
New-Item -ItemType Directory -Force "./whisper.cpp"

gh release download `
    --repo ggml-org/whisper.cpp `
    --pattern "whisper-bin-x64.zip" `
    --dir "./whisper.cpp"

Expand-Archive `
    "./whisper.cpp/whisper-bin-x64.zip" `
    -DestinationPath "./whisper.cpp"
```

Download the model:
```powershell
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin" `
  -OutFile "whisper.cpp/Release/ggml-base.en.bin"
```

Verify the build:

```powershell
.\whisper.cpp\Release\whisper-cli.exe --help
Test-Path .\whisper.cpp\models\ggml-base.en.bin
```

Both should succeed.

---
## 3. Install Piper model
```powershell
  python3 piper.download_voices
```

## 4. Install Ollama and pull a model

1. Download and install from [ollama.com](https://ollama.ai)
2. **Close and reopen PowerShell** so `ollama` is on your PATH
3. Pull the currently specified model:

```powershell
ollama pull gemma3n:e4b
```

Verify:

```powershell
ollama list
ollama run gemma3n:e4b "Hello, are you working?"
```

---
## 5. Install vosk model
Download the model:

```powershell
# From project root
Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" -OutFile vosk.zip
Expand-Archive vosk.zip -DestinationPath .
Remove-Item vosk.zip
```

---

## 5. Run

```powershell
python main.py
```

### Expected startup banner

```
[Orchestrator-Sleep] Listening for wake word...
  -96.5 dBFS  |  waiting...             | 1.1s
```

### Usage

1. Say **"companion"** — robot wakes and greets you
2. Speak your question — VAD records until you pause (~1.5s silence)
3. Listen to the spoken reply (Whisper → Ollama → Windows TTS)
4. Say **"bye companion"** — ends session, returns to sleep
5. Press **Ctrl+C** — exit anytime

---

## Troubleshooting

### `[Ollama] Error: [WinError 2] The system cannot find the file specified`

Ollama is not installed or not on PATH.

1. Install from [ollama.com](https://ollama.ai)
2. Restart PowerShell
3. Run `ollama pull gemma3:4b` (or your `ollama_model` from config)
4. Test with `ollama list`

### `[!] pyaudio/piper-tts/vosk not installed`

```powershell
uv sync
```

If install fails, try a prebuilt wheel or install from [PyAudio wheels](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio).


---


Ensure `config.json` has:

```json
"vosk_model_path": "vosk-model-small-en-us-0.15",
"vosk_interrupt_enabled": true
```

---
## Minimal checklist

**Voice only**

- [ ] Python 3.13 with `pyaudio` installed
- [ ] `whisper.cpp` model & binary downloaded
- [ ] Ollama installed, model pulled, `ollama list` works
- [ ] `python main.py` — hear wake word, get LLM reply with speech
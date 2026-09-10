# BrainCharge — PC Testing Guide

Run `main.py` on a Windows (or desktop) PC to test the **voice pipeline** without Jetson hardware. Arduino and camera tracking are disabled by default in PC mode.

For full robot deployment on NVIDIA Jetson Orin Nano, see [JETSON_SETUP.md](docs/old/JETSON_SETUP.md).

---

## What works on PC

| Feature                      | PC testing | Jetson robot                                        |
|------------------------------|------------|-----------------------------------------------------|
| Wake word (`companion`)      | Yes        | Yes                                                 |
| Speech-to-text (Whisper.cpp) | Yes        | Yes <sub>(CUDA support requires manual build)</sub> |
| Text-to-speech (PiperTTS)    | Yes        | Yes                                                 |
| VAD recording (PyAudio)      | Yes        | Yes                                                 |
| LLM replies (Ollama)         | No         | No                                                  |
| Hardware integration         | No         | No                                                  |
| Camera / person tracking     | No         | No                                                  |

---

## Prerequisites

Install these before starting:

| Tool        | Purpose                        | Windows install                                                         |
|-------------|--------------------------------|-------------------------------------------------------------------------|
| **uv**      | Installs python & dependencies | [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| **Git CLI** | gh release download            | [cli.github](https://cli.github.com)                                    |
| **Ollama**  | Installs local LLM             | [ollama.com](https://ollama.ai)                                         |
<sub> Make sure to restart terminal after install </sub>

---
# Automated Project setup
```powershell
cd C:\path\to\BrainCharge\NanoCodebase
uv sync
uv run python scripts/setup.py
```
Will install LLM from Ollama, whisper.cpp & model, Piper model, , and vosk model.

---

# Manual Project setup
This setup is for <u>**Windows PowerShell**</u>. If your on linux you may need to modify the commands to be compatable.

## 1. Install python & dependencies
Open PowerShell in the project folder and install python version & dependincies utilizing uv.
```bash
cd C:\path\to\BrainCharge\NanoCodebase
uv sync
```

---

## 2. Install Whisper.cpp (model & binary)

**Not included when you clone BrainCharge** — each PC must do this once (`whisper.cpp/` is gitignored).

<sub>`whisper-bin-x64.zip` replacements:<br>
Windows CUDA support - `whisper-cublas-12.4.0-bin-x64.zip`<br>
linux - `whisper-bin-ubuntu-x64.tar.gz`</sub>

```bash
# From project root
mkdir whisper.cpp
gh release download --repo ggml-org/whisper.cpp --pattern "whisper-bin-x64.zip" --dir "./whisper.cpp"
uv run python -m zipfile -e ./whisper.cpp/whisper-bin-x64.zip ./whisper.cpp
```

Download a model:<br>
<sub>(Example gets base model)</sub>
```bash
wget "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" -O "whisper.cpp/ggml-base.bin"
```
---

## 3. Install vosk model
Change directory for the language you want to download. `cd ./languageFiles/[SPESIFIED LANGUAGE]`<br>

Download the model:
<br><sub>Example model for english: `vosk-model-small-en-us-0.15`</sub>

```bash
# From slected language file
wget "https://alphacephei.com/vosk/models/[VOSK MODEL NAME].zip" -O vosk.zip
uv run python -m zipfile -e vosk.zip ./
rm vosk.zip
```

---
## 4. Install Piper model
To show a list of voices run:
```bash
# From slected language file
uv run python -m piper.download_voices
```
To download a voice:
<br><sub>Example model for Spanish: `es_MX-ald-medium`</sub>
```bash
# From slected language file
uv run python -m piper.download_voices [VOICE-NAME]
```

---

## 5. Install Ollama and pull a model

1. Download and install from [ollama.com](https://ollama.ai)
2. **Close and reopen PowerShell** so `ollama` is on your PATH
3. Pull a model specified in project documentation:
<br><sub>(gemma3n:e2b is a safe bet)</sub>

```bash
ollama pull [MODEL NAME]
```

Verify:

```bash
ollama list
ollama run [MODEL NAME] "Hello, are you working?"
```
---
## 

---
## 5. Run

```powershell
uv run python main.py
```

### Expected startup banner

```
[Orchestrator-Sleep] Listening for wake word...
  -96.5 dBFS  |  waiting...             | 1.1s
```

### Usage

1. Say **"companion"** — robot wakes and greets you
2. Speak your question — VAD records until you pause (1~2s silence)
3. Say **"bye companion"** — ends session, returns to sleep
4. Press **Ctrl+C** — exit anytime

---

## Troubleshooting

### `[Ollama] Error: [WinError 2] The system cannot find the file specified`

Ollama is not installed or not on PATH.

1. Install from [ollama.com](https://ollama.ai)
2. Restart PowerShell
3. Run `ollama pull gemma3n:e4b` (or your specified ollama model)
4. Test with `ollama list`

### `[!] pyaudio/piper-tts/vosk not installed`

```powershell
uv sync
```

---
## Minimal checklist

**Voice only**

- [ ] Python 3.13 with `pyaudio` installed
- [ ] `whisper.cpp` model & binary downloaded
- [ ] `vosk` model & binary downloaded
- [ ] Ollama installed, model pulled, `ollama list` works
- [ ] `uv run python main.py` — hear wake word, get LLM reply with speech
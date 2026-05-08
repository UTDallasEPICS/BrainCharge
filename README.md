# BrainCharge

Voice-enabled companion robot with conversation memory, facial recognition, and emotion detection.


## Setup

### Prerequisites

1. **Python 3.10+** 
2. **FFmpeg** - for audio recording
   - Windows: `winget install ffmpeg` or download from https://ffmpeg.org
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. **CMake** - for building Whisper.cpp
   - Windows: `winget install Kitware.CMake`
   - macOS: `brew install cmake`
   - Linux: `sudo apt install cmake`
4. **Ollama** - for LLM inference
   - Download from https://ollama.ai
   - Install and run: `ollama pull gemma3:4b`

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/UTDallasEPICS/BrainCharge.git
   cd BrainCharge
   ```

2. **Clone and build Whisper.cpp**
   ```bash
   git clone https://github.com/ggerganov/whisper.cpp.git
   cd whisper.cpp
   ```
   
   - **Windows (PowerShell)**:
     ```powershell
     cmake -B build
     cmake --build build --config Release
     ```
   
   - **macOS/Linux**:
     ```bash
     cmake -B build
     cmake --build build --config Release
     ```

3. **Download Whisper model**
   
   - **Windows (PowerShell)**:
     ```powershell
     cd models
     .\download-ggml-model.cmd base.en
     cd ..\..
     ```
   
   - **macOS/Linux**:
     ```bash
     cd models
     ./download-ggml-model.sh base.en
     cd ../..
     ```

4. **Create your config.json file**
   ```bash
   cp config.json.example config.json
   ```
   The paths auto-detect based on your OS, so no manual changes needed unless you have a custom setup.

5. **Optional: Configure audio device for advanced control**
   ```bash
   python select_audio_device.py
   ```
   This creates a `.env` file with your chosen microphone (works alongside config.json).

### Configuration

The project uses **config.json** for main settings (auto-detects OS-specific paths) and optionally **.env** for audio device overrides.

**config.json** (copy from config.json.example):
```json
{
  "whisper_path_windows": "whisper.cpp/build/bin/Release/whisper-cli.exe",
  "whisper_path_mac": "whisper.cpp/build/bin/whisper-cli",
  "whisper_path_linux": "whisper.cpp/build/bin/whisper-cli",
  "whisper_model": "whisper.cpp/models/ggml-base.en.bin",
  
  "wake_word": "companion",
  "sleep_word": "bye companion",
  "listen_duration": 3,
  "conversation_duration": 5
}
```

**Optional .env** for audio device customization:
```bash
# Example .env for Windows with custom device
FFMPEG_FORMAT=dshow
FFMPEG_DEVICE=audio=Microphone Array (Intel® Smart Sound Technology for Digital Microphones)
OLLAMA_MODEL=gemma3:4b
```

## Usage

### Basic Run

```bash
python main.py
```

The program will:
1. Record 5 seconds of audio from your microphone
2. Transcribe with Whisper.cpp
3. Generate a response with Ollama
4. Print the response (TTS coming soon)

### Custom Recording Duration

```bash
# PowerShell (Windows)
$env:RECORD_SECONDS=10
python main.py

# Bash (macOS/Linux)
export RECORD_SECONDS=10
python main.py
```

### List Available Audio Devices

- **Windows**:
  ```powershell
  ffmpeg -f dshow -list_devices true -i dummy
  ```

- **macOS**:
  ```bash
  ffmpeg -f avfoundation -list_devices true -i ""
  ```

- **Linux**:
  ```bash
  arecord -l
  ```

## Project Structure

```
BrainCharge/
├── main.py                    # Main voice pipeline
├── config.py                  # Cross-platform configuration
├── select_audio_device.py     # Audio device picker utility
├── .env                       # Local settings (gitignored)
├── .gitignore
├── README.md
└── whisper.cpp/               # External dependency (gitignored)
```

## Team Collaboration

- **Audio device config**: Each teammate runs `python select_audio_device.py` once to configure their mic
- **.env file**: Local overrides are gitignored; never commit `.env`
- **Whisper.cpp**: Not committed; each person clones and builds locally
- **Model files**: Kept in `whisper.cpp/models/` (gitignored); download via provided scripts

## Troubleshooting

### FFmpeg can't find audio device
- Run `python select_audio_device.py` to pick the correct device
- Or manually set via environment:
  ```powershell
  $env:FFMPEG_FORMAT='dshow'
  $env:FFMPEG_DEVICE='audio=Your Microphone Name'
  ```

### Whisper binary not found
- Ensure you built whisper.cpp: `cmake -B build && cmake --build build --config Release`
- Check the path in your `.env` or let config.py auto-detect

### Ollama model errors
- Verify Ollama is running: `ollama list`
- Pull the model: `ollama pull gemma3:4b`

### Unicode decode errors (Windows)
- Fixed in current version (UTF-8 encoding with error replacement)


# Goodluck!!! :)

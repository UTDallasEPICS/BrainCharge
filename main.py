# main.py
#
# Companion Robot — Fully Integrated Entry Point
# Jetson Orin Nano edition
#
# Architecture:
#   The VOICEBOT is the primary system. Hardware (Arduino + CV tracking)
#   activates ONLY after the wake word is detected.
#
# Flow:
#   [SLEEP MODE]
#     → Record short audio clip (fixed-duration, no VAD)
#     → Whisper transcription
#     → Check for wake word ("companion")
#
#   [WAKE WORD DETECTED]
#     → Open Arduino serial connection
#     → Start CV person-tracking in a background thread (non-blocking)
#     → Enter conversation loop (VAD recording → Whisper → Ollama → TTS)
#     → Hardware runs continuously in background while conversation is active
#
#   [SLEEP WORD DETECTED inside conversation]
#     → Generate conversation summary (people, appointments, topics)
#     → Signal CV thread to stop
#     → Send stop command to Arduino and close serial port
#     → Return to sleep mode
#
#   [Ctrl-C anywhere]
#     → Graceful shutdown: stop CV, stop motors, close serial, TTS farewell, exit

import subprocess
import json
import json as _json
import os
import re
import shutil
import tempfile
import time
import platform
import wave
import struct
import math
import threading
import uuid
from datetime import datetime, date

from runtime_platform import describe_runtime, get_runtime_profile

# ---------------------------------------------------------------------------
# Optional heavy deps — degrade gracefully if missing
# ---------------------------------------------------------------------------

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("[!] pyaudio not installed — VAD recording and echo-interrupt disabled.")
    print("    Install: sudo apt install portaudio19-dev && pip install pyaudio")

try:
    from vosk import Model as VoskModel, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("[!] vosk not installed — echo-aware TTS interrupt disabled.")
    print("    Install: pip install vosk  (then download a model)")

try:
    import serial as pyserial
    from serial import SerialException
    PYSERIAL_AVAILABLE = True
except ImportError:
    PYSERIAL_AVAILABLE = False
    print("[!] pyserial not installed — Arduino control disabled.")
    print("    Install: pip install pyserial")

try:
    from cv_pipeline.picture import CVPipeline
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False
    print("[!] cv_pipeline not found — camera tracking disabled.")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = "config.json"
if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(
        f"Config file not found: {CONFIG_PATH}\n"
        "Create one based on the project README or JETSON_SETUP.md."
    )

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

runtime = get_runtime_profile(config)
RUNTIME_MODE = runtime["runtime_mode"]
IS_JETSON = runtime["is_jetson"]
IS_PC = runtime["is_pc"]

system = platform.system()

# --- Whisper paths ---
if system == "Windows":
    WHISPER_PATH = config.get("whisper_path_windows", config.get("whisper_path", "whisper.cpp/build/bin/Release/whisper-cli.exe"))
elif system == "Darwin":
    WHISPER_PATH = config.get("whisper_path_mac", config.get("whisper_path", "whisper.cpp/build/bin/whisper-cli"))
else:
    WHISPER_PATH = config.get("whisper_path_linux", config.get("whisper_path", "whisper.cpp/build/bin/whisper-cli"))

WHISPER_MODEL         = config["whisper_model"]
TEMP_AUDIO            = config["temp_audio"]
TEMP_TRANSCRIPT       = config["temp_transcript"]
CONTEXT_FILE          = config.get("context_file", "conversation_context.json")
SUMMARY_FILE          = config.get("summary_file", "conversation_summary.json")
APPOINTMENTS_FILE     = config.get("appointments_file", "appointments.json")

WAKE_WORD             = config.get("wake_word", "companion").lower()
SLEEP_WORD            = config.get("sleep_word", "bye companion").lower()
LANGUAGE              = config.get("language", "en").lower()
OLLAMA_MODEL          = config.get("ollama_model", "gemma3:4b")

WAKE_WORD_LISTEN_DURATION = config.get("wake_word_listen_duration", 3)
CONVERSATION_DURATION     = config.get("conversation_duration", 5)

# VAD
VAD_SILENCE_THRESHOLD_DB = config.get("vad_silence_threshold_db", -40)
VAD_SILENCE_DURATION     = config.get("vad_silence_duration", 1.5)
VAD_MIN_RECORDING        = config.get("vad_min_recording", 0.5)
VAD_MAX_RECORDING        = config.get("vad_max_recording", 30)
VAD_SAMPLE_RATE          = config.get("vad_sample_rate", 16000)
VAD_CHUNK_SIZE           = config.get("vad_chunk_size", 1024)

# TTS
MACOS_TTS_VOICE    = config.get("macos_tts_voice", "Samantha")
MACOS_TTS_VOICE_ES = config.get("macos_tts_voice_es", "Monica")
ESPEAK_VOICE_EN    = config.get("espeak_voice_en", "en")
ESPEAK_VOICE_ES    = config.get("espeak_voice_es", "es")

# Vosk
VOSK_MODEL_PATH        = config.get("vosk_model_path", "vosk-model-small-en-us-0.15")
VOSK_INTERRUPT_ENABLED = config.get("vosk_interrupt_enabled", True)
VOSK_MIN_WORDS         = config.get("vosk_min_words", 3)
VOSK_WARMUP_SECS       = config.get("vosk_warmup_secs", 0.4)

# Hardware — defaults: enabled on Jetson, disabled on PC (override in config.json)
CONNECT_ARDUINO = runtime["connect_arduino"]
ENABLE_CV = runtime["enable_cv"]
if system == "Windows":
    SERIAL_PORT = config.get("serial_port_windows", config.get("serial_port", "COM3"))
else:
    # For Jetson: config.json serial_port_linux wins; fallback auto-detects
    _cfg_port = config.get("serial_port_linux", config.get("serial_port", ""))
    if _cfg_port:
        SERIAL_PORT = _cfg_port
    elif os.path.exists("/dev/ttyACM0"):
        SERIAL_PORT = "/dev/ttyACM0"
    elif os.path.exists("/dev/ttyUSB0"):
        SERIAL_PORT = "/dev/ttyUSB0"
    else:
        SERIAL_PORT = "/dev/ttyACM0"

BAUD_RATE      = config.get("baud_rate", 115200)
SERIAL_TIMEOUT = config.get("serial_timeout", 2)

# Linux/Jetson audio settings
LINUX_AUDIO_DEVICE  = config.get("linux_audio_device", "default")
LINUX_AUDIO_BACKEND = config.get("linux_audio_backend", "alsa")  # "alsa" or "pulse"

_WINDOWS_MIC_CACHE: str | None = None

DATE_FORMATS = (
    "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
    "%m/%d/%Y", "%B %d %Y", "%b %d %Y",
)

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def phrase(en: str, es: str) -> str:
    return es if LANGUAGE == "es" else en


def get_current_datetime_str() -> str:
    now = datetime.now()
    return now.strftime("%A, %B %-d, %Y at %-I:%M %p")


def parse_date(date_str: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def days_label(appt_date: date) -> str:
    today = datetime.now().date()
    delta = (appt_date - today).days
    if delta == 0:
        return " (TODAY)"
    elif delta == 1:
        return " (TOMORROW — 1 day away)"
    elif delta > 1:
        return f" ({delta} days from today)"
    else:
        return f" ({abs(delta)} days ago)"


def calculate_rms_db(audio_chunk) -> float:
    count = len(audio_chunk) // 2
    if count == 0:
        return -100.0
    shorts = struct.unpack(f"{count}h", audio_chunk)
    rms = math.sqrt(sum(s * s for s in shorts) / count)
    if rms == 0:
        return -100.0
    return 20 * math.log10(rms / 32768.0)


def _active_macos_voice() -> str:
    return MACOS_TTS_VOICE_ES if LANGUAGE == "es" else MACOS_TTS_VOICE


def _active_espeak_voice() -> str:
    return ESPEAK_VOICE_ES if LANGUAGE == "es" else ESPEAK_VOICE_EN


def _macos_say_available() -> bool:
    return system == "Darwin" and shutil.which("say") is not None


def _espeak_available() -> bool:
    return shutil.which("espeak") is not None


def _windows_sapi_available() -> bool:
    return system == "Windows" and shutil.which("powershell") is not None


def _piper_available() -> bool:
    """Check if piper TTS binary is installed."""
    return shutil.which("piper") is not None

# ---------------------------------------------------------------------------
# AppointmentManager
# ---------------------------------------------------------------------------

class AppointmentManager:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.appointments: list = []
        self._load()
        self._auto_expire()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                self.appointments = data if isinstance(data, list) else []
            except Exception:
                self.appointments = []
        else:
            self.appointments = []

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.appointments, f, indent=2)

    def _auto_expire(self):
        today = datetime.now().date()
        changed = False
        for appt in self.appointments:
            if appt.get("status") != "upcoming":
                continue
            appt_date = parse_date(appt.get("date", ""))
            if appt_date and appt_date < today:
                appt["status"] = "completed"
                appt["updated"] = datetime.now().isoformat()
                changed = True
        if changed:
            self._save()

    def _normalise_date(self, date_str: str) -> str:
        parsed = parse_date(date_str)
        return parsed.strftime("%Y-%m-%d") if parsed else date_str

    def _find_duplicate(self, date_str: str, event: str):
        norm_date = self._normalise_date(date_str)
        event_lower = event.strip().lower()
        for appt in self.appointments:
            if appt.get("date") != norm_date:
                continue
            existing = appt.get("event", "").strip().lower()
            if event_lower in existing or existing in event_lower:
                return appt
        return None

    def add(self, date_str: str, event: str, time_str: str = "",
            location: str = "", notes: str = "") -> dict:
        dup = self._find_duplicate(date_str, event)
        if dup:
            raise ValueError(f"Duplicate appointment on {date_str}: '{dup['event']}' already exists.")
        record = {
            "id":       str(uuid.uuid4()),
            "date":     self._normalise_date(date_str),
            "time":     time_str,
            "event":    event,
            "location": location,
            "notes":    notes,
            "status":   "upcoming",
            "created":  datetime.now().isoformat(),
            "updated":  datetime.now().isoformat(),
        }
        self.appointments.append(record)
        self._save()
        return record

    def merge_from_summary(self, raw_appointments: list) -> tuple:
        added = skipped = 0
        for raw in raw_appointments:
            date_str = raw.get("date", "").strip()
            event    = raw.get("event", "").strip()
            if not date_str or not event:
                skipped += 1
                continue
            try:
                self.add(date_str=date_str, event=event,
                         time_str=raw.get("time", ""),
                         location=raw.get("location", ""),
                         notes=raw.get("notes", ""))
                added += 1
            except ValueError:
                skipped += 1
        return added, skipped

    def upcoming(self) -> list:
        self._auto_expire()
        result = [a for a in self.appointments if a.get("status") == "upcoming"]
        result.sort(key=lambda a: a.get("date", ""))
        return result

    def summary_stats(self) -> dict:
        self._auto_expire()
        return {
            "upcoming":  sum(1 for a in self.appointments if a["status"] == "upcoming"),
            "completed": sum(1 for a in self.appointments if a["status"] == "completed"),
            "cancelled": sum(1 for a in self.appointments if a["status"] == "cancelled"),
            "total":     len(self.appointments),
        }

    def context_block(self) -> str:
        upcoming = self.upcoming()
        if not upcoming:
            return ""
        lines = ["Upcoming appointments:"]
        for appt in upcoming:
            appt_date = parse_date(appt.get("date", ""))
            label = days_label(appt_date) if appt_date else ""
            line = f"- {appt.get('date', '')}{label}"
            if appt.get("time"):
                line += f" at {appt['time']}"
            line += f": {appt.get('event', '')}"
            if appt.get("location"):
                line += f" @ {appt['location']}"
            if appt.get("notes"):
                line += f" ({appt['notes']})"
            lines.append(line)
        return "\n".join(lines) + "\n"

# ---------------------------------------------------------------------------
# ConversationContext
# ---------------------------------------------------------------------------

class ConversationContext:
    def __init__(self, context_file: str, summary_file: str,
                 appointment_manager: AppointmentManager):
        self.context_file = context_file
        self.summary_file = summary_file
        self.appt_mgr     = appointment_manager
        self.history      = self._load_json(context_file, default=[])
        self.summary      = self._load_json(summary_file, default={})

    @staticmethod
    def _load_json(path: str, default):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    def _save_context(self):
        with open(self.context_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def _save_summary(self):
        with open(self.summary_file, "w") as f:
            json.dump(self.summary, f, indent=2)

    def add_exchange(self, user_input: str, assistant_response: str) -> None:
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "user":      user_input,
            "assistant": assistant_response,
        })
        self._save_context()

    def generate_summary(self) -> None:
        if not self.history:
            return

        conversation_text = "Conversation history:\n\n"
        for exchange in self.history:
            conversation_text += (
                f"[{exchange['timestamp']}]\n"
                f"User: {exchange['user']}\n"
                f"Assistant: {exchange['assistant']}\n\n"
            )

        summary_prompt = (
            "You are analyzing a conversation between a caregiver and an AI companion bot. "
            "Extract and summarize the following information in JSON format:\n"
            "1. Important people mentioned (names, relationships)\n"
            "2. Upcoming appointments or scheduled events — include date in YYYY-MM-DD format\n"
            "3. Key concerns or topics discussed\n"
            "4. Emotional state patterns (stress levels, concerns)\n"
            "5. Action items or follow-ups needed\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            "{\n"
            '  "people": [{"name": "...", "relationship": "...", "context": "..."}],\n'
            '  "appointments": [{"date": "YYYY-MM-DD", "time": "...", "event": "...", '
            '"location": "...", "notes": "..."}],\n'
            '  "topics": ["topic1", "topic2"],\n'
            '  "emotional_patterns": "brief description",\n'
            '  "action_items": ["item1", "item2"],\n'
            '  "summary": "brief overall summary"\n'
            "}\n\n"
            f"Conversation to analyze:\n{conversation_text}"
        )

        try:
            result = subprocess.run(
                ["ollama", "run", OLLAMA_MODEL, summary_prompt],
                capture_output=True, text=True, timeout=60
            )
            summary_text = result.stdout.strip()
            if "```json" in summary_text:
                summary_text = summary_text.split("```json")[1].split("```")[0].strip()
            elif "```" in summary_text:
                summary_text = summary_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(summary_text)
            raw_appointments = parsed.pop("appointments", [])
            added, skipped = self.appt_mgr.merge_from_summary(raw_appointments)
            stats = self.appt_mgr.summary_stats()

            self.summary = parsed
            self.summary["last_updated"] = datetime.now().isoformat()
            self._save_summary()

            print(f"[Summary] Generated — "
                  f"{len(self.summary.get('people', []))} people, "
                  f"{len(self.summary.get('topics', []))} topics, "
                  f"{added} appointments added ({skipped} already existed), "
                  f"{stats['upcoming']} upcoming total.")

        except subprocess.TimeoutExpired:
            print("[Summary] Timed out.")
        except json.JSONDecodeError as e:
            print(f"[Summary] JSON parse error: {e}")
        except Exception as e:
            print(f"[Summary] Error: {e}")

    def get_context_prompt(self) -> str:
        parts = []
        if self.summary:
            parts.append("=== Conversation Summary ===")
            if "summary" in self.summary:
                parts.append(f"Overall: {self.summary['summary']}\n")
            if self.summary.get("people"):
                parts.append("People mentioned:")
                for p in self.summary["people"]:
                    line = f"- {p.get('name', 'Unknown')}"
                    if p.get("relationship"):
                        line += f" ({p['relationship']})"
                    if p.get("context"):
                        line += f": {p['context']}"
                    parts.append(line)
                parts.append("")
            appt_block = self.appt_mgr.context_block()
            if appt_block:
                parts.append(appt_block)
            if self.summary.get("topics"):
                parts.append(f"Key topics: {', '.join(self.summary['topics'])}\n")
            if "emotional_patterns" in self.summary:
                parts.append(f"Emotional context: {self.summary['emotional_patterns']}\n")
            if self.summary.get("action_items"):
                parts.append("Action items:")
                for item in self.summary["action_items"]:
                    parts.append(f"- {item}")
                parts.append("")
        if self.history:
            parts.append("=== Recent conversation ===")
            for exchange in self.history[-5:]:
                parts.append(f"User: {exchange['user']}")
                parts.append(f"Assistant: {exchange['assistant']}")
        return "\n".join(parts)

    def clear(self) -> None:
        self.history = []
        self.summary = {}
        self._save_context()
        self._save_summary()

# ---------------------------------------------------------------------------
# Audio recording  (Jetson/Linux-aware)
# ---------------------------------------------------------------------------

def _list_windows_dshow_audio_devices() -> list[str]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "dshow", "-list_devices", "true", "-i", "dummy"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        output = f"{result.stderr}\n{result.stdout}"
        devices: list[str] = []
        for line in output.splitlines():
            if "(audio)" not in line or '"' not in line:
                continue
            start = line.index('"') + 1
            end = line.index('"', start)
            name = line[start:end].strip()
            if name:
                devices.append(name)
        return devices
    except Exception:
        return []


def _resolve_windows_mic_name() -> str:
    global _WINDOWS_MIC_CACHE
    if _WINDOWS_MIC_CACHE is not None:
        return _WINDOWS_MIC_CACHE

    configured = config.get("windows_mic_name", "").strip()
    available = _list_windows_dshow_audio_devices()

    if configured and (not available or configured in available):
        _WINDOWS_MIC_CACHE = configured
        return configured

    if configured and available:
        print(f"[Audio] Configured mic not found: {configured!r}")
        print("[Audio] Available microphones:")
        for device in available:
            print(f"  - {device}")
        print(f"[Audio] Using: {available[0]!r}")
        _WINDOWS_MIC_CACHE = available[0]
        return available[0]

    if available:
        _WINDOWS_MIC_CACHE = available[0]
        return available[0]

    _WINDOWS_MIC_CACHE = configured or "Microphone (Realtek Audio)"
    return _WINDOWS_MIC_CACHE


def _detect_linux_audio_backend() -> tuple:
    """
    Returns (backend, device) for ffmpeg on this Linux/Jetson system.
    Prefers the config.json setting; auto-detects otherwise.
    """
    # Config override wins
    if LINUX_AUDIO_BACKEND == "pulse" and (
        os.path.exists("/usr/bin/pulseaudio") or os.path.exists("/usr/bin/pactl")
    ):
        return "pulse", LINUX_AUDIO_DEVICE

    # ALSA fallback (always present on Jetson)
    return "alsa", LINUX_AUDIO_DEVICE


def get_audio_input_command(duration: int, output_file: str) -> list:
    if system == "Darwin":
        return ["ffmpeg", "-f", "avfoundation", "-i", ":1",
                "-t", str(duration), "-ar", "16000", "-ac", "1",
                output_file, "-y", "-loglevel", "error"]
    elif system == "Windows":
        mic_name = _resolve_windows_mic_name()
        return ["ffmpeg", "-f", "dshow", "-i", f"audio={mic_name}",
                "-t", str(duration), "-ar", "16000", "-ac", "1",
                output_file, "-y", "-loglevel", "error"]
    else:
        # Linux / Jetson Orin Nano
        backend, device = _detect_linux_audio_backend()
        if backend == "pulse":
            return ["ffmpeg", "-f", "pulse", "-i", device,
                    "-t", str(duration), "-ar", "16000", "-ac", "1",
                    output_file, "-y", "-loglevel", "error"]
        else:
            # ALSA — device name like "default", "hw:2,0", "plughw:2,0"
            return ["ffmpeg", "-f", "alsa", "-i", device,
                    "-t", str(duration), "-ar", "16000", "-ac", "1",
                    output_file, "-y", "-loglevel", "error"]


def record_audio_vad(output_file: str) -> bool:
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16, channels=1, rate=VAD_SAMPLE_RATE,
            input=True, frames_per_buffer=VAD_CHUNK_SIZE
        )

        frames = []
        silence_start = None
        recording_start = time.time()
        speech_detected = False

        while True:
            elapsed = time.time() - recording_start
            if elapsed >= VAD_MAX_RECORDING:
                print()
                break
            try:
                chunk = stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                break

            frames.append(chunk)
            db = calculate_rms_db(chunk)
            is_speech = db > VAD_SILENCE_THRESHOLD_DB

            if is_speech:
                speech_detected = True
                silence_start = None
                status = "SPEECH"
            else:
                if elapsed >= VAD_MIN_RECORDING and speech_detected:
                    if silence_start is None:
                        silence_start = time.time()
                    sil_elapsed = time.time() - silence_start
                    status = f"silence {sil_elapsed:.1f}/{VAD_SILENCE_DURATION:.1f}s"
                else:
                    status = "waiting..."

            print(f"\r  {db:6.1f} dBFS  |  {status:<22} | {elapsed:.1f}s", end="", flush=True)

            if not is_speech and elapsed >= VAD_MIN_RECORDING and speech_detected:
                if silence_start and time.time() - silence_start >= VAD_SILENCE_DURATION:
                    print()
                    break

        stream.stop_stream()
        stream.close()
        pa.terminate()

        if not frames:
            return False

        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(VAD_SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        total = len(frames) * VAD_CHUNK_SIZE / VAD_SAMPLE_RATE
        print(f"  [VAD] Recorded {total:.1f}s")
        return True

    except Exception as e:
        print(f"[VAD] Error: {e}")
        return False


def record_audio(duration: int, output_file: str, use_vad: bool = False) -> bool:
    if use_vad and PYAUDIO_AVAILABLE:
        return record_audio_vad(output_file)
    try:
        cmd = get_audio_input_command(duration, output_file)
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        print(f"[Audio] FFmpeg error: {stderr}")
        return False
    except Exception as e:
        print(f"[Audio] Error: {e}")
        return False

# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe_audio(audio_file: str) -> str:
    try:
        subprocess.run([
            WHISPER_PATH,
            "-m", WHISPER_MODEL,
            "-f", audio_file,
            "-of", TEMP_TRANSCRIPT,
            "-otxt",
            "-l", "en",
        ], check=True, capture_output=True)

        transcript_file = TEMP_TRANSCRIPT + ".txt"
        if os.path.exists(transcript_file):
            with open(transcript_file, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        return ""
    except subprocess.CalledProcessError as e:
        print(f"[Whisper] Error: {e}")
        return ""

# ---------------------------------------------------------------------------
# LLM response generation
# ---------------------------------------------------------------------------

def generate_response(user_input: str, context: ConversationContext) -> str:
    if LANGUAGE == "es":
        system_prompt = (
            "IMPORTANT: You must respond ONLY in Spanish. Every word must be in Spanish.\n"
            "Eres el Bot de Compasión para Cuidadores, un compañero robótico gentil y empático "
            "diseñado por BrainCharge para apoyar a los cuidadores familiares. "
            "Mantén respuestas conversacionales, breves y naturales. "
            "Menos de 3 oraciones por respuesta.\n\n"
        )
    else:
        system_prompt = (
            "You are the Caregiver Compassion Bot, a gentle, empathetic robotic companion "
            "designed by BrainCharge to support family caregivers who face high stress and emotional fatigue. "
            "Keep your replies conversational, brief, and naturally worded so they sound good when spoken aloud. "
            "Avoid technical or robotic phrasing. "
            "If the user seems stressed, respond with compassion and offer small words of comfort. "
            "Keep responses under 3 sentences for natural conversation flow. "
            "Use the conversation context below to provide personalized, relevant responses.\n\n"
        )

    full_prompt = system_prompt + context.get_context_prompt() + f"\n\nUser: {user_input}\n\nAssistant:"

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL, full_prompt],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return phrase("I apologize, I'm having trouble responding right now.",
                      "Lo siento, tengo problemas para responder ahora mismo.")
    except Exception as e:
        print(f"[Ollama] Error: {e}")
        return phrase("I'm sorry, I encountered an error.",
                      "Lo siento, encontré un error.")

# ---------------------------------------------------------------------------
# Text-to-speech  (Windows SAPI; espeak on Jetson; 'say' on macOS)
# ---------------------------------------------------------------------------

def _start_tts(sentence: str):
    try:
        if _macos_say_available():
            return subprocess.Popen(
                ["say", "-v", _active_macos_voice(), sentence],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif _espeak_available():
            # espeak works well on Jetson; -s 145 slows the default rate slightly
            return subprocess.Popen(
                ["espeak", "-v", _active_espeak_voice(), "-s", "145", sentence],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif _windows_sapi_available():
            text_file = os.path.join(
                tempfile.gettempdir(), f"braincharge_tts_{uuid.uuid4().hex}.txt"
            )
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(sentence)
            ps_script = (
                "Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = 0; "
                f"$s.Speak([IO.File]::ReadAllText('{text_file}')); "
                f"Remove-Item -Force '{text_file}'"
            )
            return subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            print(f"[TTS] No TTS engine found. Text: {sentence}")
            return None
    except Exception as e:
        print(f"[TTS] Start error: {e}")
        return None


def _mic_content_matches_expected(heard_text: str, expected_text: str) -> bool:
    if not heard_text.strip():
        return True
    heard_words    = set(heard_text.lower().split())
    expected_words = set(expected_text.lower().split())
    matches = heard_words & expected_words
    overlap = len(matches) / len(heard_words)
    print(f"  [echo-check] heard={heard_text!r:.60}  overlap={overlap:.2f}", flush=True)
    return overlap >= 0.4


def _vosk_echo_monitor(tts_proc, expected_sentence: str, interrupt_event: threading.Event):
    try:
        model = VoskModel(VOSK_MODEL_PATH)
        recognizer = KaldiRecognizer(model, VAD_SAMPLE_RATE)
        recognizer.SetWords(False)

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16, channels=1, rate=VAD_SAMPLE_RATE,
            input=True, frames_per_buffer=VAD_CHUNK_SIZE
        )

        warmup_chunks = int(VAD_SAMPLE_RATE * VOSK_WARMUP_SECS / VAD_CHUNK_SIZE)
        for _ in range(warmup_chunks):
            if tts_proc.poll() is not None:
                break
            try:
                stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                break

        while tts_proc.poll() is None and not interrupt_event.is_set():
            try:
                chunk = stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                break

            if recognizer.AcceptWaveform(chunk):
                heard = _json.loads(recognizer.Result()).get("text", "").strip()
            else:
                heard = _json.loads(recognizer.PartialResult()).get("partial", "").strip()

            if len(heard.split()) < VOSK_MIN_WORDS:
                continue

            if not _mic_content_matches_expected(heard, expected_sentence):
                print("  [echo-check] Content diverged — interrupting TTS.")
                tts_proc.terminate()
                interrupt_event.set()
                break

    except Exception as e:
        print(f"[Vosk] Monitor error: {e}")
    finally:
        try:
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception:
            pass


def _speak_response_volume_based(text: str) -> bool:
    tts_proc = _start_tts(text)
    if tts_proc is None:
        return False

    interrupted = False
    stop_flag = threading.Event()

    def mic_monitor():
        nonlocal interrupted
        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16, channels=1, rate=VAD_SAMPLE_RATE,
                input=True, frames_per_buffer=VAD_CHUNK_SIZE
            )
            warmup = int(VAD_SAMPLE_RATE * 0.3 / VAD_CHUNK_SIZE)
            for _ in range(warmup):
                if stop_flag.is_set():
                    break
                try:
                    stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
                except Exception:
                    break

            consecutive = 0
            while not stop_flag.is_set():
                try:
                    chunk = stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
                except Exception:
                    break
                db = calculate_rms_db(chunk)
                if db > VAD_SILENCE_THRESHOLD_DB:
                    consecutive += 1
                    if consecutive >= 3:
                        interrupted = True
                        tts_proc.terminate()
                        break
                else:
                    consecutive = 0

            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception as e:
            print(f"[TTS] Mic monitor error: {e}")

    monitor_thread = threading.Thread(target=mic_monitor, daemon=True)
    monitor_thread.start()
    tts_proc.wait()
    stop_flag.set()
    monitor_thread.join(timeout=1.0)

    if interrupted:
        print("  [TTS] Interrupted (volume-based).")
    return interrupted


def speak_response(text: str) -> bool:
    if not VOSK_INTERRUPT_ENABLED:
        proc = _start_tts(text)
        if proc:
            proc.wait()
        return False

    if not PYAUDIO_AVAILABLE:
        proc = _start_tts(text)
        if proc:
            proc.wait()
        return False

    use_echo_aware = VOSK_AVAILABLE and os.path.exists(VOSK_MODEL_PATH)

    if not use_echo_aware:
        if VOSK_AVAILABLE and not os.path.exists(VOSK_MODEL_PATH):
            print(f"  [echo-check] Vosk model not found at '{VOSK_MODEL_PATH}'. "
                  "Falling back to volume-based interrupt.")
        return _speak_response_volume_based(text)

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    interrupt_event = threading.Event()

    for sentence in sentences:
        if interrupt_event.is_set():
            break
        tts_proc = _start_tts(sentence)
        if tts_proc is None:
            continue

        monitor_thread = threading.Thread(
            target=_vosk_echo_monitor,
            args=(tts_proc, sentence, interrupt_event),
            daemon=True
        )
        monitor_thread.start()
        tts_proc.wait()
        monitor_thread.join(timeout=0.5)

        if interrupt_event.is_set():
            print("  [TTS] Interrupted (echo-aware).")
            return True

    return False

# ---------------------------------------------------------------------------
# Wake / sleep word helpers
# ---------------------------------------------------------------------------

def check_for_wake_word(text: str) -> bool:
    return WAKE_WORD in text.lower()


def check_for_sleep_word(text: str) -> bool:
    return SLEEP_WORD in text.lower()

# ---------------------------------------------------------------------------
# Arduino helpers
# ---------------------------------------------------------------------------

def open_arduino():
    if not CONNECT_ARDUINO:
        print("[Hardware] Arduino disabled (PC testing mode or connect_arduino=false).")
        return None
    if not PYSERIAL_AVAILABLE:
        print("[Hardware] pyserial not installed — skipping Arduino.")
        return None

    print(f"[Hardware] Connecting to Arduino on {SERIAL_PORT} @ {BAUD_RATE} baud...")
    try:
        arduino = pyserial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
        time.sleep(2)
        print(f"[Hardware] Arduino connected on {SERIAL_PORT}.")
        return arduino
    except SerialException as e:
        print(f"[Hardware] Could not connect to Arduino: {e}")
        if system == "Windows":
            print("  → Check Device Manager for the COM port and set serial_port_windows in config.json")
        else:
            print("  → Check: ls /dev/tty{USB,ACM}*  |  sudo usermod -aG dialout $USER")
        return None


def stop_and_close_arduino(arduino) -> None:
    if arduino is not None and arduino.is_open:
        try:
            arduino.write(b"s")
            time.sleep(0.1)
        except Exception:
            pass
        arduino.close()
        print("[Hardware] Arduino disconnected.")

# ---------------------------------------------------------------------------
# CV pipeline background thread
# ---------------------------------------------------------------------------

class CVTrackingThread(threading.Thread):
    """
    Wraps CVPipeline tracking in a background daemon thread.
    On Jetson: cv2.imshow is called from main thread (GUI pump below).
    """

    def __init__(self, arduino):
        super().__init__(name="CVTrackingThread", daemon=True)
        self.arduino     = arduino
        self._stop_event = threading.Event()
        self.pipeline    = None
        import queue as _queue
        self.frame_queue = _queue.Queue(maxsize=1)

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        if not ENABLE_CV:
            print("[CV] Camera tracking disabled (PC testing mode or enable_cv=false).")
            return
        if not CV_AVAILABLE:
            print("[CV] cv_pipeline not available — tracking thread not starting.")
            return
        try:
            self.pipeline = CVPipeline(arduino=self.arduino)
            self.pipeline.turn_on_camera()
            print("[CV] Person-tracking started.")
            self._tracking_loop()
        except Exception as e:
            print(f"[CV] Thread error: {e}")
        finally:
            if self.pipeline:
                self.pipeline.shutdown()
            print("[CV] Tracking thread stopped.")

    def _push_frame(self, frame) -> None:
        try:
            self.frame_queue.put_nowait(frame)
        except Exception:
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame)
            except Exception:
                pass

    def _tracking_loop(self) -> None:
        import cv2

        p = self.pipeline
        prev_turn, prev_move = "", ""

        while not self._stop_event.is_set():
            success, image = p.camera.read()
            if not success:
                print("[CV] Failed to read camera frame — stopping tracking.")
                break

            analysis = p.person_detector.track(
                image, persist=True, tracker="bytetrack.yaml"
            )[0].boxes

            if analysis.id is None:
                self._push_frame(image)
                continue

            boxes     = analysis.xyxy.cpu().numpy()
            classes   = analysis.cls.cpu().numpy()
            track_ids = analysis.id.cpu().numpy()

            if (p.target is not None and
                    p.target not in [int(tid) for tid in track_ids]):
                p.target = None

            for box, class_id, track_id in zip(boxes, classes, track_ids):
                if int(class_id) == 0 and p.target is None:
                    p.target = int(track_id)

                if p.target == int(track_id):
                    h, w, _ = image.shape
                    x1, y1, x2, y2 = map(int, box)

                    new_turn = p._get_turn_signal(w, h, x1, x2, y1, y2)
                    new_move = p._get_move_signal(w, h, x1, x2, y1, y2)

                    if new_turn != prev_turn or new_move != prev_move:
                        prev_turn, prev_move = new_turn, new_move
                        p._send_command(prev_move, prev_turn)

                    cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 3)
                    cv2.putText(
                        image,
                        f"Turn: {prev_turn}  Move: {prev_move}",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 5,
                    )

            self._push_frame(image)

# ---------------------------------------------------------------------------
# Active mode
# ---------------------------------------------------------------------------

def start_active_mode(context: ConversationContext) -> None:
    arduino   = open_arduino()
    cv_thread = CVTrackingThread(arduino=arduino)
    cv_active = ENABLE_CV and CV_AVAILABLE

    if cv_active:
        cv_thread.start()
        print("[CV] Person-tracking running in background.")
    elif ENABLE_CV and not CV_AVAILABLE:
        print("[CV] Skipping camera tracking (cv_pipeline unavailable).")
    else:
        print("[CV] Skipping camera tracking (disabled for this runtime).")

    greeting = phrase("Yes, I'm here. How can I help you?",
                      "Sí, aquí estoy. ¿En qué te puedo ayudar?")
    print(f"\nAssistant: {greeting}")
    speak_response(greeting)

    if PYAUDIO_AVAILABLE:
        print(f"[Voice] VAD active — recording stops after {VAD_SILENCE_DURATION}s of silence.")
    else:
        print(f"[Voice] Fixed-duration recording ({CONVERSATION_DURATION}s).")

    import queue as _queue

    def pump_gui(timeout_ms: int = 1) -> bool:
        if not cv_active:
            return False
        import cv2 as _cv2
        try:
            frame = cv_thread.frame_queue.get_nowait()
            _cv2.imshow("Companion — Tracking", frame)
        except _queue.Empty:
            pass
        return (_cv2.waitKey(timeout_ms) & 0xFF) == ord("q")

    try:
        while True:
            if pump_gui(1):
                print("[CV] Q pressed — stopping tracking and ending session.")
                break

            print("\n[Voice] Listening... (speak now)")

            if not record_audio(CONVERSATION_DURATION, TEMP_AUDIO, use_vad=True):
                pump_gui(1)
                speak_response(phrase(
                    "I didn't hear you clearly. Could you repeat that?",
                    "No te escuché bien. ¿Podrías repetir eso?"
                ))
                continue

            pump_gui(1)
            user_input = transcribe_audio(TEMP_AUDIO)
            pump_gui(1)

            if not user_input:
                speak_response(phrase(
                    "I didn't catch that. Please say that again.",
                    "No entendí. Por favor, dilo de nuevo."
                ))
                continue

            print(f"You said: {user_input}")

            if check_for_sleep_word(user_input):
                print(f"\n[Voice] Sleep word detected — ending session.")
                print("[Summary] Generating conversation summary...")
                context.generate_summary()

                farewell = phrase(
                    "Goodbye! I'll be here when you need me. Just say my name to talk again.",
                    "¡Adiós! Aquí estaré cuando me necesites. Solo di mi nombre para volver a hablar."
                )
                print(f"Assistant: {farewell}")
                speak_response(farewell)
                break

            response = generate_response(user_input, context)
            pump_gui(1)
            print(f"Assistant: {response}")
            context.add_exchange(user_input, response)

            interrupted = speak_response(response)
            pump_gui(1)

            if interrupted:
                print("[Voice] User interrupted — listening straight away...")
                continue

            deadline = time.time() + 0.5
            while time.time() < deadline:
                if pump_gui(16):
                    break

    finally:
        print("\n[→] Stopping hardware...")
        cv_thread.request_stop()
        if cv_active and cv_thread.is_alive():
            cv_thread.join(timeout=5)
        if cv_active:
            try:
                import cv2 as _cv2
                _cv2.destroyAllWindows()
                _cv2.waitKey(1)
            except Exception:
                pass
        stop_and_close_arduino(arduino)
        print("[→] Hardware stopped. Returning to sleep mode.\n")

# ---------------------------------------------------------------------------
# Main — sleep mode loop
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  BrainCharge Companion Robot — Caregiver Compassion Bot")
    print(f"  Wake word : \"{WAKE_WORD}\"")
    print(f"  Sleep word: \"{SLEEP_WORD}\"")
    print(f"  Language  : {'Spanish (es)' if LANGUAGE == 'es' else 'English (en)'}")
    print(f"  LLM model : {OLLAMA_MODEL}")
    print(f"  Platform  : {system} ({platform.machine()})")
    print(f"  Runtime   : {describe_runtime(runtime)}")
    try:
        print(f"  Time      : {get_current_datetime_str()}")
    except ValueError:
        print(f"  Time      : {datetime.now().isoformat()}")

    if _macos_say_available():
        print(f"  TTS       : macOS 'say' (voice: {_active_macos_voice()})")
    elif _espeak_available():
        print(f"  TTS       : eSpeak (voice: {_active_espeak_voice()})")
    elif _windows_sapi_available():
        print("  TTS       : Windows SAPI (System.Speech)")
    else:
        print("  TTS       : !! No TTS engine found — install espeak !!")

    if PYAUDIO_AVAILABLE:
        print(f"  VAD       : Enabled ({VAD_SILENCE_THRESHOLD_DB} dBFS, "
              f"{VAD_SILENCE_DURATION}s silence)")
    else:
        print("  VAD       : Disabled (install portaudio19-dev + pyaudio to enable)")

    if not VOSK_INTERRUPT_ENABLED:
        print("  Interrupt : Disabled (vosk_interrupt_enabled = false)")
    elif VOSK_AVAILABLE and os.path.exists(VOSK_MODEL_PATH):
        print(f"  Interrupt : Echo-aware (model: {VOSK_MODEL_PATH})")
    elif VOSK_AVAILABLE:
        print(f"  Interrupt : Vosk model missing — volume-based fallback")
    else:
        print("  Interrupt : Volume-based (install vosk for echo-aware)")

    if system == "Windows":
        mic_name = _resolve_windows_mic_name()
        print(f"  Audio     : dshow device={mic_name!r}")
    elif system == "Darwin":
        print("  Audio     : avfoundation (default input)")
    else:
        backend, device = _detect_linux_audio_backend()
        print(f"  Audio     : {backend} device={device!r}")

    if ENABLE_CV and CV_AVAILABLE:
        print("  CV        : Enabled (starts on wake word)")
    elif ENABLE_CV:
        print("  CV        : Requested but cv_pipeline unavailable")
    else:
        print("  CV        : Disabled (set enable_cv=true in config.json to enable on PC)")

    if CONNECT_ARDUINO and PYSERIAL_AVAILABLE:
        print(f"  Arduino   : {SERIAL_PORT} @ {BAUD_RATE} baud (connects on wake)")
    elif CONNECT_ARDUINO:
        print(f"  Arduino   : Requested on {SERIAL_PORT} (install pyserial)")
    else:
        print("  Arduino   : Disabled (set connect_arduino=true in config.json to enable on PC)")

    if system not in ("Windows", "Darwin") and CONNECT_ARDUINO:
        print(f"  Serial    : {SERIAL_PORT} @ {BAUD_RATE} baud")

    print("  Press Ctrl-C to exit at any time")
    print("=" * 60)

    appt_mgr = AppointmentManager(APPOINTMENTS_FILE)
    context  = ConversationContext(CONTEXT_FILE, SUMMARY_FILE, appt_mgr)

    if context.history:
        print(f"\n[Context] Loaded {len(context.history)} previous exchanges.")
    if context.summary:
        print(f"[Context] Summary from {context.summary.get('last_updated', 'unknown')}.")
        if context.summary.get("topics"):
            print(f"  Topics: {', '.join(context.summary['topics'][:3])}")

    stats = appt_mgr.summary_stats()
    if stats["total"]:
        print(f"[Appointments] {stats['upcoming']} upcoming, "
              f"{stats['completed']} completed, {stats['cancelled']} cancelled")

    try:
        while True:
            print("\n[Sleep] Listening for wake word...")

            if not record_audio(WAKE_WORD_LISTEN_DURATION, TEMP_AUDIO, use_vad=False):
                time.sleep(1)
                continue

            transcription = transcribe_audio(TEMP_AUDIO)

            if transcription:
                print(f"[Sleep] Heard: {transcription}")
                if check_for_wake_word(transcription):
                    print(f"\n[Wake] \"{WAKE_WORD}\" detected! Starting active mode...\n")
                    start_active_mode(context)
                    print("[Sleep] Returning to sleep mode...")
                    time.sleep(1)

            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\n[Exit] Shutting down. Goodbye!")
        speak_response(phrase("Goodbye, take care!", "¡Adiós, cuídate!"))
    except Exception as e:
        print(f"\n[Error] Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()

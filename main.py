import subprocess
import json
import os
import time
import platform
import wave
import struct
import math
from datetime import datetime

# Try to import pyaudio for VAD recording
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("Warning: pyaudio not installed. Install with: pip install pyaudio")
    print("Falling back to fixed-duration ffmpeg recording.")

# Try to import config.py utilities, fall back to config.json
try:
    from config import ffmpeg_record_command as get_config_ffmpeg_cmd
    USE_CONFIG_PY = True
except ImportError:
    USE_CONFIG_PY = False

CONFIG_PATH = "config.json"

if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

# Auto-detect whisper path based on OS
system = platform.system()
if system == "Windows":
    WHISPER_PATH = config.get("whisper_path_windows", config.get("whisper_path", "whisper.cpp/build/bin/Release/whisper-cli.exe"))
elif system == "Darwin":
    WHISPER_PATH = config.get("whisper_path_mac", config.get("whisper_path", "whisper.cpp/build/bin/whisper-cli"))
else:
    WHISPER_PATH = config.get("whisper_path_linux", config.get("whisper_path", "whisper.cpp/build/bin/whisper-cli"))

WHISPER_MODEL = config["whisper_model"]
PIPER_MODEL = config.get("piper_model", "")

TEMP_AUDIO = config["temp_audio"]
TEMP_TRANSCRIPT = config["temp_transcript"]
TEMP_RESPONSE = config.get("temp_response", "response.wav")

CONTEXT_FILE = config.get("context_file", "conversation_context.json")
SUMMARY_FILE = config.get("summary_file", "conversation_summary.json")

WAKE_WORD = config.get("wake_word", "companion").lower()
SLEEP_WORD = config.get("sleep_word", "bye companion").lower()

# Legacy fixed durations (used as fallback if pyaudio unavailable)
LISTEN_DURATION = config.get("listen_duration", 3)
CONVERSATION_DURATION = config.get("conversation_duration", 5)

# VAD (Voice Activity Detection) settings - tunable in config.json
VAD_SILENCE_THRESHOLD_DB = config.get("vad_silence_threshold_db", -40)  # dBFS below which is "silence"
VAD_SILENCE_DURATION = config.get("vad_silence_duration", 1.5)          # seconds of silence before stopping
VAD_MIN_RECORDING = config.get("vad_min_recording", 0.5)                # min seconds to record before VAD kicks in
VAD_MAX_RECORDING = config.get("vad_max_recording", 30)                  # hard ceiling in seconds
VAD_SAMPLE_RATE = config.get("vad_sample_rate", 16000)
VAD_CHUNK_SIZE = config.get("vad_chunk_size", 1024)

# For wake word listening, we use a shorter fixed window (no need for VAD)
WAKE_WORD_LISTEN_DURATION = config.get("wake_word_listen_duration", 3)


def calculate_rms_db(audio_chunk):
    """
    Calculate the RMS volume of an audio chunk in dBFS.
    Returns -inf for silence (all zeros), otherwise a negative dB value
    where 0 dBFS is the maximum possible level.
    """
    count = len(audio_chunk) // 2  # 16-bit = 2 bytes per sample
    if count == 0:
        return -100.0
    
    shorts = struct.unpack(f"{count}h", audio_chunk)
    sum_squares = sum(s * s for s in shorts)
    rms = math.sqrt(sum_squares / count)
    
    if rms == 0:
        return -100.0
    
    # Normalize to 16-bit range (max 32768) and convert to dB
    db = 20 * math.log10(rms / 32768.0)
    return db


def record_audio_vad(output_file, min_duration=None, max_duration=None, silence_threshold_db=None, silence_duration=None):
    """
    Record audio using PyAudio with voice activity detection.
    Stops recording after 'silence_duration' seconds of audio below 'silence_threshold_db'.
    
    Args:
        output_file: path to save the WAV file
        min_duration: minimum recording time in seconds before VAD activates
        max_duration: hard cap on recording length in seconds
        silence_threshold_db: dBFS level below which audio counts as silence
        silence_duration: how many consecutive seconds of silence triggers stop
    
    Returns:
        True on success, False on error
    """
    min_dur = min_duration if min_duration is not None else VAD_MIN_RECORDING
    max_dur = max_duration if max_duration is not None else VAD_MAX_RECORDING
    thresh_db = silence_threshold_db if silence_threshold_db is not None else VAD_SILENCE_THRESHOLD_DB
    sil_dur = silence_duration if silence_duration is not None else VAD_SILENCE_DURATION

    try:
        pa = pyaudio.PyAudio()
        
        # Find the right input device index
        device_index = None
        try:
            device_index = pa.get_default_input_device_info()["index"]
        except Exception:
            pass  # Use None = default

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=VAD_SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=VAD_CHUNK_SIZE
        )

        frames = []
        silence_start = None
        recording_start = time.time()
        speech_detected = False

        chunks_per_second = VAD_SAMPLE_RATE / VAD_CHUNK_SIZE

        while True:
            elapsed = time.time() - recording_start

            # Hard cap
            if elapsed >= max_dur:
                print()  # newline after the meter
                print(f"  [VAD] Max duration ({max_dur}s) reached, stopping.")
                break

            try:
                chunk = stream.read(VAD_CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                break

            frames.append(chunk)
            db = calculate_rms_db(chunk)

            is_speech = db > thresh_db

            if is_speech:
                status = "SPEECH"
                speech_detected = True
                silence_start = None
            else:
                if elapsed >= min_dur and speech_detected:
                    if silence_start is None:
                        silence_start = time.time()
                    sil_elapsed = time.time() - silence_start
                    status = f"silence {sil_elapsed:.1f}/{sil_dur:.1f}s"
                else:
                    status = "waiting..."

            print(f"\r {db:6.1f} dBFS  |  {status:<22} | {elapsed:.1f}s", end="", flush=True)

            if not is_speech and elapsed >= min_dur and speech_detected:
                if silence_start and time.time() - silence_start >= sil_dur:
                    print()
                    print(f"  [VAD] Silence threshold reached, stopping.")
                    break

        stream.stop_stream()
        stream.close()
        pa.terminate()

        if not frames:
            return False

        # Save as WAV
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(VAD_SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        total_duration = len(frames) * VAD_CHUNK_SIZE / VAD_SAMPLE_RATE
        print(f"  [VAD] Recorded {total_duration:.1f}s of audio")
        return True

    except Exception as e:
        print(f"VAD recording error: {e}")
        return False


def get_audio_input_command(duration, output_file):
    """Get OS-specific ffmpeg audio recording command (fallback when pyaudio unavailable)."""
    
    if USE_CONFIG_PY:
        try:
            return get_config_ffmpeg_cmd(output_file)
        except Exception:
            pass

    system = platform.system()

    if system == "Darwin":
        return [
            "ffmpeg", "-f", "avfoundation", "-i", ":1",
            "-t", str(duration), output_file, "-y"
        ]
    elif system == "Windows":
        return [
            "ffmpeg", "-f", "dshow",
            "-i", "audio=Microphone (Realtek Audio)",
            "-t", str(duration), output_file, "-y"
        ]
    else:
        if os.path.exists("/usr/bin/pulseaudio") or os.path.exists("/usr/bin/pactl"):
            return ["ffmpeg", "-f", "pulse", "-i", "default", "-t", str(duration), output_file, "-y"]
        else:
            return ["ffmpeg", "-f", "alsa", "-i", "default", "-t", str(duration), output_file, "-y"]


def record_audio(duration, output_file, use_vad=False):
    """
    Record audio. Uses VAD if pyaudio is available and use_vad=True,
    otherwise falls back to fixed-duration ffmpeg recording.
    
    Args:
        duration: fallback fixed duration (used when pyaudio unavailable)
        output_file: path to save audio
        use_vad: whether to attempt VAD-based recording
    """
    if use_vad and PYAUDIO_AVAILABLE:
        return record_audio_vad(output_file)
    
    # Fallback: fixed-duration ffmpeg
    try:
        cmd = get_audio_input_command(duration, output_file)
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg recording error:\n{e.stderr.decode() if e.stderr else e}")
        return False
    except Exception as e:
        print(f"Unexpected audio recording error: {e}")
        return False


class ConversationContext:
    """Manages conversation history and context with AI summarization"""
    def __init__(self, context_file, summary_file):
        self.context_file = context_file
        self.summary_file = summary_file
        self.history = self.load_context()
        self.summary = self.load_summary()
    
    def load_context(self):
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, "r") as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def load_summary(self):
        if os.path.exists(self.summary_file):
            try:
                with open(self.summary_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_context(self):
        with open(self.context_file, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def save_summary(self):
        with open(self.summary_file, "w") as f:
            json.dump(self.summary, f, indent=2)
    
    def add_exchange(self, user_input, assistant_response):
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "assistant": assistant_response
        })
        self.save_context()
    
    def generate_summary(self):
        """Use Ollama to summarize the conversation and extract key information"""
        if os.path.exists(self.summary_file):
            os.remove(self.summary_file)

        if not self.history:
            return
        
        conversation_text = "Conversation history:\n\n"
        for exchange in self.history:
            conversation_text += f"[{exchange['timestamp']}]\n"
            conversation_text += f"User: {exchange['user']}\n"
            conversation_text += f"Assistant: {exchange['assistant']}\n\n"
        
        summary_prompt = (
            "You are analyzing a conversation between a caregiver and an AI companion bot. "
            "Extract and summarize the following information in JSON format:\n"
            "1. Important people mentioned (names, relationships)\n"
            "2. Important dates and events mentioned\n"
            "3. Key concerns or topics discussed\n"
            "4. Emotional state patterns (stress levels, concerns)\n"
            "5. Action items or follow-ups needed\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            "{\n"
            '  "people": [{"name": "...", "relationship": "...", "context": "..."}],\n'
            '  "dates": [{"date": "...", "event": "..."}],\n'
            '  "topics": ["topic1", "topic2"],\n'
            '  "emotional_patterns": "brief description",\n'
            '  "action_items": ["item1", "item2"],\n'
            '  "summary": "brief overall summary"\n'
            "}\n\n"
            f"Conversation to analyze:\n{conversation_text}"
        )
        
        try:
            result = subprocess.run(
                ["ollama", "run", "gemma3:4b", summary_prompt],
                capture_output=True, text=True, timeout=60
            )
            summary_text = result.stdout.strip()
            
            if "```json" in summary_text:
                summary_text = summary_text.split("```json")[1].split("```")[0].strip()
            elif "```" in summary_text:
                summary_text = summary_text.split("```")[1].split("```")[0].strip()
            
            self.summary = json.loads(summary_text)
            self.summary["last_updated"] = datetime.now().isoformat()
            self.save_summary()
            
            print("Summary generated successfully!")
            print(f"   People: {len(self.summary.get('people', []))}")
            print(f"   Topics: {len(self.summary.get('topics', []))}")
            print(f"   Action items: {len(self.summary.get('action_items', []))}")
            
        except subprocess.TimeoutExpired:
            print("Summary generation timed out")
        except json.JSONDecodeError as e:
            print(f"Failed to parse summary JSON: {e}")
        except Exception as e:
            print(f"Error generating summary: {e}")
    
    def get_context_prompt(self):
        """Build context string using AI summary and recent exchanges"""
        context_str = ""
        
        if self.summary:
            context_str += "\n=== Conversation Summary ===\n"
            if "summary" in self.summary:
                context_str += f"Overall: {self.summary['summary']}\n\n"
            if "people" in self.summary and self.summary["people"]:
                context_str += "People mentioned:\n"
                for person in self.summary["people"]:
                    context_str += f"- {person.get('name', 'Unknown')}"
                    if person.get('relationship'):
                        context_str += f" ({person['relationship']})"
                    if person.get('context'):
                        context_str += f": {person['context']}"
                    context_str += "\n"
                context_str += "\n"
            if "dates" in self.summary and self.summary["dates"]:
                context_str += "Important dates:\n"
                for date_info in self.summary["dates"]:
                    context_str += f"- {date_info.get('date', 'Unknown')}: {date_info.get('event', '')}\n"
                context_str += "\n"
            if "topics" in self.summary and self.summary["topics"]:
                context_str += f"Key topics: {', '.join(self.summary['topics'])}\n\n"
            if "emotional_patterns" in self.summary:
                context_str += f"Emotional context: {self.summary['emotional_patterns']}\n\n"
            if "action_items" in self.summary and self.summary["action_items"]:
                context_str += "Action items:\n"
                for item in self.summary["action_items"]:
                    context_str += f"- {item}\n"
                context_str += "\n"
        
        if self.history:
            context_str += "=== Recent conversation ===\n"
            for exchange in self.history[-5:]:
                context_str += f"User: {exchange['user']}\n"
                context_str += f"Assistant: {exchange['assistant']}\n"
        
        return context_str
    
    def clear_context(self):
        self.history = []
        self.summary = {}
        self.save_context()
        self.save_summary()


def transcribe_audio(audio_file):
    """Transcribe audio using Whisper"""
    try:
        subprocess.run([
            WHISPER_PATH,
            "-m", WHISPER_MODEL,
            "-f", audio_file,
            "-of", TEMP_TRANSCRIPT,
            "-otxt"
        ], check=True, capture_output=True)
        
        transcript_file = TEMP_TRANSCRIPT + ".txt"
        if os.path.exists(transcript_file):
            with open(transcript_file, "r") as f:
                return f.read().strip()
        return ""
    except subprocess.CalledProcessError as e:
        print(f"Error transcribing: {e}")
        return ""


def generate_response(user_input, context):
    """Generate response using Ollama with context"""
    prompt_instruction = (
        "You are the Caregiver Compassion Bot, a gentle, empathetic robotic companion "
        "designed by BrainCharge to support family caregivers who face high stress and emotional fatigue. "
        "Keep your replies conversational, brief, "
        "and naturally worded so they sound good when spoken aloud. Avoid technical or robotic phrasing. "
        "If the user seems stressed, respond with compassion and offer small words of comfort. "
        "Keep responses under 3 sentences for natural conversation flow. "
        "Use the conversation context below to provide personalized, relevant responses."
    )
    
    context_prompt = context.get_context_prompt()
    full_prompt = prompt_instruction + context_prompt + f"\n\nUser: {user_input}\n\nAssistant:"
    
    try:
        result = subprocess.run(
            ["ollama", "run", "gemma3:4b", full_prompt],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "I apologize, I'm having trouble responding right now."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm sorry, I encountered an error."


def speak_response(text):
    """Speak the response using eSpeak"""
    try:
        subprocess.run(["espeak", text], check=True, capture_output=True)
    except Exception as e:
        print(f"Error speaking response: {e}")


def check_for_wake_word(text):
    return WAKE_WORD in text.lower()


def check_for_sleep_word(text):
    return SLEEP_WORD in text.lower()


def continuous_conversation(context):
    """Handle continuous back-and-forth conversation until sleep word"""
    print("\n Starting conversation mode...")
    if PYAUDIO_AVAILABLE:
        print(f" VAD active — recording will stop after {VAD_SILENCE_DURATION}s of silence below {VAD_SILENCE_THRESHOLD_DB} dBFS")
    speak_response("Yes, I'm here. How can I help you?")
    
    conversation_active = True
    
    while conversation_active:
        print("\n Listening... (speak now, I'll stop when you're done)")
        
        # Use VAD for conversation turns so length is natural
        if not record_audio(CONVERSATION_DURATION, TEMP_AUDIO, use_vad=True):
            speak_response("I didn't hear you clearly. Could you repeat that?")
            continue
        
        user_input = transcribe_audio(TEMP_AUDIO)
        if not user_input:
            speak_response("I didn't catch that. Please say that again.")
            continue
        
        print(f"You said: {user_input}")
        
        if check_for_sleep_word(user_input):
            print(f"\n Sleep word '{SLEEP_WORD}' detected!")
            print("\n Generating final conversation summary before sleep...")
            context.generate_summary()
            farewell_message = "Goodbye! I'll be here when you need me. Just say the wake word to talk again."
            print(f"Assistant: {farewell_message}\n")
            speak_response(farewell_message)
            conversation_active = False
            break
        
        response = generate_response(user_input, context)
        print(f"Assistant: {response}\n")
        context.add_exchange(user_input, response)
        speak_response(response)
        time.sleep(0.5)


def main():
    """Main loop - continuously listen for wake word"""
    print("Caregiver Compassion Bot - Wake Word System")
    print(f"Wake word: '{WAKE_WORD}' - Say this to start a conversation")
    print(f"Sleep word: '{SLEEP_WORD}' - Say this to end the conversation")
    
    if PYAUDIO_AVAILABLE:
        print(f"VAD: Enabled (silence threshold: {VAD_SILENCE_THRESHOLD_DB} dBFS, stops after {VAD_SILENCE_DURATION}s silence)")
    else:
        print("VAD: Disabled (pyaudio not installed — using fixed-duration recording)")
        print("  Install with: pip install pyaudio")
    
    print("Press Ctrl+C to exit\n")
    
    context = ConversationContext(CONTEXT_FILE, SUMMARY_FILE)
    
    if context.history:
        print(f" Loaded {len(context.history)} previous exchanges")
    if context.summary:
        print(f" Loaded conversation summary from {context.summary.get('last_updated', 'unknown time')}")
        if context.summary.get('people'):
            print(f"   - {len(context.summary['people'])} people tracked")
        if context.summary.get('topics'):
            print(f"   - Topics: {', '.join(context.summary['topics'][:3])}...")
    
    try:
        while True:
            print("\n Sleeping mode - Listening for wake word...")
            
            # Wake word detection uses short fixed window (VAD not needed here)
            if not record_audio(WAKE_WORD_LISTEN_DURATION, TEMP_AUDIO, use_vad=False):
                time.sleep(1)
                continue
            
            transcription = transcribe_audio(TEMP_AUDIO)
            
            if transcription:
                print(f"Heard: {transcription}")
                if check_for_wake_word(transcription):
                    print(f"\n Wake word detected! Entering conversation mode...\n")
                    continuous_conversation(context)
                    print("\n Returning to sleep mode...")
                    time.sleep(1)
            
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\nShutting down. Goodbye!")
        speak_response("Goodbye, take care!")
    except Exception as e:
        print(f"\n Error: {e}")


if __name__ == "__main__":
    main()

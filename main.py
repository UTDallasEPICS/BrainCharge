import subprocess
import json
import os
import re
import time
import platform
import wave
import struct
import math
import requests
from datetime import datetime
from ollama_client import call_ollama
from cv.picture import CVPipeline
import identity_backend
from voice_text_emotion.voice_emotion import detect_voice_emotion
from voice_text_emotion.text_emotion import detect_text_emotion
from memory.memory_manager import save_session
from memory.session_summary import record_session, summarize_session
from display.robot_face import RobotFaceDisplay, classify_reply_expression

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

# subprocess/CreateProcess on Windows resolves a relative executable path
# differently than normal file access (os.path.exists can find it, but
# subprocess.run can't launch it) -- make it absolute to avoid that.
WHISPER_PATH = os.path.abspath(WHISPER_PATH)

if system == "Windows":
    ESPEAK_PATH = config.get("espeak_path_windows", "espeak-ng")
elif system == "Darwin":
    ESPEAK_PATH = config.get("espeak_path_mac", "espeak-ng")
else:
    ESPEAK_PATH = config.get("espeak_path_linux", "espeak-ng")

WHISPER_MODEL = config["whisper_model"]
PIPER_MODEL = config.get("piper_model", "")

TEMP_AUDIO = config["temp_audio"]
TEMP_TRANSCRIPT = config["temp_transcript"]
TEMP_RESPONSE = config.get("temp_response", "response.wav")

CONTEXT_FILE = config.get("context_file", "conversation_context.json")
SUMMARY_FILE = config.get("summary_file", "conversation_summary.json")

# Below this, a vision/voice emotion reading is treated as "no reliable
# signal" rather than handed to the LLM as fact.
EMOTION_CONFIDENCE_THRESHOLD = config.get("emotion_confidence_threshold", 0.4)

WAKE_WORD = config.get("wake_word", "companion").lower()
SLEEP_WORD = config.get("sleep_word", "bye companion").lower()

# Whisper reliably mishears "bye" as its homophones "by"/"buy" in casual
# speech -- generate those variants from whatever sleep word is configured,
# rather than requiring the exact spelling to match.
SLEEP_WORD_VARIANTS = [SLEEP_WORD]
if SLEEP_WORD.startswith("bye "):
    _rest = SLEEP_WORD[len("bye "):]
    SLEEP_WORD_VARIANTS.append("by " + _rest)
    SLEEP_WORD_VARIANTS.append("buy " + _rest)

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
        # Deliberately start blank on every process launch instead of loading
        # whatever's on disk -- this file is short-term scratch for the
        # current conversation, not long-term memory (that's the DB's job via
        # save_session). Loading stale content here meant any non-graceful
        # shutdown (an IDE's hard-kill Stop button doesn't raise a catchable
        # KeyboardInterrupt, a closed terminal, a crash) left data that bled
        # into a completely different future conversation.
        self.history = []
        self.summary = {}
        self.save_context()
        self.save_summary()
    
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
            summary_text = call_ollama(summary_prompt, json_mode=True, timeout=90)

            self.summary = json.loads(summary_text)
            self.summary["last_updated"] = datetime.now().isoformat()
            self.save_summary()

            print("Summary generated successfully!")
            print(f"   People: {len(self.summary.get('people', []))}")
            print(f"   Topics: {len(self.summary.get('topics', []))}")
            print(f"   Action items: {len(self.summary.get('action_items', []))}")

        except requests.exceptions.Timeout:
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


def extract_name(transcript):
    """Pulls just a person's name out of a free-form reply like 'My name is Alice'.
    Returns the name as a string, or None if nothing usable could be extracted."""
    prompt = (
        "Extract just the person's first name from the following statement. "
        "Respond with ONLY the name itself, capitalized, nothing else -- no punctuation, "
        "no extra words. If no name is stated, respond with exactly: NONE\n\n"
        f"Statement: {transcript}"
    )
    try:
        name = call_ollama(prompt, timeout=90)
        if not name or name.upper() == "NONE":
            return None

        # Guard against the model fabricating a name that was never actually
        # said -- only trust it if that exact word genuinely appears in the
        # transcript (seen it hallucinate "Tom"/"John" out of statements that
        # never mentioned a name at all).
        transcript_words = [w.strip(".,!?").lower() for w in transcript.split()]
        if name.strip(".,!?").lower() not in transcript_words:
            print(f"Rejected extracted name '{name}' -- doesn't appear in the transcript")
            return None

        return name
    except requests.exceptions.Timeout:
        print("Name extraction timed out")
        return None
    except Exception as e:
        print(f"Error extracting name: {e}")
        return None


def generate_response(user_input, context, person_name=None, vision_emotion=None, vision_confidence=None, text_emotion=None, text_confidence=None, text_description=None, voice_emotion=None, voice_confidence=None):
    """Generate response using Ollama with context"""
    prompt_instruction = (
        "You are the Caregiver Compassion Bot, a warm, friendly robotic companion designed by "
        "BrainCharge for family caregivers. Treat this like an ordinary, everyday conversation -- "
        "most turns are just normal chat, not a moment of crisis. Only bring up stress, burden, "
        "or emotional support when the user's own words or the emotion context below actually "
        "indicate it; never assume it by default. "
        "Always engage with what the user actually just said first -- answer their question or respond "
        "to their specific statement directly. Do not fall back on generic comfort phrases instead of "
        "addressing the content of their message. "
        "Keep your replies conversational, brief, "
        "and naturally worded so they sound good when spoken aloud. Avoid technical or robotic phrasing. "
        "Keep responses under 3 sentences for natural conversation flow. "
        "You do not have access to real-time information such as weather, news, or current events -- "
        "if asked about something you can't actually know, say so honestly instead of making up an answer. "
        "Use the conversation context below to provide personalized, relevant responses."
    )

    context_prompt = context.get_context_prompt()

    # State absence explicitly rather than just omitting it -- an implicit
    # "if asked, don't guess" instruction wasn't reliably followed; the model
    # kept borrowing a different modality's reading and mislabeling it. An
    # explicit negative fact for the specific modality being asked about is
    # much harder to route around than an abstract behavioral rule.
    if vision_emotion is not None:
        vision_fact = f"Their face showed {vision_emotion} ({vision_confidence:.2f} confidence)."
    else:
        vision_fact = "No reliable facial-expression reading is available right now."
    if voice_emotion is not None:
        voice_fact = f"Their voice sounded {voice_emotion} ({voice_confidence:.2f} confidence)."
    else:
        voice_fact = "No reliable voice-tone reading is available right now."

    # Whichever modality the question is actually about goes first -- testing
    # showed the model is more likely to correctly use (or correctly admit
    # the absence of) a reading when it leads, rather than trailing behind a
    # different modality's reading.
    user_input_lower = user_input.lower()
    asks_about_voice = any(kw in user_input_lower for kw in ["voice", "tone of voice", "sound like", "how i sound"])
    asks_about_face = any(kw in user_input_lower for kw in ["face", "facial", "expression", "look like"])

    face_line = f"Face reading: {vision_fact}\n"
    voice_line = f"Voice reading: {voice_fact}\n"
    if asks_about_voice and not asks_about_face:
        emotion_context = f"\n\n{voice_line}{face_line}"
    else:
        emotion_context = f"\n\n{face_line}{voice_line}"

    if text_emotion is not None:
        emotion_context += f"Words reading: Their words suggested {text_emotion}"
        if text_description:
            emotion_context += f" -- {text_description}"
        emotion_context += ".\n"

    emotion_context += (
        "If the user asks specifically about their face, voice, or words, answer using ONLY "
        "that exact modality's reading above -- if it says no reliable reading is available, "
        "say so plainly instead of guessing or borrowing a different modality's reading. "
        "Match your tone to whichever readings are available -- if neutral or positive, respond "
        "normally and do not introduce concern about stress or struggling. These are "
        "single-moment readings and can be noisy or wrong -- treat them as a soft, uncertain "
        "signal rather than a confident diagnosis. Let this subtly inform the warmth and tone of "
        "your reply -- it should never replace directly addressing what they said, and don't "
        "list these back to the user unless asked."
    )

    if person_name:
        name_fact = (
            f"\n\n[Fact: the person you are talking to right now is named {person_name}. "
            f"If they ask their own name or whether you remember them, say their name back to them directly.]"
        )
    else:
        name_fact = (
            "\n\n[You do not know this person's name. Never invent or guess a name for them -- "
            "if asked, say you don't have their name yet and ask for it.]"
        )

    tone_reminder = (
        "\n\n[Reminder: don't assume the user is stressed, overwhelmed, or struggling unless "
        "their words or the emotion context above actually indicate it. Respond to what they "
        "actually said like a normal conversation. You have no internet access and no way to "
        "look up real-world facts like weather, news, or current events -- if asked something "
        "like that, say plainly that you can't check that, don't invent a plausible-sounding "
        "answer. If the user asks specifically about their face, voice, or words and no reading "
        "for that exact modality was given above, say plainly you don't have a clear read on "
        "that right now -- do not guess and do not answer using a different modality instead.]"
    )

    full_prompt = prompt_instruction + context_prompt + emotion_context + name_fact + tone_reminder + f"\n\nUser: {user_input}\n\nAssistant:"

    try:
        return call_ollama(full_prompt, model="gemma3:4b", timeout=90)
    except requests.exceptions.Timeout:
        return "I apologize, I'm having trouble responding right now."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm sorry, I encountered an error."


EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols, pictographs, emoticons, transport, supplemental symbols
    "\U00002600-\U000027BF"  # misc symbols and dingbats (e.g. the smileys used here)
    "\U0001F1E6-\U0001F1FF"  # regional indicator symbols (flags)
    "\U0000FE0F"             # variation selector (emoji presentation)
    "]+"
)


def speak_response(text):
    """Speak the response using eSpeak NG"""
    # The robot has no screen -- emoji have no way to be conveyed through
    # speech, so leaving them in risks espeak mangling or reading out
    # placeholder text for glyphs it has no phonemes for.
    text = EMOJI_PATTERN.sub("", text).strip()
    try:
        subprocess.run([ESPEAK_PATH, text], check=True, capture_output=True)
    except Exception as e:
        print(f"Error speaking response: {e}")


def check_for_wake_word(text):
    return WAKE_WORD in text.lower()


def check_for_sleep_word(text):
    text_lower = text.lower()
    return any(variant in text_lower for variant in SLEEP_WORD_VARIANTS)


NON_SPEECH_TOKEN_PATTERN = re.compile(r"\[[^\]]*\]")


def is_non_speech_transcript(text):
    """Whisper emits bracketed placeholders like [BLANK_AUDIO], [Silence],
    [Music], [Pause] for audio with no real speech in it. A transcript made
    up entirely of these (and whitespace) means nothing was actually said --
    treat it the same as empty, rather than feeding it to the LLM as if it
    were a real (if cryptic) statement."""
    stripped = NON_SPEECH_TOKEN_PATTERN.sub("", text).strip()
    return stripped == ""


def continuous_conversation(context, cv_pipeline, robot_face):
    """Handle continuous back-and-forth conversation until sleep word"""
    print("\n Starting conversation mode...")
    if PYAUDIO_AVAILABLE:
        print(f" VAD active — recording will stop after {VAD_SILENCE_DURATION}s of silence below {VAD_SILENCE_THRESHOLD_DB} dBFS")
    speak_response("Yes, I'm here. How can I help you?")
    cv_pipeline.turn_on_camera()

    # A single frame can easily miss the person's face (they haven't stepped
    # into view yet, camera still focusing, etc.) -- retry a few times rather
    # than permanently losing identity for the whole conversation on one bad frame.
    result = identity_backend.recognize(cv_pipeline)
    for attempt in range(4):
        if result.person_id is not None or result.is_new_person:
            break
        time.sleep(0.5)
        result = identity_backend.recognize(cv_pipeline)

    person_id = result.person_id
    person_name = None
    if result.is_new_person:
        print(" Unrecognized person -- not yet enrolled")
        speak_response("I don't think we've met yet. What's your name?")
        if record_audio(CONVERSATION_DURATION, TEMP_AUDIO, use_vad=True):
            name_transcript = transcribe_audio(TEMP_AUDIO)
            person_name = None if is_non_speech_transcript(name_transcript) else extract_name(name_transcript)
            if person_name:
                person_id = identity_backend.enroll(person_name, cv_pipeline)
                speak_response(f"Nice to meet you, {person_name}!")
                print(f" Name captured: {person_name}")
            else:
                print(" Could not extract a name from the reply")
    elif person_id is not None:
        person_name = identity_backend.get_name(person_id)
        print(f" Recognized returning person: {person_id} (name: {person_name})")
    else:
        print(" No face detected -- proceeding without identity")

    conversation_active = True
    session_readings = []
    conversation_transcript = []

    while conversation_active:
        print("\n Listening... (speak now, I'll stop when you're done)")
        
        # Use VAD for conversation turns so length is natural
        if not record_audio(CONVERSATION_DURATION, TEMP_AUDIO, use_vad=True):
            speak_response("I didn't hear you clearly. Could you repeat that?")
            continue
        
        user_input = transcribe_audio(TEMP_AUDIO)
        if not user_input or is_non_speech_transcript(user_input):
            # Silently loops back rather than replying -- feeding a whisper
            # placeholder straight to the LLM produced confident-sounding
            # nonsense (e.g. asserting the user seemed sad) instead of
            # recognizing that nothing was actually said.
            speak_response("I didn't catch that. Please say that again.")
            continue

        print(f"You said: {user_input}")
        conversation_transcript.append(user_input)

        # The one-time enrollment flow above only asks for a name once, right
        # at the start -- if that capture failed (or no face was found yet
        # to trigger it), keep an eye out for a name in whatever they say
        # naturally, on any turn, until it sticks.
        if person_name is None:
            candidate_name = extract_name(user_input)
            if candidate_name:
                person_id = identity_backend.enroll(candidate_name, cv_pipeline)
                person_name = candidate_name
                print(f" Name captured mid-conversation: {person_name}")

        voice_label, voice_confidence = detect_voice_emotion(TEMP_AUDIO)
        text_label, text_confidence, text_description = detect_text_emotion(user_input)
        emotions, face_rgb = cv_pipeline.execute()
        vision_label, vision_confidence = (emotions[0]["emotion"], emotions[0]["confidence"]) if emotions else (None,
                                                                                                                None)
        print(f" Emotion readings -- vision: {vision_label} ({vision_confidence}), "
              f"voice: {voice_label} ({voice_confidence}), text: {text_label} ({text_confidence})")

        # Only hand the LLM readings confident enough to be meaningful.
        # Vision in particular has been landing around 0.25-0.4 confidence
        # consistently (likely a detector calibration issue, not a one-off) --
        # stating that as if it were a solid fact, or letting the model
        # quietly substitute a more-confident modality when asked specifically
        # about this one, was worse than just admitting there's no clear read.
        reliable_vision_label = vision_label if (vision_label is not None and vision_confidence >= EMOTION_CONFIDENCE_THRESHOLD) else None
        reliable_vision_confidence = vision_confidence if reliable_vision_label else None
        reliable_voice_label = voice_label if (voice_label is not None and voice_confidence >= EMOTION_CONFIDENCE_THRESHOLD) else None
        reliable_voice_confidence = voice_confidence if reliable_voice_label else None

        if vision_label is not None:
            record_session(session_readings, vision_label, vision_confidence, "vision")
        if text_label is not None:
            record_session(session_readings, text_label, text_confidence, "text")
        if voice_label is not None:
            record_session(session_readings, voice_label, voice_confidence, "voice")
        
        if check_for_sleep_word(user_input):
            print(f"\n Sleep word '{SLEEP_WORD}' detected!")
            print("\n Generating final conversation summary before sleep...")
            context.generate_summary()

            # Clear immediately after the summary is captured to disk, before
            # any further hardware calls (speak_response, camera shutdown)
            # that could get interrupted (e.g. Ctrl+C) -- otherwise a stale
            # summary/history can survive on disk and bleed into a future
            # conversation with a completely different person, which is
            # exactly what happened when an earlier run got killed mid-farewell
            # and its (hallucinated) summary stuck around to confuse the next one.
            context.clear_context()

            emotion_summary = summarize_session(session_readings)
            full_transcript = " ".join(conversation_transcript)
            save_session(
                person_id,
                full_transcript,
                emotion_summary["vision_emotion"], emotion_summary["vision_confidence"],
                emotion_summary["text_emotion"], emotion_summary["text_confidence"],
                emotion_summary["voice_emotion"], emotion_summary["voice_confidence"],
            )

            farewell_message = "Goodbye! I'll be here when you need me. Just say the wake word to talk again."
            print(f"Assistant: {farewell_message}\n")
            speak_response(farewell_message)
            cv_pipeline.turn_off_camera()

            conversation_active = False
            break
        
        response = generate_response(user_input, context, person_name=person_name, vision_emotion=reliable_vision_label, vision_confidence=reliable_vision_confidence, voice_emotion=reliable_voice_label, voice_confidence=reliable_voice_confidence, text_emotion=text_label, text_confidence=text_confidence, text_description=text_description)
        print(f"Assistant: {response}\n")
        context.add_exchange(user_input, response)
        robot_face.set_expression(classify_reply_expression(response))
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
    cv_pipeline = CVPipeline()
    robot_face = RobotFaceDisplay()
    robot_face.start()

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
                    continuous_conversation(context, cv_pipeline, robot_face)
                    print("\n Returning to sleep mode...")
                    robot_face.set_expression("Neutral")
                    time.sleep(1)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nShutting down. Goodbye!")
        # A conversation stopped mid-way (Ctrl+C instead of the sleep word)
        # never reaches the sleep-word branch's clear_context() call -- without
        # this, its raw history/summary sticks around on disk and gets loaded
        # into the next run, bleeding into a different conversation later.
        context.clear_context()
        robot_face.stop()
        speak_response("Goodbye, take care!")
    except Exception as e:
        print(f"\n Error: {e}")
        context.clear_context()
        robot_face.stop()


if __name__ == "__main__":
    main()
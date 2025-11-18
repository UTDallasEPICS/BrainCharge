import subprocess
import json
import os
import time
import platform
from datetime import datetime
import torch
from TTS.api import TTS

CONFIG_PATH = "config.json"

if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

WHISPER_PATH = config["whisper_path"]
WHISPER_MODEL = config["whisper_model"]

TEMP_AUDIO = config["temp_audio"]
TEMP_TRANSCRIPT = config["temp_transcript"]
TEMP_RESPONSE = config.get("temp_response", "response.wav")

CONTEXT_FILE = config.get("context_file", "conversation_context.json")
SUMMARY_FILE = config.get("summary_file", "conversation_summary.json")

WAKE_WORD = config.get("wake_word", "companion").lower()
SLEEP_WORD = config.get("sleep_word", "bye companion").lower()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TTS_MODEL = TTS(config["tts_model"]).to(DEVICE)
SPEAKER = TTS_MODEL.speakers[0]

#need to look into how not not limit conversation duration and base it on when the user stops talking
LISTEN_DURATION = config.get("listen_duration", 3)
CONVERSATION_DURATION = config.get("conversation_duration", 5)


def get_audio_input_command(duration, output_file):
    """Get OS-specific ffmpeg audio recording command."""

    system = platform.system()

   #mac
   #mac testing comamnd to figure out mic ffmpeg -f avfoundation -list_devices true -i ""
    if system == "Darwin":
        return [
            "ffmpeg",
            "-f", "avfoundation",
            "-i", ":1",      
            "-t", str(duration),
            output_file,
            "-y"
        ]

    #windows
    #ffmpeg -list_devices true -f dshow -i dummy
    elif system == "Windows":
        return [
            "ffmpeg",
            "-f", "dshow",
            "-i", "audio=Microphone (Realtek Audio)",  # ur windows mic can be diff check using comamnd
            "-t", str(duration),
            output_file,
            "-y"
        ]

    #linux need to test pluse audio vs alsa and check if the extra latency is fine as alsa
    #is the lower overhead but more comptible and easier to use need to test and reserch

    #also need to look into the command
    else:
        if os.path.exists("/usr/bin/pulseaudio") or os.path.exists("/usr/bin/pactl"):
            #pulse
            return [
                "ffmpeg",
                "-f", "pulse",
                "-i", "default",
                "-t", str(duration),
                output_file,
                "-y"
            ]
        else:
            #ALSA
            return [
                "ffmpeg",
                "-f", "alsa",
                "-i", "default",
                "-t", str(duration),
                output_file,
                "-y"
            ]


class ConversationContext:
    """Manages conversation history and context with AI summarization"""
    def __init__(self, context_file, summary_file):
        self.context_file = context_file
        self.summary_file = summary_file
        self.history = self.load_context()
        self.summary = self.load_summary()
    
    def load_context(self):
        """Load full conversation history from file"""
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, "r") as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def load_summary(self):
        """Load AI-generated summary from file"""
        if os.path.exists(self.summary_file):
            try:
                with open(self.summary_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_context(self):
        """Save full conversation history to file"""
        with open(self.context_file, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def save_summary(self):
        """Save AI-generated summary to file"""
        with open(self.summary_file, "w") as f:
            json.dump(self.summary, f, indent=2)
    
    def add_exchange(self, user_input, assistant_response):
        """Add a conversation exchange to history"""
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
                capture_output=True,
                text=True,
                timeout=60
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
        """Clear all conversation data"""
        self.history = []
        self.summary = {}
        self.save_context()
        self.save_summary()

def record_audio(duration, output_file):
    """Record audio using ffmpeg with OS detection."""
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
            capture_output=True,
            text=True,
            timeout=30
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
        TTS_MODEL.tts_to_file(
            text=text, speaker=SPEAKER, language="en", file_path=TEMP_RESPONSE)
        subprocess.run(["afplay", TEMP_RESPONSE], check=True, capture_output=True)
    except Exception as e:
        print(f"Error speaking response: {e}")

def check_for_wake_word(text):
    """Check if wake word is in transcribed text"""
    return WAKE_WORD in text.lower()

def check_for_sleep_word(text):
    """Check if sleep word is in transcribed text"""
    return SLEEP_WORD in text.lower()

def continuous_conversation(context):
    """Handle continuous back-and-forth conversation until sleep word"""
    print("\n Starting conversation mode...")
    speak_response("Yes, I'm here. How can I help you?")
    
    conversation_active = True
    
    while conversation_active:
        print("\n Listening for your message...")
        
        
        if not record_audio(CONVERSATION_DURATION, TEMP_AUDIO):
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
    print("Press Ctrl+C to exit")
    
    
    context = ConversationContext(CONTEXT_FILE, SUMMARY_FILE)
    
    
    if context.history:
        print(f"\n Loaded {len(context.history)} previous exchanges")
    if context.summary:
        print(f" Loaded conversation summary from {context.summary.get('last_updated', 'unknown time')}")
        if context.summary.get('people'):
            print(f"   - {len(context.summary['people'])} people tracked")
        if context.summary.get('topics'):
            print(f"   - Topics: {', '.join(context.summary['topics'][:3])}...")
    
    try:
        while True:
            print("\n Sleeping mode - Listening for wake word...")
            
           
            if not record_audio(LISTEN_DURATION, TEMP_AUDIO):
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
        print("\n\nhutting down. Goodbye!")
        speak_response("Goodbye, take care!")
    except Exception as e:
        print(f"\n Error: {e}")

if __name__ == "__main__":
    main()
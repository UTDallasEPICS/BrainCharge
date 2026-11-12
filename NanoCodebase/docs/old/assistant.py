import whisper, requests, os, sounddevice as sd, numpy as np, tempfile, wave
import faiss
from sentence_transformers import SentenceTransformer
import torch
import json
from datetime import datetime
import time

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# use CUDA if available, with fallback to CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
whisper_model = whisper.load_model("base").to(device)

# Configuration for local llama.cpp server
llama_url = "http://127.0.0.1:5000/v1/chat/completions"

# Initial prompt for Gemma model's behavior
initial_prompt = ("You are the Caregiver Compassion Bot, a gentle, empathetic robotic companion "
                  "designed by BrainCharge to support family caregivers who face high stress and emotional fatigue. "
                  "Keep your replies conversational, brief, "
                  "and naturally worded so they sound good when spoken aloud. Avoid technical or robotic phrasing. "
                  "If the user seems stressed, respond with compassion and offer small words of comfort. "
                  "Keep responses under 3 sentences for natural conversation flow. "
                  "Use the conversation context below to provide personalized, relevant responses."
                  "Answer questions clearly and concisely in a friendly, professional tone. Do not use asterisks, do not ask new questions "
                  "or act as the user. Keep replies short to speed up inference. If unsure, admit it and suggest looking into it further.")

# location for beep sound files
current_dir = os.path.dirname(os.path.abspath(__file__))
bip_sound = os.path.join(current_dir, "assets/bip.wav")
bip2_sound = os.path.join(current_dir, "assets/bip2.wav")

# Wake / sleep + memory

WAKE_WORD = "companion"
SLEEP_WORD = "bye companion"

# how long to record while listening for wake word
LISTEN_DURATION = 3  # seconds
# how long to record each turn in active conversation
CONVERSATION_DURATION = 5  # seconds

CONTEXT_FILE = "conversation_context.json"
SUMMARY_FILE = "conversation_summary.json"

# Simple RAG docs / to be implemented after coordination with Behavioral and Brain Sciences contacts

docs = [
    "The Jetson Nano is a compact, powerful computer designed by NVIDIA for AI applications at the edge.",
    "Developers can create AI assistants in under 100 lines of Python code using open-source libraries.",
    "Retrieval Augmented Generation enhances AI responses by combining language models with external knowledge bases.",
]


# Vector Database for RAG / to be implemented after coordination with Behavioral and Brain Sciences contacts

class VectorDatabase:
    def __init__(self, dim):
        # Create FAISS index with specified dimension (384 for SentenceTransformer embeddings)
        self.index = faiss.IndexFlatL2(dim)
        self.documents = []

    # Add documents and their embeddings to the FAISS index
    def add_documents(self, docs):
        embeddings = embedding_model.encode(docs)  # Get embeddings for the docs
        self.index.add(np.array(embeddings, dtype=np.float32))  # Add them to the FAISS index
        self.documents.extend(docs)

    # Search for the top K most relevant documents based on query embedding
    def search(self, query, top_k=3):
        query_embedding = embedding_model.encode([query])[0].astype(np.float32)
        distances, indices = self.index.search(np.array([query_embedding]), top_k)
        return [self.documents[i] for i in indices[0]]


# Create a VectorDatabase and add documents to it
db = VectorDatabase(dim=384)
db.add_documents(docs)


# Conversation context & summary


class ConversationContext:
    """Manages conversation history and context with AI summarization (using llama-server)."""

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
            except Exception:
                return []
        return []

    def load_summary(self):
        if os.path.exists(self.summary_file):
            try:
                with open(self.summary_file, "r") as f:
                    return json.load(f)
            except Exception:
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
        """Use Gemma via llama-server to summarize the conversation and extract key info."""
        if not self.history:
            return

        conversation_text = "Conversation history:\n\n"
        for exchange in self.history:
            conversation_text += f"[{exchange['timestamp']}]\n"
            conversation_text += f"User: {exchange['user']}\n"
            conversation_text += f"Assistant: {exchange['assistant']}\n\n"

        summary_prompt = (
            "You are analyzing a conversation between a user and an AI assistant. "
            "Extract and summarize the following information in JSON format:\n"
            "1. Important people mentioned (names, relationships)\n"
            "2. Important dates and events mentioned\n"
            "3. Key concerns or topics discussed\n"
            "4. Emotional state patterns (stress levels, concerns)\n"
            "5. Action items or follow-ups needed\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            "{\n"
            '  \"people\": [{\"name\": \"...\", \"relationship\": \"...\", \"context\": \"...\"}],\n'
            '  \"dates\": [{\"date\": \"...\", \"event\": \"...\"}],\n'
            '  \"topics\": [\"topic1\", \"topic2\"],\n'
            '  \"emotional_patterns\": \"brief description\",\n'
            '  \"action_items\": [\"item1\", \"item2\"],\n'
            '  \"summary\": \"brief overall summary\"\n'
            "}\n\n"
            f"Conversation to analyze:\n{conversation_text}"
        )

        messages = [
            {
                "role": "system",
                "content": "You are a tool that converts conversation logs into structured JSON summaries."
            },
            {
                "role": "user",
                "content": summary_prompt
            }
        ]

        payload = {
            "model": "gemma-2-2b-it",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.0,
        }

        try:
            resp = requests.post(
                llama_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120,
            )
            if resp.status_code != 200:
                print("Summary error:", resp.status_code, resp.text)
                return

            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()

            # Strip possible ```json fences
            if "```json" in text:
                text = text.split("```json", 1)[1]
                if "```" in text:
                    text = text.split("```", 1)[0]
                text = text.strip()
            elif text.startswith("```") and "```" in text[3:]:
                text = text.split("```", 1)[1].strip()

            self.summary = json.loads(text)
            self.summary["last_updated"] = datetime.now().isoformat()
            self.save_summary()

            print("Summary generated successfully!")
            print(f"   People: {len(self.summary.get('people', []))}")
            print(f"   Topics: {len(self.summary.get('topics', []))}")
            print(f"   Action items: {len(self.summary.get('action_items', []))}")
        except Exception as e:
            print("Error generating summary:", e)

    def get_context_prompt(self):
        """Build context string using summary + recent exchanges."""
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


# Audio


# Play sound (beep) to signal recording start/stop
def play_sound(sound_file):
    os.system(f"aplay {sound_file}")


# Record audio using sounddevice, save it as a .wav file
def record_audio(filename, duration=5, fs=16000):
    play_sound(bip_sound)  # Start beep
    print(f"{duration} seconds recording started...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # Wait for the recording to complete
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(audio.tobytes())
    play_sound(bip2_sound)  # End beep
    print("recording completed")


# Whisper speech to text


# Transcribe recorded audio to text using Whisper
def transcribe_audio(filename):
    return whisper_model.transcribe(filename, language="en")['text']


# Gemma LLM calls through llama-server


def ask_llama(query, context):
    """
    Send query + RAG/conv context to local llama-server (llama.cpp) and return reply text.
    Uses OpenAI-style /v1/chat/completions with `messages`.
    """
    messages = [
        {
            "role": "system",
            "content": initial_prompt,
        },
        {
            "role": "user",
            "content": f"Context: {context}\n\nQuestion: {query}",
        },
    ]

    payload = {
        "model": "gemma-2-2b-it",
        "messages": messages,
        "max_tokens": 80,
        "temperature": 0.7,
    }

    try:
        resp = requests.post(
            llama_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
    except Exception as e:
        print("DEBUG LLM EXCEPTION:", repr(e))
        return f"Error: {e}"

    if resp.status_code != 200:
        print("DEBUG LLM ERROR:", resp.status_code)
        print("DEBUG LLM BODY:", resp.text)
        return f"Error: {resp.status_code}"

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("DEBUG PARSE ERROR:", e, resp.text)
        return "Sorry, I could not understand the language model's response."


# Generate a response using RAG (ignore until implemented) + conversation memory
def generate_agent_response(user_text, conv_context: ConversationContext | None):
    docs_context = " ".join(db.search(user_text))
    full_context = ""
    if conv_context is not None:
        full_context += conv_context.get_context_prompt()
    if docs_context:
        full_context += "\n\nRelevant technical docs:\n" + docs_context
    return ask_llama(user_text, full_context)


# text to speech with piper

def text_to_speech(text):
    os.system(
        f'echo "{text}" | /ssd/piper/build/piper '
        '--model /usr/local/share/piper/models/en_US-lessac-medium.onnx '
        '--output_file response.wav && aplay response.wav'
    )


# Wake / sleep helpers

def check_for_wake_word(text: str) -> bool:
    return WAKE_WORD.lower() in text.lower()


def check_for_sleep_word(text: str) -> bool:
    return SLEEP_WORD.lower() in text.lower()


# Conversation loops

def continuous_conversation(context: ConversationContext):
    """Handle continuous back-and-forth conversation until sleep word."""
    print("\nStarting conversation mode...")
    text_to_speech("Yes, I'm here. How can I help you?")

    conversation_active = True

    while conversation_active:
        print("\nListening for your message...")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            record_audio(tmpfile.name, duration=CONVERSATION_DURATION)
            user_input = transcribe_audio(tmpfile.name)

        if not user_input.strip():
            print("I didn't catch that. Please say that again.")
            text_to_speech("I didn't catch that. Please say that again.")
            continue

        print(f"User said: {user_input}")

        if check_for_sleep_word(user_input):
            print(f"\nSleep word '{SLEEP_WORD}' detected!")
            print("\nGenerating final conversation summary before sleep...")
            context.generate_summary()
            farewell_message = (
                "Goodbye! I'll be here when you need me. "
                "Just say the wake word to talk again."
            )
            print(f"Assistant: {farewell_message}\n")
            text_to_speech(farewell_message)
            conversation_active = False
            break

        response = generate_agent_response(user_input, context)
        print(f"Assistant: {response}\n")

        context.add_exchange(user_input, response)
        text_to_speech(response)

        time.sleep(0.5)


def main():
    """Main loop - continuously listen for wake word."""
    print("Jetson Gemma Assistant - Wake Word System")
    print(f"Wake word: '{WAKE_WORD}' - say this to start a conversation")
    print(f"Sleep word: '{SLEEP_WORD}' - say this to end the conversation")
    print("Press Ctrl+C to exit")

    context = ConversationContext(CONTEXT_FILE, SUMMARY_FILE)

    if context.history:
        print(f"\nLoaded {len(context.history)} previous exchanges")
    if context.summary:
        print(f"Loaded conversation summary from {context.summary.get('last_updated', 'unknown time')}")
        if context.summary.get('people'):
            print(f"   - {len(context.summary['people'])} people tracked")
        if context.summary.get('topics'):
            print(f"   - Topics: {', '.join(context.summary['topics'][:3])}...")

    try:
        while True:
            print("\nSleep mode - listening for wake word...")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
                record_audio(tmpfile.name, duration=LISTEN_DURATION)
                transcription = transcribe_audio(tmpfile.name)

            if transcription:
                print(f"Heard: {transcription}")
                if check_for_wake_word(transcription):
                    print(f"\nWake word '{WAKE_WORD}' detected! Entering conversation mode...\n")
                    continuous_conversation(context)
                    print("\nReturning to sleep mode...")
                    time.sleep(1)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nShutting down. Goodbye!")
        text_to_speech("Goodbye, take care!")
    except Exception as e:
        print(f"\nError in main loop: {e}")


# Entry point
if __name__ == "__main__":
    main()
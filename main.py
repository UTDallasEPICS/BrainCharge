import subprocess
import json
import os
#from piper.voice import PiperVoice
#import is this but its not working so its cooked and for the program to not crash its gotta be commented out
#there is an issue with installing piper and theres an issue with deprecations i found a link but didnt have time to look
#over it investigate here https://github.com/rhasspy/piper/issues/725


#changed the file paths to be in a json file so that there wont be tons of confusion with people changing code on main file
#so to run on your machince just change the filepaths on your config.json

with open("config.json", "r") as f:
    config = json.load(f)

WHISPER_PATH = config["whisper_path"]
WHISPER_MODEL = config["whisper_model"]
PIPER_MODEL = config["piper_model"]
TEMP_AUDIO = config["temp_audio"]
TEMP_TRANSCRIPT = config["temp_transcript"]
TEMP_RESPONSE = config["temp_response"]

# the -i is telling it to using input device :1 which for my macbook is the mic but could be diffrent for everyone
#run the command ffmpeg -f avfoundation -list_devices true -i ""
#this command will tell you what options your device has choose the one thats closest to input device you want to use

print("Recording 5 seconds of audio")
subprocess.run(["ffmpeg", "-f", "avfoundation", "-i", ":1", "-t", "5", TEMP_AUDIO, "-y"], check=True)

print("Transcribing with Whisper.cpp...")
subprocess.run([
    WHISPER_PATH,
    "-m", WHISPER_MODEL,
    "-f", TEMP_AUDIO,
    "-of", TEMP_TRANSCRIPT,
    "-otxt"
], check=True)

with open(TEMP_TRANSCRIPT + ".txt", "r") as f:
    user_text = f.read().strip()


#if we want to use a context based system here is where we would add context so we can append the msg with a context.txt

#need to prompt engineer this so that it gives output that is easily spoken instead 
#I just added basic structure of how we can do it so its easier for people to edit and change

print(f"\nYou said: {user_text}\n")

prompt_instruction = (
    "You are the Caregiver Compassion Bot, a gentle, empathetic robotic companion "
    "designed by BrainCharge to support family caregivers who face high stress and emotional fatigue. "
    "Respond with warmth, validation, and encouragement. Keep your replies conversational, brief, "
    "and naturally worded so they sound good when spoken aloud. Avoid technical or robotic phrasing. "
    "If the user seems stressed, respond with compassion and offer small words of comfort. "
    "Here is the user's message:\n\n"
)

full_prompt = prompt_instruction + user_text

#if you want to run this download this ollama model you can download some other model if you want
#but make sure its a lighter model as thats closer to the representation that we will be doing so under 4 billion parameters
#if you use a diffrent model make sure that you change the name on your version

print("Generating response with Ollama")
result = subprocess.run(
    ["ollama", "run", "gemma3:4b", full_prompt],
    capture_output=True,
    text=True
)

response = result.stdout.strip()
print(f"\nModel said: {response}\n")


#this is the last part this code should work as its super simple its just that
#there are issues with the piper install

"""
print("Speaking response...")
voice = PiperVoice.load(PIPER_MODEL)
voice.speak_to_file(response, TEMP_RESPONSE)

os.system(f"afplay {TEMP_RESPONSE}")
"""

# Temporarily using a basic TTS engine for overall functionality testing
# The voice quality isn't great, but it serves as a fallback to allow end-to-end testing
# as i continue iterating on the full system

print("Speaking response with eSpeak")
try:
    subprocess.run(["espeak", response], check=True)
except Exception as e:
    print(f"Error running eSpeak: {e}")

import subprocess
import os
from pathlib import Path

from config import (
    WHISPER_PATH,
    WHISPER_MODEL,
    TEMP_AUDIO,
    TEMP_TRANSCRIPT,
    TEMP_RESPONSE,
    ffmpeg_record_command,
    OLLAMA_MODEL,
)
#from piper.voice import PiperVoice
#import is this but its not working so its cooked and for the program to not crash its gotta be commented out
#there is an issue with installing piper and theres an issue with deprecations i found a link but didnt have time to look
#over it investigate here https://github.com/rhasspy/piper/issues/725

# Paths and recording settings now centralized in config.py for portability
PIPER_MODEL = "/Users/gwenk/piper_models/en_US-libritts-high.onnx"  # TODO: make cross-platform if re-enabled

# the -i is telling it to using input device :1 which for my macbook is the mic but could be diffrent for everyone
#run the command ffmpeg -f avfoundation -list_devices true -i ""
#this command will tell you what options your device has choose the one thats closest to input device you want to use

print("Recording audio...")
subprocess.run(ffmpeg_record_command(TEMP_AUDIO), check=True)

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
#this is also where we could prompt engineer
#need to prompt engineer this so that it gives output that is easily spoken instead

print(f"\nYou said: {user_text}\n")


#if you want to run this download this ollama model you can download some other model if you want
#but make sure its a lighter model as thats closer to the representation that we will be doing so under 4 billion parameters
#if you use a diffrent model make sure that you change the name on your version
print("Generating response with Ollama...")
result = subprocess.run([
    "ollama",
    "run",
    OLLAMA_MODEL,
    user_text,
], capture_output=True, text=True, encoding="utf-8", errors="replace")

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

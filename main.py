import subprocess
import os
#from piper.voice import PiperVoice
#import is this but its not working so its cooked and for the program to not crash its gotta be commented out
#there is an issue with installing piper and theres an issue with deprecations i found a link but didnt have time to look
#over it investigate here https://github.com/rhasspy/piper/issues/725

#change the file paths based on the spesific locations of the downloads/where your repo is at
WHISPER_PATH = "/Users/sashaankghanta/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = "/Users/sashaankghanta/whisper.cpp/models/ggml-base.en.bin"
PIPER_MODEL = "/Users/sashaankghanta/piper_models/en_US-libritts-high.onnx"
TEMP_AUDIO = "input.wav"
TEMP_TRANSCRIPT = "transcript"
TEMP_RESPONSE = "response.wav"

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
#this is also where we could prompt engineer
#need to prompt engineer this so that it gives output that is easily spoken instead

print(f"\nYou said: {user_text}\n")


#if you want to run this download this ollama model you can download some other model if you want
#but make sure its a lighter model as thats closer to the representation that we will be doing so under 4 billion parameters
#if you use a diffrent model make sure that you change the name on your version
print("Generating response with Ollama")
result = subprocess.run(
    ["ollama", "run", "gemma3:4b", user_text],
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

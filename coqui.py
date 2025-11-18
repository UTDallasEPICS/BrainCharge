import torch
from TTS.api import TTS
import subprocess

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)


for speaker in tts.speakers[:20]: 
    # TTS to a file, use a preset speaker
    print(f"For {speaker}")
    tts.tts_to_file(
    text="If you want, I can give you a ready-to-run Python script that detects available GPUs and uses the fastest local TTS automatically",
    speaker=speaker,
    language="en",
    file_path=f"./output_{speaker}.wav"
    )

    subprocess.run(["afplay", f"./output_{speaker}.wav"], check=True)
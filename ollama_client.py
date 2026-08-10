import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def call_ollama(prompt, model="gemma3:1b", json_mode=False, timeout=90):
    """Call Ollama's HTTP API and return the generated text.

    Uses the HTTP API rather than shelling out to `ollama run`: the CLI does
    its own terminal line wrapping by inserting ANSI cursor control escape
    codes into stdout once a line gets long, even when
    stdout is a pipe. Those codes were ending up baked into stored context,
    spoken TTS text, and splicing into the middle of JSON responses. The API
    returns plain text with none of that.
    """
    payload = {"model": model, "prompt": prompt, "stream": False}
    if json_mode:
        payload["format"] = "json"
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()["response"].strip()

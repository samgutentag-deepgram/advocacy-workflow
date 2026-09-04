"""Deepgram helpers: batch TTS out, word-level timings back.

Key lookup, in order: $DEEPGRAM_API_KEY, then $DEEPGRAM_ENV_FILE, then ./.env,
then any .env in a parent directory. Never printed.
"""
import os, json, wave, pathlib, urllib.request, urllib.parse

SR = 24000

def _from_env_file(p):
    try:
        for line in pathlib.Path(p).read_text().splitlines():
            if line.strip().startswith("DEEPGRAM_API_KEY="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v and v != "your_key_here":
                    return v
    except OSError:
        pass
    return None

def api_key():
    if os.environ.get("DEEPGRAM_API_KEY"):
        return os.environ["DEEPGRAM_API_KEY"]
    if os.environ.get("DEEPGRAM_ENV_FILE"):
        k = _from_env_file(os.environ["DEEPGRAM_ENV_FILE"])
        if k:
            return k
    here = pathlib.Path.cwd().resolve()
    for d in [here, *here.parents]:
        k = _from_env_file(d / ".env")
        if k:
            return k
    raise RuntimeError(
        "No Deepgram key. Set DEEPGRAM_API_KEY, or DEEPGRAM_ENV_FILE=/path/to/.env, "
        "or put DEEPGRAM_API_KEY= in a .env at or above the working directory."
    )

_KEY = None
def _key():
    global _KEY
    if _KEY is None:
        _KEY = api_key()
    return _KEY

def speak(text, voice="flux-alexis-en", timeout=180):
    """Batch TTS -> raw linear16 PCM bytes (headerless, so concatenation is trivial)."""
    q = urllib.parse.urlencode({"model": voice, "encoding": "linear16",
                                "container": "none", "sample_rate": SR})
    req = urllib.request.Request(
        f"https://api.deepgram.com/v2/speak?{q}",
        data=json.dumps({"text": text}).encode(),
        headers={"Authorization": f"Token {_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def write_wav(pcm, path, sr=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)

def words(wav_path, model="nova-3", timeout=300):
    """STT the synthesis back to get word-level timings. Batch TTS returns no timing
    metadata, so transcribing your own audio is the cheapest way to drive karaoke."""
    data = pathlib.Path(wav_path).read_bytes()
    q = urllib.parse.urlencode({"model": model, "punctuate": "true", "smart_format": "false"})
    req = urllib.request.Request(
        f"https://api.deepgram.com/v1/listen?{q}", data=data,
        headers={"Authorization": f"Token {_key()}", "Content-Type": "audio/wav"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    return j["results"]["channels"][0]["alternatives"][0]["words"]

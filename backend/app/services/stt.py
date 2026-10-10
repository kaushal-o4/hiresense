"""Local speech-to-text with Whisper (MIT license), run through Hugging Face `transformers` on the CPU.

The browser records only while the interview is in its LISTENING state and uploads one WAV clip per answer.
The clip is processed in memory and never written to disk or stored. The model (~150 MB for base.en)
downloads once, then runs offline.
"""
from __future__ import annotations

import io
import logging
import threading

from ..config import get_settings

log = logging.getLogger("hiresense.stt")

TARGET_SR = 16000
MIN_SPEECH_SECONDS = 0.4
# Whisper invents these phrases from silence or noise (it was trained on subtitled videos). Compared after
# lower-casing and removing punctuation; only discarded when there is little real speech in the clip.
HALLUCINATIONS = {
    "thank you", "thanks for watching", "thank you for watching", "thank you so much for watching", "you", "bye",
    "okay", "", "ill see you in the next video", "see you in the next video", "see you next time",
    "please subscribe", "subscribe to my channel", "dont forget to like and subscribe", "thanks for listening",
    "thank you for listening", "were going to take a look at what were doing here",
    "we are going to take a look at what we are doing here",
}
MAX_WORDS_PER_VOICED_SECOND = 5.0  # people speak ~2-3 words/s; far more text than speech means invented text


class STTUnavailable(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BadAudio(ValueError):
    pass


_asr = None
_load_error: str | None = None
_lock = threading.Lock()


def status() -> dict:
    s = get_settings()
    return {"enabled": s.stt_enabled, "engine": "whisper", "model": s.stt_model, "loaded": _asr is not None,
            "error": _load_error}


def _load():
    global _asr, _load_error
    if _asr is not None:
        return _asr
    with _lock:
        if _asr is None:
            try:
                from transformers import pipeline
                _asr = pipeline("automatic-speech-recognition", model=get_settings().stt_model, device="cpu")
                _load_error = None
            except ImportError as exc:
                _load_error = f"Speech-recognition packages are not installed ({exc.name})."
            except Exception as exc:
                _load_error = (f"Could not load the Whisper model ({type(exc).__name__}). It needs internet access "
                               "once to download.")
                log.warning("stt load failed: %s", exc)
            if _asr is None:
                raise STTUnavailable(_load_error)
    return _asr


def warmup() -> None:
    if not get_settings().stt_enabled:
        return
    try:
        _load()
    except STTUnavailable:
        pass


def decode_wav(data: bytes):
    """WAV bytes -> (mono float32 samples at 16 kHz, duration seconds). Raises BadAudio."""
    import numpy as np
    import soundfile as sf
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise BadAudio("The recording must be a WAV file.")
    try:
        audio, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception:
        raise BadAudio("The recording could not be read. Please try recording again.")
    audio = audio.mean(axis=1)
    if sr <= 0 or len(audio) == 0:
        raise BadAudio("The recording is empty.")
    if sr != TARGET_SR:
        idx = np.arange(0, len(audio), sr / TARGET_SR)
        audio = np.interp(idx, np.arange(len(audio)), audio).astype("float32")
    if not np.isfinite(audio).all():
        raise BadAudio("The recording contains invalid samples.")
    return audio, len(audio) / TARGET_SR


def speech_seconds(audio, frame_ms: int = 30, threshold_db: float = -45.0) -> float:
    """Rough voice-activity measure: total length of frames louder than `threshold_db` dBFS."""
    import numpy as np
    n = int(TARGET_SR * frame_ms / 1000)
    frames = len(audio) // n
    if frames == 0:
        return 0.0
    rms = np.sqrt((audio[: frames * n].reshape(frames, n) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    return float((db > threshold_db).sum() * frame_ms / 1000)


LONG_PAUSE_SECONDS = 1.5


def pause_profile(audio, frame_ms: int = 30, threshold_db: float = -45.0) -> dict:
    """Silent gaps BETWEEN stretches of speech (leading/trailing silence ignored), measured from the audio itself,
    so it does not depend on what the recogniser wrote. Same loudness threshold as speech_seconds()."""
    import numpy as np
    n = int(TARGET_SR * frame_ms / 1000)
    frames = len(audio) // n
    if frames == 0:
        return {"longest_pause_s": 0.0, "long_pauses": 0, "spoken_span_s": 0.0}
    rms = np.sqrt((audio[: frames * n].reshape(frames, n) ** 2).mean(axis=1) + 1e-12)
    voiced = np.flatnonzero(20 * np.log10(rms) > threshold_db)
    if len(voiced) < 2:
        return {"longest_pause_s": 0.0, "long_pauses": 0, "spoken_span_s": round(len(voiced) * frame_ms / 1000, 2)}
    gaps = (np.diff(voiced) - 1) * frame_ms / 1000  # silent seconds between consecutive voiced frames
    return {"longest_pause_s": round(float(gaps.max()), 2),
            "long_pauses": int((gaps >= LONG_PAUSE_SECONDS).sum()),
            # first word to last word: the silence before starting and after finishing is not speaking time
            "spoken_span_s": round(float((voiced[-1] - voiced[0] + 1) * frame_ms / 1000), 2)}


def _key(s: str) -> str:
    return " ".join("".join(ch for ch in s.lower() if ch.isalnum() or ch.isspace()).split())


def collapse_loops(text: str) -> str:
    """Whisper sometimes loops, writing the same sentence or phrase again and again. Keep one copy of a sentence
    repeated back to back, and of any 3-12 word phrase repeated 3+ times back to back."""
    import re
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        if not out or _key(sent) != _key(out[-1]):
            out.append(sent)
    words = " ".join(out).split()
    keys = [_key(w) for w in words]
    for n in range(12, 2, -1):
        i = 0
        while i + 3 * n <= len(words):
            reps = 1
            while keys[i + reps * n:i + (reps + 1) * n] == keys[i:i + n]:
                reps += 1
            if reps >= 3:
                del words[i + n:i + reps * n], keys[i + n:i + reps * n]
            i += 1
    return " ".join(words)


def clean_transcript(text: str, voiced: float) -> str:
    """Remove Whisper's invented text. Returns "" when nothing the speaker plausibly said remains."""
    text = collapse_loops(text)
    if _key(text) in HALLUCINATIONS and voiced < 3.0:
        return ""
    if len(text.split()) > 8 and len(text.split()) / max(voiced, 0.1) > MAX_WORDS_PER_VOICED_SECOND:
        return ""
    return text


def transcribe(data: bytes) -> dict:
    """WAV bytes -> {"text", "duration", "speech_seconds", "engine"}. Raises BadAudio / STTUnavailable."""
    s = get_settings()
    if not s.stt_enabled:
        raise STTUnavailable("Speech recognition is turned off on this server. Please type your answer.")
    audio, duration = decode_wav(data)
    if duration > s.voice_max_answer_seconds + 5:
        raise BadAudio(f"The recording is longer than {s.voice_max_answer_seconds} seconds.")
    voiced = speech_seconds(audio)
    if voiced < MIN_SPEECH_SECONDS:
        return {"text": "", "duration": round(duration, 2), "speech_seconds": round(voiced, 2), "engine": s.stt_model,
                "note": "No speech was detected. Check that the right microphone is selected and try again."}
    asr = _load()
    with _lock:
        out = asr({"raw": audio, "sampling_rate": TARGET_SR}, chunk_length_s=30, batch_size=1)
    text = clean_transcript(" ".join((out.get("text") or "").split()), voiced)
    return {"text": text[:8000], "duration": round(duration, 2), "speech_seconds": round(voiced, 2),
            **pause_profile(audio),
            "engine": s.stt_model, "note": None if text else "No clear speech was recognised. Please try again."}

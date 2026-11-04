"""Local speech-to-text with Whisper (MIT license) on the CPU.

Two engines (STT_ENGINE):
  faster       - faster-whisper (CTranslate2, int8, greedy decoding). Default: several times faster than transformers
                 on this laptop's CPU (numbers: tests_perf/bench_stt.py, README section 2e).
  transformers - the Hugging Face pipeline used before 2026-10-29. Used automatically if faster-whisper is missing.
  gemini       - hosted: the clip is sent to the Gemini API (services/gemini_llm.transcribe). For servers without
                 the Whisper/numpy packages (requirements-cloud.txt). Live captions are off with it (one request per
                 caption would use up the API quota); finished speech segments are still transcribed.

The browser records only while the interview is in its LISTENING state and uploads WAV clips (live pieces while the
candidate talks, then the last piece). Clips are processed in memory and never written to disk or stored. The model
(~150 MB for base.en) downloads once, then runs offline.
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


_asr = None  # callable(audio float32 16 kHz, prompt: str | None) -> text
_engine: str | None = None  # engine actually loaded ("faster" / "transformers")
_load_error: str | None = None
_lock = threading.Lock()


def _hosted() -> bool:
    return get_settings().stt_engine.strip().lower() == "gemini"


def status() -> dict:
    s = get_settings()
    if _hosted():
        has_key = bool(s.gemini_api_key.strip())
        return {"enabled": s.stt_enabled, "engine": "gemini", "model": "gemini", "loaded": has_key,
                "error": None if has_key else "GEMINI_API_KEY is not set.", "live_captions": False}
    return {"enabled": s.stt_enabled, "engine": _engine or s.stt_engine, "model": s.stt_model,
            "loaded": _asr is not None, "error": _load_error, "live_captions": True}


def reset() -> None:
    """Forget the loaded model (benchmarks switch engines; the next call loads again)."""
    global _asr, _engine, _load_error
    with _lock:
        _asr, _engine, _load_error = None, None, None


def _faster_name(model: str) -> str:
    # "openai/whisper-base.en" (transformers name, still in older .env files) -> "base.en"
    return model.split("/")[-1].removeprefix("whisper-") if model.startswith("openai/") else model


def _load_faster():
    from faster_whisper import WhisperModel
    s = get_settings()
    m = WhisperModel(_faster_name(s.stt_model), device="cpu", compute_type="int8", cpu_threads=s.stt_threads)

    def run(audio, prompt=None):
        # Greedy decoding and no timestamps: fastest settings; condition_on_previous_text=False avoids Whisper's
        # repetition loops on long clips.
        segments, _ = m.transcribe(audio, language="en", beam_size=1, best_of=1, temperature=0.0,
                                   condition_on_previous_text=False, without_timestamps=True,
                                   initial_prompt=prompt or None, vad_filter=False)
        return " ".join(seg.text for seg in segments)
    return run


def _load_transformers():
    from transformers import pipeline
    name = get_settings().stt_model
    pipe = pipeline("automatic-speech-recognition", model=name if "/" in name else f"openai/whisper-{name}",
                    device="cpu")

    def run(audio, prompt=None):
        return pipe({"raw": audio, "sampling_rate": TARGET_SR}, chunk_length_s=30, batch_size=1).get("text") or ""
    return run


def _load():
    global _asr, _engine, _load_error
    if _asr is not None:
        return _asr
    with _lock:
        if _asr is None:
            wanted = get_settings().stt_engine.strip().lower()
            order = ["faster", "transformers"] if wanted != "transformers" else ["transformers"]
            for engine in order:
                try:
                    _asr = _load_faster() if engine == "faster" else _load_transformers()
                    _engine, _load_error = engine, None
                    break
                except ImportError as exc:
                    _load_error = f"Speech-recognition packages are not installed ({exc.name})."
                except Exception as exc:
                    _load_error = (f"Could not load the Whisper model ({type(exc).__name__}). It needs internet "
                                   "access once to download.")
                    log.warning("stt load failed (%s): %s", engine, exc)
                if engine == "faster" and len(order) > 1:
                    log.warning("faster-whisper unavailable; using transformers for speech recognition")
            if _asr is None:
                raise STTUnavailable(_load_error)
    return _asr


def warmup() -> None:
    if not get_settings().stt_enabled or _hosted():
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


def wav_stats(data: bytes) -> tuple[float, float]:
    """(duration, speech seconds) of a PCM WAV using only the standard library (hosts without numpy/soundfile)."""
    import array
    import sys
    import wave
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise BadAudio("The recording must be a WAV file.")
    try:
        with wave.open(io.BytesIO(data)) as w:
            sr, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            frames = w.readframes(n)
    except (wave.Error, EOFError):
        raise BadAudio("The recording could not be read. Please try recording again.")
    if sr <= 0 or n == 0:
        raise BadAudio("The recording is empty.")
    duration = n / sr
    if width != 2:  # the browser recorder always sends 16-bit PCM; don't guess at other formats
        return duration, duration
    samples = array.array("h", frames[: len(frames) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    sub = samples[::ch][::max(1, sr // 4000)]  # ~4 kHz is plenty for a loudness measure
    frame = max(1, int(0.03 * len(sub) / duration))
    threshold = (10 ** (-45 / 20) * 32768) ** 2  # -45 dBFS, the same level as speech_seconds()
    loud = sum(1 for i in range(0, len(sub) - frame + 1, frame)
               if sum(x * x for x in sub[i:i + frame]) / frame > threshold)
    return duration, loud * 0.03


def _transcribe_hosted(data: bytes, prompt: str | None) -> dict:
    from . import gemini_llm
    from .local_llm import LLMError
    s = get_settings()
    duration, voiced = wav_stats(data)
    if duration > s.voice_max_answer_seconds + 5:
        raise BadAudio(f"The recording is longer than {s.voice_max_answer_seconds} seconds.")
    if voiced < MIN_SPEECH_SECONDS:
        return {"text": "", "duration": round(duration, 2), "speech_seconds": round(voiced, 2), "engine": "gemini",
                "note": "No speech was detected. Check that the right microphone is selected and try again."}
    try:
        raw = gemini_llm.transcribe(data, prompt)
    except LLMError as exc:
        raise STTUnavailable(f"Speech recognition failed: {exc.message}")
    text = clean_transcript(" ".join(raw.split()), voiced)
    return {"text": text[:8000], "duration": round(duration, 2), "speech_seconds": round(voiced, 2),
            "engine": "gemini", "note": None if text else "No clear speech was recognised. Please try again."}


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


def transcribe(data: bytes, prompt: str | None = None) -> dict:
    """WAV bytes -> {"text", "duration", "speech_seconds", "engine"}. Raises BadAudio / STTUnavailable.

    prompt: optional context (e.g. the interview question) that helps Whisper spell technical words."""
    s = get_settings()
    if not s.stt_enabled:
        raise STTUnavailable("Speech recognition is turned off on this server. Please type your answer.")
    if _hosted():
        return _transcribe_hosted(data, prompt)
    audio, duration = decode_wav(data)
    if duration > s.voice_max_answer_seconds + 5:
        raise BadAudio(f"The recording is longer than {s.voice_max_answer_seconds} seconds.")
    voiced = speech_seconds(audio)
    if voiced < MIN_SPEECH_SECONDS:
        return {"text": "", "duration": round(duration, 2), "speech_seconds": round(voiced, 2), "engine": s.stt_model,
                "note": "No speech was detected. Check that the right microphone is selected and try again."}
    asr = _load()
    with _lock:
        raw = asr(audio, prompt)
    text = clean_transcript(" ".join(raw.split()), voiced)
    return {"text": text[:8000], "duration": round(duration, 2), "speech_seconds": round(voiced, 2),
            "engine": s.stt_model, "note": None if text else "No clear speech was recognised. Please try again."}

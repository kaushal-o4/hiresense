"""Local text-to-speech with a viseme (mouth-shape) timeline for lip sync.

Engine: Kokoro-82M (Apache-2.0, https://huggingface.co/hexgrad/Kokoro-82M), running on the CPU.
Text -> phonemes with espeak-ng (bundled by the `espeakng-loader` package) -> Kokoro model.

Kokoro predicts how long each phoneme lasts (`pred_dur`, 1 unit = 600 samples = 25 ms at 24 kHz). We turn
those durations into a timeline of mouth shapes, so the avatar's lips follow the actual audio rather than a
looping animation. The model downloads once (~330 MB) from Hugging Face, then runs offline.
"""
from __future__ import annotations

import base64
import io
import logging
import re
import sys
import threading
import types
from collections import OrderedDict

from ..config import get_settings

log = logging.getLogger("hiresense.tts")

SAMPLE_RATE = 24000
SAMPLES_PER_UNIT = 600  # verified: len(audio) / sum(pred_dur) == 600 for Kokoro-82M
VOICES = {
    "af_heart": "American English, female (warm)",
    "af_bella": "American English, female (bright)",
    "af_nicole": "American English, female (soft)",
    "bf_emma": "British English, female",
    "am_michael": "American English, male",
    "bm_george": "British English, male",
}

# Technical terms espeak would mispronounce. Applied with word boundaries, case-sensitive.
PRONUNCIATIONS = [
    (r"\bPostgreSQL\b", "Postgres Q L"), (r"\bMySQL\b", "My sequel"), (r"\bNoSQL\b", "No sequel"),
    (r"\bSQLite\b", "sequel light"), (r"\bSQL\b", "sequel"), (r"\bJSON\b", "jay son"), (r"\bYAML\b", "yammel"),
    (r"\bC\+\+", "C plus plus"), (r"\bC#", "C sharp"), (r"(?<!\w)\.NET\b", "dot net"),
    (r"\b(Node|React|Vue|Next|Express)\.js\b", r"\1 J S"), (r"\bCI/CD\b", "C I C D"), (r"\bDevOps\b", "dev ops"),
    (r"\bOOPs?\b", "O O P"), (r"\bDBMS\b", "D B M S"), (r"\bRDBMS\b", "R D B M S"), (r"\bAPIs\b", "A P eyes"),
    (r"\bGUI\b", "gooey"), (r"\bUI\b", "U I"), (r"\bUX\b", "U X"), (r"\bk8s\b", "Kubernetes"),
    (r"\bnginx\b", "engine X"), (r"\bGitHub\b", "Git hub"), (r"\bLLMs?\b", "L L M"), (r"\b3NF\b", "third normal form"),
    (r"\bO\(1\)", "O of one"), (r"\bO\(n\)", "O of n"), (r"\bO\(log n\)", "O of log n"), (r"\bO\(n\^2\)", "O of n squared"),
    (r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is"), (r"\bvs\.?(?=\s)", "versus"), (r"\betc\.", "etcetera"),
    (r"&", " and "), (r"%", " percent"),
]

# Phoneme -> viseme. Viseme names follow the common 15-shape set (Oculus/ARKit style).
_VISEME_GROUPS = {
    "PP": "pbm", "FF": "fv", "TH": "θð", "DD": "tdnlɾ", "KK": "kgŋhx", "CH": "ʃʒʧʤj", "SS": "sz", "RR": "ɹrɚɝ",
    "AA": "aɑæʌɐAIW", "E": "ɛeəᵊɜ", "I": "iɪɨ", "O": "ɔoOY", "U": "uʊwᵻ",
}
PHONEME_VISEME = {p: v for v, ps in _VISEME_GROUPS.items() for p in ps}
_MODIFIERS = set("ˈˌːʰ̩̃ʲ")  # stress / length marks: extend the previous mouth shape
_PAUSES = set(" .,!?;:—…-\"'()")


class TTSUnavailable(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


_engine = None
_load_error: str | None = None
_lock = threading.Lock()
_cache: "OrderedDict[tuple, dict]" = OrderedDict()


def status() -> dict:
    s = get_settings()
    return {"enabled": s.tts_enabled, "engine": "kokoro-82m", "voice": s.tts_voice, "loaded": _engine is not None,
            "error": _load_error, "voices": VOICES}


def normalize_text(text: str) -> str:
    out = " ".join((text or "").split())
    for pattern, repl in PRONUNCIATIONS:
        out = re.sub(pattern, repl, out)
    return " ".join(out.split())


def _load():
    """Load espeak + Kokoro once per process. Raises TTSUnavailable with a readable reason."""
    global _engine, _load_error
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        try:
            import espeakng_loader
            from phonemizer.backend.espeak.wrapper import EspeakWrapper
            EspeakWrapper.set_library(espeakng_loader.get_library_path())
            EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
            # kokoro/__init__ imports its English pipeline, which imports spaCy. We only use the model class and
            # espeak phonemes, so a placeholder module is enough (spaCy has no Python 3.14 wheels yet).
            sys.modules.setdefault("spacy", types.ModuleType("spacy"))
            import torch
            if get_settings().tts_torch_threads > 0:
                torch.set_num_threads(get_settings().tts_torch_threads)
            from huggingface_hub import hf_hub_download
            from kokoro import KModel
            from misaki import espeak
            g2p = espeak.EspeakG2P(language="en-us")
            model = KModel().eval()
            voices = {}

            def voice(name):
                if name not in voices:
                    voices[name] = torch.load(hf_hub_download("hexgrad/Kokoro-82M", f"voices/{name}.pt"),
                                              weights_only=True)
                return voices[name]
            voice(get_settings().tts_voice)
            _engine = {"g2p": g2p, "model": model, "voice": voice, "torch": torch}
            _load_error = None
        except ImportError as exc:
            _load_error = f"Text-to-speech packages are not installed ({exc.name}). See README section 2."
        except Exception as exc:
            _load_error = (f"Could not load the Kokoro speech model ({type(exc).__name__}). It needs internet "
                           "access once to download.")
            log.warning("tts load failed: %s", exc)
        if _engine is None:
            raise TTSUnavailable(_load_error)
    return _engine


def warmup() -> None:
    if not get_settings().tts_enabled:
        return
    try:
        _load()
    except TTSUnavailable:
        pass


def _sentences(text: str, max_chars: int = 220) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:
        while len(p) > max_chars:  # very long sentence: split at a comma or space
            cut = max(p.rfind(",", 0, max_chars), p.rfind(" ", 0, max_chars))
            cut = cut if cut > 40 else max_chars
            out.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        if p.strip():
            out.append(p.strip())
    return out


def visemes_from_durations(phonemes: str, durations: list[int], offset_s: float = 0.0) -> list[dict]:
    """Phoneme string + Kokoro durations (with one pad unit at each end) -> [{t, d, v}] in seconds."""
    unit = SAMPLES_PER_UNIT / SAMPLE_RATE
    t = offset_s + durations[0] * unit if durations else offset_s
    timeline: list[dict] = []
    for ph, d in zip(phonemes, durations[1:-1]):
        secs = d * unit
        if ph in _MODIFIERS and timeline:
            timeline[-1]["d"] += secs
        else:
            v = "sil" if ph in _PAUSES else PHONEME_VISEME.get(ph, "E" if ph.isalpha() else "sil")
            if timeline and timeline[-1]["v"] == v:
                timeline[-1]["d"] += secs
            else:
                timeline.append({"t": t, "d": secs, "v": v})
        t += secs
    # Word gaps of a few tens of ms are not visible pauses: let the previous mouth shape carry through them.
    merged: list[dict] = []
    for seg in timeline:
        if seg["v"] == "sil" and seg["d"] < 0.06 and merged:
            merged[-1]["d"] += seg["d"]
        elif merged and merged[-1]["v"] == seg["v"]:
            merged[-1]["d"] += seg["d"]
        else:
            merged.append(seg)
    timeline = merged
    for seg in timeline:
        seg["t"], seg["d"] = round(seg["t"], 3), round(seg["d"], 3)
    return timeline


def static_phrases() -> set[str]:
    """Fixed lines that are identical for every candidate (reactions, closings, previews, the stress-interview
    interjection). Only these are cached: personalised questions are never kept in the shared cache."""
    from . import interviewers
    out = {"Let me stop you there. I have what I need."}
    for p in interviewers.INTERVIEWERS.values():
        out.update(p.reactions)
        out.update({p.closing, p.sample_line})
    return out


def is_static(text: str) -> bool:
    return " ".join((text or "").split()) in static_phrases()


def prewarm_static() -> int:
    """Synthesise every fixed phrase once (background, after the model loads) so they play instantly."""
    from . import interviewers
    n = 0
    for p in interviewers.INTERVIEWERS.values():
        for line in (*p.reactions, p.closing):
            try:
                synthesize(line, p.tts_voice, p.tts_speed, cache=True)
                n += 1
            except (TTSUnavailable, ValueError):
                return n
    return n


def split_segments(text: str) -> list[str]:
    """Sentence-sized pieces for streaming speech (short pieces start playing sooner)."""
    return _sentences(" ".join((text or "").split()))


def synthesize(text: str, voice: str | None = None, speed: float | None = None, cache: bool = False) -> dict:
    """-> {"audio_wav_b64", "sample_rate", "duration", "visemes": [{t, d, v}], "voice", "text"}.
    cache=True only for fixed phrases (see static_phrases)."""
    s = get_settings()
    if not s.tts_enabled:
        raise TTSUnavailable("Text-to-speech is turned off on this server (TTS_ENABLED=false).")
    voice = voice if voice in VOICES else s.tts_voice
    speed = min(1.4, max(0.7, float(speed or s.tts_speed)))
    clean = normalize_text(text)[:1500]
    if not clean:
        raise ValueError("Nothing to say")
    key = (clean, voice, round(speed, 2))
    if cache and key in _cache:
        _cache.move_to_end(key)
        return {**_cache[key], "cached": True}
    eng = _load()
    import numpy as np
    import soundfile as sf
    chunks, timeline, offset = [], [], 0.0
    with _lock:  # one synthesis at a time: the model is not shared safely across threads
        # Phonemise per sentence, then synthesise several sentences together (up to ~400 phonemes): Kokoro then
        # carries intonation across sentence boundaries and makes its own natural pauses, which sounds far less
        # robotic than reading one sentence at a time.
        groups, cur = [], ""
        for sentence in _sentences(clean):
            ps = eng["g2p"](sentence)
            ps = ps[0] if isinstance(ps, tuple) else ps
            ps = "".join(p for p in ps if p in eng["model"].vocab)  # same filter the model applies
            if not ps.strip():
                continue
            if cur and len(cur) + 1 + len(ps) > 400:
                groups.append(cur)
                cur = ps
            else:
                cur = f"{cur} {ps}" if cur else ps
        if cur:
            groups.append(cur)
        for ps in groups:
            ps = ps[:510]
            pack = eng["voice"](voice)
            out = eng["model"](ps, pack[len(ps) - 1], speed, return_output=True)
            audio = out.audio.numpy().astype("float32")
            durs = [int(x) for x in out.pred_dur.numpy().tolist()]
            timeline += visemes_from_durations(ps, durs, offset)
            gap = np.zeros(int(0.12 * SAMPLE_RATE), dtype="float32")  # short breath between sentences
            chunks += [audio, gap]
            offset += (len(audio) + len(gap)) / SAMPLE_RATE
    if not chunks:
        raise TTSUnavailable("The speech engine produced no audio for this text.")
    audio = np.concatenate(chunks)
    if not np.isfinite(audio).all() or float(np.abs(audio).max()) < 1e-4:
        raise TTSUnavailable("The speech engine produced silent or invalid audio.")
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    result = {"audio_wav_b64": base64.b64encode(buf.getvalue()).decode("ascii"), "sample_rate": SAMPLE_RATE,
              "duration": round(len(audio) / SAMPLE_RATE, 3), "visemes": timeline, "voice": voice,
              "text": text, "engine": "kokoro-82m", "lipsync": "phoneme-durations"}
    if cache:
        _cache[key] = result
        while len(_cache) > 96:
            _cache.popitem(last=False)
    return result

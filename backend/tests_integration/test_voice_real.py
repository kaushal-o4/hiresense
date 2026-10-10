"""REAL local voice engines (Kokoro TTS + Whisper STT). Not mocked. Run: pytest tests_integration -s -k voice"""
import base64
import io
import time

import numpy as np
import pytest
import soundfile as sf

QUESTION = ("Hello Priya. Can you walk me through how you designed the REST API for your Placement Tracker "
            "project, and why you chose PostgreSQL over MySQL?")


@pytest.fixture(scope="module")
def engines():
    from app.services import stt, tts
    try:
        tts._load()
        stt._load()
    except (tts.TTSUnavailable, stt.STTUnavailable) as exc:
        pytest.skip(f"voice engine unavailable: {exc.message}")
    return tts, stt


def _wav16k(b64: str) -> bytes:
    audio, sr = sf.read(io.BytesIO(base64.b64decode(b64)), dtype="float32")
    idx = np.arange(0, len(audio), sr / 16000)
    a16 = np.interp(idx, np.arange(len(audio)), audio).astype("float32")
    buf = io.BytesIO()
    sf.write(buf, a16, 16000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_voice_tts_audio_and_viseme_timeline(engines):
    tts, _ = engines
    t = time.monotonic()
    r = tts.synthesize(QUESTION)
    secs = time.monotonic() - t
    audio, sr = sf.read(io.BytesIO(base64.b64decode(r["audio_wav_b64"])), dtype="float32")
    rms = float(np.sqrt((audio ** 2).mean()))
    vis = r["visemes"]
    print(f"\nTTS: {secs:.1f}s to make {r['duration']}s of audio | rms={rms:.3f} | {len(vis)} viseme segments")
    print("  first visemes:", [(v["v"], v["t"]) for v in vis[:12]])
    assert sr == 24000 and rms > 0.01, "audio must be audible, not silence"
    assert abs(len(audio) / sr - r["duration"]) < 0.01
    # timeline is ordered, inside the audio, and covers most of it
    assert all(a["t"] <= b["t"] for a, b in zip(vis, vis[1:]))
    assert vis[-1]["t"] + vis[-1]["d"] <= r["duration"] + 0.05
    spoken = sum(v["d"] for v in vis if v["v"] != "sil")
    assert spoken > 0.5 * r["duration"]
    # "Placement" starts with P -> lips must close (PP) somewhere; "walk" -> rounded (U)
    shapes = {v["v"] for v in vis}
    assert {"PP", "U", "AA", "SS", "DD"} <= shapes


def test_voice_mouth_is_closed_in_pauses(engines):
    tts, _ = engines
    r = tts.synthesize("First sentence. Second sentence.")
    gap_start = None
    # between the two sentences there must be a silent (closed-mouth) moment
    for a, b in zip(r["visemes"], r["visemes"][1:]):
        if b["t"] - (a["t"] + a["d"]) > 0.08 or a["v"] == "sil":
            gap_start = a
            break
    assert gap_start is not None


def test_voice_round_trip_tts_to_stt(engines):
    tts, stt = engines
    r = tts.synthesize(QUESTION)
    t = time.monotonic()
    out = stt.transcribe(_wav16k(r["audio_wav_b64"]))
    print(f"\nSTT ({time.monotonic() - t:.1f}s): {out['text']!r} speech={out['speech_seconds']}s")
    words = set(out["text"].lower().replace(",", "").replace("?", "").replace(".", "").split())
    expected = {"walk", "through", "rest", "api", "placement", "tracker", "project"}
    assert len(expected & words) >= 6, f"transcript too different: {out['text']}"


def test_voice_silence_is_not_transcribed(engines):
    _, stt = engines
    buf = io.BytesIO()
    sf.write(buf, np.random.default_rng(0).normal(0, 0.0005, 16000 * 3).astype("float32"), 16000,
             format="WAV", subtype="PCM_16")
    out = stt.transcribe(buf.getvalue())
    assert out["text"] == "" and out["note"]

"""Voice-interview API tests. TTS/STT engines are MOCKED here (real engines: tests_integration/test_voice_real.py)."""
import io

import numpy as np
import pytest
import soundfile as sf

from conftest import login, register_student
from test_local_ai import mock_llm, question_json, eval_json  # noqa: F401  (fixture + helpers)


def wav_bytes(seconds=2.0, freq=220.0, amp=0.3, sr=16000):
    t = np.arange(int(sr * seconds)) / sr
    buf = io.BytesIO()
    sf.write(buf, (amp * np.sin(2 * np.pi * freq * t)).astype("float32"), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def start_interview(c, mock_llm):
    mock_llm.responses.append(question_json("Tell me about your final-year project."))
    r = c.post("/api/student/interviews", json={"job_role": "Developer", "category": "technical",
                                                "mode": "voice", "question_count": 3})
    assert r.status_code == 201, r.text
    return r.json()["session"]


def send(c, sid, qid, data=None):
    return c.post(f"/api/student/interviews/{sid}/transcribe", data={"question_id": str(qid)},
                  files={"audio": ("answer.wav", data if data is not None else wav_bytes(), "audio/wav")})


# --------------------------------------------------------------------------- speech output

def test_voice_endpoints_require_login(client):
    assert client.get("/api/voice/status").status_code == 401
    assert client.post("/api/voice/speak", json={"text": "hi"}).status_code == 401


def test_speak_reports_disabled_engine_honestly(client):
    register_student(client)
    r = client.post("/api/voice/speak", json={"text": "Hello"})
    assert r.status_code == 503 and "turned off" in r.json()["detail"]
    st = client.get("/api/voice/status").json()
    assert st["tts"]["enabled"] is False and st["stt"]["enabled"] is False


def test_speak_returns_audio_and_visemes(client, monkeypatch):
    from app.services import tts
    monkeypatch.setattr(tts, "synthesize", lambda text, voice=None, speed=None: {
        "audio_wav_b64": "UklGRg==", "sample_rate": 24000, "duration": 1.0,
        "visemes": [{"t": 0.0, "d": 0.2, "v": "PP"}], "voice": "af_heart", "text": text})
    register_student(client)
    r = client.post("/api/voice/speak", json={"text": "Hello", "speed": 1.1})
    assert r.status_code == 200 and r.json()["visemes"][0]["v"] == "PP"
    assert client.post("/api/voice/speak", json={"text": "x" * 1501}).status_code == 422
    assert client.post("/api/voice/speak", json={"text": "hi", "speed": 3}).status_code == 422


def test_viseme_timeline_from_durations():
    from app.services.tts import visemes_from_durations
    # "map" with stress mark: m->PP, ˈ extends PP, a->AA, p->PP ; pads 2 units each side (25 ms per unit)
    tl = visemes_from_durations("mˈap", [2, 4, 1, 6, 3, 2])
    assert [s["v"] for s in tl] == ["PP", "AA", "PP"]
    assert tl[0]["t"] == 0.05 and tl[0]["d"] == 0.125      # m (4 units) + stress mark (1 unit)
    assert tl[1]["t"] == 0.175 and tl[2]["t"] == 0.325
    # a short gap between words is merged; a long one stays as a closed mouth
    short = visemes_from_durations("a a", [1, 4, 1, 4, 1])
    long = visemes_from_durations("a. a", [1, 4, 8, 1, 4, 1])
    assert [s["v"] for s in short] == ["AA"]
    assert [s["v"] for s in long] == ["AA", "sil", "AA"]


def test_pronunciation_normalisation():
    from app.services.tts import normalize_text
    out = normalize_text("Compare MySQL vs PostgreSQL in C++ and Node.js, e.g. for CI/CD.")
    assert "My sequel" in out and "Postgres Q L" in out and "C plus plus" in out and "Node J S" in out
    assert "for example" in out and "C I C D" in out and "versus" in out


# --------------------------------------------------------------------------- speech input

def test_transcribe_mocked_then_submit_through_existing_answer_api(client, mock_llm, monkeypatch):
    from app.services import stt
    register_student(client)
    s = start_interview(client, mock_llm)
    q = s["questions"][0]
    prompts = []
    monkeypatch.setattr(stt, "transcribe", lambda data, prompt=None: prompts.append(prompt) or {
        "text": "I built a placement tracker with React and Flask for three hundred students.",
        "duration": 4.2, "speech_seconds": 3.5, "engine": "mock", "note": None})
    r = send(client, s["id"], q["id"])
    assert r.status_code == 200 and r.json()["text"].startswith("I built") and r.json()["question_id"] == q["id"]
    assert prompts == [" ".join(q["text"].split())[:300]]  # the question helps Whisper spell technical words
    # transcription alone must NOT create an answer
    assert client.get(f"/api/student/interviews/{s['id']}").json()["questions"][0]["answer"] is None
    mock_llm.responses += [eval_json(7), question_json("Why did you choose Flask?", followup=True)]
    r = client.post(f"/api/student/interviews/{s['id']}/answer", json={
        "question_id": q["id"], "answer": r.json()["text"], "input_mode": "voice"})
    ans = r.json()["session"]["questions"][0]["answer"]
    assert ans["input_mode"] == "voice" and ans["evaluation_status"] == "scored" and ans["score"] == 66.0  # 14 words: completeness capped at 5, blended in (ai.COMPLETENESS_SHARE)
    assert r.json()["session"]["questions"][1]["text"] == "Why did you choose Flask?"
    # an old recording for the answered question is refused
    assert send(client, s["id"], q["id"]).status_code == 409


def test_live_captions_have_their_own_rate_limit(client, mock_llm, monkeypatch):
    from app.routers import voice
    from app.services import stt
    register_student(client)
    s = start_interview(client, mock_llm)
    q = s["questions"][0]
    monkeypatch.setattr(stt, "transcribe", lambda data, prompt=None: {
        "text": "so far", "duration": 1.2, "speech_seconds": 1.0, "engine": "mock", "note": None})
    voice._hits.clear()
    for _ in range(300):  # a long answer sends a live caption about every 1.2 s: more than the 240 pieces limit
        r = client.post(f"/api/student/interviews/{s['id']}/transcribe",
                        data={"question_id": str(q["id"]), "partial": "true", "live": "true"},
                        files={"audio": ("live.wav", wav_bytes(), "audio/wav")})
        assert r.status_code == 200 and r.json()["live"] is True
    assert send(client, s["id"], q["id"]).status_code == 200  # the final transcription is not blocked by them
    voice._hits.clear()


def test_transcribe_rejects_wrong_question_other_student_and_recruiter(client, new_client, mock_llm):
    register_student(client, "a@test.dev")
    s = start_interview(client, mock_llm)
    assert send(client, s["id"], 999999).status_code == 409
    assert send(client, 424242, s["questions"][0]["id"]).status_code == 404
    other = new_client()
    register_student(other, "b@test.dev")
    assert send(other, s["id"], s["questions"][0]["id"]).status_code == 404
    from conftest import admin_login
    admin = new_client()
    admin_login(admin)
    assert send(admin, s["id"], s["questions"][0]["id"]).status_code == 403


def test_transcribe_when_stt_disabled_suggests_typing(client, mock_llm):
    register_student(client)
    s = start_interview(client, mock_llm)
    r = send(client, s["id"], s["questions"][0]["id"])
    assert r.status_code == 503 and "type your answer" in r.json()["detail"]


def test_transcribe_finished_interview_refused(client, mock_llm, monkeypatch):
    register_student(client)
    s = start_interview(client, mock_llm)
    client.delete(f"/api/student/interviews/{s['id']}")
    assert send(client, s["id"], s["questions"][0]["id"]).status_code == 400


def test_bad_and_silent_audio(monkeypatch):
    from app.config import get_settings
    from app.services import stt
    monkeypatch.setattr(get_settings(), "stt_enabled", True)
    with pytest.raises(stt.BadAudio):
        stt.transcribe(b"not a wav file at all, just some bytes ......................")
    with pytest.raises(stt.BadAudio):
        stt.transcribe(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 40)
    called = []
    monkeypatch.setattr(stt, "_load", lambda: called.append(1))
    out = stt.transcribe(wav_bytes(amp=0.0))  # pure silence: model is never called, no text invented
    assert out["text"] == "" and out["note"] and not called


def test_speech_activity_measure():
    from app.services.stt import decode_wav, speech_seconds
    tone, dur = decode_wav(wav_bytes(seconds=2.0, sr=24000))   # also checks resampling to 16 kHz
    assert abs(dur - 2.0) < 0.01 and speech_seconds(tone) > 1.8
    silent, _ = decode_wav(wav_bytes(seconds=2.0, amp=0.0))
    assert speech_seconds(silent) == 0

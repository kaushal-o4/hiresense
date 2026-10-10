"""Speaking practice: deterministic delivery measures, the personal practice plan, plan/retry drills and local
transcription timing. The LLM and STT are MOCKED."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from conftest import register_student
from app.services import fluency, stt


@pytest.fixture()
def llm(monkeypatch):
    from app.services import local_llm
    state = SimpleNamespace(calls=[], responses=[])

    def chat_json(system, prompt, schema, **kw):
        state.calls.append({"system": system, "prompt": prompt})
        item = state.responses.pop(0) if state.responses else None
        return local_llm.LLMResult(content=json.dumps(item), prompt_tokens=1, output_tokens=1, latency_ms=1)

    monkeypatch.setattr(local_llm, "chat_json", chat_json)
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": "mock", "running": True, "model_ready": True, "error": None})
    return state


SPEAKING = {"grammar": 7, "vocabulary": 6, "fluency": 7, "sentence_formation": 7, "relevance": 8,
            "feedback": "Clear.", "corrections": [], "sample_answer": "Sample."}


# ----------------------------------------------------------------------------- deterministic measures

def test_pause_profile_measures_gaps_between_speech_only():
    sr = stt.TARGET_SR
    tone = lambda s: 0.3 * np.sin(np.linspace(0, 2 * np.pi * 220 * s, int(sr * s))).astype("float32")  # noqa: E731
    gap = lambda s: np.zeros(int(sr * s), dtype="float32")  # noqa: E731
    audio = np.concatenate([gap(2.0), tone(1.0), gap(2.0), tone(1.0), gap(0.5), tone(1.0), gap(3.0)])
    p = stt.pause_profile(audio)
    assert 1.9 <= p["longest_pause_s"] <= 2.1 and p["long_pauses"] == 1  # leading/trailing silence ignored
    assert 5.3 <= p["spoken_span_s"] <= 5.7  # first word to last word, not the 10.5 s clip
    # regression (real recording): pace used the whole clip incl. silence after the answer -> "too slow"
    f = fluency.analyse(" ".join(["we", "built", "it"] * 4), {"duration": 26.0, "spoken_span_s": 6.0}, None)
    assert f["pace_wpm"] == 120


def test_delivery_measures_and_tips():
    text = " ".join(["we", "built", "a", "clear", "app", "for", "nurses", "today", "and", "tested", "it", "well", "too"] * 10)
    good = fluency.analyse(text, {"duration": 60, "longest_pause_s": 0.8, "long_pauses": 0}, 60)
    assert good["pace_wpm"] == 130 and good["delivery_score"] >= 95
    um = ("Um so basically I I built the app and um you know it was basically like, good and um I mean we finished "
          "it on time basically")
    bad = fluency.analyse(um, {"duration": 30, "longest_pause_s": 4.0, "long_pauses": 4}, 60)
    assert bad["fillers"] >= 8 and bad["repetitions"] == 1 and bad["delivery_score"] < good["delivery_score"]
    assert any("filler" in t for t in bad["tips"]) and any("target" in t for t in bad["tips"])
    typed = fluency.analyse("I built the bed allocation module and tested it.", None, 60)
    assert typed["timed"] is False and typed["pace_wpm"] is None and typed["long_pauses"] is None
    assert "leaves out 'um'" in typed["limitations"]
    cmp = fluency.compare(good, bad)
    assert cmp["delivery_score"] == {"before": bad["delivery_score"], "after": good["delivery_score"]}


# ----------------------------------------------------------------------------- plan

def test_plan_starts_with_a_baseline_when_there_is_no_data(client):
    register_student(client)
    plan = client.get("/api/student/exercises/plan").json()
    assert [i["id"] for i in plan["items"]] == ["baseline"]


def test_plan_uses_real_corrections_and_resume_project(client, db):
    from datetime import datetime, timezone
    from app.models import EnglishMessage, EnglishSession, Resume
    sid = register_student(client)["id"]
    s = EnglishSession(student_id=sid, topic="t", mode="text")
    s.messages = [EnglishMessage(sender="student", content="Yesterday I go to college", corrections=[
        {"original": "Yesterday I go", "corrected": "Yesterday I went to college", "explanation": "Use the past tense."}]),
        EnglishMessage(sender="student", content="Last week I meet him", corrections=[
            {"original": "I meet him", "corrected": "I met him last week", "explanation": "past tense"}])]
    db.add(s)
    db.add(Resume(student_id=sid, filename="r", stored_path="-", content_type="text/plain", raw_text="x",
                  is_current=True, analysis_status="completed", analyzed_at=datetime.now(timezone.utc),
                  analysis={"projects": [{"name": "Hospital Resources Management System"}]}))
    db.commit()
    items = {i["id"]: i for i in client.get("/api/student/exercises/plan").json()["items"]}
    mine = items["my_sentences"]
    assert "past tense" in mine["title"] and "Yesterday I went to college." in mine["prompts"]
    assert "'Yesterday I go' -> 'Yesterday I went to college'" in mine["evidence"]
    assert "Hospital Resources Management System" in items["project_pitch"]["prompts"][0]
    assert "baseline" not in items
    # a drill started from the plan uses the server-side prompt (the client only sends the item id)
    x = client.post("/api/student/exercises", json={"kind": "speaking", "plan_item": "project_pitch"}).json()
    assert "Hospital Resources Management System" in x["prompt"] and x["details"]["target_seconds"] == 60
    x = client.post("/api/student/exercises", json={"kind": "speaking", "plan_item": "my_sentences"}).json()
    assert x["kind"] == "pronunciation" and x["prompt"] in mine["prompts"]
    assert client.post("/api/student/exercises", json={"kind": "speaking", "plan_item": "nope"}).status_code == 404


# ----------------------------------------------------------------------------- drills

def wav():
    import io

    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, np.zeros(16000, dtype="float32"), 16000, format="WAV")
    return buf.getvalue()


def test_timed_drill_with_local_transcription_and_retry(client, llm, monkeypatch):
    register_student(client)
    x = client.post("/api/student/exercises", json={"kind": "speaking", "drill": "timed_answer", "level": "easy"}).json()
    assert x["details"] == {"drill": "timed_answer", "target_seconds": 60}
    said = "Um I am a final year student and um I like building web apps with Python and I I enjoy cricket"
    monkeypatch.setattr(stt, "transcribe", lambda data: {
        "text": said, "duration": 20.0, "speech_seconds": 14.0, "longest_pause_s": 2.5, "long_pauses": 2,
        "engine": "mock", "note": None})
    r = client.post(f"/api/student/exercises/{x['id']}/transcribe", files={"audio": ("a.wav", wav(), "audio/wav")})
    assert r.status_code == 200 and r.json()["text"] == said
    llm.responses.append(SPEAKING)
    done = client.post(f"/api/student/exercises/{x['id']}/submit", json={"transcript": said}).json()["exercise"]
    d = done["details"]
    assert d["fluency"] == 7 and d["delivery"]["timed"] and d["delivery"]["pace_wpm"] == 63  # AI score kept
    assert d["delivery"]["long_pauses"] == 2 and "audio_transcript" not in d and done["score"] == 70.0
    # retry: same prompt, compared with the first attempt; typed text gets no timing
    again = client.post("/api/student/exercises", json={"kind": "speaking", "retry_of": x["id"]}).json()
    assert again["prompt"] == x["prompt"] and again["details"]["retry_of"] == x["id"]
    llm.responses.append(SPEAKING)
    d2 = client.post(f"/api/student/exercises/{again['id']}/submit", json={
        "transcript": "I am a final year student who enjoys building Python web apps."}).json()["exercise"]["details"]
    assert d2["delivery"]["timed"] is False and "words" in d2["delivery"]["compared_to_previous"]


def test_edited_transcript_loses_audio_timing(client, llm, monkeypatch):
    register_student(client)
    x = client.post("/api/student/exercises", json={"kind": "speaking", "drill": "timed_answer"}).json()
    monkeypatch.setattr(stt, "transcribe", lambda data: {"text": "hello there", "duration": 3.0, "speech_seconds": 2,
                                                         "longest_pause_s": 0, "long_pauses": 0, "engine": "m", "note": None})
    client.post(f"/api/student/exercises/{x['id']}/transcribe", files={"audio": ("a.wav", wav(), "audio/wav")})
    llm.responses.append(SPEAKING)
    d = client.post(f"/api/student/exercises/{x['id']}/submit", json={
        "transcript": "A completely different, much longer typed answer about my final year project."}).json()
    assert d["exercise"]["details"]["delivery"]["timed"] is False


def test_transcribe_requires_owner_and_open_exercise(client, new_client):
    register_student(client)
    x = client.post("/api/student/exercises", json={"kind": "speaking"}).json()
    other = new_client()
    register_student(other, "o@test.dev")
    assert other.post(f"/api/student/exercises/{x['id']}/transcribe",
                      files={"audio": ("a.wav", wav(), "audio/wav")}).status_code == 404
    r = client.post(f"/api/student/exercises/{x['id']}/transcribe", files={"audio": ("a.wav", wav(), "audio/wav")})
    assert r.status_code == 503  # STT is off in tests

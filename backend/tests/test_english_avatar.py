"""Spoken-English avatar practice ("Aria"): persona output contract, live widgets, local transcription.

The LLM and STT are MOCKED here."""
from datetime import datetime, timedelta, timezone

from conftest import register_student
from test_local_ai import mock_llm  # noqa: F401  (fixture)
from test_voice import wav_bytes


def aria(reply="That sounds great! What did you enjoy most?", mode="speaking", enc="", corrections=None,
         followups=None):
    return {"reply": reply, "avatar_mode": mode, "encouragement": enc, "corrections": corrections or [],
            "suggested_followups": followups if followups is not None else ["I enjoyed...", "The best part was..."]}


def start(client, mock_llm, style="free_talk", **kw):
    mock_llm.responses.append(aria("Hi, I'm Aria! Tell me, what do you enjoy doing on weekends?", **kw))
    r = client.post("/api/student/english", json={"topic": "Hobbies", "mode": "voice", "style": style})
    assert r.status_code == 201, r.text
    return r.json()


def test_opening_uses_aria_persona_and_style(client, mock_llm):
    register_student(client)
    # even if the model invents corrections/praise for the synthetic opener, none are shown
    s = start(client, mock_llm, style="interview", enc="Nice!",
              corrections=[{"original": "practise", "corrected": "practice", "explanation": "x"}])
    assert s["style"] == "interview" and s["mode"] == "voice"
    opening = s["messages"][0]
    assert opening["sender"] == "ai" and opening["content"].startswith("Hi, I'm Aria")
    assert opening["meta"]["encouragement"] == "" and opening["meta"]["avatar_mode"] == "speaking"
    assert opening["meta"]["suggested_followups"] == ["I enjoyed...", "The best part was..."]
    assert s["confidence"] is None and s["live_active_seconds"] == 0
    system = mock_llm.calls[0]["system"]
    assert "You are Aria" in system and "Job Interview Practice" in system
    assert set(mock_llm.calls[0]["schema"]["properties"]) >= {"reply", "avatar_mode", "encouragement",
                                                              "corrections", "suggested_followups"}


def test_reply_contract_is_enforced(client, mock_llm):
    register_student(client)
    s = start(client, mock_llm)
    assert "English Free Talk" in mock_llm.calls[0]["system"]
    mock_llm.responses.append(aria(
        "Oh, you went to the market and studied React yesterday? What were you practising?",
        mode="EXCITED",  # unknown -> speaking
        enc="Great use of the word 'productive'!",
        corrections=[
            {"original": "I go to market", "corrected": "I went to the market", "explanation": "Use past tense."},
            {"original": "never said this", "corrected": "x", "explanation": "invented quote is dropped"},
            {"original": "learn React", "corrected": "learn React", "explanation": "no-op is dropped"},
            {"original": "Yesterday I go", "corrected": "Yesterday, I go", "explanation": "punctuation-only is dropped"},
        ],
        followups=["I was practising hooks", "x" * 120, "I was practising hooks", "Mostly components"]))
    r = client.post(f"/api/student/english/{s['id']}/message",
                    json={"content": "Yesterday I go to market and learn React, it was productive", "input_mode": "voice"})
    assert r.status_code == 200, r.text
    body = r.json()
    student, reply = body["messages"][-2], body["messages"][-1]
    assert [c["original"] for c in student["corrections"]] == ["I go to market"]
    assert reply["meta"] == {"avatar_mode": "speaking", "encouragement": "Great use of the word 'productive'!",
                             "suggested_followups": ["I was practising hooks", "Mostly components"]}
    assert "corrected" not in reply["content"]
    assert 0 < body["confidence"] <= 100

    mock_llm.responses.append(aria("Take your time, you're doing well. What else?", mode="encouraging"))
    body = client.post(f"/api/student/english/{s['id']}/message", json={"content": "um ok"}).json()
    assert body["messages"][-1]["meta"]["avatar_mode"] == "encouraging"


REPEATED = ("Your message was a bit repetitive but I love how you're trying to share your thoughts clearly! "
            "What's one small habit you use to stay organized in your daily life?")


def test_aria_does_not_repeat_her_previous_turn(client, mock_llm):
    """Regression (real session): the model returned the identical reply to three different answers."""
    register_student(client)
    s = start(client, mock_llm)
    mock_llm.responses.append(aria(REPEATED))
    client.post(f"/api/student/english/{s['id']}/message", json={"content": "I like to keep my desk clean"})
    fresh = "Waking up at six is impressive! What do you study first in the morning?"
    mock_llm.responses += [aria(REPEATED), aria(fresh)]  # copy -> retried -> new reply
    body = client.post(f"/api/student/english/{s['id']}/message",
                       json={"content": "I wake up early at 6 a.m. to study and go for a walk"}).json()
    assert body["messages"][-1]["content"] == fresh
    retry_prompt = mock_llm.calls[-1]["prompt"]
    assert "DIFFERENT reply" in retry_prompt and REPEATED in retry_prompt  # earlier turns listed as do-not-repeat
    assert "LATEST message" in retry_prompt and "I wake up early" in retry_prompt.split("LATEST message")[1]


def test_repeat_detection():
    from app.services.ai import repeats_earlier_turn
    assert repeats_earlier_turn(REPEATED, [REPEATED])
    # same closing question with a different opener still counts as repeating
    assert repeats_earlier_turn("Nice! What's one small habit you use to stay organized in your daily life?", [REPEATED])
    assert not repeats_earlier_turn("Waking up early is great. What do you study first?", [REPEATED])


def test_whisper_hallucinations_are_removed():
    from app.services.stt import clean_transcript, collapse_loops
    loop = " ".join(["We are going to take a look at what we are doing here."] * 6)
    assert collapse_loops(loop) == "We are going to take a look at what we are doing here."
    assert clean_transcript(loop, voiced=1.0) == ""  # known phrase from near-silence
    assert clean_transcript("I'll see you in the next video.", voiced=0.8) == ""
    real = "About my habits, I think small habits such as waking up early, cleaning my room, going on a walk."
    assert clean_transcript(real, voiced=7.0) == real
    loop3 = "and then we and then we and then we and then we went home"
    assert collapse_loops(loop3) == "and then we went home"
    # short stutters are the student's real speech (they matter for fluency) and are kept
    assert collapse_loops("I like I like coding") == "I like I like coding"
    assert collapse_loops("Yes, yes. I agree.") == "Yes, yes. I agree."
    # 40 words of text from 2 seconds of sound cannot be what the speaker said
    assert clean_transcript(" ".join(f"word{i}" for i in range(40)), voiced=2.0) == ""


def test_spoken_text_has_no_emoji():
    from app.services.ai import clean_english_reply
    out = clean_english_reply(aria("Let's practise together! 😊 How are you? ✨", enc="Nice 👍",
                                   followups=["I am fine 🙂"]), "I am good today")
    assert out["reply"] == "Let's practise together! How are you?"
    assert out["encouragement"] == "Nice" and out["suggested_followups"] == ["I am fine"]


def test_empty_model_reply_is_an_error_not_a_silent_turn(client, mock_llm):
    register_student(client)
    s = start(client, mock_llm)
    mock_llm.responses.append(aria(reply="   "))
    r = client.post(f"/api/student/english/{s['id']}/message", json={"content": "I like playing football a lot"})
    assert r.status_code == 502
    assert len(client.get(f"/api/student/english/{s['id']}").json()["messages"]) == 1  # nothing half-saved


def test_confidence_meter_rewards_longer_cleaner_spoken_answers():
    from app.models import EnglishMessage, EnglishSession
    from app.routers.english import confidence_meter

    def sess(*msgs):
        s = EnglishSession(topic="t", mode="voice")
        s.messages = [EnglishMessage(sender="ai", content="Hi?")] + list(msgs)
        return s

    assert confidence_meter(sess()) is None
    short = sess(EnglishMessage(sender="student", content="yes ok", input_mode="text",
                                corrections=[{"original": "a"}, {"original": "b"}]))
    long_ = sess(*[EnglishMessage(sender="student", input_mode="voice", corrections=[],
                                  content="I usually spend my weekends playing cricket with friends near my college "
                                          "and then we watch a movie together in the evening") for _ in range(6)])
    assert confidence_meter(short) < 25 and confidence_meter(long_) >= 90


def test_live_active_time_matches_final_verified_time(client, fake_ai, db):
    from app.models import EnglishSession
    register_student(client)
    s = client.post("/api/student/english", json={"topic": "Hobbies", "mode": "voice"}).json()
    for text in ["I enjoy playing cricket on weekends", "I also like reading novels at night"]:
        client.post(f"/api/student/english/{s['id']}/message", json={"content": text, "input_mode": "voice"})
    sess = db.get(EnglishSession, s["id"])
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    sess.created_at = base
    for m, off in zip(sorted(sess.messages, key=lambda m: m.id), [5, 60, 65, 150, 155]):
        m.created_at = base + timedelta(seconds=off)
    db.commit()
    live = client.get(f"/api/student/english/{s['id']}").json()["live_active_seconds"]
    assert live == 55 + 85
    ended = client.post(f"/api/student/english/{s['id']}/end").json()["session"]
    assert ended["active_seconds"] == live and "live_active_seconds" not in ended
    assert set(ended["scores"]) >= {"fluency", "vocabulary", "grammar", "sentence_formation"}


def test_english_stats_streak(client, db):
    from app.models import EnglishSession
    sid = register_student(client)["id"]
    assert client.get("/api/student/english/stats").json()["current_streak"] == 0
    now = datetime.now(timezone.utc)
    for days_ago, secs in [(0, 300), (1, 120), (2, 90), (4, 600), (3, 30)]:  # day 3 < 1 minute: breaks the run
        db.add(EnglishSession(student_id=sid, topic="t", mode="voice", status="completed", active_seconds=secs,
                              ended_at=now - timedelta(days=days_ago), overall_score=60 + days_ago))
    db.commit()
    st = client.get("/api/student/english/stats").json()
    assert st["current_streak"] == 3 and st["longest_streak"] == 3 and st["practiced_today"] is True
    assert st["sessions_completed"] == 5 and st["total_minutes"] == round(1140 / 60)


def test_english_transcribe_local(client, mock_llm, monkeypatch, new_client):
    from app.services import stt
    register_student(client)
    s = start(client, mock_llm)
    send = lambda c, sid: c.post(f"/api/student/english/{sid}/transcribe",  # noqa: E731
                                 files={"audio": ("reply.wav", wav_bytes(), "audio/wav")})
    r = send(client, s["id"])
    assert r.status_code == 503 and "type your answer" in r.json()["detail"]  # STT off in tests
    monkeypatch.setattr(stt, "transcribe", lambda data, prompt=None: {"text": "I like cricket", "duration": 2.0,
                                                         "speech_seconds": 1.6, "engine": "mock", "note": None})
    r = send(client, s["id"])
    assert r.status_code == 200 and r.json()["text"] == "I like cricket"
    # transcription alone never adds a message
    assert len(client.get(f"/api/student/english/{s['id']}").json()["messages"]) == 1
    other = new_client()
    register_student(other, "other@test.dev")
    assert send(other, s["id"]).status_code == 404

"""English conversation companion: learning modes, topic following, conversation memory, no repeated questions.

The LLM is MOCKED (prompts are inspected); real-model behaviour is measured by eval/run_eval.py."""
import json
from types import SimpleNamespace

import pytest

from conftest import register_student
from app.services import english_companion as ec


@pytest.fixture()
def llm(monkeypatch):
    """MOCKED local LLM (accepts any extra keyword arguments the client may pass)."""
    from app.services import local_llm
    state = SimpleNamespace(calls=[], responses=[])

    def chat_json(system, prompt, schema, **kw):
        state.calls.append({"system": system, "prompt": prompt, "schema": schema})
        item = state.responses.pop(0) if state.responses else None
        if isinstance(item, Exception):
            raise item
        return local_llm.LLMResult(content=json.dumps(item), prompt_tokens=1, output_tokens=1, latency_ms=1)

    monkeypatch.setattr(local_llm, "chat_json", chat_json)
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": "mock", "running": True, "model_ready": True, "error": None})
    return state


def turn(reply, corrections=None, topic="", changed=False, details=None, interests=None, followups=None):
    return {"reply": reply, "avatar_mode": "speaking", "encouragement": "", "corrections": corrections or [],
            "suggested_followups": followups or ["I like..."], "current_topic": topic, "topic_changed": changed,
            "new_details": details or [], "interests": interests or []}


def start(c, llm, learning_mode="free_conversation", topic="Your hobbies and weekends"):
    llm.responses.append(turn("Hi, I'm Aria! What do you usually enjoy doing in your free time?", topic=topic))
    r = c.post("/api/student/english", json={"topic": topic, "mode": "text", "learning_mode": learning_mode})
    assert r.status_code == 201, r.text
    return r.json()


def say(c, llm, s, text, *responses):
    llm.responses.extend(responses)
    r = c.post(f"/api/student/english/{s['id']}/message", json={"content": text})
    assert r.status_code == 200, r.text
    return r.json()


# ----------------------------------------------------------------------------- deterministic parts

@pytest.mark.parametrize("text, topic", [
    ("Actually, I prefer talking about technology.", "technology"),
    ("Can we talk about movies instead?", "movies"),
    ("Let's talk about cricket now", "cricket"),
    ("how about football?", "football"),
    ("I'd like to talk about my college fest please.", "college fest"),
    ("Can we change the topic to travel", "travel"),
])
def test_topic_switch_is_detected(text, topic):
    assert ec.detect_topic_switch(text) == topic


@pytest.mark.parametrize("text", ["I like playing video games.", "We talked about it yesterday.",
                                  "Let's talk about it", "Yesterday I go to college and meet my friend."])
def test_no_false_topic_switch(text):
    assert ec.detect_topic_switch(text) is None


def test_memory_tracks_topics_details_and_skips_sensitive_items():
    m = ec.empty_memory("Hobbies", "free_conversation")
    m = ec.update_memory(m, topic="Hobbies", learning_mode="free_conversation", student_text="I like video games",
                         switched_to=None, model_topic="video games", topic_changed=True,
                         new_details=["prefers story-based games", "takes medicine for anxiety"],
                         interests=["video games"], reply="Nice! What kind of games do you enjoy?")
    assert m["current_topic"] == "video games" and m["previous_topics"] == ["Hobbies"]
    assert m["important_details"] == ["prefers story-based games"]  # sensitive detail not stored
    assert m["recent_questions"] == ["What kind of games do you enjoy?"] and m["student_turns"] == 1
    m2 = ec.update_memory(m, topic="Hobbies", learning_mode="free_conversation", student_text="Can we talk about movies?",
                          switched_to="movies", reply="Sure! Which film did you see recently?")
    assert m2["current_topic"] == "movies" and m2["previous_topics"] == ["Hobbies", "video games"]
    assert "movies" in m2["candidate_interests"] and m["current_topic"] == "video games"  # pure function
    for i in range(20):
        m2 = ec.update_memory(m2, topic="t", learning_mode="free_conversation", student_text="x",
                              switched_to=None, reply=f"Question number {i}?")
    assert len(m2["recent_questions"]) == ec.MEMORY_LIMITS["recent_questions"]
    assert "Question number 19?" in ec.memory_for_prompt(m2)


def test_modes_differ_in_behaviour_config():
    free, learn, conf = (ec.MODES[k] for k in ("free_conversation", "english_learning", "confidence"))
    assert learn.spoken_correction and not free.spoken_correction and not conf.spoken_correction
    assert learn.max_corrections > free.max_corrections and free.correction_gap_turns > 0
    assert conf.tts_speed < 1 and conf.listen_silence_ms > free.listen_silence_ms


# ----------------------------------------------------------------------------- through the API

def test_start_stores_mode_and_memory_and_uses_companion_persona(client, llm):
    register_student(client)
    s = start(client, llm, "confidence")
    assert s["learning_mode"] == "confidence" and s["learning_mode_settings"]["tts_speed"] == 0.85
    assert s["memory"]["current_topic"] and s["memory"]["important_details"] == []  # synthetic opener not stored
    system = llm.calls[0]["system"]
    assert "conversation partner" in system and "You are NOT conducting an interview" in system
    assert "Learning mode: CONFIDENCE" in system
    schema = llm.calls[0]["schema"]
    assert set(schema["required"]) >= {"reply", "current_topic", "topic_changed", "new_details", "interests"}


def test_interview_style_is_isolated_from_free_talk(client, llm):
    register_student(client)
    llm.responses.append(turn("Hello! Tell me about yourself."))
    client.post("/api/student/english", json={"topic": "Tell me about yourself", "style": "interview"})
    llm.responses.append(turn("Hi! What do you enjoy?"))
    client.post("/api/student/english", json={"topic": "Games", "style": "free_talk"})
    interview, free = llm.calls[0]["system"], llm.calls[1]["system"]
    assert "Job Interview Practice" in interview and "AI interviewer" in interview
    assert "Job Interview Practice" not in free and "AI interviewer" not in free and "English Free Talk" in free


def test_topic_switch_is_followed_and_enforced(client, llm):
    register_student(client)
    s = start(client, llm)
    s = say(client, llm, s, "I like story based games where choices change the ending.",
            turn("Choices that change the ending are fun. Would you prefer several endings or one powerful ending?",
                 topic="story-based video games", changed=True, details=["likes games where choices change the ending"],
                 interests=["video games"]))
    assert s["memory"]["current_topic"] == "story-based video games"
    # the model ignores the requested topic -> regenerated once with an explicit instruction
    s = say(client, llm, s, "Actually, I prefer talking about movies now.",
            turn("Games are great. What else do you like about choices in games?"),
            turn("Sure, movies it is! What kind of films do you enjoy watching on a weekend?", topic="movies"))
    assert "movies" in llm.calls[-2]["prompt"] and "wants to talk about movies" in llm.calls[-2]["prompt"]
    assert "ignored the student's request" in llm.calls[-1]["prompt"]
    assert "films" in s["messages"][-1]["content"]
    mem = s["memory"]
    assert mem["current_topic"] == "movies" and "story-based video games" in mem["previous_topics"]
    assert "likes games where choices change the ending" in mem["important_details"]
    # the memory (not the whole transcript) carries earlier details into later prompts
    say(client, llm, s, "I watched a science fiction movie.", turn("Nice. What was the story about?", topic="movies"))
    assert "likes games where choices change the ending" in llm.calls[-1]["prompt"]


def test_paraphrased_question_is_rejected_by_meaning(client, llm, fake_embeddings):
    register_student(client)
    s = start(client, llm)
    s = say(client, llm, s, "I like playing video games.", turn("Nice! What kind of games do you enjoy playing?"))
    s = say(client, llm, s, "Mostly story games.",
            turn("Cool. What kind of games do you enjoy playing most?"),  # paraphrase -> retried
            turn("Story games can be moving. Which game's ending surprised you the most?"))
    assert "DIFFERENT reply" in llm.calls[-1]["prompt"]
    assert s["messages"][-1]["content"].startswith("Story games")


def test_free_conversation_spaces_out_corrections(client, llm):
    register_student(client)
    s = start(client, llm)
    fix = lambda o, f: {"original": o, "corrected": f, "explanation": "Use the past tense."}  # noqa: E731
    s = say(client, llm, s, "Yesterday I go to college and meet my friend.",
            turn("Sounds fun! What did you and your friend do there?",
                 corrections=[fix("I go", "I went"), fix("meet my friend", "met my friend")]))
    student = s["messages"][-2]
    assert [c["original"] for c in student["corrections"]] == ["I go"]  # at most one in free conversation
    assert "natural way" not in s["messages"][-1]["content"]  # never spoken in free conversation
    s = say(client, llm, s, "We play cricket and eat samosa.",
            turn("Cricket and samosas, perfect! Who won?", corrections=[fix("We play", "We played")]))
    assert s["messages"][-2]["corrections"] == []  # too soon after the last correction
    assert s["memory"]["practising"] == ["past tense"]


def test_learning_mode_speaks_a_gentle_correction_and_continues(client, llm):
    register_student(client)
    s = start(client, llm, "english_learning")
    assert "Learning mode: ENGLISH LEARNING" in llm.calls[0]["system"]
    s = say(client, llm, s, "Yesterday I go to college and meet my friend.",
            turn("I understood you perfectly! What did you and your friend do there?",
                 corrections=[{"original": "Yesterday I go to college and meet my friend",
                               "corrected": "Yesterday, I went to college and met my friend",
                               "explanation": "Use the past tense for yesterday."}]))
    reply = s["messages"][-1]["content"]
    assert 'A more natural way to say that is: "Yesterday, I went to college and met my friend." ' in reply
    assert reply.endswith("What did you and your friend do there?")
    # the same correction is not given twice
    s = say(client, llm, s, "Yesterday I go to college and meet my friend again.",
            turn("Again? What happened this time?",
                 corrections=[{"original": "Yesterday I go to college and meet my friend",
                               "corrected": "Yesterday, I went to college and met my friend", "explanation": "x"}]))
    assert s["messages"][-2]["corrections"] == [] and "natural way" not in s["messages"][-1]["content"]


def test_bad_corrections_from_the_real_model_are_dropped():
    """Regressions from the real-model eval: a British spelling 'corrected', and a long rewrite of 'one match'."""
    from app.services.ai import clean_english_reply
    out = clean_english_reply(turn("Nice!", corrections=[
        {"original": "I practise it every evening", "corrected": "I practice it every evening", "explanation": "x"},
        {"original": "one match", "corrected": "you mentioned a match with close final overs", "explanation": "x"},
        {"original": "my favourite colour", "corrected": "my favorite color", "explanation": "x"},
        {"original": "he give me", "corrected": "he gave me", "explanation": "Past tense."}]),
        "I practise it every evening and um yes one match, my favourite colour, he give me")
    assert [c["corrected"] for c in out["corrections"]] == ["he gave me"]


def test_repeated_reply_opener_is_dropped():
    from app.services.ai import drop_repeated_opener
    earlier = ["I love that you mentioned video games! What kind do you play?"]
    assert drop_repeated_opener("I love that you mentioned movies! Which film did you watch most recently?", earlier) \
        == "Which film did you watch most recently?"
    keep = "I love that! Why?"  # too little would be left: keep it
    assert drop_repeated_opener(keep, earlier) == keep
    assert drop_repeated_opener("Movies are fun. Which film did you watch recently at home?", earlier).startswith("Movies")
    # regression (real-model eval, confidence mode): the student's "um" was echoed back
    assert drop_repeated_opener("Um yes one match? Which match was it?", []) == "Yes one match? Which match was it?"
    assert drop_repeated_opener("Umbrellas are useful. Why?", []).startswith("Umbrellas")


def test_companion_config_endpoint(client):
    register_student(client)
    cfg = client.get("/api/student/english/companion").json()
    assert cfg["id"] == "english_companion" and cfg["interview_pressure"] == "none"
    assert [m["id"] for m in cfg["modes"]] == ["free_conversation", "english_learning", "confidence"]


def test_old_sessions_without_memory_still_work(client, llm, db):
    from app.models import EnglishSession
    register_student(client)
    s = start(client, llm)
    row = db.get(EnglishSession, s["id"])
    row.memory, row.learning_mode = None, None
    db.commit()
    s = say(client, llm, s, "I like cricket.", turn("Cricket! Do you prefer watching or playing?", topic="cricket"))
    assert s["learning_mode"] == "free_conversation" and s["memory"]["current_topic"] == "Your hobbies and weekends"
    db.expire_all()
    assert db.get(EnglishSession, s["id"]).memory["student_turns"] == 1


# ----------------------------------------------------------------------------- streamed replies

def parse_sse(text):
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


def test_streamed_reply_sends_growing_text_then_the_saved_session(client, llm, monkeypatch):
    from app.services import local_llm
    c = client
    register_student(c)
    s = start(c, llm)
    reply = "That sounds fun! Which game did you play last?"
    full = json.dumps(turn(reply))

    def streaming(system, prompt, schema, *, on_delta=None, **kw):
        for i in range(10, len(full) + 10, 10):  # the way Ollama delivers it: a few characters at a time
            if on_delta:
                on_delta(full[:i])
        return local_llm.LLMResult(content=full, prompt_tokens=1, output_tokens=1, latency_ms=1)

    monkeypatch.setattr(local_llm, "chat_json", streaming)
    r = c.post(f"/api/student/english/{s['id']}/message/stream", json={"content": "I played games yesterday."})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    names = [n for n, _ in events]
    assert names[-1] == "done" and names.count("done") == 1 and "error" not in names
    texts = [d["text"] for n, d in events if n == "delta"]
    assert texts and all(reply.startswith(t) for t in texts) and texts[-1] == reply
    msgs = events[-1][1]["session"]["messages"]
    assert msgs[-1]["content"] == reply and msgs[-2]["content"] == "I played games yesterday."
    # the same turn is saved exactly once and can be reloaded
    assert len(c.get(f"/api/student/english/{s['id']}").json()["messages"]) == len(msgs)


def test_streamed_reply_reports_model_failure_without_saving(client, llm):
    from app.services import ai
    c = client
    register_student(c)
    s = start(c, llm)
    llm.responses.append(ai.local_llm.LLMError("Ollama is not running.", kind="not_running"))
    r = c.post(f"/api/student/english/{s['id']}/message/stream", json={"content": "Hello there my friend."})
    events = parse_sse(r.text)
    assert [n for n, _ in events] == ["error"] and events[0][1]["status"] == 503
    assert len(c.get(f"/api/student/english/{s['id']}").json()["messages"]) == 1  # only Aria's opening


def test_streamed_reply_is_private_to_the_owner(client, new_client, llm):
    register_student(client)
    s = start(client, llm)
    other = new_client()
    register_student(other, email="other@test.dev")
    r = other.post(f"/api/student/english/{s['id']}/message/stream", json={"content": "Hello there my friend."})
    assert r.status_code == 404

"""Recurring-mistake profile for the English companion. The language model is mocked."""
import json
from types import SimpleNamespace

import pytest

from conftest import register_student
from app.services import english_profile as ep


@pytest.mark.parametrize("original, corrected, category", [
    ("Yesterday I go to college.", "Yesterday I went to college.", "verb_tense"),
    ("I play football yesterday.", "I played football yesterday.", "verb_tense"),
    ("Yesterday I go to college and meet my friend.", "Yesterday I went to college and met my friend.", "verb_tense"),
    ("I bought car.", "I bought a car.", "articles"),
    ("She is a engineer.", "She is an engineer.", "articles"),
    ("I am good in cricket.", "I am good at cricket.", "prepositions"),
    ("He go to school.", "He goes to school.", "subject_verb_agreement"),
    ("They was happy.", "They were happy.", "subject_verb_agreement"),
])
def test_classify_known_patterns(original, corrected, category):
    assert ep.classify(original, corrected) == category


@pytest.mark.parametrize("original, corrected", [
    ("I like games", "I like games"),                                  # no change
    ("I like games.", "I like games!"),                                # punctuation only
    ("Me and friend go market", "My friend and I went to the market"),  # a rewrite, not one identifiable mistake
    ("I recieve it.", "I receive it."),                                # spelling
    ("", "Hello"),
])
def test_classify_does_not_guess(original, corrected):
    assert ep.classify(original, corrected) is None


@pytest.fixture()
def llm(monkeypatch):
    from app.services import local_llm
    state = SimpleNamespace(prompts=[], correction=None)

    def chat_json(system, prompt, schema, **kw):
        state.prompts.append(prompt)
        corrections = [state.correction] if state.correction else []
        return local_llm.LLMResult(content=json.dumps({
            "reply": "That sounds good. What did you do next?", "avatar_mode": "speaking", "encouragement": "",
            "corrections": corrections, "suggested_followups": ["I..."], "current_topic": "", "topic_changed": False,
            "new_details": [], "interests": []}), prompt_tokens=1, output_tokens=1, latency_ms=1)

    monkeypatch.setattr(local_llm, "chat_json", chat_json)
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": "mock", "running": True, "model_ready": True, "error": None})
    return state


def new_session(c, learning_mode="english_learning"):
    r = c.post("/api/student/english", json={"topic": "weekends", "mode": "text", "learning_mode": learning_mode})
    assert r.status_code == 201, r.text
    return r.json()


def say(c, s, text, original, corrected):
    c.llm.correction = {"original": original, "corrected": corrected, "explanation": "Past tense."}
    r = c.post(f"/api/student/english/{s['id']}/message", json={"content": text})
    assert r.status_code == 200, r.text


def test_a_pattern_becomes_recurring_only_after_enough_corrections_in_enough_sessions(client, llm):
    client.llm = llm
    register_student(client)
    s1 = new_session(client)
    for i in range(3):  # three corrections in ONE session: counted, not yet recurring
        say(client, s1, f"Yesterday I go to college {i}.", f"Yesterday I go to college {i}.",
            f"Yesterday I went to college {i}.")
    p = client.get("/api/student/english/profile").json()["patterns"]
    assert len(p) == 1 and p[0]["category"] == "verb_tense" and p[0]["count"] == 3 and p[0]["sessions"] == 1
    assert p[0]["recurring"] is False
    assert not any("keeps making mistakes" in x for x in llm.prompts)

    s2 = new_session(client)
    say(client, s2, "Last week I meet him.", "Last week I meet him.", "Last week I met him.")
    p = client.get("/api/student/english/profile").json()["patterns"][0]
    assert p["count"] == 4 and p["sessions"] == 2 and p["recurring"] is True
    say(client, s2, "Then I eat dinner.", "Then I eat dinner.", "Then I ate dinner.")
    assert "keeps making mistakes with: Verb tense" in llm.prompts[-1]


def test_the_note_is_not_sent_in_other_learning_modes(client, llm):
    client.llm = llm
    register_student(client)
    for _ in range(2):
        s = new_session(client)
        for i in range(2):
            say(client, s, f"I go there {i}.", f"I go there {i}.", f"I went there {i}.")
    assert client.get("/api/student/english/profile").json()["patterns"][0]["recurring"] is True
    free = new_session(client, "free_conversation")
    say(client, free, "I like movies.", "I like movies.", "I like movies.")
    assert "keeps making mistakes" not in llm.prompts[-1]


def test_student_can_dismiss_and_clear_and_cannot_touch_anothers(client, new_client, llm):
    client.llm = llm
    register_student(client)
    s = new_session(client)
    say(client, s, "I go there.", "I go there.", "I went there.")
    pid = client.get("/api/student/english/profile").json()["patterns"][0]["id"]

    other = new_client()
    register_student(other, email="other@test.dev")
    assert other.get("/api/student/english/profile").json()["patterns"] == []
    assert other.post(f"/api/student/english/profile/{pid}/dismiss").status_code == 404

    assert client.post(f"/api/student/english/profile/{pid}/dismiss").json()["patterns"] == []
    say(client, s, "I go there again.", "I go there again.", "I went there again.")  # stays dismissed
    assert client.get("/api/student/english/profile").json()["patterns"] == []
    assert client.delete("/api/student/english/profile").json()["patterns"] == []


def test_deleting_a_session_keeps_the_learning_profile(client, llm):
    client.llm = llm
    register_student(client)
    s = new_session(client)
    say(client, s, "I go there.", "I go there.", "I went there.")
    assert client.delete(f"/api/student/english/{s['id']}").status_code in (200, 204)
    assert len(client.get("/api/student/english/profile").json()["patterns"]) == 1

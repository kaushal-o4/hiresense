"""Interviewer personalities: selection list, per-personality behaviour, fair scoring and the report.

The LLM is MOCKED (prompts are inspected); real-model checks are in tests_integration and tests_e2e."""
import pytest

from conftest import register_student
from test_local_ai import eval_json, feedback_json, mock_llm, question_json  # noqa: F401  (fixture + helpers)


def start(c, mock_llm, interviewer, **over):
    mock_llm.responses.append(question_json("Explain how you used Python in your project."))
    body = {"job_role": "Python Developer", "category": "technical", "question_count": 3, "difficulty": "medium",
            "mode": "voice", "interviewer": interviewer, **over}
    r = c.post("/api/student/interviews", json=body)
    assert r.status_code == 201, r.text
    return r.json()["session"]


def answer(c, mock_llm, s, text, score, next_q="Next question?"):
    q = s["questions"][-1]
    mock_llm.responses += [eval_json(score), question_json(next_q, followup=True), feedback_json()]
    r = c.post(f"/api/student/interviews/{s['id']}/answer",
               json={"question_id": q["id"], "answer": text, "input_mode": "voice", "response_seconds": 40,
                     "speech_seconds": 20.0})
    assert r.status_code == 200, r.text
    return r.json()["session"]


def test_interviewer_list_is_public_but_prompts_stay_private(client):
    assert client.get("/api/interviewers").status_code == 401
    register_student(client)
    items = client.get("/api/interviewers").json()
    assert [i["id"] for i in items] == ["aria", "victor", "marcus", "elena"]
    for i in items:
        assert i["name"] and i["description"] and i["voice_description"] and i["sample_line"] and i["greeting"]
        assert i["ui"]["model"].endswith(".glb") and i["tts_voice"] and i["categories"] and i["filters"]
        assert not {"persona_prompt", "question_strategy", "followup_policy", "feedback_style"} & set(i)
    assert len({i["ui"]["model"] for i in items}) == 4 and len({i["tts_voice"] for i in items}) == 4
    assert {f for i in items for f in i["filters"]} == {"friendly", "standard", "strict", "stress", "hr", "english"}
    marcus = next(i for i in items if i["id"] == "marcus")
    assert marcus["interrupts"] and marcus["answer_seconds"] < 120 and marcus["tts_speed"] > 1


def test_default_is_aria_and_unknown_interviewer_rejected(client, mock_llm):
    register_student(client)
    mock_llm.responses.append(question_json("Tell me about yourself."))
    s = client.post("/api/student/interviews", json={"job_role": "Developer", "question_count": 3}).json()["session"]
    assert s["interviewer"] == "aria"
    r = client.post("/api/student/interviews", json={"job_role": "Developer", "interviewer": "hal9000"})
    assert r.status_code == 422


@pytest.mark.parametrize("who, expect", [
    ("aria", "friendly, supportive and patient"),
    ("victor", "strict, formal technical interview"),
    ("marcus", "controlled stress interview"),
    ("elena", "professional HR interviewer"),
])
def test_each_personality_gets_its_own_instructions(client, mock_llm, who, expect):
    register_student(client)
    s = start(client, mock_llm, who)
    assert s["interviewer"] == who
    system, prompt = mock_llm.calls[-1]["system"], mock_llm.calls[-1]["prompt"]
    assert expect in system
    assert "Professional boundaries" in system and "CLAIM" in system  # same boundaries for everyone
    assert f"spoken aloud by {who.capitalize()}" in prompt


def test_greeting_is_not_repeated_in_the_question():
    """Regression (real model): Aria's first question started 'Hi Priya! I'm Aria...' after her spoken greeting."""
    from app.services.ai import strip_greeting
    q = ("Hi Priya! I'm Aria, your interviewer today. Let's start with something simple - can you tell me how "
         "you'd explain REST API design?")
    assert strip_greeting(q).startswith("Let's start with something simple")
    assert strip_greeting("Hello, and welcome. Good morning! What is a database index?") == "What is a database index?"
    assert strip_greeting("How do you handle authentication in Flask?") == "How do you handle authentication in Flask?"
    assert strip_greeting("Hi there!") == "Hi there!"  # nothing left: keep the original


def test_followup_and_hint_policies_differ(client, mock_llm):
    register_student(client, "a@test.dev")
    # Aria: weak answer -> gentle explanation + simpler follow-up
    s = start(client, mock_llm, "aria")
    answer(client, mock_llm, s, "Python is a language I used a bit for things in my project.", 3)
    aria_q_prompt = mock_llm.calls[-2]["prompt"]
    assert "give a short, kind 1-2 sentence explanation" in aria_q_prompt
    client.delete(f"/api/student/interviews/{s['id']}")
    # Victor: weak answer -> no explanation, ask to clarify
    s = start(client, mock_llm, "victor")
    answer(client, mock_llm, s, "Python is a language I used a bit for things in my project.", 3)
    victor_q_prompt = mock_llm.calls[-2]["prompt"]
    assert "do not explain the answer" in victor_q_prompt and "kind 1-2 sentence" not in victor_q_prompt
    client.delete(f"/api/student/interviews/{s['id']}")
    # Victor: decent answer -> demands specifics when vague (his follow-up policy is in the prompt)
    s = start(client, mock_llm, "victor")
    answer(client, mock_llm, s, "I wrote a Flask API with SQLAlchemy models and pytest tests for the endpoints.", 6)
    assert "Be specific" in mock_llm.calls[-2]["prompt"]
    client.delete(f"/api/student/interviews/{s['id']}")
    # Elena: STAR-based follow-ups
    s = start(client, mock_llm, "elena", category="behavioral")
    answer(client, mock_llm, s, "In my team project we disagreed about the database and I talked to everyone.", 6)
    assert "situation, their own action, or the result" in mock_llm.calls[-2]["prompt"]


def test_scores_do_not_depend_on_the_interviewer(client, mock_llm):
    register_student(client)
    results = {}
    for who in ("aria", "victor", "marcus", "elena"):
        s = start(client, mock_llm, who)
        s = answer(client, mock_llm, s, "I used Python with pandas to clean and analyse attendance data for my "
                                        "college project and plotted trends with matplotlib.", 7)
        scoring_call = next(c for c in mock_llm.calls if "answers_the_question" in c["prompt"] and c is mock_llm.calls[-3])
        assert "personality never changes how you score" in scoring_call["system"]
        assert "must NOT lower relevance, correctness or completeness" in scoring_call["system"]
        results[who] = s["questions"][0]["answer"]["score"]
        assert who.capitalize() in mock_llm.calls[-1]["prompt"]  # feedback written in the interviewer's voice
        client.delete(f"/api/student/interviews/{s['id']}")
    assert len(set(results.values())) == 1, results


def test_difficulty_steps_depend_on_interviewer(client, mock_llm):
    register_student(client)
    # 70/100: below Aria's "harder" threshold (75), at Victor's (70)
    text = ("I wrote a decorator in Python that wraps each Flask view, measures how long it takes, and logs the "
            "route name and duration so we could find slow endpoints in our placement portal project.")
    s = start(client, mock_llm, "aria")
    s = answer(client, mock_llm, s, text, 7)
    assert s["questions"][0]["answer"]["score"] == 70.0 and s["questions"][1]["difficulty"] == "medium"
    client.delete(f"/api/student/interviews/{s['id']}")
    s = start(client, mock_llm, "victor")
    s = answer(client, mock_llm, s, text, 7)
    assert s["questions"][1]["difficulty"] == "hard"
    assert s["questions"][0]["answer"]["details"]["next_difficulty"] == "hard"  # shown to the student, consistent


def test_report_has_dimensions_indicators_and_closing_remarks(client, mock_llm):
    register_student(client)
    s = start(client, mock_llm, "victor", question_count=3)
    s = answer(client, mock_llm, s, "Um, I used Python and Flask to build the REST API for the placement app, "
                                    "uh, with SQLAlchemy and JWT auth, and I wrote pytest tests.", 8)
    s = answer(client, mock_llm, s, "I don't know", 1)
    q = s["questions"][-1]
    mock_llm.responses += [eval_json(6), feedback_json(missing_concepts=["Indexing"])]
    r = client.post(f"/api/student/interviews/{s['id']}/answer", json={
        "question_id": q["id"], "answer": "I would add an index on the email column and check the plan with "
                                          "EXPLAIN before and after.", "input_mode": "text", "interrupted": True})
    assert r.json()["ready_to_complete"]
    mock_llm.responses.append({"summary": "Solid technical base.", "strengths": ["Flask"], "weaknesses": ["Depth"],
                               "suggestions": ["Explain trade-offs"], "recommended_practice": ["3 SQL questions"],
                               "closing_remarks": "Your Flask answer was precise. 🙂 Work on depth."})
    done = client.post(f"/api/student/interviews/{s['id']}/complete").json()["session"]
    rep = done["report"]
    assert rep["closing_remarks"] == "Your Flask answer was precise. Work on depth."  # spoken: no emoji
    assert "Victor" in mock_llm.calls[-1]["prompt"] and "psychological" in mock_llm.calls[-1]["system"]
    assert set(rep["dimensions"]) == {"technical_knowledge", "relevance", "answer_structure", "communication_clarity"}
    assert rep["dimensions"]["technical_knowledge"] is not None
    ind = rep["indicators"]
    assert ind["answers"] == 3 and ind["spoken_answers"] == 2 and ind["very_short_answers"] == 1
    assert ind["stopped_at_time_limit"] == 1 and ind["speaking_pace_wpm"] and "not a measure" in ind["limitations"]
    assert "Indexing" in rep["suggested_topics"] or "Edge cases" in rep["suggested_topics"]
    assert rep["recommended_next"]["difficulty"] in ("easy", "medium", "hard")
    assert rep["recommended_next"]["interviewer"] in ("aria", "victor", "marcus", "elena")
    assert [x["position"] for x in rep["question_scores"]] == [1, 2, 3]


def test_revision_topics_are_deduplicated():
    """Regression (real run): near-identical missing concepts were listed separately."""
    from app.services.report_metrics import _near
    assert _near("Specific middleware implementation for security", "Specific middleware implementation details")
    assert _near("Token validation", "token validation.")
    assert not _near("Database indexing", "Authentication token handling mechanism")


def test_report_numbers_survive_ai_outage(client, mock_llm):
    from app.services.local_llm import LLMError
    register_student(client)
    s = start(client, mock_llm, "elena", question_count=3)
    for _ in range(2):
        s = answer(client, mock_llm, s, "When our project deadline moved, I split the work and we delivered on time.", 7)
    q = s["questions"][-1]
    mock_llm.responses += [eval_json(7), feedback_json()]
    client.post(f"/api/student/interviews/{s['id']}/answer", json={
        "question_id": q["id"], "answer": "When a teammate left mid-project I stayed calm, re-planned the remaining "
                                          "tasks with the team, and we still delivered the demo on time."})
    mock_llm.responses.append(LLMError("down", kind="not_running"))
    done = client.post(f"/api/student/interviews/{s['id']}/complete").json()["session"]
    assert done["report_status"] == "unavailable" and done["report"]["dimensions"]["relevance"] == 70.0

"""Interview intelligence wired into the interview API: resume-grounded prompts, answer signals, coverage,
duplicate rejection with retries, fallbacks and per-personality behaviour. The LLM is MOCKED (prompts are inspected);
real-model behaviour is measured by eval/run_eval.py."""
from datetime import datetime, timezone

import pytest

from conftest import register_student
from test_local_ai import eval_json, mock_llm  # noqa: F401  (fixture + helper)

ANALYSIS = {
    "candidate_summary": "Final-year student who built a hospital resource management web app.",
    "skills": [{"name": "Python", "category": "programming_language"}, {"name": "Django", "category": "framework"}],
    "projects": [{"name": "Hospital Resources Management System",
                  "description": "Django app tracking beds and oxygen; built the bed-allocation module.",
                  "technologies": ["Python", "Django"]}],
    "internships": [], "experience": [], "education": [], "recommended_topics": ["input validation"],
}


def q(text, topic="", aspect="overview", kind="new_topic", followup=False, qtype="project"):
    return {"preface": "", "question": text, "question_type": qtype, "is_followup": followup, "topic": topic,
            "aspect": aspect, "followup_kind": kind}


@pytest.fixture()
def student(client, db):
    from app.models import Resume
    sid = register_student(client)["id"]
    db.add(Resume(student_id=sid, filename="r.pdf", stored_path="-", content_type="application/pdf", raw_text="x",
                  is_current=True, analysis_status="completed", analysis=ANALYSIS,
                  analyzed_at=datetime.now(timezone.utc)))
    db.commit()
    return sid


def start(client, mock_llm, first, interviewer="aria", **over):
    mock_llm.responses.append(first)
    body = {"job_role": "Python Developer", "category": "technical", "question_count": 5, "difficulty": "medium",
            "interviewer": interviewer, **over}
    r = client.post("/api/student/interviews", json=body)
    assert r.status_code == 201, r.text
    return r.json()["session"]


def answer(client, s, text):
    r = client.post(f"/api/student/interviews/{s['id']}/answer",
                    json={"question_id": s["questions"][-1]["id"], "answer": text})
    assert r.status_code == 200, r.text
    return r.json()["session"]


def q_prompts(mock_llm):
    return [c for c in mock_llm.calls if "Interview focus" in c["prompt"]]


def test_prompt_uses_full_resume_facts_and_stage(client, mock_llm, student):
    start(client, mock_llm, q("What problem were you trying to solve with the hospital system?",
                              "Hospital Resources Management System", "objective"))
    call = q_prompts(mock_llm)[-1]
    assert "bed-allocation module" in call["prompt"] and "[Python, Django]" in call["prompt"]
    assert "the only experience you may refer to" in call["prompt"] and "(opening" in call["prompt"]
    assert "ask about it instead of assuming" in call["system"]
    props = call["schema"]["properties"]
    assert list(props)[:2] == ["preface", "question"] and "aspect" in props
    assert not {"topic", "followup_kind", "reason"} & set(props)  # no free-text metadata: costs output tokens


def test_vague_answer_signal_reaches_the_prompt_and_metadata_is_stored(client, mock_llm, student, db):
    s = start(client, mock_llm, q("Tell me about your hospital project.", "Hospital Resources Management System"))
    mock_llm.responses += [eval_json(5), q("Which part of the hospital system did you build yourself?",
                                           "Hospital Resources Management System", "personal_contribution",
                                           "clarify", followup=True)]
    s = answer(client, s, "I worked with a team and we finished the hospital project on time.")
    prompt = q_prompts(mock_llm)[-1]["prompt"]
    assert "which part they were personally responsible for" in prompt
    assert "Already explored: hospital resources management system / overview" in prompt
    from app.models import InterviewQuestion
    stored = s["questions"][-1]
    assert stored["text"] == "Which part of the hospital system did you build yourself?"
    db.expire_all()
    meta = db.get(InterviewQuestion, stored["id"]).meta  # audit metadata stays on the server
    assert meta["aspect"] == "personal_contribution" and meta["topic"] == "Hospital Resources Management System"
    assert meta["signals"] == ["vague_contribution"] and meta["attempts"] == 1


def test_paraphrased_duplicate_is_rejected_and_regenerated(client, mock_llm, student):
    s = start(client, mock_llm, q("Explain your Hospital Management System project.", "Hospital system"))
    mock_llm.responses += [eval_json(6), q("Tell me about your hospital management project.", "Hospital system"),
                           q("How did you test the bed allocation module?", "Hospital system", "testing")]
    s = answer(client, s, "It is a Django app that tracks beds, oxygen cylinders and staff shifts across wards. "
                          "I built the bed allocation module and its REST endpoints myself.")
    assert s["questions"][-1]["text"] == "How did you test the bed allocation module?"
    assert "Do NOT ask anything similar to: Tell me about your hospital management project." in \
        q_prompts(mock_llm)[-1]["prompt"]


def test_repeated_failures_use_a_resume_grounded_fallback_not_a_loop(client, mock_llm, student):
    s = start(client, mock_llm, q("Explain your Hospital Management System project.", "Hospital system"))
    dup = q("Tell me about your hospital management project.", "Hospital system")
    mock_llm.responses += [eval_json(6), dup, dup, dup]  # the model keeps repeating itself
    s = answer(client, s, "It is a Django app that tracks beds and oxygen across wards, and I built the allocation.")
    last = s["questions"][-1]
    assert len(q_prompts(mock_llm)) == 4  # first question + 3 attempts, then it stops
    assert last["text"] == "What problem were you trying to solve with Hospital Resources Management System?"
    assert last["source"] == "fallback_template"


def test_clarifying_followup_on_same_aspect_is_allowed(client, mock_llm, student):
    s = start(client, mock_llm, q("Which part of the hospital system did you build yourself?", "Hospital system",
                                  "personal_contribution"))
    mock_llm.responses += [eval_json(4), q("Be specific: what exactly did you implement in the allocation code?",
                                           "Hospital system", "personal_contribution", "clarify", followup=True)]
    s = answer(client, s, "We did the whole thing together as a group and it worked well in the end for everyone.")
    assert s["questions"][-1]["text"].startswith("Be specific")


def test_repeat_request_allows_asking_again(client, mock_llm, student):
    s = start(client, mock_llm, q("How did you handle invalid input in the allocation API?", "allocation API",
                                  "error_handling"))
    mock_llm.responses += [eval_json(1), q("How did you handle invalid input in the allocation API?",
                                           "allocation API", "error_handling", "clarify", followup=True)]
    s = answer(client, s, "Sorry, can you repeat the question?")
    assert len(s["questions"]) == 2 and s["questions"][-1]["text"].startswith("How did you handle invalid input")


def test_stock_praise_is_removed_from_the_spoken_question(client, mock_llm, student):
    s = start(client, mock_llm, q("Great answer! Excellent. Why did you choose Django for the hospital system?",
                                  "Django", "decision"))
    assert s["questions"][0]["text"] == "Why did you choose Django for the hospital system?"


@pytest.mark.parametrize("who, rule", [
    ("aria", "Never generic praise"), ("victor", "No praise"),
    ("marcus", "realistic constraints"), ("elena", "guessing at personality, mental health"),
])
def test_each_personality_adds_its_own_behaviour_rules(client, mock_llm, student, who, rule):
    start(client, mock_llm, q("Why did you choose Django?", "Django", "decision"), interviewer=who)
    system = q_prompts(mock_llm)[-1]["system"]
    assert rule in system
    others = {"aria": "Never generic praise", "victor": "No praise.", "marcus": "realistic constraints",
              "elena": "guessing at personality"}
    assert not any(v in system for k, v in others.items() if k != who)  # no leakage between personalities


def test_personality_configs_are_distinct_and_public_part_hides_prompts(client):
    from app.services import interviewers
    ps = list(interviewers.INTERVIEWERS.values())
    assert len({p.max_question_words for p in ps}) >= 3 and len({p.aspect_order for p in ps}) == 4
    marcus = interviewers.get("marcus")
    assert marcus.stress_notice and marcus.max_question_words < interviewers.get("aria").max_question_words
    register_student(client)
    for item in client.get("/api/interviewers").json():
        assert "traits" in item and not {"objective", "acknowledgement", "prohibited", "aspect_order"} & set(item)
        assert item["ui"].get("hd_model")  # kept from the avatar work

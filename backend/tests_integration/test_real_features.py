"""REAL-model checks for the features README section 9 listed as "not yet verified with the real model":
English conversation + evaluation, AI MCQ generation, code review, student/mentor recommendations and job-role
suggestions. Uses whatever provider backend/.env configures (Gemini with Ollama fallback, or Ollama only).

Each test prints the model that answered and the time it took (run with -s). Smoke tests of quality, not benchmarks.
"""
import time

import pytest

SNAPSHOT = {
    "name": "Test Student", "target_role": "Backend Developer",
    "skills": ["Python", "SQL", "Flask", "Git"],
    "interviews": {"count": 3, "average_score": 52, "weakest_criteria": ["completeness", "clarity"],
                   "recent_feedback": ["Answers lack concrete examples", "Explain trade-offs, not only definitions"]},
    "assessments": {"count": 2, "average_percent": 48, "weak_topics": ["SQL joins", "time complexity"]},
    "english": {"sessions": 1, "average": {"grammar": 6, "fluency": 5}},
    "projects": [{"name": "Library API", "description": "REST API in Flask with SQLite",
                  "technologies": ["Python", "Flask", "SQLite"]}],
    "experience": [],
}


@pytest.fixture()
def answered_by(monkeypatch):
    """Records which model answered each language-model call (from the result's timings)."""
    from app.services import local_llm
    seen: list[str] = []
    real = local_llm.chat_json

    def spy(*a, **kw):
        r = real(*a, **kw)
        seen.append((getattr(r, "timings", None) or {}).get("model") or "?")
        return r
    monkeypatch.setattr(local_llm, "chat_json", spy)
    return seen


def _timed(fn):
    t = time.monotonic()
    out = fn()
    return out, round(time.monotonic() - t, 1)


def test_real_english_conversation_and_evaluation(db, llm_ready, answered_by):
    from app.services import ai
    history = [{"sender": "ai", "content": "Hi! What do you like to do at the weekend?"},
               {"sender": "student", "content": "On weekend I am going to cricket ground with my friends and we "
                                                "plays a match, it is very fun for me."}]
    r, s1 = _timed(lambda: ai.english_reply(db, None, topic="Hobbies", history=history,
                                            learning_mode="free_conversation"))
    print(f"\nenglish reply ({s1}s, {answered_by}): {r['reply']!r}\n  corrections={r.get('corrections')}")
    assert r["reply"].strip() and len(r["reply"].split()) >= 4
    assert r["reply"].strip().lower() != history[0]["content"].lower(), "must not repeat its own question"

    msgs = ["On weekend I am going to cricket ground with my friends and we plays a match, it is very fun for me.",
            "I am liking batting more than bowling because I can hit the sixes.",
            "Last month our team won a small tournament in my college, I was very happy."]
    ev, s2 = _timed(lambda: ai.english_evaluate(db, None, topic="Hobbies", student_messages=msgs))
    print(f"english evaluation ({s2}s, {answered_by[-1]}): grammar={ev['grammar']} vocab={ev['vocabulary']} "
          f"fluency={ev['fluency']} sentence={ev['sentence_formation']}\n  suggestions={ev['suggestions'][:2]}")
    assert all(0 <= ev[k] <= 10 for k in ("grammar", "vocabulary", "fluency", "sentence_formation"))
    assert ev["grammar"] <= 8, "messages with clear tense/agreement errors should not get top grammar marks"
    assert ev["summary"] and ev["suggestions"]


def test_real_mcq_generation(db, llm_ready, answered_by):
    from app.services import ai
    qs, secs = _timed(lambda: ai.generate_assessment(db, None, topic="SQL joins", count=4, difficulty="medium"))
    print(f"\nMCQ generation ({secs}s, {answered_by}): {len(qs)} questions")
    for q in qs:
        print(f"  - {q['question'][:90]} -> {q['options'][q['answer_index']]!r}")
    assert len(qs) >= 3
    for q in qs:
        assert len(q["options"]) == 4 and 0 <= q["answer_index"] < 4
        assert len({o.strip().lower() for o in q["options"]}) == 4, "options must be distinct"
        assert q["explanation"].strip()
        assert not any(o[:2] in ("1:", "1.", "A)", "A.", "a)") for o in q["options"]), "options must not be numbered"


def test_real_code_review_separates_correct_and_buggy(db, llm_ready, answered_by):
    from app.services import ai
    task = "Write a function second_largest(nums) that returns the second largest DISTINCT value, or None."
    cases = [{"input": [3, 1, 4, 4], "expected": 3}, {"input": [5], "expected": None},
             {"input": [2, 2], "expected": None}]
    good = ("def second_largest(nums):\n    vals = sorted(set(nums), reverse=True)\n"
            "    return vals[1] if len(vals) > 1 else None\n")
    buggy = "def second_largest(nums):\n    nums.sort()\n    return nums[-2]\n"
    g, s1 = _timed(lambda: ai.evaluate_code(db, None, question=task, language="python", code=good, test_cases=cases))
    b, s2 = _timed(lambda: ai.evaluate_code(db, None, question=task, language="python", code=buggy, test_cases=cases))
    print(f"\ncode review correct: {g['score']} ({s1}s) verdicts={[v['likely_passes'] for v in g['verdicts']]}")
    print(f"code review buggy:   {b['score']} ({s2}s) verdicts={[(v['traced_output'], v['likely_passes']) for v in b['verdicts']]} "
          f"models={answered_by}")
    assert g["score"] >= b["score"] + 25
    assert all(v["likely_passes"] for v in g["verdicts"])
    # sorted([3,1,4,4])[-2] is 4, not 3, and [5] / [2,2] raise or return 2: the buggy code fails every case
    assert sum(not v["likely_passes"] for v in b["verdicts"]) >= 2
    assert b["feedback"].strip() and b["improved_solution"].strip()


def test_real_student_recommendations(db, llm_ready, answered_by):
    """Used by both the student page (POST /students/recommendations) and the mentor page
    (POST /mentors/students/{id}/recommendations) - same function, same prompt."""
    from app.services import ai
    r, secs = _timed(lambda: ai.student_recommendations(db, None, snapshot=SNAPSHOT))
    print(f"\nrecommendations ({secs}s, {answered_by}): weak={r['weak_areas']}")
    for x in r["recommendations"]:
        print(f"  - [{x['activity_type']}] {x['title']}")
    assert 2 <= len(r["recommendations"]) <= 8 and r["weak_areas"]
    assert not any("_" in w for w in r["weak_areas"]), "weak areas must be specific, not category labels"
    assert len({x["activity_type"] for x in r["recommendations"]}) >= 2, "activities should fit each weakness"
    text = " ".join([*r["weak_areas"], *(x["title"] + " " + x["reason"] for x in r["recommendations"])]).lower()
    assert any(k in text for k in ("sql", "join", "complexity", "example", "clarity", "complete")), \
        "recommendations must be grounded in the weak areas in the data"


def test_real_job_role_suggestions(db, llm_ready, answered_by):
    from app.services import ai
    r, secs = _timed(lambda: ai.job_role_recommendations(db, None, snapshot=SNAPSHOT, interests="backend, APIs"))
    print(f"\nrole suggestions ({secs}s, {answered_by}): " +
          ", ".join(f"{x['role']} ({x['fit_score']})" for x in r["roles"]))
    assert 2 <= len(r["roles"]) <= 6
    assert r["roles"] == sorted(r["roles"], key=lambda x: -x["fit_score"])
    top = r["roles"][0]["role"].lower()
    assert any(k in top for k in ("backend", "python", "software", "api", "developer", "engineer")), top
    assert all(x["skills_to_learn"] for x in r["roles"])

"""REAL local-model checks (not mocked). These measure behaviour of the actual models on a few fixed examples.

Passing means the pipeline works end to end with the real model on these examples - it is a smoke test of
quality, not a benchmark. Timings are printed with -s.
"""
import time

RESUME_TEXT = """Priya Sharma
priya@example.com | github.com/priya
Education: B.Tech Computer Science, XYZ Institute of Technology, 2026, CGPA 8.4
Skills: Python, JavaScript, React, SQL, Git
Projects:
Placement Tracker - A web app built with React and Flask to track campus placement drives for 300 students.
Internship: Software Intern at Infosys, May-July 2025, built REST APIs in Python.
Certifications: AWS Cloud Practitioner
Led a team of 4 students in a hackathon."""

JOB = {"title": "Backend Developer", "description": "Build REST APIs in Python with PostgreSQL. Deploy with Docker.",
       "experience_years": 0, "required_skills": ["Python", "PostgreSQL", "REST"], "preferred_skills": ["Docker"]}


def _timed(fn):
    t = time.monotonic()
    out = fn()
    return out, round(time.monotonic() - t, 1)


# --------------------------------------------------------------------------- embeddings

def test_real_embeddings_rank_candidates(embeddings_ready):
    from app.services.matching import compute_match
    strong = {"target_role": "Backend Developer", "skills": ["Python", "MySQL", "REST APIs", "Docker"],
              "projects": [{"name": "Library API", "description": "REST API in Python with MySQL",
                            "technologies": ["Python", "MySQL"]}], "experience": [], "internships": []}
    medium = {"target_role": "Data analyst", "skills": ["Python", "Excel", "Tableau"],
              "projects": [{"name": "Sales dashboard", "description": "Analysed sales data with pandas",
                            "technologies": ["Python"]}], "experience": [], "internships": []}
    weak = {"target_role": "Graphic designer", "skills": ["Photoshop", "Illustrator"],
            "projects": [{"name": "Poster series", "description": "Event posters", "technologies": ["Photoshop"]}],
            "experience": [], "internships": []}
    results = {n: compute_match(JOB, c) for n, c in (("strong", strong), ("medium", medium), ("weak", weak))}
    for n, m in results.items():
        print(f"\n{n}: score={m['score']} sim={m['semantic_similarity']} rec={m['recommendation']} "
              f"partial={m['partially_matched_skills']} missing={m['missing_required_skills']}")
    assert all(m["method"] == "semantic" for m in results.values())
    assert results["strong"]["score"] > results["medium"]["score"] > results["weak"]["score"]
    # MySQL is related to PostgreSQL -> partial, not a full match and not silently ignored
    assert [p["skill"] for p in results["strong"]["partially_matched_skills"]] == ["PostgreSQL"]
    assert results["weak"]["recommendation"] == "not_a_fit"


# --------------------------------------------------------------------------- resume

def test_real_resume_analysis(db, llm_ready):
    from app.services import ai
    a, secs = _timed(lambda: ai.analyze_resume(db, None, RESUME_TEXT, "Backend Developer"))
    skills = {s["name"].lower() for s in a["skills"]}
    print(f"\nresume analysis: {secs}s | name={a['full_name']} | skills={sorted(skills)}")
    print(f"  internships={[e['organization'] for e in a['internships']]} experience={[e['organization'] for e in a['experience']]}")
    print(f"  certs={a['certifications']} score={a['resume_score']} removed={a['validation']['removed_unsupported']}")
    print(f"  topics={a['recommended_topics'][:5]}\n  questions={a['suggested_interview_questions'][:3]}")
    assert a["full_name"] == "Priya Sharma"
    assert {"python", "react", "sql"} <= skills
    assert not skills & {"kubernetes", "docker", "java", "aws lambda"}   # never present in the resume
    assert any("infosys" in (e["organization"] or "").lower() for e in a["internships"] + a["experience"])
    assert all(len(s.split()) <= 5 for s in skills), "skill names must not be sentences"
    orgs = [e["organization"].lower() for e in a["internships"] + a["experience"]]
    assert len(orgs) == len(set(orgs)), "the same organisation must not be listed twice"
    assert a["projects"] and "placement tracker" in a["projects"][0]["name"].lower()
    assert a["suggested_interview_questions"] and a["recommended_topics"]


# --------------------------------------------------------------------------- interview

def test_real_question_is_personalised(db, llm_ready):
    from app.services import ai
    q, secs = _timed(lambda: ai.next_interview_question(
        db, None, job_role="Backend Developer", category="technical", position=1, total=5,
        resume_summary="CS student who built a placement tracker with React and Flask; interned at Infosys.",
        skills=["Python", "React", "Flask", "SQL", "REST"], history=[], difficulty="medium",
        projects=["Placement Tracker"], topics=["REST API design", "SQL joins"]))
    print(f"\nquestion ({secs}s): [{q['question_type']}] {q['question']}")
    text = q["question"].lower()
    assert len(text) > 15
    assert any(k in text for k in ("placement tracker", "flask", "react", "python", "sql", "rest", "api", "infosys")), \
        "question does not reference the candidate's resume"


def test_real_evaluation_separates_good_and_bad_answers(db, llm_ready):
    from app.services import ai
    from app.routers.interviews import DEFAULT_RUBRIC
    q = "What is a database index and what is its trade-off?"
    good = ("An index is a separate data structure, usually a B-tree, that stores column values with pointers to "
            "rows so the database can find matching rows without scanning the whole table. Lookups and range "
            "queries become much faster, but every insert, update and delete must also update the index, so "
            "writes get slower and the index uses extra storage. I would index columns used in WHERE and JOIN.")
    bad = ("An index is the first page of the database where all the table names are written in alphabetical "
           "order so people can read them, it does not affect speed at all.")
    g, s1 = _timed(lambda: ai.evaluate_answer(db, None, job_role="Backend Developer", question=q,
                                              question_type="technical", answer=good, rubric=DEFAULT_RUBRIC))
    b, s2 = _timed(lambda: ai.evaluate_answer(db, None, job_role="Backend Developer", question=q,
                                              question_type="technical", answer=bad, rubric=DEFAULT_RUBRIC))
    print(f"\ngood answer: {g['score']} ({s1}s) next={g['details']['next_difficulty']} missing={g['details']['missing_concepts']}")
    print(f"bad answer:  {b['score']} ({s2}s) next={b['details']['next_difficulty']} missing={b['details']['missing_concepts']}")
    assert g["score"] >= b["score"] + 25
    assert b["correctness"] <= 4
    assert g["sample_answer"] and b["details"]["improvements"]


def test_real_struggling_followup_is_simpler(db, llm_ready):
    from app.services import ai
    history = [{"question": "Explain how a B-tree index speeds up range queries.", "type": "technical",
                "difficulty": "hard", "answer": "I am not sure, maybe it sorts things.", "score": 20.0}]
    q, secs = _timed(lambda: ai.next_interview_question(
        db, None, job_role="Backend Developer", category="technical", position=2, total=5, resume_summary="",
        skills=["SQL"], history=history, difficulty="medium", struggling=True))
    print(f"\nfollow-up ({secs}s): preface={q['preface']!r}\n  question={q['question']!r} followup={q['is_followup']}")
    assert q["preface"], "a struggling student should get a short explanation first"
    assert q["question"]

import io
from datetime import datetime, timedelta, timezone

from docx import Document

from conftest import admin_login, login, register_student


def _docx_bytes(text: str) -> bytes:
    d = Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


RESUME = "Asha Kumar\nB.Tech Computer Science, 2027\nSkills: Python, Docker, SQL\nProject: Placement portal using FastAPI"


def _make_recruiter(admin, email="r@corp.dev"):
    admin.post("/api/admin/users", json={"full_name": "Ravi Recruiter", "email": email, "password": "Passw0rd!",
                                         "role": "recruiter", "company_name": "Acme"})


def test_ai_unavailable_is_reported_not_faked(client):
    register_student(client)
    files = {"file": ("cv.docx", _docx_bytes(RESUME),
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = client.post("/api/student/resumes", files=files)
    assert r.status_code == 201
    body = r.json()
    assert body["resume"]["analysis_status"] == "unavailable"
    assert body["resume"]["analysis"] is None
    assert "Ollama is not running" in body["ai_error"]

    # Interview falls back to the admin question bank and says so; no fake scores.
    r = client.post("/api/student/interviews", json={"job_role": "Backend Developer", "category": "technical"})
    assert r.status_code == 201
    s = r.json()["session"]
    assert s["question_source"] == "question_bank" and r.json()["notice"]
    q = s["questions"][0]
    r = client.post(f"/api/student/interviews/{s['id']}/answer",
                    json={"question_id": q["id"], "answer": "A process has its own memory space while threads share it."})
    ans = r.json()["session"]["questions"][0]["answer"]
    assert ans["evaluation_status"] == "unavailable" and ans["score"] is None

    # English practice needs AI -> clear 503 error
    r = client.post("/api/student/english", json={"topic": "My hometown"})
    assert r.status_code == 503 and "Ollama is not running" in r.json()["detail"]


def test_rejects_non_resume_files(client):
    register_student(client)
    r = client.post("/api/student/resumes", files={"file": ("x.txt", b"hello world", "text/plain")})
    assert r.status_code == 400


def test_full_interview_flow_with_rewards_and_mentor_goal(client, new_client, fake_ai, db):
    student = register_student(client)
    admin = new_client()
    admin_login(admin)
    m = admin.post("/api/admin/users", json={"full_name": "Meera Mentor", "email": "m@test.dev",
                                            "password": "Passw0rd!", "role": "mentor"}).json()
    admin.post("/api/admin/assignments", json={"mentor_id": m["id"], "student_ids": [student["id"]]})
    mentor = new_client()
    login(mentor, "m@test.dev", "Passw0rd!")
    plan = mentor.post(f"/api/mentor/students/{student['id']}/plans", json={
        "title": "Interview readiness", "goals": [{"title": "Complete 1 mock interview", "goal_type": "mock_interview",
                                                   "target_count": 1}]}).json()
    assert plan["goals"][0]["status"] == "pending"

    # Resume analysis with (stubbed) AI
    files = {"file": ("cv.docx", _docx_bytes(RESUME),
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/student/resumes", files=files).json()["resume"]
    assert res["analysis_status"] == "completed" and res["analysis"]["resume_score"] == 72
    client.post(f"/api/student/resumes/{res['id']}/apply-skills")
    assert "Docker" in client.get("/api/profile").json()["profile"]["skills"]

    s = client.post("/api/student/interviews", json={"job_role": "Backend Developer", "category": "technical",
                                                     "question_count": 3}).json()["session"]
    assert s["question_source"] == "ai"
    answer = "I would design the API with FastAPI, validate input with Pydantic and store data in PostgreSQL."
    for _ in range(3):
        q = s["questions"][-1]
        r = client.post(f"/api/student/interviews/{s['id']}/answer",
                        json={"question_id": q["id"], "answer": answer + f" Point {q['position']}.", "response_seconds": 60})
        assert r.status_code == 200, r.text
        s = r.json()["session"]
    assert len(s["questions"]) == 3
    # Cannot answer an old question again
    assert client.post(f"/api/student/interviews/{s['id']}/answer",
                       json={"question_id": s["questions"][0]["id"], "answer": "again"}).status_code == 400
    r = client.post(f"/api/student/interviews/{s['id']}/complete").json()
    assert r["session"]["overall_score"] == 79.0
    assert r["session"]["report"]["summary"] == "Solid."
    assert "First Interview" in r["new_badges"]

    rewards = client.get("/api/student/rewards").json()
    reasons = [t["reason"] for t in rewards["transactions"]]
    assert any("Completed mock interview" in x for x in reasons)
    assert any("mentor goal" in x for x in reasons)
    assert rewards["points"] == 30 + 20 + 30  # interview + First Interview badge + goal

    # Completing again is rejected; points cannot be earned twice
    assert client.post(f"/api/student/interviews/{s['id']}/complete").status_code == 400

    detail = mentor.get(f"/api/mentor/students/{student['id']}").json()
    assert detail["plans"][0]["goals"][0]["status"] == "completed"
    assert detail["summary"]["interviews"]["average_score"] == 79.0
    notes = mentor.get("/api/notifications").json()["items"]
    assert any(n["title"] == "Goal completed" for n in notes)


def test_short_answers_earn_no_points(client, fake_ai):
    register_student(client)
    s = client.post("/api/student/interviews", json={"job_role": "Dev", "category": "technical",
                                                     "question_count": 3}).json()["session"]
    for i in range(3):
        q = s["questions"][-1]
        s = client.post(f"/api/student/interviews/{s['id']}/answer",
                        json={"question_id": q["id"], "answer": f"yes {i}"}).json()["session"]
    client.post(f"/api/student/interviews/{s['id']}/complete")
    reasons = [t["activity_type"] for t in client.get("/api/student/rewards").json()["transactions"]]
    assert "interview_completed" not in reasons


def test_pasted_duplicate_answers_are_flagged(client, new_client, fake_ai):
    register_student(client)
    s = client.post("/api/student/interviews", json={"job_role": "Dev", "category": "technical",
                                                     "question_count": 3}).json()["session"]
    text = "This is exactly the same long answer that I am pasting into every single question box here."
    for _ in range(3):
        q = s["questions"][-1]
        s = client.post(f"/api/student/interviews/{s['id']}/answer",
                        json={"question_id": q["id"], "answer": text}).json()["session"]
    s = client.post(f"/api/student/interviews/{s['id']}/complete").json()["session"]
    assert s["flagged"] is True
    # Flagged interviews earn nothing - not even the First Interview badge
    assert client.get("/api/student/rewards").json()["points"] == 0
    admin = new_client()
    admin_login(admin)
    flagged = admin.get("/api/admin/flagged").json()["interviews"]
    assert flagged and flagged[0]["id"] == s["id"]
    r = admin.post(f"/api/admin/flagged/interview/{s['id']}", json={"action": "confirm", "note": "copy-paste"})
    assert r.status_code == 200


def test_english_active_time_is_verified(client, fake_ai, db):
    from app.models import EnglishMessage, EnglishSession
    register_student(client)
    s = client.post("/api/student/english", json={"topic": "Hobbies"}).json()
    for text in ["I enjoy playing cricket on weekends with my friends", "ok", "I also like reading novels in the evening"]:
        client.post(f"/api/student/english/{s['id']}/message", json={"content": text})
    # Simulate realistic timing: shift timestamps into the past (2 min between messages, then a 30 min idle gap)
    sess = db.get(EnglishSession, s["id"])
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    sess.created_at = base
    offsets = [0, 120, 240, 360, 480, 2280, 2400]
    for m, off in zip(sorted(sess.messages, key=lambda m: m.id), offsets[1:]):
        m.created_at = base + timedelta(seconds=off)
    db.commit()
    r = client.post(f"/api/student/english/{s['id']}/end").json()
    # msgs: ai(120) stu(240,+120) ai(360) stu"ok"(480, <3 words: 0) ai(2280) stu(2400,+120 capped)
    assert r["session"]["active_seconds"] == 240
    assert r["session"]["overall_score"] == 70.0
    # 4 minutes < 5-minute minimum -> no english_session points
    acts = [t["activity_type"] for t in client.get("/api/student/rewards").json()["transactions"]]
    assert "english_session" not in acts


def test_recruiter_job_application_cycle(client, new_client):
    student = register_student(client, cgpa=None)
    client.put("/api/profile", json={"cgpa": 8.2, "skills": ["Python", "SQL"]})

    admin = new_client()
    admin_login(admin)
    _make_recruiter(admin)
    rec = new_client()
    login(rec, "r@corp.dev", "Passw0rd!")
    job = rec.post("/api/recruiter/jobs", json={
        "title": "Backend Engineer", "description": "Build APIs with Python and SQL for our platform.",
        "location": "Pune", "min_cgpa": 7.5, "eligible_branches": ["Computer Science"],
        "required_skills": ["Python", "SQL"], "preferred_skills": ["Docker"], "status": "draft"}).json()
    # Drafts are invisible to students
    assert client.get(f"/api/student/jobs/{job['id']}").status_code == 404
    rec.post(f"/api/recruiter/jobs/{job['id']}/status/publish")
    listing = client.get("/api/student/jobs").json()["items"]
    assert listing[0]["eligible"] is True

    app = client.post(f"/api/student/jobs/{job['id']}/apply", json={}).json()
    # Embeddings are off in tests, so the match is rule-based: required 100% (w .50), preferred 0% (w .15),
    # experience 100% (w .15, job needs 0 years) -> (0.50 + 0.15) / 0.80 = 81.25 -> 81
    assert app["match"]["method"] == "rule_based" and app["match"]["score"] == 81
    assert app["match"]["missing_preferred_skills"] == ["Docker"] and app["match"]["missing_required_skills"] == []
    assert client.post(f"/api/student/jobs/{job['id']}/apply", json={}).status_code == 409

    # Recruiter now has full access to this applicant's records
    detail = rec.get(f"/api/recruiter/candidates/{student['id']}").json()
    assert detail["full_access"] is True
    # AI match with the local model down -> computed score is returned, AI explanation reported as unavailable
    r = rec.post(f"/api/recruiter/applications/{app['id']}/match")
    assert r.status_code == 200
    assert "Ollama is not running" in r.json()["ai_error"] and r.json()["match"]["method"] == "rule_based"

    r = rec.patch(f"/api/recruiter/applications/{app['id']}/status", json={"status": "interview_scheduled"})
    assert r.status_code == 400  # needs a date
    when = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    r = rec.patch(f"/api/recruiter/applications/{app['id']}/status",
                  json={"status": "interview_scheduled", "interview_at": when, "note": "Round 1"})
    assert r.status_code == 200
    rec.patch(f"/api/recruiter/applications/{app['id']}/status", json={"status": "selected"})

    mine = client.get("/api/student/applications").json()[0]
    assert mine["status"] == "selected" and len(mine["history"]) == 3
    titles = [n["title"] for n in client.get("/api/notifications").json()["items"]]
    assert titles.count("Application update") == 2

    # Another recruiter cannot touch this job or application
    _make_recruiter(admin, "r2@corp.dev")
    rec2 = new_client()
    login(rec2, "r2@corp.dev", "Passw0rd!")
    assert rec2.get(f"/api/recruiter/jobs/{job['id']}").status_code == 404
    assert rec2.patch(f"/api/recruiter/applications/{app['id']}/status", json={"status": "rejected"}).status_code == 404
    # Without consent (and no application to rec2) the student is invisible to rec2...
    assert rec2.get(f"/api/recruiter/candidates/{student['id']}").status_code == 404
    assert rec2.get("/api/recruiter/candidates").json()["total"] == 0
    # ...after opting in, rec2 sees the summary but not the detailed reports.
    client.put("/api/settings", json={"share_with_recruiters": True})
    d = rec2.get(f"/api/recruiter/candidates/{student['id']}").json()
    assert d["full_access"] is False and "interviews" not in d
    assert rec2.get("/api/recruiter/candidates").json()["total"] == 1

    report = admin.get("/api/admin/reports/placements").json()
    assert report["placed"] == 1


def test_ineligible_student_cannot_apply(client, new_client):
    register_student(client)
    client.put("/api/profile", json={"cgpa": 6.0})
    admin = new_client()
    admin_login(admin)
    _make_recruiter(admin)
    rec = new_client()
    login(rec, "r@corp.dev", "Passw0rd!")
    job = rec.post("/api/recruiter/jobs", json={"title": "SDE", "description": "Software development role for graduates.",
                                                "location": "Remote", "min_cgpa": 7.0, "status": "published"}).json()
    r = client.post(f"/api/student/jobs/{job['id']}/apply", json={})
    assert r.status_code == 400 and "CGPA" in r.json()["detail"]


def test_assessment_grading_and_answer_secrecy(client, new_client):
    register_student(client)
    admin = new_client()
    admin_login(admin)
    a = admin.post("/api/assessments", json={"title": "SQL Basics", "topic": "SQL", "questions": [
        {"question": "Which clause filters groups?", "options": ["WHERE", "HAVING", "ORDER BY"], "answer_index": 1},
        {"question": "Which is a DDL command?", "options": ["SELECT", "CREATE", "UPDATE"], "answer_index": 1}]}).json()
    started = client.post(f"/api/student/assessments/{a['id']}/start").json()
    assert all("answer_index" not in q for q in started["assessment"]["questions"])
    r = client.post(f"/api/student/assessments/results/{started['result_id']}/submit", json={"answers": [1, 0]}).json()
    assert r["result"]["score"] == 50.0 and r["result"]["passed"] is False
    assert client.post(f"/api/student/assessments/results/{started['result_id']}/submit",
                       json={"answers": [1, 1]}).status_code == 400
    # Students cannot manage assessments
    assert client.post("/api/assessments", json={}).status_code == 403


def test_admin_settings_and_rubric_validation(client):
    admin_login(client)
    assert client.put("/api/admin/settings/student_registration_open", json={"value": False}).status_code == 200
    r = client.post("/api/admin/rubrics", json={"name": "Bad", "applies_to": "interview",
                                                "criteria": [{"name": "Accuracy", "weight": 0.3}]})
    assert r.status_code == 400
    client.post("/api/auth/logout")
    r = client.post("/api/auth/register/student", json={"full_name": "New Person", "email": "n@test.dev",
                                                        "password": "Passw0rd!"})
    assert r.status_code == 403

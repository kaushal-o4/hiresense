"""Tests for the extended feature set: English learning, coding tests, readiness, challenges,
recruiter communication/assignments, mentor tools and admin management."""
import io
import zipfile
from datetime import datetime, timedelta, timezone

from bson import json_util

from app.config import get_settings
from conftest import admin_login, login, register_student


def _recruiter(admin, new_client, email="r@corp.dev"):
    admin.post("/api/admin/users", json={"full_name": "Ravi Recruiter", "email": email, "password": "Passw0rd!",
                                         "role": "recruiter", "company_name": "Acme"})
    rec = new_client()
    login(rec, email, "Passw0rd!")
    return rec


def test_speaking_drills_are_not_available_to_students(client):
    """The pronunciation/speaking drill feature was removed from the student portal (2026-10-11)."""
    register_student(client)
    assert client.post("/api/student/exercises", json={"kind": "pronunciation"}).status_code in (404, 405)
    titles = {c["title"] for c in client.get("/api/student/challenges").json()["challenges"]}
    assert "Pronunciation warm-up" not in titles


def test_challenge_completes_once_per_period(client, db):
    from app.models import Challenge, EnglishSession
    sid = register_student(client)["id"]
    db.add(Challenge(title="Two chats", description="", metric="english_sessions", target=2, period="daily", points=10))
    now = datetime.now(timezone.utc)
    for _ in range(4):
        db.add(EnglishSession(student_id=sid, topic="t", mode="text", status="completed", active_seconds=120,
                              ended_at=now))
    db.commit()
    from app.services.rewards import evaluate_challenges
    for _ in range(2):  # evaluated after two activities: must not award twice
        evaluate_challenges(db, sid)
        db.commit()
    ch = {c["title"]: c for c in client.get("/api/student/challenges").json()["challenges"]}
    assert ch["Two chats"]["completed"] is True
    txs = client.get("/api/student/rewards").json()["transactions"]
    assert sum(1 for t in txs if t["activity_type"] == "challenge") == 1


CODING_TEST = {"title": "Coding warm-up", "topic": "Python", "category": "coding", "pass_percent": 50, "questions": [
    {"type": "mcq", "question": "Which keyword defines a function?", "options": ["func", "def", "fn"], "answer_index": 1, "marks": 2},
    {"type": "coding", "question": "Return the sum of two numbers a and b.", "language": "python", "function_name": "add",
     "starter_code": "def add(a, b):\n    pass", "test_cases": [{"input": [1, 2], "expected": 3}], "marks": 8}]}


def test_coding_assessment_pending_then_ai_review(client, new_client, monkeypatch):
    register_student(client)
    admin = new_client()
    admin_login(admin)
    a = admin.post("/api/assessments", json=CODING_TEST)
    assert a.status_code == 201, a.text
    a = a.json()
    assert a["total_marks"] == 10 and a["has_coding"]
    started = client.post(f"/api/student/assessments/{a['id']}/start").json()
    qs = started["assessment"]["questions"]
    assert "answer_index" not in qs[0] and qs[1]["starter_code"].startswith("def add")
    code = "def add(a, b):\n    return a + b"
    r = client.post(f"/api/student/assessments/results/{started['result_id']}/submit", json={"answers": [1, code]}).json()
    # No AI -> coding answer pending, no score invented
    assert r["result"]["evaluation_status"] == "pending" and r["result"]["score"] is None
    assert client.post(f"/api/student/assessments/results/{started['result_id']}/evaluate").status_code == 503

    from app.services import ai
    monkeypatch.setattr(ai, "evaluate_code", lambda db, uid, **kw: {
        "score": 90, "verdicts": [{"case": 1, "likely_passes": True, "reason": "ok"}], "feedback": "Correct",
        "improved_solution": code})
    r = client.post(f"/api/student/assessments/results/{started['result_id']}/evaluate").json()
    assert r["result"]["marks_obtained"] == 2 + 7.2 and r["result"]["score"] == 92.0 and r["result"]["passed"]
    report = client.get("/api/student/report").json()
    assert report["summary"]["assessments"]["by_category"]["coding"] == 92.0


def test_readiness_report_history_and_role_recs(client):
    register_student(client)
    d = client.get("/api/student/dashboard").json()
    r = d["summary"]["readiness"]
    assert r["level"] == "not_ready" and r["components"]["interviews"] is None and 0 <= r["score"] < 20
    assert any(x["weakness"] == "No resume uploaded" for x in d["summary"]["remedies"])
    assert client.get("/api/student/history").json() == []
    rep = client.get("/api/student/report").json()
    assert "mistakes" in rep and len(rep["weekly"]) == 8
    assert client.post("/api/student/role-recommendations").status_code == 503  # AI not configured


def test_settings_preferences_and_consent(client, new_client):
    register_student(client)
    assert client.get("/api/settings").json()["share_with_recruiters"] is False
    s = client.put("/api/settings", json={"speech_lang": "en-GB", "subtitles": False}).json()
    assert s["speech_lang"] == "en-GB" and s["subtitles"] is False
    assert client.put("/api/settings", json={"speech_lang": "fr-FR"}).status_code == 422
    admin = new_client()
    admin_login(admin)
    assert admin.put("/api/settings", json={"share_with_recruiters": True}).status_code == 400


def test_recruiter_messages_assignment_on_hold_export(client, new_client):
    student = register_student(client)
    admin = new_client()
    admin_login(admin)
    rec = _recruiter(admin, new_client)
    job = rec.post("/api/recruiter/jobs", json={"title": "Backend Engineer", "description": "Build APIs with Python and SQL.",
                                                "location": "Pune", "required_skills": ["Python"], "status": "published"}).json()
    app = client.post(f"/api/student/jobs/{job['id']}/apply", json={}).json()
    a = rec.post("/api/assessments", json={**CODING_TEST, "job_id": job["id"]}).json()
    r = rec.post(f"/api/recruiter/applications/{app['id']}/assessments",
                 json={"assessment_id": a["id"], "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()})
    assert r.status_code == 201, r.text
    assert rec.post(f"/api/recruiter/applications/{app['id']}/assessments", json={"assessment_id": a["id"]}).status_code == 409
    mine = client.get("/api/student/assessments").json()
    assert mine[0]["assignment"]["status"] == "assigned"

    rec.post(f"/api/recruiter/applications/{app['id']}/messages", json={"body": "Please bring your ID card.", "kind": "invitation"})
    thread = client.get(f"/api/student/applications/{app['id']}/messages").json()
    assert [m["kind"] for m in thread] == ["assessment", "invitation"]
    client.post(f"/api/student/applications/{app['id']}/messages", json={"body": "Thank you, I will."})
    apps = rec.get(f"/api/recruiter/jobs/{job['id']}/applications").json()["items"]
    assert apps[0]["unread_messages"] == 1 and apps[0]["assignments"][0]["status"] == "assigned"
    # Other students can't read the thread
    other = new_client()
    register_student(other, email="other@test.dev")
    assert other.get(f"/api/student/applications/{app['id']}/messages").status_code == 404

    assert rec.patch(f"/api/recruiter/applications/{app['id']}/status", json={"status": "on_hold"}).status_code == 200
    assert client.get("/api/student/applications").json()[0]["status"] == "on_hold"
    csv_text = rec.get(f"/api/recruiter/jobs/{job['id']}/export").text
    assert "Test Student" in csv_text and "on_hold" in csv_text
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/screen").status_code == 503  # AI not configured


def test_mentor_dashboard_cards_remedies_and_reports(client, new_client, db):
    student = register_student(client)
    admin = new_client()
    admin_login(admin)
    m = admin.post("/api/admin/users", json={"full_name": "Meera Mentor", "email": "m@test.dev",
                                            "password": "Passw0rd!", "role": "mentor"}).json()
    admin.post("/api/admin/assignments", json={"mentor_id": m["id"], "student_ids": [student["id"]]})
    from app.models import User
    u = db.get(User, student["id"])
    u.created_at = datetime.now(timezone.utc) - timedelta(days=30)  # joined long ago, never practised
    db.commit()
    mentor = new_client()
    login(mentor, "m@test.dev", "Passw0rd!")
    d = mentor.get("/api/mentor/dashboard").json()
    assert d["cards"]["my_students"] == 1 and d["cards"]["need_attention"] == 1 and d["cards"]["placement_ready"] == 0
    assert d["student_rows"][0]["inactive"] is True
    titles = [n["title"] for n in mentor.get("/api/notifications").json()["items"]]
    assert "Student stopped practising" in titles
    mentor.get("/api/mentor/dashboard")  # alert is not repeated within a week
    assert [n["title"] for n in mentor.get("/api/notifications").json()["items"]].count("Student stopped practising") == 1

    rem = d["recommendations"][0]
    plan = mentor.post(f"/api/mentor/students/{student['id']}/remedies/assign", json=rem["goal"])
    assert plan.status_code == 201 and plan.json()["title"] == "Recommended remedies"
    assert plan.json()["goals"][0]["deadline"]  # weekly default deadline
    assert mentor.get("/api/mentor/dashboard").json()["cards"]["tasks_pending"] == 1
    mentor.post(f"/api/mentor/students/{student['id']}/feedback", json={"content": "Great start!", "category": "encouragement"})
    assert any("Encouragement" in n["title"] for n in client.get("/api/notifications").json()["items"])
    detail = mentor.get(f"/api/mentor/students/{student['id']}").json()
    assert len(detail["weekly"]) == 8 and "readiness" in detail["summary"]
    assert "readiness" in mentor.get(f"/api/mentor/students/{student['id']}/report").text
    assert "Test Student" in mentor.get("/api/mentor/report").text


def test_admin_announcements_drives_challenges_verification(client, new_client):
    register_student(client, cgpa=None)
    client.put("/api/profile", json={"cgpa": 8.0, "branch": "Computer Science"})
    admin = new_client()
    admin_login(admin)
    r = admin.post("/api/admin/announcements", json={"title": "Placement week", "message": "Drives start Monday", "audience": "student"}).json()
    assert r["recipients"] == 1
    assert any("Placement week" in n["title"] for n in client.get("/api/notifications").json()["items"])

    when = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    drive = admin.post("/api/admin/drives", json={"title": "Campus hiring", "company_name": "Acme", "drive_date": when,
                                                  "min_cgpa": 7.5, "eligible_branches": ["Computer Science"]}).json()
    assert drive["notified"] == 1
    assert client.post(f"/api/student/drives/{drive['id']}/register").status_code == 200
    assert client.post(f"/api/student/drives/{drive['id']}/register").status_code == 409
    assert admin.get(f"/api/admin/drives/{drive['id']}/registrations").json()[0]["name"] == "Test Student"
    high = admin.post("/api/admin/drives", json={"title": "Elite", "company_name": "Xyz Corp", "drive_date": when, "min_cgpa": 9.5}).json()
    assert client.post(f"/api/student/drives/{high['id']}/register").status_code == 400

    assert admin.post("/api/admin/challenges", json={"title": "Daily interview", "metric": "interviews_completed",
                                                     "target": 1, "period": "daily", "points": 15}).status_code == 201
    assert any(c["title"] == "Daily interview" for c in client.get("/api/student/challenges").json()["challenges"])

    rec = _recruiter(admin, new_client)
    rid = rec.get("/api/auth/me").json()["user"]["id"]
    job = rec.post("/api/recruiter/jobs", json={"title": "SDE", "description": "Software development for graduates.",
                                                "location": "Remote", "status": "published"}).json()
    assert job["company_verified"] is False
    admin.post(f"/api/admin/recruiters/{rid}/verify", json={"verified": True})
    assert client.get("/api/student/jobs").json()["items"][0]["company_verified"] is True

    assert admin.put("/api/admin/settings/evaluation_strictness", json={"value": "strict"}).status_code == 200
    assert admin.put("/api/admin/settings/evaluation_strictness", json={"value": "brutal"}).status_code == 400
    overview = admin.get("/api/admin/students").json()
    assert overview["items"][0]["readiness_level"] in ("ready", "almost", "not_ready")
    dash = admin.get("/api/admin/dashboard").json()
    assert sum(dash["readiness"]["levels"].values()) == 1
    assert admin.get("/api/admin/ai-reports").status_code == 200
    backup = admin.get("/api/admin/backup")
    assert backup.status_code == 200 and backup.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(backup.content)) as zf:
        users = json_util.loads(zf.read("users.json"))
    assert {u["email"] for u in users} >= {get_settings().admin_email}
    assert client.get("/api/admin/announcements").status_code == 403


def test_interview_difficulty_and_sample_answers(client, fake_ai, monkeypatch):
    register_student(client)
    from app.services import ai
    seen = []
    topics = iter(["Explain recursion?", "How does a hash map handle collisions?", "Design a rate limiter."])

    def next_q(db, user_id, **kw):
        seen.append(kw.get("difficulty"))
        return {"question": next(topics), "question_type": "technical", "is_followup": False, "preface": ""}

    monkeypatch.setattr(ai, "next_interview_question", next_q)
    monkeypatch.setattr(ai, "score_answer", lambda db, uid, **kw: {
        "relevance": 8, "correctness": 8, "clarity": 8, "communication": 8, "score": 80.0,
        "details": {"completeness": 8}, "feedback": ""})
    monkeypatch.setattr(ai, "answer_feedback", lambda db, uid, **kw: {
        "strengths": [], "missing_concepts": [], "improvements": ["x"], "feedback": "ok", "better_answer_hint": "",
        "sample_answer": "Recursion is when a function calls itself."})
    s = client.post("/api/student/interviews", json={"job_role": "Dev", "category": "technical", "difficulty": "hard",
                                                     "question_count": 3}).json()["session"]
    # A "hard" interview opens with a medium warm-up, then climbs after a strong (>= 75) answer.
    assert s["difficulty"] == "hard" and seen == ["medium"]
    q = s["questions"][0]
    client.post(f"/api/student/interviews/{s['id']}/answer", json={"question_id": q["id"], "answer": "A function calling itself with a base case."})
    s = client.get(f"/api/student/interviews/{s['id']}").json()  # sample answer is added in the background
    assert s["questions"][0]["answer"]["sample_answer"].startswith("Recursion")
    assert seen == ["medium", "hard"] and s["questions"][1]["difficulty"] == "hard"

"""Live notification stream (SSE) and the recruiter comparison / candidate report endpoints."""
import threading
import time

import pytest

from app import database
from app.config import get_settings
from app.models import IntegrityEvent, InterviewSession
from app.services import live_events
from app.services.common import notify
from conftest import admin_login, login, register_student


def _recruiter(admin, new_client, email="r@corp.dev"):
    admin.post("/api/admin/users", json={"full_name": "Ravi Recruiter", "email": email, "password": "Passw0rd!",
                                         "role": "recruiter", "company_name": "Acme"})
    rec = new_client()
    login(rec, email, "Passw0rd!")
    return rec


def _job(rec, title="Backend Engineer"):
    r = rec.post("/api/recruiter/jobs", json={"title": title, "description": "Build APIs with Python and SQL.",
                                              "location": "Pune", "required_skills": ["Python", "SQL"],
                                              "status": "published"})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def short_streams(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "notifications_stream_max_seconds", 1.2)
    monkeypatch.setattr(cfg, "notifications_heartbeat_seconds", 0.3)
    return cfg


def _events(text: str) -> list[str]:
    return [line[len("event: "):] for line in text.splitlines() if line.startswith("event: ")]


# --------------------------------------------------------------------------- after-commit hooks

def test_notify_signals_only_after_commit(db_session_factory, monkeypatch):
    sent = []
    monkeypatch.setattr(live_events, "publish", lambda uid, ev: sent.append((uid, ev)))
    db = db_session_factory()
    try:
        notify(db, 4242, "t", "m")
        assert sent == []  # nothing before the commit
        db.rollback()
        db.commit()
        assert sent == []  # rolled back: the signal is dropped too
        notify(db, 4242, "t", "m")
        db.commit()
        assert sent == [(4242, {"type": "notification"})]
        db.commit()
        assert len(sent) == 1  # fires once
    finally:
        db.close()


def test_failing_after_commit_hook_does_not_break_commit(db_session_factory):
    db = db_session_factory()
    try:
        db.after_commit(lambda: 1 / 0)
        db.commit()  # logged, not raised
    finally:
        db.close()


# --------------------------------------------------------------------------- SSE endpoint

def test_stream_requires_login(client):
    assert client.get("/api/notifications/stream").status_code == 401


def test_stream_delivers_new_notification_and_heartbeats(client, short_streams):
    user = register_student(client)

    def create_later():
        for _ in range(100):
            if live_events.stream_count(user["id"]):
                break
            time.sleep(0.02)
        db = database.SessionLocal()
        try:
            notify(db, user["id"], "Hello", "A live one", "info")
            db.commit()
        finally:
            db.close()

    t = threading.Thread(target=create_later)
    t.start()
    r = client.get("/api/notifications/stream")
    t.join(5)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"].startswith("no-cache")
    evs = _events(r.text)
    assert evs[0] == "ready" and "notification" in evs and evs[-1] == "bye"
    assert ": ping" in r.text  # heartbeat comment
    assert "A live one" not in r.text  # signals only; content comes from GET /api/notifications
    assert live_events.stream_count(user["id"]) == 0  # unsubscribed when the stream ends
    assert client.get("/api/notifications").json()["unread"] >= 1


def test_mark_read_signals_other_tabs(client, db_session_factory, monkeypatch):
    user = register_student(client)
    db = db_session_factory()
    try:
        notify(db, user["id"], "x", "y")
        db.commit()
    finally:
        db.close()
    sent = []
    monkeypatch.setattr(live_events, "publish", lambda uid, ev: sent.append((uid, ev["type"])))
    nid = client.get("/api/notifications").json()["items"][0]["id"]
    client.post(f"/api/notifications/{nid}/read")
    client.post("/api/notifications/read-all")
    client.delete(f"/api/notifications/{nid}")
    assert sent == [(user["id"], "sync")] * 3


def test_stream_limit_per_user(client, monkeypatch):
    user = register_student(client)
    monkeypatch.setattr(live_events, "stream_count", lambda uid=None: live_events.MAX_STREAMS_PER_USER)
    r = client.get("/api/notifications/stream")
    assert r.status_code == 429
    assert user["id"]


def test_publish_reaches_only_that_user():
    import asyncio

    async def run():
        with live_events.subscribe(1) as q1, live_events.subscribe(2) as q2:
            assert live_events.publish(1, {"type": "notification"}) == 1
            ev = await asyncio.wait_for(q1.get(), 1)
            assert ev == {"type": "notification"} and q2.empty()
        assert live_events.stream_count() == 0
    asyncio.run(run())


# --------------------------------------------------------------------------- recruiter comparison and report

def _two_applicants(client, new_client):
    admin = new_client()
    admin_login(admin)
    rec = _recruiter(admin, new_client)
    job = _job(rec)
    s1 = register_student(client, email="s1@test.dev")
    a1 = client.post(f"/api/student/jobs/{job['id']}/apply", json={}).json()
    other = new_client()
    s2 = register_student(other, email="s2@test.dev")
    a2 = other.post(f"/api/student/jobs/{job['id']}/apply", json={}).json()
    return admin, rec, job, (s1, a1, client), (s2, a2, other)


def test_compare_two_to_four_applicants_with_breakdown(client, new_client):
    admin, rec, job, (s1, a1, _), (s2, a2, _) = _two_applicants(client, new_client)
    r = rec.post(f"/api/recruiter/jobs/{job['id']}/compare", json={"application_ids": [a1["id"], a2["id"]]})
    assert r.status_code == 200, r.text
    rows = r.json()["candidates"]
    assert [c["student_id"] for c in rows] == [s1["id"], s2["id"]]
    c = rows[0]
    for key in ("match_breakdown", "job_assessments", "interviews_by_category", "recent_interviews", "integrity",
                "required_skills_covered", "readiness"):
        assert key in c
    assert c["integrity"]["visible"] is False and c["integrity"]["reason"]
    # limits: 2..4 distinct applications
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/compare", json={"application_ids": [a1["id"]]}).status_code == 422
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/compare",
                    json={"application_ids": [a1["id"], a1["id"]]}).status_code == 400
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/compare",
                    json={"application_ids": [a1["id"], a2["id"], 9991, 9992, 9993]}).status_code == 422


def test_compare_and_report_respect_recruiter_ownership(client, new_client):
    admin, rec, job, (s1, a1, c1), (s2, a2, c2) = _two_applicants(client, new_client)
    rival = _recruiter(admin, new_client, email="rival@corp.dev")
    rival_job = _job(rival, "Other job")
    # another recruiter can't compare or report on these applications
    assert rival.post(f"/api/recruiter/jobs/{job['id']}/compare",
                      json={"application_ids": [a1["id"], a2["id"]]}).status_code == 404
    assert rival.post(f"/api/recruiter/jobs/{rival_job['id']}/compare",
                      json={"application_ids": [a1["id"], a2["id"]]}).status_code == 404
    assert rival.get(f"/api/recruiter/applications/{a1['id']}/report").status_code == 404
    # students and mentors can't use the recruiter endpoints at all
    assert c1.get(f"/api/recruiter/applications/{a1['id']}/report").status_code == 403
    # mixing jobs is rejected
    a3 = c1.post(f"/api/student/jobs/{rival_job['id']}/apply", json={}).json()
    own_other = _job(rec, "Second job")
    a4 = c2.post(f"/api/student/jobs/{own_other['id']}/apply", json={}).json()
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/compare",
                    json={"application_ids": [a1["id"], a4["id"]]}).status_code == 400
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/compare",
                    json={"application_ids": [a1["id"], a3["id"]]}).status_code == 404
    # withdrawn applications are excluded
    c2.post(f"/api/student/applications/{a2['id']}/withdraw")
    assert rec.post(f"/api/recruiter/jobs/{job['id']}/compare",
                    json={"application_ids": [a1["id"], a2["id"]]}).status_code == 400
    assert rec.get(f"/api/recruiter/applications/{a2['id']}/report").status_code == 404


def test_candidate_report_contents_and_audit(client, new_client):
    admin, rec, job, (s1, a1, _), _ = _two_applicants(client, new_client)
    rec.patch(f"/api/recruiter/applications/{a1['id']}/status", json={"status": "shortlisted", "note": "Strong SQL"})
    r = rec.get(f"/api/recruiter/applications/{a1['id']}/report")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["candidate"]["name"] == "Test Student" and d["contact"]["email"] == "s1@test.dev"
    assert d["job"]["id"] == job["id"] and d["profile"]["education"]["college"] == "ABC College"
    assert [h["to"] for h in d["history"]][-1] == "shortlisted"
    assert "never a basis" in d["note"]
    logs = admin.get("/api/admin/audit-logs", params={"action": "candidate.report"}).json()
    items = logs["items"] if isinstance(logs, dict) else logs
    assert any(x["action"] == "candidate.report" for x in items)


def test_integrity_overview_only_when_shared(client, new_client, db_session_factory):
    admin, rec, job, (s1, a1, _), _ = _two_applicants(client, new_client)
    db = db_session_factory()
    try:
        for shared in (False, True):
            s = InterviewSession(student_id=s1["id"], job_role="Backend", category="technical", status="completed",
                                 monitoring={"features": {"camera": True, "focus_changes": True},
                                             "recruiters_can_view": shared, "camera_permission": "granted"})
            db.add(s)
            db.commit()
            db.add(IntegrityEvent(session_id=s.id, event_type="tab_hidden", t_ms=1000, severity="medium",
                                  confidence_sufficient=True))
            db.commit()
    finally:
        db.close()
    integ = rec.get(f"/api/recruiter/applications/{a1['id']}/report").json()["candidate"]["integrity"]
    # one session was consented under a policy that disclosed recruiter access, the other wasn't
    assert integ["visible"] is True and integ["monitored_sessions"] == 1 and integ["hidden_sessions"] == 1
    assert integ["highest_band"]["code"] in ("none", "low", "moderate", "high")
    assert set(integ["sessions"][0]) == {"session_id", "job_role", "band", "status", "events"}  # counts only
    # an admin switching recruiter access off hides everything, also for the already-consented session
    cfg = admin.get("/api/admin/security-settings").json()["config"]
    assert admin.put("/api/admin/security-settings", json={**cfg, "recruiters_can_view": False}).status_code == 200
    integ = rec.get(f"/api/recruiter/applications/{a1['id']}/report").json()["candidate"]["integrity"]
    assert integ["visible"] is False and integ["monitored_sessions"] == 0 and integ["hidden_sessions"] == 2

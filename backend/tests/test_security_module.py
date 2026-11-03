"""Interview security module (2026-10-23): event engine (validation, idempotency, time window, rate limit), session
reconnects, admin security settings, recruiter access, review history and the risk summary.

Detector outputs are SIMULATED here (events posted as the browser would send them). These tests prove the server's
rules; they say nothing about how well the on-device computer vision works - see README for the camera checks.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from conftest import admin_login, join_app_threads, login, register_student
from test_latency_and_monitoring import FEATURES, _consent, streaming_ai  # noqa: F401 (fixture)
from test_latency_and_monitoring import _start as _start_interview

ALL = {**FEATURES, "attention": True, "audio": True, "paste": True, "screen": True}


def _start(client):
    """Start a live interview WITHOUT the background first-question prefetch (these tests only need an interview
    in progress)."""
    s = _start_interview(client, defer_first_question=False)
    join_app_threads()
    return s


def _events(client, sid, *events):
    return client.post(f"/api/student/interviews/{sid}/integrity-events", json={"events": list(events)})


def _finish(db, sid, ago=timedelta(0)):
    from app.models import InterviewSession
    s = db.get(InterviewSession, sid)
    s.status = "completed"
    s.completed_at = datetime.now(timezone.utc) - ago
    db.commit()


def _recruiter(admin, new_client, email="r@test.dev"):
    u = admin.post("/api/admin/users", json={"full_name": "Rita Recruiter", "email": email, "password": "Passw0rd!",
                                             "role": "recruiter", "company_name": "Acme"}).json()
    admin.patch(f"/api/admin/users/{u['id']}", json={"status": "active"})
    c = new_client()
    login(c, email, "Passw0rd!")
    return c


# --------------------------------------------------------------------------- event engine

def test_own_interview_events_carry_taxonomy_details_and_wall_clock(client, streaming_ai):
    register_student(client)
    s = _start(client)
    assert _consent(client, s["id"], ALL).status_code == 200
    r = _events(client, s["id"],
                {"event_type": "multiple_faces", "t_ms": 0, "duration_ms": 6000, "confidence": 0.9,
                 "client_event_id": "evt-aaaaaaaa", "details": {"max_faces": 2, "photo": "x", "cause": "nonsense"}},
                {"event_type": "attention_repeated", "t_ms": 10, "confidence": 1.0,
                 "details": {"count": 5, "window_s": 120}})
    assert r.json() == {"stored": 2, "ignored": 0}
    mine = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()
    mf = next(e for e in mine["events"] if e["event_type"] == "multiple_faces")
    assert mf["category"] == "MULTIPLE_FACES_DETECTED" and mf["detection_source"] == "face_landmarker"
    assert mf["details"] == {"max_faces": 2}  # unknown keys / values are dropped by the whitelist
    assert "up to 2 faces" in mf["description"] and mf["start_timestamp"] and mf["end_timestamp"]
    rep = next(e for e in mine["events"] if e["event_type"] == "attention_repeated")
    assert rep["severity"] == "low" and rep["category"] == "EYE_GAZE_DEVIATION"
    assert mine["summary"]["risk"]["band"]["code"] in ("low", "moderate")


def test_cannot_post_to_or_read_another_candidates_interview(client, new_client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    other = new_client()
    register_student(other, email="other@test.dev")
    assert _events(other, s["id"], {"event_type": "face_absent", "t_ms": 1, "duration_ms": 5000}).status_code == 404
    assert other.get(f"/api/student/interviews/{s['id']}/integrity-events").status_code == 404
    assert other.get(f"/api/monitoring/sessions/{s['id']}").status_code == 403  # students are not reviewers


def test_duplicate_events_are_stored_once(client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    ev = {"event_type": "face_absent", "t_ms": 5, "duration_ms": 20000, "confidence": 0.9,
          "client_event_id": "dup-12345678"}
    assert _events(client, s["id"], ev, ev).json() == {"stored": 1, "ignored": 1}  # same batch
    assert _events(client, s["id"], ev).json() == {"stored": 0, "ignored": 1}  # retried batch
    events = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"]
    assert len([e for e in events if e["event_type"] == "face_absent"]) == 1


@pytest.mark.parametrize("bad", [
    {"event_type": "cheating_detected", "t_ms": 1},
    {"event_type": "face_absent", "t_ms": -1},
    {"event_type": "face_absent", "t_ms": 1, "confidence": 1.5},
    {"event_type": "face_absent", "t_ms": 1, "client_event_id": "has spaces!"},
    {"event_type": "session_reconnected", "t_ms": 1},  # server-generated only
    {"event_type": "face_absent", "t_ms": 1, "details": {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7}},
])
def test_malformed_events_are_rejected(client, streaming_ai, bad):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    assert _events(client, s["id"], bad).status_code == 422


def test_too_many_events_in_one_request_rejected(client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    many = [{"event_type": "focus_change", "t_ms": i, "duration_ms": 900} for i in range(51)]
    assert _events(client, s["id"], *many).status_code == 422


def test_expired_interview_and_future_timestamps(client, streaming_ai, db):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    # an event claiming to be an hour in the future of this interview is ignored
    r = _events(client, s["id"], {"event_type": "face_absent", "t_ms": 3_600_000, "duration_ms": 5000})
    assert r.json() == {"stored": 0, "ignored": 1}
    _finish(db, s["id"], ago=timedelta(minutes=1))  # just finished: the last flush is still accepted
    assert _events(client, s["id"], {"event_type": "focus_change", "t_ms": 10, "duration_ms": 2000}).status_code == 200
    _finish(db, s["id"], ago=timedelta(hours=2))  # long finished
    assert _events(client, s["id"], {"event_type": "focus_change", "t_ms": 20, "duration_ms": 2000}).status_code == 400


def test_rate_limit(client, streaming_ai, monkeypatch):
    from app.routers import monitoring
    monkeypatch.setattr(monitoring, "RATE_LIMIT", (3, 60.0))
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    codes = [_events(client, s["id"], {"event_type": "focus_change", "t_ms": i, "duration_ms": 900}).status_code
             for i in range(4)]
    assert codes == [200, 200, 200, 429]
    monitoring._rate.clear()


def test_reconsent_records_reconnect_and_keeps_the_interview_clock(client, streaming_ai):
    register_student(client)
    s = _start(client)
    first = _consent(client, s["id"]).json()
    assert first["elapsed_ms"] < 5000
    events = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"]
    assert not [e for e in events if e["event_type"] == "session_reconnected"]
    again = _consent(client, s["id"]).json()  # page reloaded: setup shown and accepted again
    assert again["monitoring"]["clock_origin"] == first["monitoring"]["clock_origin"]
    assert again["elapsed_ms"] >= first["elapsed_ms"]
    events = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"]
    rec = [e for e in events if e["event_type"] == "session_reconnected"]
    assert len(rec) == 1 and rec[0]["category"] == "SESSION_RECONNECTED" and rec[0]["severity"] == "info"


def test_session_events_need_some_consent_but_not_a_specific_feature(client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"], {"camera": True, "face_presence": True, "multiple_faces": True})
    r = _events(client, s["id"],
                {"event_type": "network_interruption", "t_ms": 1, "duration_ms": 8000, "details": {"reason": "offline"}},
                {"event_type": "microphone_disconnected", "t_ms": 2, "details": {"reason": "ended"}},
                {"event_type": "background_speech", "t_ms": 3, "duration_ms": 5000, "confidence": 0.9})  # no consent
    assert r.json() == {"stored": 2, "ignored": 1}


# --------------------------------------------------------------------------- admin security settings

def test_security_settings_admin_only_validated_audited_and_applied(client, new_client, streaming_ai):
    stu = new_client()
    register_student(stu)
    assert stu.get("/api/admin/security-settings").status_code == 403
    assert stu.put("/api/admin/security-settings", json={}).status_code == 403
    admin = new_client()
    admin_login(admin)
    cfg = admin.get("/api/admin/security-settings").json()["config"]
    assert cfg["thresholds"]["gaze_record_ms"] == 3000 and cfg["detectors"]["audio"] is True

    bad = {**cfg, "thresholds": {**cfg["thresholds"], "frame_rate": 99}}
    assert admin.put("/api/admin/security-settings", json=bad).status_code == 422
    assert admin.put("/api/admin/security-settings", json={**cfg, "severity_caps": {"nope": "info"}}).status_code == 400
    assert admin.put("/api/admin/security-settings",
                     json={**cfg, "risk_bands": {"low": 5, "moderate": 2, "high": 9}}).status_code == 400

    new = {**cfg, "detectors": {**cfg["detectors"], "attention": False},
           "thresholds": {**cfg["thresholds"], "gaze_record_ms": 4000},
           "severity_caps": {"multiple_faces": "low"}}
    r = admin.put("/api/admin/security-settings", json=new)
    assert r.status_code == 200 and "detectors.attention" in r.json()["changed"]
    logs = admin.get("/api/admin/audit-logs", params={"action": "security_settings.update"}).json()["items"]
    assert len(logs) == 1

    pol = stu.get("/api/monitoring/policy").json()
    assert "attention" not in pol["features"] and pol["thresholds"]["gaze_record_ms"] == 4000
    s = _start(stu)
    out = _consent(stu, s["id"], ALL).json()["monitoring"]
    assert out["features"]["attention"] is False  # a disabled detector cannot be consented to
    assert out["config"]["thresholds"]["gaze_record_ms"] == 4000  # interview-specific copy
    _events(stu, s["id"], {"event_type": "multiple_faces", "t_ms": 1, "duration_ms": 90000, "confidence": 0.99},
            {"event_type": "attention_away", "t_ms": 2, "duration_ms": 9000, "confidence": 0.99})
    events = stu.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"]
    assert [(e["event_type"], e["severity"]) for e in events] == [("multiple_faces", "low")]  # capped; gaze off

    # later changes do not rewrite the settings an existing interview ran with
    admin.put("/api/admin/security-settings", json={**new, "severity_caps": {}})
    _events(stu, s["id"], {"event_type": "multiple_faces", "t_ms": 3, "duration_ms": 90000, "confidence": 0.99})
    events = stu.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"]
    assert {e["severity"] for e in events} == {"low"}


def test_monitoring_can_be_switched_off_by_policy(client, new_client, streaming_ai):
    admin = new_client()
    admin_login(admin)
    admin.put("/api/admin/settings/monitoring_camera_required", json={"value": False})
    admin.put("/api/admin/settings/monitoring_enabled", json={"value": False})
    register_student(client)
    s = _start(client)
    out = _consent(client, s["id"], ALL).json()["monitoring"]
    assert not any(out["features"].values())
    assert _events(client, s["id"], {"event_type": "face_absent", "t_ms": 1, "duration_ms": 9000}).json()["stored"] == 0


# --------------------------------------------------------------------------- recruiter access and reviews

def _applied_student(client, new_client, admin):
    register_student(client)
    rec = _recruiter(admin, new_client)
    job = rec.post("/api/recruiter/jobs", json={"title": "Backend Engineer", "description": "Build APIs with Python.",
                                                "location": "Pune", "required_skills": ["Python"],
                                                "status": "published"}).json()
    assert client.post(f"/api/student/jobs/{job['id']}/apply", json={}).status_code in (200, 201)
    return rec


def test_recruiter_sees_only_completed_interviews_of_own_applicants(client, new_client, streaming_ai, db):
    admin = new_client()
    admin_login(admin)
    rec = _applied_student(client, new_client, admin)
    stranger = _recruiter(admin, new_client, email="r2@test.dev")
    s = _start(client)
    _consent(client, s["id"])
    _events(client, s["id"], {"event_type": "multiple_faces", "t_ms": 1, "duration_ms": 30000, "confidence": 0.9})
    assert rec.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404  # still in progress
    _finish(db, s["id"])
    items = rec.get("/api/monitoring/sessions").json()["items"]
    assert [i["id"] for i in items] == [s["id"]] and "config" not in items[0]["monitoring"]
    assert stranger.get("/api/monitoring/sessions").json()["items"] == []
    assert stranger.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404
    detail = rec.get(f"/api/monitoring/sessions/{s['id']}").json()
    assert "review_history" not in detail["events"][0]  # admins only

    # recruiter review: status + notes only; detection fields cannot be rewritten
    eid = detail["events"][0]["id"]
    before = {k: detail["events"][0][k] for k in ("t_ms", "duration_ms", "confidence", "severity", "event_type")}
    r = rec.patch(f"/api/monitoring/events/{eid}", json={"review_status": "needs_review", "reviewer_notes": "Ask admin",
                                                         "t_ms": 999, "severity": "info", "duration_ms": 1})
    assert r.status_code == 200 and r.json()["review_status"] == "needs_review"
    assert {k: r.json()[k] for k in before} == before
    stranger_try = stranger.patch(f"/api/monitoring/events/{eid}", json={"review_status": "false_positive"})
    assert stranger_try.status_code == 404
    admin.patch(f"/api/monitoring/events/{eid}", json={"review_status": "false_positive", "reviewer_notes": "Poster"})
    hist = admin.get(f"/api/monitoring/sessions/{s['id']}").json()["events"][0]["review_history"]
    assert [(h["status"], h["role"]) for h in hist] == [("needs_review", "recruiter"), ("false_positive", "admin")]
    # a false positive no longer counts toward the risk summary
    risk = admin.get(f"/api/monitoring/sessions/{s['id']}").json()["monitoring"]["risk"]
    assert risk["points"] == 0 and risk["excluded"]["cleared_by_reviewer"] == 1

    # switching recruiter access off hides it again at once
    cfg = admin.get("/api/admin/security-settings").json()["config"]
    admin.put("/api/admin/security-settings", json={**cfg, "recruiters_can_view": False})
    assert rec.get("/api/monitoring/sessions").json()["items"] == []
    assert rec.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404


def test_recruiter_access_requires_disclosure_at_consent(client, new_client, streaming_ai, db):
    admin = new_client()
    admin_login(admin)
    cfg = admin.get("/api/admin/security-settings").json()["config"]
    admin.put("/api/admin/security-settings", json={**cfg, "recruiters_can_view": False})
    rec = _applied_student(client, new_client, admin)
    s = _start(client)
    assert "do not receive" in client.get("/api/monitoring/policy").json()["access"]
    _consent(client, s["id"])  # consented while recruiters were NOT disclosed
    _finish(db, s["id"])
    admin.put("/api/admin/security-settings", json={**cfg, "recruiters_can_view": True})
    assert rec.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404  # not retroactive


def test_reviewer_filters(client, new_client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    _events(client, s["id"], {"event_type": "focus_change", "t_ms": 1, "duration_ms": 40000})
    admin = new_client()
    admin_login(admin)
    get = lambda **p: [i["id"] for i in admin.get("/api/monitoring/sessions", params=p).json()["items"]]  # noqa: E731
    assert get(category="BROWSER_TAB_SWITCH") == [s["id"]]
    assert get(category="MULTIPLE_FACES_DETECTED") == []
    assert get(severity="low") == [s["id"]] and get(severity="high") == []
    assert get(review_status="pending") == [s["id"]] and get(review_status="false_positive") == []
    assert get(q="test student") == [s["id"]] and get(q="nobody") == []
    today = datetime.now(timezone.utc).date().isoformat()
    assert get(date_from=today, date_to=today) == [s["id"]]
    assert get(date_to="2020-01-01") == []
    assert admin.get("/api/monitoring/sessions", params={"date_from": "yesterday"}).status_code == 400


# --------------------------------------------------------------------------- risk summary (pure)

def _ev(i, t, secs=0, sure=True, status="pending"):
    return SimpleNamespace(id=i, event_type=t, duration_ms=secs * 1000, confidence_sufficient=sure, review_status=status)


def test_risk_summary_aggregates_caps_and_excludes_uncertain_or_cleared():
    from app.services.integrity import SecurityConfig, risk_summary
    assert risk_summary([])["band"]["code"] == "none"
    brief = [_ev(1, "attention_away", 4), _ev(2, "focus_change", 2), _ev(3, "face_absent", 5)]
    assert risk_summary(brief)["points"] == 0  # brief, natural events add nothing
    r = risk_summary([_ev(i, "focus_change", 2) for i in range(7)])  # 7 short switches = 2 groups of 3
    assert r["contributions"][0]["occurrences"] == 2 and r["points"] == 4 and r["band"]["code"] == "moderate"
    many = [_ev(i, "multiple_faces", 30) for i in range(10)]
    r = risk_summary(many)
    assert r["points"] == 9 and r["band"]["code"] == "high"  # capped at 3 occurrences x 3
    r = risk_summary([_ev(1, "multiple_faces", 30, sure=False), _ev(2, "multiple_faces", 30, status="false_positive")])
    assert r["points"] == 0 and r["excluded"] == {"low_confidence": 1, "cleared_by_reviewer": 1}
    cfg = SecurityConfig.model_validate({"risk_weights": {"multiple_faces": 0}})
    assert risk_summary(many, cfg)["points"] == 0
    assert "never" in risk_summary(many)["disclaimer"] and "sole basis" in risk_summary(many)["disclaimer"]

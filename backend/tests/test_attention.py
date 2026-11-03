"""Estimated visual attention: server storage rules, the report, and who can read it.

The percentage is measured in the browser (frontend/src/monitoring/attentionMeter.js, unit-tested there). These tests
prove what the server accepts, how it combines monitor runs and that unobserved time is never counted as attention.
"""
from datetime import datetime, timedelta, timezone

import pytest

from conftest import admin_login, register_student
from test_latency_and_monitoring import _consent, streaming_ai  # noqa: F401 (fixture)
from test_security_module import ALL, _applied_student, _events, _finish, _start


def spread(toward, away, unobserved, first=0):
    """Fill consecutive 10-second buckets with the time, the way the browser does."""
    out, idx, room = [], first, 10_000
    cur = [0, 0, 0]
    for slot, amount in enumerate((toward, away, unobserved)):
        while amount > 0:
            take = min(amount, room)
            cur[slot] += take
            amount -= take
            room -= take
            if room == 0:
                out.append([idx, *cur])
                idx, room, cur = idx + 1, 10_000, [0, 0, 0]
    if any(cur):
        out.append([idx, *cur])
    return out


def snap(epoch="run-aaaaaa", toward=24_000, away=6_000, unobserved=0, paused=0, calibrating=0,
         reasons=None, buckets=None, window=30_000):
    reasons = reasons if reasons is not None else ({"face_not_visible": unobserved} if unobserved else {})
    return {"epoch": epoch, "window_ms": window, "toward_ms": toward, "away_ms": away, "unobserved_ms": unobserved,
            "paused_ms": paused, "calibrating_ms": calibrating, "by_reason": reasons,
            "buckets": buckets if buckets is not None else spread(toward, away, unobserved)}


def put(c, sid, body):
    return c.put(f"/api/student/interviews/{sid}/attention", json=body)


def started(client, db, minutes_ago=10, features=ALL):
    register_student(client)
    s = _start(client)
    assert _consent(client, s["id"], features).status_code == 200
    from app.models import InterviewSession
    row = db.get(InterviewSession, s["id"])
    m = dict(row.monitoring)  # the interview clock started `minutes_ago`
    m["clock_origin"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    row.monitoring = m
    db.commit()
    return s


def report(client, sid):
    return client.get(f"/api/student/interviews/{sid}/integrity-events").json()["attention"]


def test_percentage_is_toward_over_valid_time_and_unobserved_time_is_separate(client, streaming_ai, db):
    s = started(client, db)
    assert put(client, s["id"], snap(toward=24_000, away=6_000, unobserved=10_000)).json() == {"accepted": True}
    r = report(client, s["id"])
    assert r["overall_attention_pct"] == 80  # 24 / (24 + 6); the 10 s without a face are not in it
    assert r["valid_observation_ms"] == 30_000 and r["unobserved_ms"] == 10_000
    assert r["coverage_pct"] == 75  # 30 s valid of 40 s monitored
    assert r["looking_away_ms"] == 6_000 and r["label"].startswith("Estimated visual attention")
    assert "does not show whether" in r["limitations"]


def test_half_and_half_and_too_little_data(client, streaming_ai, db):
    s = started(client, db)
    put(client, s["id"], snap(toward=15_000, away=15_000))
    assert report(client, s["id"])["overall_attention_pct"] == 50
    s2_client_data = snap(epoch="run-bbbbbb", toward=3_000, away=0, buckets=[[40, 3_000, 0, 0]])
    # a second run adds up (page reload): 18 s toward, 15 s away
    put(client, s["id"], s2_client_data)
    r = report(client, s["id"])
    assert r["valid_observation_ms"] == 33_000 and r["monitor_runs"] == 2 and r["overall_attention_pct"] == 55


def test_no_percentage_without_enough_valid_data_and_never_zero_for_a_dead_camera(client, streaming_ai, db):
    s = started(client, db)
    put(client, s["id"], snap(toward=0, away=0, unobserved=60_000))
    r = report(client, s["id"])
    assert r["overall_attention_pct"] is None and r["coverage_pct"] == 0 and r["sufficient_data"] is False
    put(client, s["id"], snap(epoch="run-cccccc", toward=1_000, away=2_000, buckets=[[50, 1_000, 2_000, 0]]))
    assert report(client, s["id"])["overall_attention_pct"] is None  # 3 s of valid time is not enough


def test_a_running_total_can_grow_but_not_shrink_and_resends_are_idempotent(client, streaming_ai, db):
    s = started(client, db)
    assert put(client, s["id"], snap(toward=20_000, away=5_000)).json()["accepted"] is True
    assert put(client, s["id"], snap(toward=20_000, away=5_000)).json()["accepted"] is True
    assert put(client, s["id"], snap(toward=30_000, away=5_000)).json()["accepted"] is True
    stale = put(client, s["id"], snap(toward=20_000, away=5_000)).json()
    assert stale == {"accepted": False, "reason": "stale"}
    assert report(client, s["id"])["looking_toward_ms"] == 30_000


def test_totals_cannot_exceed_the_interview_clock(client, streaming_ai, db):
    s = started(client, db, minutes_ago=1)  # 60 s old
    r = put(client, s["id"], snap(toward=600_000, away=0))
    assert r.json() == {"accepted": False, "reason": "exceeds_interview_time"}
    assert put(client, s["id"], snap(toward=40_000, away=10_000)).json()["accepted"] is True


@pytest.mark.parametrize("patch", [
    {"toward_ms": -1}, {"away_ms": 90_000_000}, {"epoch": "bad epoch!"}, {"window_ms": 100},
    {"buckets": [[0, 9_000, 9_000, 0]]},           # a 10 s bucket cannot hold 18 s
    {"buckets": [[-1, 1, 1, 1]]}, {"by_reason": {"mystery": 5}}, {"landmarks": [1, 2, 3], "toward_ms": "x"},
])
def test_malformed_snapshots_are_rejected(client, streaming_ai, db, patch):
    s = started(client, db)
    assert put(client, s["id"], {**snap(), **patch}).status_code == 422


def test_only_the_owner_with_attention_consent_can_send(client, new_client, streaming_ai, db):
    s = started(client, db)
    other = new_client()
    register_student(other, email="other@test.dev")
    assert put(other, s["id"], snap()).status_code == 404
    # no attention consent -> not accepted, and there is no attention section in the report
    c2 = new_client()
    register_student(c2, email="third@test.dev")
    s2 = _start(c2)
    _consent(c2, s2["id"], {**ALL, "attention": False})
    assert put(c2, s2["id"], snap()).status_code == 409
    assert c2.get(f"/api/student/interviews/{s2['id']}/integrity-events").json()["attention"] is None


def test_a_reload_re_consent_keeps_the_totals_and_they_stay_out_of_the_config(client, streaming_ai, db):
    s = started(client, db)
    put(client, s["id"], snap())
    assert _consent(client, s["id"], ALL).status_code == 200  # the page was reloaded
    assert report(client, s["id"])["valid_observation_ms"] == 30_000
    summary = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["summary"]
    assert "attention" not in summary["config"]


def test_report_counts_deviation_events_and_tracking_failures(client, streaming_ai, db):
    s = started(client, db)
    _events(client, s["id"],
            {"event_type": "attention_away", "t_ms": 1_000, "duration_ms": 4_000, "confidence": 0.9},
            {"event_type": "attention_away", "t_ms": 20_000, "duration_ms": 6_000, "confidence": 0.9},
            {"event_type": "camera_interrupted", "t_ms": 30_000, "duration_ms": 2_000},
            {"event_type": "monitoring_unavailable", "t_ms": 40_000})
    put(client, s["id"], snap())
    r = report(client, s["id"])
    assert (r["prolonged_deviation_events"], r["prolonged_deviation_ms"]) == (2, 10_000)
    assert (r["camera_interruptions"], r["tracking_failures"]) == (1, 1)
    # 24 s toward + 6 s away fill buckets 0-2: the first two are all "toward", the third is 4 s toward / 6 s away
    assert [b["attention_pct"] for b in r["timeline"]] == [100, 100, 40] and r["bucket_ms"] == 10_000


def test_no_measurements_means_unavailable_not_a_fake_zero(client, streaming_ai, db):
    s = started(client, db)
    r = report(client, s["id"])
    assert r["available"] is False and "overall_attention_pct" not in r


def test_updates_are_rate_limited(client, streaming_ai, db):
    s = started(client, db)
    codes = [put(client, s["id"], snap(toward=20_000 + i, away=0)).status_code for i in range(35)]
    assert codes.count(429) >= 1 and codes[0] == 200


def test_recruiter_and_other_roles_see_it_only_where_they_may_review(client, new_client, streaming_ai, db):
    admin = new_client()
    admin_login(admin)
    rec = _applied_student(client, new_client, admin)
    s = _start(client)
    _consent(client, s["id"], ALL)
    from app.models import InterviewSession
    row = db.get(InterviewSession, s["id"])
    m = dict(row.monitoring)
    m["clock_origin"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    row.monitoring = m
    db.commit()
    put(client, s["id"], snap())
    assert rec.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404  # still in progress
    _finish(db, s["id"])
    d = rec.get(f"/api/monitoring/sessions/{s['id']}").json()
    assert d["attention"]["overall_attention_pct"] == 80 and "config" not in d["monitoring"]
    assert admin.get(f"/api/monitoring/sessions/{s['id']}").json()["attention"]["coverage_pct"] == 100
    stranger = new_client()
    register_student(stranger, email="stranger@test.dev")
    assert stranger.get(f"/api/monitoring/sessions/{s['id']}").status_code == 403


def test_attention_summary_is_purged_with_the_events(client, streaming_ai, db):
    from app.models import InterviewSession
    from app.routers import monitoring as mon
    s = started(client, db)
    put(client, s["id"], snap())
    row = db.get(InterviewSession, s["id"])
    row.created_at = datetime.now(timezone.utc) - timedelta(days=400)
    db.commit()
    mon.purge_expired(db)
    db.refresh(row)
    assert "attention" not in row.monitoring and row.monitoring.get("features")

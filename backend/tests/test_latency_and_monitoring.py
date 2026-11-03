"""Streamed interview turns, response modes, performance metrics and camera-monitoring integrity events.

All model calls are MOCKED (no Ollama/Kokoro): these tests prove the pipeline logic, ordering, access control and
privacy rules. Real latency is measured by tests_perf/bench_interview_latency.py and tests_e2e/.
"""
import json
import threading
import time

import pytest

from conftest import admin_login, login, register_student


@pytest.fixture(autouse=True)
def _join_background_threads():
    """Let prefetch / turn / feedback threads finish before the next test empties the database."""
    yield
    for t in list(threading.enumerate()):
        if t.name.startswith(("prefetch-", "turn-", "feedback-")):
            t.join(timeout=10)


def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.split("\n\n"):
        ev, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                ev = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if ev:
            out.append((ev, data))
    return out


# --------------------------------------------------------------------------- sentence streaming (pure)

def test_partial_json_string_handles_unfinished_values_and_escapes():
    from app.services.speech_stream import partial_json_string
    assert partial_json_string('{"preface": "', "question") is None
    assert partial_json_string('{"preface": "", "question": "How do yo', "question") == ("How do yo", False)
    assert partial_json_string('{"question": "Say \\"hi\\" now", "x"', "question") == ('Say "hi" now', True)
    assert partial_json_string('{"question": "ends with \\', "question") == ("ends with ", False)


def test_split_complete_never_cuts_words_or_abbreviations():
    from app.services.speech_stream import split_complete
    done, rest = split_complete("Good point about indexes. Now, e.g. in Postgres, how would yo", final=False)
    assert done == ["Good point about indexes."]
    assert rest == "Now, e.g. in Postgres, how would yo"
    done, rest = split_complete("Version 3.5 was used. Why", final=False)
    assert done == ["Version 3.5 was used."] and rest == "Why"
    assert split_complete("Okay. Tell me about yourself.", final=True)[0] == ["Okay. Tell me about yourself."]


def test_spoken_stream_emits_preface_then_question_and_skips_greeting():
    from app.services.speech_stream import SpokenStream, final_sentences, remaining_after
    full = json.dumps({"preface": "You covered the basics well. You missed indexing.",
                       "question": "Hello, I'm Aria. How would you speed up a slow query in PostgreSQL?",
                       "question_type": "technical", "is_followup": False})
    got = []
    s = SpokenStream(got.append)
    for i in range(1, len(full) + 1, 5):
        s.feed(full[:i])
    s.feed(full, final=True)
    assert got == ["You covered the basics well.", "You missed indexing.",
                   "How would you speed up a slow query in PostgreSQL?"]
    final = final_sentences("You covered the basics well. You missed indexing.",
                            "How would you speed up a slow query in PostgreSQL?")
    assert remaining_after(got[:2], final) == [final[2]]
    assert remaining_after(["Something else entirely here."], final) is None


def test_ollama_url_avoids_slow_localhost_lookup(monkeypatch):
    """Windows: 'localhost' tried IPv6 first and cost ~2.1 s per connection to Ollama (measured)."""
    from app.config import get_settings
    from app.services import local_llm
    for given, expected in [("http://localhost:11434", "http://127.0.0.1:11434"),
                            ("http://localhost:11434/", "http://127.0.0.1:11434"),
                            ("http://gpu-box:11434", "http://gpu-box:11434")]:
        monkeypatch.setattr(get_settings(), "ollama_base_url", given)
        assert local_llm._base_url() == expected


def test_question_starting_like_a_greeting_is_still_spoken():
    """Regression (browser run): "Hi Priya, how did you ...?" matched the greeting filter and was never spoken."""
    from app.services.speech_stream import final_sentences
    q = "Hi Priya, how did you decide to build the Placement Tracker app with React and Flask?"
    assert final_sentences("", q) == [q]
    assert final_sentences("", "Hello, I'm Victor. How would you index a large table?") == \
        ["How would you index a large table?"]


def test_long_first_sentence_split_at_a_natural_pause_only():
    from app.services.speech_stream import split_first_clause
    long = ("Thanks for walking me through your library API, so tell me how you decided which columns to index "
            "in PostgreSQL?")
    head, tail = split_first_clause(long)
    assert head.endswith("library API,") and f"{head} {tail}" == long
    assert split_first_clause("How does a hash map handle collisions?") == ("How does a hash map handle collisions?", "")
    no_comma = "Explain how a B tree index speeds up lookups in a relational database and when it does not help much"
    assert split_first_clause(no_comma) == (no_comma, "")


# --------------------------------------------------------------------------- streamed turns

@pytest.fixture()
def streaming_ai(monkeypatch):
    """Fake model that streams its question JSON through on_delta like Ollama does, plus fake TTS."""
    from app.services import ai, tts
    monkeypatch.setattr(ai, "ai_status", lambda db: {"configured": True, "enabled": True, "available": True,
                                                     "model": "stub"})
    state = {"n": 0, "kwargs": [], "repeat_once": False}

    def next_q(db, user_id, **kw):
        state["n"] += 1
        state["kwargs"].append(kw)
        q = f"Question number {state['n']}: how does a hash map handle collisions in practice?"
        if state["repeat_once"] and state["n"] == 2:
            q = "Question number 1: how does a hash map handle collisions in practice?"  # a repeat
        if kw.get("avoid"):
            q = "Explain the CAP theorem using an example from one of your own projects."
        coaching = kw.get("response_mode") == "coaching" and kw.get("history")
        out = {"preface": "Good effort on that one." if coaching else "",
               "question": q, "question_type": "technical", "is_followup": False}
        text = json.dumps(out)
        if kw.get("on_delta"):
            for i in range(4, len(text) + 4, 4):
                kw["on_delta"](text[:i])
        return out

    def score(db, user_id, **kw):
        return {"relevance": 8, "correctness": 7, "clarity": 8, "communication": 9, "completeness": 7, "score": 79.0,
                "details": {"completeness": 7, "next_difficulty": "medium"}, "feedback": ""}

    monkeypatch.setattr(ai, "next_interview_question", next_q)
    monkeypatch.setattr(ai, "score_answer", score)
    monkeypatch.setattr(ai, "answer_feedback", lambda db, uid, **kw: {
        "strengths": ["clear"], "missing_concepts": [], "improvements": ["x"], "feedback": "ok",
        "better_answer_hint": "", "sample_answer": "s"})
    monkeypatch.setattr(tts, "synthesize", lambda text, voice=None, speed=None, cache=False: {
        "audio_wav_b64": "UklGRg==", "duration": 1.0, "visemes": [], "voice": voice or "af_heart", "text": text})
    return state


def _start(client, **extra):
    body = {"job_role": "Backend Developer", "category": "technical", "mode": "voice", "question_count": 3,
            "defer_first_question": True, **extra}
    r = client.post("/api/student/interviews", json=body)
    assert r.status_code == 201, r.text
    # Wait for the first-question prefetch thread so the next request sees the question it stores.
    if extra.get("defer_first_question", True):
        from conftest import join_app_threads
        join_app_threads()
    return r.json()["session"]


def _wait_question(client, sid, n=1):
    for t in list(threading.enumerate()):
        if t.name == f"prefetch-{sid}":
            t.join(timeout=10)
    for _ in range(100):
        s = client.get(f"/api/student/interviews/{sid}").json()
        if len(s["questions"]) >= n:
            return s
        time.sleep(0.05)
    raise AssertionError("prefetch did not create the first question")


def test_live_interview_prefetches_first_question_and_streams_turns(client, streaming_ai):
    register_student(client)
    s = _start(client, response_mode="coaching")
    assert s["response_mode"] == "coaching"
    s = _wait_question(client, s["id"])  # written in the background while the candidate does the setup
    q1 = s["questions"][0]

    events = parse_sse(client.post(f"/api/student/interviews/{s['id']}/turn",
                                   json={"tts": {"voice": "af_heart", "speed": 1.0}}).text)
    kinds = [e for e, _ in events]
    assert kinds[-1] == "done" and "sentence" in kinds and "audio" in kinds
    assert [d["text"] for e, d in events if e == "sentence"] == [q1["text"]]  # first question, spoken as is
    assert all(d["index"] == i for i, d in enumerate(d for e, d in events if e == "audio"))

    answer = {"question_id": q1["id"], "answer": "Collisions are handled with chaining or open addressing; Java "
                                                 "uses linked lists that turn into trees.", "input_mode": "voice"}
    events = parse_sse(client.post(f"/api/student/interviews/{s['id']}/turn",
                                   json={"answer": answer, "tts": {"voice": "af_heart"}}).text)
    kinds = [e for e, _ in events]
    assert kinds.index("scored") < kinds.index("sentence") < kinds.index("done")  # score first, then question
    spoken = [d["text"] for e, d in events if e == "sentence"]
    assert spoken[0] == "Good effort on that one."  # coaching mode: brief spoken feedback before the question
    done = events[-1][1]
    assert done["session"]["answered"] == 1 and len(done["session"]["questions"]) == 2
    assert done["timings"]["first_text_ms"] is not None
    assert streaming_ai["kwargs"][-1]["response_mode"] == "coaching"

    # the same answer again (double click / retry) is rejected, not processed twice
    dup = client.post(f"/api/student/interviews/{s['id']}/turn", json={"answer": answer})
    assert dup.status_code == 409


def test_turn_lock_blocks_concurrent_turns(client, streaming_ai):
    from app.routers import interviews
    register_student(client)
    s = _start(client)
    _wait_question(client, s["id"])
    assert interviews._lock_turn(s["id"])
    try:
        assert client.post(f"/api/student/interviews/{s['id']}/turn", json={}).status_code == 409
    finally:
        interviews._unlock_turn(s["id"])


def test_repeated_question_is_retracted_and_replaced(client, streaming_ai):
    register_student(client)
    streaming_ai["repeat_once"] = True
    s = _start(client)
    s = _wait_question(client, s["id"])
    events = parse_sse(client.post(f"/api/student/interviews/{s['id']}/turn", json={
        "answer": {"question_id": s["questions"][0]["id"], "answer": "Chaining and open addressing with probing."},
        "tts": {"voice": "af_heart"}}).text)
    kinds = [e for e, _ in events]
    assert "retract" in kinds
    after = kinds[kinds.index("retract"):]
    assert "sentence" in after and events[-1][0] == "done"
    final_q = events[-1][1]["session"]["questions"][-1]["text"]
    assert "CAP theorem" in final_q  # regenerated, not the repeat
    assert [d["text"] for e, d in events if e == "sentence"][-1] == final_q


def test_text_mode_start_is_unchanged(client, streaming_ai):
    register_student(client)
    r = client.post("/api/student/interviews", json={"job_role": "Dev", "mode": "text", "question_count": 3})
    assert r.status_code == 201 and len(r.json()["session"]["questions"]) == 1


# --------------------------------------------------------------------------- performance metrics

def test_perf_metrics_whitelisted_and_admin_only(client, new_client, streaming_ai):
    register_student(client)
    r = client.post("/api/perf/client", json={"metrics": [
        {"metric": "client.answer_to_next_question", "duration_ms": 4200, "meta": {"mode": "fast", "answer": "secret"}},
        {"metric": "client.anything_else", "duration_ms": 1}]})
    assert r.json() == {"stored": 1}
    assert client.get("/api/admin/performance").status_code == 403
    admin = new_client()
    admin_login(admin)
    rows = {m["metric"]: m for m in admin.get("/api/admin/performance").json()["metrics"]}
    m = rows["client.answer_to_next_question"]
    assert m["count"] == 1 and m["p95_ms"] == 4200
    from app import database
    from app.models import PerfMetric
    db = database.SessionLocal()
    stored = db.query(PerfMetric).filter_by(metric="client.answer_to_next_question").one()
    assert stored.meta == {"mode": "fast"}  # non-whitelisted / text fields never stored
    db.close()


# --------------------------------------------------------------------------- monitoring

FEATURES = {"camera": True, "face_presence": True, "multiple_faces": True, "attention": False, "focus_changes": True}


def _consent(client, sid, features=FEATURES, permission="granted"):
    pol = client.get("/api/monitoring/policy").json()
    return client.post(f"/api/student/interviews/{sid}/monitoring/consent",
                       json={"policy_version": pol["version"], "features": features, "camera_permission": permission})


def test_policy_discloses_processing_retention_and_access(client):
    register_student(client)
    p = client.get("/api/monitoring/policy").json()
    assert "browser" in p["processing"] and p["retention_days"] == 90
    # recruiters: only for jobs the candidate applied to (security module, 2026-10-23); disclosed in the policy
    assert "recruiters of jobs you have applied to" in p["access"] and p["camera_required"] is True  # default
    assert "never" in p["review"].lower()


def test_events_only_for_consented_features_with_server_side_severity(client, streaming_ai):
    register_student(client)
    s = _start(client)
    assert _consent(client, s["id"]).status_code == 200
    r = client.post(f"/api/student/interviews/{s['id']}/integrity-events", json={"events": [
        {"event_type": "face_absent", "t_ms": 1000, "duration_ms": 3000, "confidence": 0.95},
        {"event_type": "face_absent", "t_ms": 9000, "duration_ms": 70000, "confidence": 0.9},
        {"event_type": "multiple_faces", "t_ms": 5000, "duration_ms": 20000, "confidence": 0.4},  # unreliable
        {"event_type": "attention_away", "t_ms": 6000, "duration_ms": 90000, "confidence": 0.99},  # not consented
        {"event_type": "focus_change", "t_ms": 7000, "duration_ms": 2000}]})
    assert r.json() == {"stored": 4, "ignored": 1}
    # a client cannot set severity or review status
    bad = client.post(f"/api/student/interviews/{s['id']}/integrity-events", json={"events": [
        {"event_type": "face_absent", "t_ms": 1, "severity": "info", "review_status": "no_concern"}]})
    assert bad.status_code == 422 or bad.json()["stored"] == 1
    mine = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()
    by = [(e["event_type"], e["severity"]) for e in mine["events"] if e["t_ms"] > 1]
    assert ("face_absent", "info") in by and ("face_absent", "medium") in by
    assert ("multiple_faces", "info") in by  # low confidence never rises above info
    assert mine["summary"]["status"]["code"] == "review"
    eid = mine["events"][0]["id"]
    ex = client.put(f"/api/student/interviews/{s['id']}/integrity-events/{eid}/explanation",
                    json={"text": "My lamp switched off."})
    assert ex.json()["candidate_explanation"] == "My lamp switched off."


def test_attention_signal_never_above_low_and_no_score_change(client, streaming_ai):
    from app.services.integrity import severity
    assert severity("attention_away", 10 * 60_000, 1.0)[0] == "low"
    assert severity("multiple_faces", 120_000, 0.95)[0] == "high"
    assert severity("monitoring_unavailable", 999_999, 1.0)[0] == "info"
    register_student(client)
    s = _start(client)
    s = _wait_question(client, s["id"])
    _consent(client, s["id"], {**FEATURES, "attention": True})
    client.post(f"/api/student/interviews/{s['id']}/integrity-events", json={"events": [
        {"event_type": "attention_away", "t_ms": 100, "duration_ms": 600000, "confidence": 1.0}]})
    events = parse_sse(client.post(f"/api/student/interviews/{s['id']}/turn", json={"answer": {
        "question_id": s["questions"][0]["id"], "answer": "Chaining and open addressing with linear probing."}}).text)
    assert events[-1][1]["session"]["questions"][0]["answer"]["score"] == 79.0  # same as without monitoring


def test_camera_required_setting_blocks_start_without_camera(client, new_client, streaming_ai):
    admin = new_client()
    admin_login(admin)
    admin.put("/api/admin/settings/monitoring_camera_required", json={"value": True})
    register_student(client)
    s = _start(client)
    r = _consent(client, s["id"], {**FEATURES, "camera": False}, permission="denied")
    assert r.status_code == 403 and "requires the camera" in r.json()["detail"]


def test_withdraw_stops_recording_events(client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    assert client.post(f"/api/student/interviews/{s['id']}/monitoring/withdraw", params={"t_ms": 5000}).status_code == 200
    r = client.post(f"/api/student/interviews/{s['id']}/integrity-events",
                    json={"events": [{"event_type": "face_absent", "t_ms": 6000, "duration_ms": 30000}]})
    assert r.status_code == 409
    ev = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"]
    assert [e["event_type"] for e in ev] == ["monitoring_withdrawn"]


def test_reviewer_access_is_least_privilege_and_audited(client, new_client, streaming_ai):
    stu = register_student(client)
    s = _start(client)
    _consent(client, s["id"])
    client.post(f"/api/student/interviews/{s['id']}/integrity-events", json={"events": [
        {"event_type": "multiple_faces", "t_ms": 100, "duration_ms": 30000, "confidence": 0.9}]})
    other = new_client()
    register_student(other, email="other@test.dev")
    assert other.get(f"/api/student/interviews/{s['id']}/integrity-events").status_code == 404

    admin = new_client()
    admin_login(admin)
    m = admin.post("/api/admin/users", json={"full_name": "Meera Mentor", "email": "m@test.dev",
                                            "password": "Passw0rd!", "role": "mentor"}).json()
    rec = admin.post("/api/admin/users", json={"full_name": "Rita Recruiter", "email": "r@test.dev",
                                              "password": "Passw0rd!", "role": "recruiter",
                                              "company_name": "Acme"}).json()
    admin.patch(f"/api/admin/users/{rec['id']}", json={"status": "active"})
    mentor = new_client()
    login(mentor, "m@test.dev", "Passw0rd!")
    recruiter = new_client()
    login(recruiter, "r@test.dev", "Passw0rd!")

    # a recruiter the student never applied to sees nothing (security module: recruiters see applicants only)
    assert recruiter.get("/api/monitoring/sessions").json()["items"] == []
    assert recruiter.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404
    assert mentor.get("/api/monitoring/sessions").status_code == 403  # no review permission yet
    admin.patch(f"/api/admin/users/{m['id']}", json={"permissions": ["review_integrity"]})
    assert mentor.get("/api/monitoring/sessions").json()["items"] == []  # permission, but student not assigned
    assert mentor.get(f"/api/monitoring/sessions/{s['id']}").status_code == 404
    admin.post("/api/admin/assignments", json={"mentor_id": m["id"], "student_ids": [stu["id"]]})
    items = mentor.get("/api/monitoring/sessions").json()["items"]
    assert [i["id"] for i in items] == [s["id"]] and items[0]["monitoring"]["status"]["code"] == "review"

    detail = admin.get(f"/api/monitoring/sessions/{s['id']}").json()
    assert detail["events"][0]["severity"] == "medium" and "not evidence" in detail["note"]
    eid = detail["events"][0]["id"]
    r = mentor.patch(f"/api/monitoring/events/{eid}", json={"review_status": "no_concern",
                                                             "reviewer_notes": "Sibling walked past."})
    assert r.status_code == 200 and r.json()["review_status"] == "no_concern"
    assert mentor.get("/api/monitoring/sessions").json()["items"][0]["monitoring"]["status"]["code"] == "warning"
    # the student sees the review result but not the reviewer's private notes
    mine = client.get(f"/api/student/interviews/{s['id']}/integrity-events").json()["events"][0]
    assert mine["review_status"] == "no_concern" and "reviewer_notes" not in mine
    logs = admin.get("/api/admin/audit-logs", params={"action": "monitoring.review"}).json()["items"]
    assert len(logs) == 1
    # recruiters' candidate view never includes monitoring data
    assert "monitoring" not in json.dumps(admin.get(f"/api/admin/interviews/{s['id']}").json())


def test_expired_events_are_purged(client, streaming_ai, db):
    from datetime import datetime, timedelta, timezone
    from app.models import IntegrityEvent
    from app.routers.monitoring import purge_expired
    register_student(client)
    s = _start(client)
    _wait_question(client, s["id"])
    db.add(IntegrityEvent(session_id=s["id"], event_type="low_light", t_ms=1, severity="info",
                          confidence_sufficient=True, created_at=datetime.now(timezone.utc) - timedelta(days=200)))
    db.commit()
    assert purge_expired(db) == 1

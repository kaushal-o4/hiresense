"""Integrity detectors added on top of the camera monitoring: paste, full screen / second display, phone or notes."""
from app.services import integrity
from conftest import register_student
# shared helpers and fixtures from the monitoring tests (imported, so pytest sees the fixtures here too)
from test_latency_and_monitoring import _consent, _join_background_threads, _start, streaming_ai  # noqa: F401

ALL = {"camera": True, "face_presence": True, "multiple_faces": True, "attention": False, "focus_changes": True,
       "paste": True, "screen": True, "objects": True}


def _events(client, sid):
    return client.get(f"/api/student/interviews/{sid}/integrity-events").json()["events"]


def _send(client, sid, events):
    return client.post(f"/api/student/interviews/{sid}/integrity-events", json={"events": events})


# ---------------------------------------------------------------- severity rules (pure)

def test_new_detectors_are_never_high_severity():
    for t in ("paste_detected", "paste_long", "fullscreen_exit", "second_display", "phone_in_view", "notes_in_view"):
        for dur in (0, 5_000, 600_000):
            level, _ = integrity.severity(t, dur, 0.99 if t.endswith("_in_view") else None)
            assert level in ("info", "low", "medium"), (t, dur, level)


def test_paste_is_informational_and_long_pastes_escalate_only_when_repeated():
    assert integrity.severity("paste_detected", None, None)[0] == "info"
    assert integrity.severity("paste_long", None, None)[0] == "low"
    assert integrity.paste_severity("low", 0) == "low"
    assert integrity.paste_severity("low", 1) == "low"
    assert integrity.paste_severity("low", 2) == "medium"  # the third long paste


def test_phone_needs_duration_and_confidence_for_medium():
    assert integrity.severity("phone_in_view", 12_000, 0.9)[0] == "medium"
    assert integrity.severity("phone_in_view", 4_000, 0.9)[0] == "low"
    assert integrity.severity("phone_in_view", 12_000, 0.65)[0] == "low"
    assert integrity.severity("phone_in_view", 12_000, 0.3)[0] == "info"  # unreliable frames -> info only
    assert integrity.severity("fullscreen_exit", 3_000, None)[0] == "info"
    assert integrity.severity("fullscreen_exit", 15_000, None)[0] == "low"


def test_policy_discloses_new_features_and_marks_them_optional():
    for key in ("paste", "screen", "objects"):
        f = integrity.FEATURES[key]
        assert "optional" in f["label"].lower()
    assert "never stored" in integrity.FEATURES["paste"]["why"]
    assert "legitimate" in integrity.FEATURES["paste"]["why"]
    assert "objects" in integrity.FEATURES["camera"]["required_for"]


# ---------------------------------------------------------------- API

def test_new_events_are_stored_only_with_their_own_consent(client, streaming_ai):
    register_student(client)
    s = _start(client)
    base = {k: v for k, v in ALL.items() if k not in ("paste", "screen", "objects")}
    assert _consent(client, s["id"], features=base).status_code == 200  # camera etc. but none of the new opt-ins
    r = _send(client, s["id"], [{"event_type": "paste_long", "t_ms": 1000},
                                {"event_type": "phone_in_view", "t_ms": 2000, "duration_ms": 12000, "confidence": 0.9},
                                {"event_type": "fullscreen_exit", "t_ms": 3000, "duration_ms": 20000}])
    assert r.json() == {"stored": 0, "ignored": 3}


def test_new_events_get_server_side_severity(client, streaming_ai):
    register_student(client)
    s = _start(client)
    assert _consent(client, s["id"], features=ALL).status_code == 200
    r = _send(client, s["id"], [
        {"event_type": "paste_detected", "t_ms": 1000},
        {"event_type": "phone_in_view", "t_ms": 2000, "duration_ms": 12000, "confidence": 0.9},
        {"event_type": "notes_in_view", "t_ms": 3000, "duration_ms": 60000, "confidence": 0.95},
        {"event_type": "fullscreen_exit", "t_ms": 4000, "duration_ms": 20000},
        {"event_type": "second_display", "t_ms": 5000}])
    assert r.json()["stored"] == 5
    sev = {e["event_type"]: e["severity"] for e in _events(client, s["id"])}
    assert sev == {"paste_detected": "info", "phone_in_view": "medium", "notes_in_view": "low",
                   "fullscreen_exit": "low", "second_display": "low"}


def test_repeated_long_pastes_escalate_across_batches(client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"], features=ALL)
    _send(client, s["id"], [{"event_type": "paste_long", "t_ms": 1000}, {"event_type": "paste_long", "t_ms": 2000}])
    _send(client, s["id"], [{"event_type": "paste_long", "t_ms": 3000}])  # a later batch still counts the earlier ones
    levels = [e["severity"] for e in sorted(_events(client, s["id"]), key=lambda e: e["t_ms"])]
    assert levels == ["low", "low", "medium"]


def test_object_detection_is_switched_off_without_camera(client, streaming_ai):
    register_student(client)
    s = _start(client)
    from app import database
    from app.models import PlatformSetting
    db = database.SessionLocal()
    db.merge(PlatformSetting(key="monitoring_camera_required", value=False))  # camera optional for this check
    db.commit()
    db.close()
    r = _consent(client, s["id"], features={**ALL, "camera": False}, permission="denied")
    assert r.status_code == 200, r.text
    f = r.json()["monitoring"]["features"]
    assert f["objects"] is False and f["paste"] is True and f["screen"] is True


def test_unknown_event_type_is_rejected(client, streaming_ai):
    register_student(client)
    s = _start(client)
    _consent(client, s["id"], features=ALL)
    assert _send(client, s["id"], [{"event_type": "mind_reading", "t_ms": 1}]).status_code == 422

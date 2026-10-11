"""Interview integrity monitoring: disclosure policy, severity rules and neutral status labels.

Principles (enforced here and in routers/monitoring.py):
  * Camera analysis runs in the candidate's browser (MediaPipe face landmarks). No video, image, face landmark or
    biometric measurement leaves the browser - only short event records (type, interview-relative time, duration,
    how consistently the frames agreed).
  * Signals are approximate. A missing face, a second face or looking away is NEVER treated as proof of
    misconduct; severity reflects how reliable and how relevant a signal is, and the highest level only says a
    human should look at it.
  * Integrity signals are kept apart from interview scoring: they never change any score.
  * No face recognition / identification, no emotion, honesty or personality inference.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

POLICY_VERSION = "2026-10-12"  # bump whenever FEATURES or what is stored changes, so consent is asked again
CONFIDENCE_SUFFICIENT = 0.6  # share of analysed frames that must agree before a signal can rise above "info"

FEATURES = {
    "camera": {
        "label": "Camera with self-view",
        "why": "Lets you check your framing and lighting, and is needed for the features below.",
        "required_for": ["face_presence", "multiple_faces", "attention"],
    },
    "face_presence": {
        "label": "Face visibility",
        "why": "Notices when no face is visible for a sustained time (for example you moved out of frame or the "
               "camera is covered), so you can be reminded to adjust your camera.",
    },
    "multiple_faces": {
        "label": "More than one face",
        "why": "Notices when more than one face appears to be visible for a sustained time. It does not identify "
               "anyone.",
    },
    "attention": {
        "label": "Approximate head direction and gaze (optional)",
        "why": "Estimates whether your face is generally turned toward the screen. This is approximate and can be "
               "wrong because of glasses, lighting, camera position, disability or individual differences. Looking "
               "away is normal while thinking and is never treated as cheating.",
    },
    "focus_changes": {
        "label": "Browser focus changes",
        "why": "Records when you switch to another tab or window during the interview (the app cannot see what is "
               "on other tabs or screens).",
    },
    "paste": {
        "label": "Pasted text in answers (optional)",
        "why": "Records that text of 40 or more characters was pasted into a typed answer, and whether it was long "
               "(200+ characters). The pasted text itself is never stored. Pasting can be legitimate, for example "
               "from dictation or accessibility tools, so a normal paste is only noted for information.",
    },
    "screen": {
        "label": "Full screen and extra displays (optional)",
        "why": "Asks for full screen during the interview and records when you leave it and for how long, and notes "
               "when a second display is connected (supported in Chrome and Edge). The app cannot see what is on "
               "any screen.",
    },
    "objects": {
        "label": "Phone or notes in view (optional, approximate)",
        "why": "Uses on-device object detection on the camera picture to notice a phone or a book/notes that stays "
               "visible for several seconds. It looks only for objects, never at you, and can mistake other objects "
               "(for example a wallet) for a phone.",
        "requires": "camera",
    },
}
FEATURES["camera"]["required_for"] = FEATURES["camera"]["required_for"] + ["objects"]


def policy(retention_days: int, camera_required: bool) -> dict:
    return {
        "version": POLICY_VERSION,
        "features": FEATURES,
        "processing": "All camera analysis happens in your browser on this device. Video and images are never "
                      "uploaded, recorded or stored.",
        "stored": "Only short event records: event type, time since the interview started, how long it lasted and "
                  "how consistently the camera frames agreed (confidence), plus any explanation you add.",
        "not_stored": "No video, photos, audio recordings, face measurements or identity information.",
        "retention_days": retention_days,
        "access": "You, platform administrators, and mentors who have been explicitly authorised to review "
                  "integrity events for students they support. Recruiters do not receive monitoring data.",
        "review": "Every event can be reviewed by a person, and you can add an explanation to any event. Events never "
                  "change your interview scores and never lead to an automatic penalty.",
        "withdraw": "You can switch monitoring off at any time with 'Stop monitoring', or end the interview. The "
                    "camera stops immediately.",
        "camera_required": camera_required,
        "microphone": "Your microphone is on only while it is your turn to answer (red Recording badge). Audio is "
                      "transcribed on this app's server and not stored.",
    }


# event type -> consent feature that must be on for the browser to report it
EVENT_FEATURE = {
    "face_absent": "face_presence", "camera_obstructed": "face_presence", "low_light": "face_presence",
    "multiple_faces": "multiple_faces", "attention_away": "attention", "focus_change": "focus_changes",
    "camera_interrupted": "camera", "permission_revoked": "camera", "monitoring_interrupted": "camera",
    "monitoring_unavailable": "camera",
    "paste_detected": "paste", "paste_long": "paste", "fullscreen_exit": "screen", "second_display": "screen",
    "phone_in_view": "objects", "notes_in_view": "objects",
}

LABELS = {
    "face_absent": "Face not visible", "multiple_faces": "More than one face visible",
    "attention_away": "Attention appeared away from screen (approximate)", "camera_interrupted": "Camera stream interrupted",
    "camera_obstructed": "Camera view blocked or very dark", "low_light": "Low lighting",
    "monitoring_interrupted": "Monitoring paused (technical)", "focus_change": "Left the interview tab/window",
    "permission_revoked": "Camera or microphone permission revoked", "monitoring_withdrawn": "Candidate stopped monitoring",
    "monitoring_unavailable": "Monitoring unavailable on this device",
    "paste_detected": "Pasted text into an answer", "paste_long": "Pasted a long text into an answer",
    "fullscreen_exit": "Left full screen", "second_display": "Second display connected",
    "phone_in_view": "Phone appeared to be visible (approximate)",
    "notes_in_view": "Book or notes appeared to be visible (approximate)",
}

# Repeated long pastes in one interview are more meaningful than one (see report_events).
PASTE_LONG_REPEAT = 3


def severity(event_type: str, duration_ms: int | None, confidence: float | None) -> tuple[str, bool]:
    """(severity, confidence_sufficient). Based on how reliable and how relevant the signal is - see module doc."""
    sure = confidence is None or confidence >= CONFIDENCE_SUFFICIENT
    secs = (duration_ms or 0) / 1000
    if event_type in ("monitoring_withdrawn", "monitoring_unavailable", "monitoring_interrupted", "low_light"):
        level = "info"  # environment / technical: says nothing about conduct
    elif event_type == "camera_obstructed":
        level = "low" if secs >= 60 else "info"
    elif event_type == "face_absent":
        level = "medium" if secs >= 60 else "low" if secs >= 15 else "info"
    elif event_type == "multiple_faces":
        level = "high" if secs >= 60 and (confidence or 0) >= 0.85 else "medium" if secs >= 15 else "low" if secs >= 5 else "info"
    elif event_type == "attention_away":
        level = "low" if secs >= 20 else "info"  # gaze/head estimates are unreliable: never above "low"
    elif event_type == "focus_change":
        level = "low" if secs >= 30 else "info"
    elif event_type == "camera_interrupted":
        level = "low"
    elif event_type == "permission_revoked":
        level = "medium"  # could be accidental: a reviewer should look, nothing more
    elif event_type == "paste_detected":
        level = "info"  # pasting is a legitimate input route (dictation, accessibility)
    elif event_type == "paste_long":
        level = "low"  # raised to "medium" only when repeated - see paste_severity()
    elif event_type == "fullscreen_exit":
        level = "low" if secs >= 10 else "info"
    elif event_type == "second_display":
        level = "low"  # a docked laptop is common; it only says another screen exists
    elif event_type == "phone_in_view":
        # object detection can mistake a wallet or remote for a phone: never above "medium"
        level = "medium" if secs >= 10 and (confidence or 0) >= 0.7 else "low"
    elif event_type == "notes_in_view":
        level = "low"  # books on a shelf behind the candidate are common
    else:
        level = "info"
    if not sure:
        level = "info"
    return level, sure


def paste_severity(level: str, previous_long_pastes: int) -> str:
    """A long paste becomes "medium" once it has happened PASTE_LONG_REPEAT times in the same interview."""
    return "medium" if level == "low" and previous_long_pastes + 1 >= PASTE_LONG_REPEAT else level


def session_status(monitoring: dict | None, counts: dict[str, int], unreviewed_serious: int) -> dict:
    """Neutral, non-accusatory summary. The absence of events is not proof that nothing happened."""
    if not monitoring or not monitoring.get("features", {}).get("camera") and not monitoring.get("features", {}).get("focus_changes"):
        return {"code": "unavailable", "label": "Monitoring unavailable",
                "detail": "This interview was not monitored (not enabled, not consented, or no camera)."}
    if monitoring.get("withdrawn_at"):
        note = "The candidate stopped monitoring during the interview."
    elif monitoring.get("camera_permission") in ("denied", "unavailable") and monitoring.get("features", {}).get("camera"):
        return {"code": "unavailable", "label": "Monitoring unavailable", "detail": "Camera access was not available."}
    else:
        note = None
    if unreviewed_serious:
        return {"code": "review", "label": "Event requires review",
                "detail": f"{unreviewed_serious} medium/high event(s) not reviewed yet." + (f" {note}" if note else "")}
    if sum(counts.values()):
        return {"code": "warning", "label": "Monitoring warning",
                "detail": "Some signals were recorded; see the events." + (f" {note}" if note else "")}
    return {"code": "none", "label": "No integrity events detected",
            "detail": "No signals were recorded. This does not prove that nothing happened." + (f" {note}" if note else "")}


def retention_cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, days))

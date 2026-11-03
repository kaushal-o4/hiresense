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
from typing import Literal

from pydantic import BaseModel, Field

POLICY_VERSION = "2026-10-23"  # bump whenever FEATURES or what is stored changes, so consent is asked again
CONFIDENCE_SUFFICIENT = 0.6  # default share of analysed frames that must agree before a signal can rise above "info"
SECURITY_CONFIG_KEY = "security_config"  # platform_settings row edited at admin -> Security settings

Severity = Literal["info", "low", "medium", "high"]


# --------------------------------------------------------------------------- admin-configurable policy
# The numbers below are engineering starting points, NOT validated cheating thresholds. They are meant to be tuned
# against real test sessions. The browser reads them from GET /api/monitoring/policy; the server applies the
# severity rules itself, so changing them in the browser changes nothing that is stored.

class DetectorSwitches(BaseModel):
    face_presence: bool = True
    multiple_faces: bool = True
    attention: bool = True  # approximate head direction + eye direction
    focus_changes: bool = True
    screen: bool = True
    paste: bool = True
    objects: bool = True
    audio: bool = True  # possible additional voice during answers (on-device, approximate)


class Thresholds(BaseModel):
    frame_rate: float = Field(2, ge=0.5, le=8)  # face analyses per second (lowered automatically on slow devices)
    calibration_ms: int = Field(5000, ge=2000, le=20000)  # neutral head/eye position measured at the start
    gaze_record_ms: int = Field(3000, ge=1000, le=60000)  # a deviation this long becomes an event
    gaze_warn_ms: int = Field(8000, ge=2000, le=120000)  # ... and this long shows the candidate a reminder
    gaze_yaw_deg: float = Field(25, ge=10, le=60)  # head turn beyond the calibrated position
    gaze_pitch_deg: float = Field(20, ge=10, le=60)
    gaze_eye: float = Field(0.5, ge=0.2, le=1.0)  # eye-direction blendshape difference from calibration (0-1)
    gaze_repeat_count: int = Field(5, ge=2, le=50)  # this many recorded deviations ...
    gaze_repeat_window_s: int = Field(120, ge=30, le=1800)  # ... within this window = one "repeated" event
    face_absent_warn_ms: int = Field(5000, ge=1000, le=120000)
    face_absent_record_ms: int = Field(4000, ge=1000, le=120000)
    multiple_faces_warn_ms: int = Field(3000, ge=1000, le=120000)
    multiple_faces_record_ms: int = Field(3000, ge=1000, le=120000)
    focus_record_ms: int = Field(500, ge=0, le=60000)
    audio_min_speech_ms: int = Field(4000, ge=1000, le=60000)  # voiced audio needed before attribution is judged
    min_confidence: float = Field(CONFIDENCE_SUFFICIENT, ge=0.3, le=0.95)
    attention_window_s: int = Field(30, ge=10, le=300)  # live "visual attention" percentage = the last N seconds
    attention_confirm_ms: int = Field(1000, ge=0, le=5000)  # a change toward/away must last this long to count (natural glances)
    attention_max_gap_ms: int = Field(2500, ge=1000, le=10000)  # longer without a camera frame = unobserved, not attention


class RiskWeights(BaseModel):
    gaze: float = Field(1, ge=0, le=10)  # repeated / very long gaze deviations
    face_absent: float = Field(2, ge=0, le=10)  # sustained absence from the camera frame
    focus: float = Field(2, ge=0, le=10)  # repeated tab switching or long time away
    multiple_faces: float = Field(3, ge=0, le=10)  # persistent second face
    background_speech: float = Field(1, ge=0, le=10)  # repeated possible additional voice
    objects: float = Field(2, ge=0, le=10)  # phone visible for a sustained time
    paste: float = Field(1, ge=0, le=10)  # long pastes
    fullscreen: float = Field(1, ge=0, le=10)
    devices: float = Field(1, ge=0, le=10)  # camera / microphone / permission interruptions


class RiskBands(BaseModel):
    low: float = Field(1, ge=0)
    moderate: float = Field(4, ge=0)
    high: float = Field(8, ge=0)


class SecurityConfig(BaseModel):
    detectors: DetectorSwitches = DetectorSwitches()
    thresholds: Thresholds = Thresholds()
    warning_cooldown_s: int = Field(30, ge=0, le=600)  # the same reminder is not repeated more often than this
    # Pause rule: 0 = never pause. Otherwise the interview pauses (the candidate resumes it) when no face has been
    # visible for this many seconds. Brief detection failures never pause or end an interview.
    pause_on_face_absent_s: int = Field(0, ge=0, le=600)
    # Highest severity an event type may receive (can only lower it, e.g. {"focus_change": "info"}).
    severity_caps: dict[str, Severity] = {}
    risk_weights: RiskWeights = RiskWeights()
    risk_bands: RiskBands = RiskBands()
    # Recruiters may see the security report of a COMPLETED interview of a candidate who applied to one of their
    # jobs - only if this was on (and therefore disclosed) when the candidate consented.
    recruiters_can_view: bool = True


def load_config(raw: dict | None) -> SecurityConfig:
    """Stored JSON -> validated config (an invalid stored row falls back to the defaults)."""
    try:
        return SecurityConfig.model_validate(raw or {})
    except Exception:  # noqa: BLE001 - a broken stored row must not break interviews
        return SecurityConfig()

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
FEATURES["audio"] = {
    "label": "Possible additional voice during your answers (optional, approximate)",
    "why": "While your microphone is on for an answer, this browser checks whether speech is heard while your mouth "
           "does not appear to move (which can mean another voice in the room). It needs the camera. No audio is "
           "recorded for this and nothing about your voice is stored. The interviewer's voice is never included "
           "(your microphone is off while the interviewer speaks). It can be wrong - for example with a face partly "
           "out of view, a beard or a mask - so it is only ever a note for a person to check.",
    "requires": "camera",
}
FEATURES["camera"]["required_for"] = FEATURES["camera"]["required_for"] + ["objects", "audio"]
# Device and connection events (microphone disconnected, network interruption, page reloaded, interview paused) are
# recorded whenever any monitoring feature is on: they describe the session and explain gaps in the other records.
SESSION_FEATURE = "*"


def policy(retention_days: int, camera_required: bool, cfg: SecurityConfig | None = None) -> dict:
    cfg = cfg or SecurityConfig()
    on = cfg.detectors.model_dump()
    return {
        "version": POLICY_VERSION,
        "features": {k: v for k, v in FEATURES.items() if on.get(k, True)},  # disabled detectors are not offered
        "detectors": on,
        "thresholds": cfg.thresholds.model_dump(),
        "warning_cooldown_s": cfg.warning_cooldown_s,
        "pause_on_face_absent_s": cfg.pause_on_face_absent_s,
        "session_events": "While any monitoring is on, connection interruptions, microphone or camera "
                          "disconnections, pauses and page reloads are also recorded, because they explain gaps in "
                          "the other records.",
        "identity": "Your identity is not checked automatically. The app never compares faces and never stores face "
                    "templates or other biometric data.",
        "recruiters_can_view": cfg.recruiters_can_view,
        "processing": "All camera analysis happens in your browser on this device. Video and images are never "
                      "uploaded, recorded or stored.",
        "stored": "Only short event records: event type, time since the interview started, how long it lasted and "
                  "how consistently the camera frames agreed (confidence), plus any explanation you add.",
        "not_stored": "No video, photos, audio recordings, face measurements or identity information.",
        "retention_days": retention_days,
        "access": ("You, platform administrators, mentors who have been explicitly authorised to review integrity "
                   "events for students they support, and recruiters of jobs you have applied to (completed "
                   "interviews only: the event records and review notes, never any images).")
                  if cfg.recruiters_can_view else
                  ("You, platform administrators, and mentors who have been explicitly authorised to review "
                   "integrity events for students they support. Recruiters do not receive monitoring data."),
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
    "face_partial": "face_presence", "attention_repeated": "attention", "background_speech": "audio",
    "microphone_disconnected": SESSION_FEATURE, "network_interruption": SESSION_FEATURE,
    "session_reconnected": SESSION_FEATURE, "interview_paused": SESSION_FEATURE,
}


def event_allowed(event_type: str, features: dict) -> bool:
    """Only what the candidate agreed to is recorded."""
    need = EVENT_FEATURE.get(event_type, "camera")
    return any(features.values()) if need == SESSION_FEATURE else bool(features.get(need))


# Controlled taxonomy for reports, filters and the API (event_type stays the stored value).
CATEGORIES = {
    "attention_away": "PROLONGED_LOOKING_AWAY", "attention_repeated": "EYE_GAZE_DEVIATION",
    "face_absent": "FACE_NOT_DETECTED", "face_partial": "FACE_PARTIALLY_VISIBLE",
    "multiple_faces": "MULTIPLE_FACES_DETECTED", "focus_change": "BROWSER_TAB_SWITCH",
    "fullscreen_exit": "FULLSCREEN_EXIT", "second_display": "SECOND_DISPLAY",
    "background_speech": "POSSIBLE_BACKGROUND_SPEECH", "microphone_disconnected": "MICROPHONE_DISCONNECTED",
    "camera_interrupted": "CAMERA_DISCONNECTED", "permission_revoked": "PERMISSION_REVOKED",
    "camera_obstructed": "CAMERA_OBSTRUCTED", "low_light": "LOW_LIGHT",
    "network_interruption": "NETWORK_INTERRUPTION", "session_reconnected": "SESSION_RECONNECTED",
    "interview_paused": "INTERVIEW_PAUSED", "paste_detected": "PASTE", "paste_long": "PASTE",
    "phone_in_view": "OBJECT_IN_VIEW", "notes_in_view": "OBJECT_IN_VIEW",
    "monitoring_interrupted": "MONITORING_STATUS", "monitoring_unavailable": "MONITORING_STATUS",
    "monitoring_withdrawn": "MONITORING_STATUS",
}
# POSSIBLE_IDENTITY_MISMATCH belongs to the taxonomy but has no detector: identity matching would need face
# recognition, which this platform deliberately does not do (README, "Interview security module").
ALL_CATEGORIES = sorted(set(CATEGORIES.values()) | {"POSSIBLE_IDENTITY_MISMATCH"})

SOURCES = {
    "attention_away": "face_landmarker", "attention_repeated": "face_landmarker", "face_absent": "face_landmarker",
    "face_partial": "face_landmarker", "multiple_faces": "face_landmarker", "camera_obstructed": "camera_frame",
    "low_light": "camera_frame", "focus_change": "page_visibility", "fullscreen_exit": "fullscreen_api",
    "second_display": "screen_api", "background_speech": "audio_vad+mouth", "microphone_disconnected": "media_device",
    "camera_interrupted": "media_device", "permission_revoked": "permissions_api",
    "network_interruption": "connection", "session_reconnected": "server", "interview_paused": "interview_room",
    "paste_detected": "clipboard_event", "paste_long": "clipboard_event", "phone_in_view": "object_detector",
    "notes_in_view": "object_detector", "monitoring_interrupted": "face_landmarker",
    "monitoring_unavailable": "face_landmarker", "monitoring_withdrawn": "candidate",
}

# Whitelisted per-event details; anything else the browser sends is dropped.
DETAIL_INTS = ("max_faces", "count", "window_s")
DETAIL_ENUMS = {"cause": {"head", "eyes", "head+eyes"}, "edge": {"left", "right", "top", "bottom"},
                "reason": {"offline", "server_unreachable", "ended", "not_found", "not_readable", "page_reload",
                           "face_absent", "manual"}}


def clean_details(raw: dict | None) -> dict | None:
    out: dict = {}
    for k, v in (raw or {}).items():
        if k in DETAIL_INTS and isinstance(v, int) and not isinstance(v, bool):
            out[k] = max(0, min(v, 100_000))
        elif k in DETAIL_ENUMS and v in DETAIL_ENUMS[k]:
            out[k] = v
    return out or None


def describe(event_type: str, duration_ms: int | None, details: dict | None) -> str:
    """One neutral sentence for reports and the timeline."""
    d = details or {}
    extra = []
    if duration_ms:
        extra.append(f"lasting {round(duration_ms / 1000)} s")
    if d.get("max_faces"):
        extra.append(f"up to {d['max_faces']} faces")
    if d.get("count"):
        extra.append(f"{d['count']} times within {d.get('window_s', '?')} s")
    if d.get("cause"):
        extra.append({"head": "head turned", "eyes": "eye direction", "head+eyes": "head and eye direction"}[d["cause"]])
    if d.get("edge"):
        extra.append(f"at the {d['edge']} edge")
    if d.get("reason"):
        extra.append(d["reason"].replace("_", " "))
    base = LABELS.get(event_type, event_type)
    return base + (f" ({', '.join(extra)})" if extra else "")

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
    "face_partial": "Face partly outside the camera frame",
    "attention_repeated": "Repeated looking away (approximate)",
    "background_speech": "Possible additional voice during an answer (uncertain)",
    "microphone_disconnected": "Microphone disconnected or unavailable",
    "network_interruption": "Network connection interrupted",
    "session_reconnected": "Interview page reloaded / reconnected",
    "interview_paused": "Interview paused",
}

# Repeated long pastes in one interview are more meaningful than one (see report_events).
PASTE_LONG_REPEAT = 3


SEVERITY_ORDER = ("info", "low", "medium", "high")


def severity(event_type: str, duration_ms: int | None, confidence: float | None,
             cfg: SecurityConfig | None = None) -> tuple[str, bool]:
    """(severity, confidence_sufficient). Based on how reliable and how relevant the signal is - see module doc."""
    sure = confidence is None or confidence >= (cfg.thresholds.min_confidence if cfg else CONFIDENCE_SUFFICIENT)
    secs = (duration_ms or 0) / 1000
    if event_type in ("monitoring_withdrawn", "monitoring_unavailable", "monitoring_interrupted", "low_light",
                      "session_reconnected", "interview_paused"):
        level = "info"  # environment / technical: says nothing about conduct
    elif event_type == "face_partial":
        level = "low" if secs >= 60 else "info"
    elif event_type in ("attention_repeated", "background_speech"):
        level = "low"  # gaze estimates and voice attribution are unreliable: never above "low"
    elif event_type == "microphone_disconnected":
        level = "low"
    elif event_type == "network_interruption":
        level = "low" if secs >= 30 else "info"
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
    cap = cfg.severity_caps.get(event_type) if cfg else None
    if cap and SEVERITY_ORDER.index(level) > SEVERITY_ORDER.index(cap):
        level = cap
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


# --------------------------------------------------------------------------- risk summary
# A transparent count of potential irregularities, NOT a verdict. It is never used for scores, rejection or any
# automatic decision. Events a reviewer cleared, and events whose frames did not agree enough, are not counted.

CLEARED = ("no_concern", "dismissed", "false_positive")
RISK_RULES = {
    # rule: (label, what one occurrence is, cap on occurrences)
    "gaze": ("Repeated or very long looking away", "each repeated-looking-away event, and each look away of 20 s+", 3),
    "face_absent": ("Sustained absence from the camera frame", "each time no face was visible for 15 s+", 3),
    "focus": ("Repeated tab switching", "every 3 times the interview tab was left, and each time away for 30 s+", 3),
    "multiple_faces": ("Persistent second face", "each time more than one face stayed visible for 5 s+", 3),
    "background_speech": ("Repeated possible additional voice", "every 2 possible-additional-voice events", 3),
    "objects": ("Phone visible for a sustained time", "each time a phone stayed visible for 10 s+", 2),
    "paste": ("Long pastes into answers", "each long paste (200+ characters)", 3),
    "fullscreen": ("Left full screen", "each time full screen was left for 10 s+", 3),
    "devices": ("Device interruptions", "each camera/microphone disconnection or revoked permission", 2),
}
BAND_LABELS = {
    "none": "No significant events detected",
    "low": "Low number of potential irregularities",
    "moderate": "Moderate number of potential irregularities",
    "high": "High number of potential irregularities - requires human review",
}


def _rule_hits(events) -> dict[str, list[list]]:
    """rule -> list of occurrences, each occurrence being the events it is made of."""
    hits: dict[str, list[list]] = {k: [] for k in RISK_RULES}
    short_focus, speech = [], []
    for e in events:
        secs = (e.duration_ms or 0) / 1000
        t = e.event_type
        if t == "attention_repeated" or (t == "attention_away" and secs >= 20):
            hits["gaze"].append([e])
        elif t == "face_absent" and secs >= 15:
            hits["face_absent"].append([e])
        elif t == "multiple_faces" and secs >= 5:
            hits["multiple_faces"].append([e])
        elif t == "phone_in_view" and secs >= 10:
            hits["objects"].append([e])
        elif t == "paste_long":
            hits["paste"].append([e])
        elif t == "fullscreen_exit" and secs >= 10:
            hits["fullscreen"].append([e])
        elif t in ("camera_interrupted", "microphone_disconnected", "permission_revoked"):
            hits["devices"].append([e])
        elif t == "focus_change":
            (hits["focus"].append([e]) if secs >= 30 else short_focus.append(e))
        elif t == "background_speech":
            speech.append(e)
    hits["focus"] += [short_focus[i:i + 3] for i in range(0, len(short_focus) - 2, 3)]
    hits["background_speech"] += [speech[i:i + 2] for i in range(0, len(speech) - 1, 2)]
    return hits


def risk_summary(events, cfg: SecurityConfig | None = None) -> dict:
    cfg = cfg or SecurityConfig()
    weights = cfg.risk_weights.model_dump()
    counted, low_conf, cleared = [], 0, 0
    for e in events:
        if e.review_status in CLEARED:
            cleared += 1
        elif not e.confidence_sufficient:
            low_conf += 1
        else:
            counted.append(e)
    contributions, total = [], 0.0
    for rule, groups in _rule_hits(counted).items():
        if not groups:
            continue
        label, how, cap = RISK_RULES[rule]
        pts = round(weights[rule] * min(len(groups), cap), 2)
        total += pts
        contributions.append({"rule": rule, "label": label, "counted_as": how, "weight": weights[rule],
                              "occurrences": len(groups), "capped_at": cap, "points": pts,
                              "event_ids": [e.id for g in groups for e in g]})
    b = cfg.risk_bands
    code = "high" if total >= b.high else "moderate" if total >= b.moderate else "low" if total >= b.low else "none"
    return {
        "points": round(total, 2), "band": {"code": code, "label": BAND_LABELS[code]},
        "contributions": sorted(contributions, key=lambda c: -c["points"]),
        "excluded": {"low_confidence": low_conf, "cleared_by_reviewer": cleared},
        "method": "Each rule counts related events (never individual video frames), multiplies them by a configurable "
                  "weight and is capped, so one kind of signal cannot dominate. Bands: low from "
                  f"{b.low:g}, moderate from {b.moderate:g}, high from {b.high:g} points. Events a reviewer marked "
                  "as no concern or false positive, and events whose frames did not agree enough, are not counted.",
        "disclaimer": "This summary counts approximate signals for a person to review. It is not evidence of "
                      "misconduct, it is kept separate from interview performance, and it must never be the sole "
                      "basis for rejection, disqualification or any hiring decision.",
    }

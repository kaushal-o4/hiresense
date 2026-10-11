"""Disclosed, opt-in interview integrity monitoring, and the performance dashboard API.

Who may see what (least privilege):
  * the student: their own consent, events and explanations;
  * admins: all monitored interviews;
  * mentors: only with the extra permission `review_integrity`, and only for students they may access
    (assigned, or `view_all_students`);
  * recruiters: never (403). There is no raw footage to share - none is ever recorded.
Every reviewer view and review is written to the audit log (ids only, no candidate content).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_ip, get_current_user, mentor_can_access, require_admin, require_student
from ..models import IntegrityEvent, InterviewSession, User
from ..schemas import (
    ClientMetricsIn, ExplanationIn, IntegrityEventsIn, IntegrityReviewIn, MonitoringConsentIn,
)
from ..services import integrity, perf
from ..services.common import audit, get_setting

router = APIRouter(tags=["monitoring"])

MAX_EVENTS_PER_SESSION = 500
LATE_EVENTS_GRACE = timedelta(minutes=3)  # events flushed by the browser right after the interview ended


def _retention(db: Session) -> int:
    return int(get_setting(db, "monitoring_retention_days") or 90)


def purge_expired(db: Session) -> int:
    """Delete integrity events older than the retention period. Called on reviewer list views and at startup."""
    r = db.execute(delete(IntegrityEvent).where(IntegrityEvent.created_at < integrity.retention_cutoff(_retention(db))))
    db.commit()
    return r.rowcount or 0


def _own_session(db: Session, user: User, session_id: int) -> InterviewSession:
    s = db.get(InterviewSession, session_id)
    if not s or s.student_id != user.id:
        raise HTTPException(404, "Interview not found")
    return s


def event_out(e: IntegrityEvent, reviewer: bool = False) -> dict:
    d = {"id": e.id, "event_type": e.event_type, "label": integrity.LABELS.get(e.event_type, e.event_type),
         "t_ms": e.t_ms, "duration_ms": e.duration_ms, "confidence": e.confidence,
         "confidence_sufficient": e.confidence_sufficient, "severity": e.severity,
         "candidate_explanation": e.candidate_explanation, "review_status": e.review_status,
         "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None}
    if reviewer:
        d["reviewer_notes"] = e.reviewer_notes
    return d


def monitoring_summary(db: Session, s: InterviewSession) -> dict:
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id == s.id)).all()
    counts: dict[str, int] = {}
    for e in events:
        counts[e.severity] = counts.get(e.severity, 0) + 1
    serious = sum(1 for e in events if e.severity in ("medium", "high") and e.review_status == "pending")
    return {"config": s.monitoring, "counts": counts, "total": len(events),
            "status": integrity.session_status(s.monitoring, counts, serious)}


# --------------------------------------------------------------------------- student

@router.get("/api/monitoring/policy")
def monitoring_policy(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {**integrity.policy(_retention(db), bool(get_setting(db, "monitoring_camera_required"))),
            "enabled": bool(get_setting(db, "monitoring_enabled"))}


@router.post("/api/student/interviews/{session_id}/monitoring/consent")
def give_consent(session_id: int, body: MonitoringConsentIn, user: User = Depends(require_student),
                 db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    if s.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    if body.policy_version != integrity.POLICY_VERSION:
        raise HTTPException(409, "The monitoring policy has changed. Please reload the page and read it again.")
    f = body.features.model_dump()
    if not get_setting(db, "monitoring_enabled"):
        f = {k: False for k in f}
    if not f["camera"]:  # camera features need the camera
        f.update(face_presence=False, multiple_faces=False, attention=False)
        if "objects" in f:
            f["objects"] = False
    if get_setting(db, "monitoring_camera_required") and (not f["camera"] or body.camera_permission != "granted"):
        raise HTTPException(403, "This assessment requires the camera. It cannot start without camera access. "
                                 "If you cannot use a camera, contact your placement cell for an alternative.")
    prev = s.monitoring or {}
    s.monitoring = {"policy_version": body.policy_version, "features": f, "camera_permission": body.camera_permission,
                    "accepted_at": prev.get("accepted_at") or datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(), "withdrawn_at": None}
    db.commit()
    return {"monitoring": s.monitoring}


@router.post("/api/student/interviews/{session_id}/monitoring/withdraw")
def withdraw_consent(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db),
                     t_ms: int | None = None):
    s = _own_session(db, user, session_id)
    if not s.monitoring:
        return {"monitoring": None}
    now = datetime.now(timezone.utc).isoformat()
    s.monitoring = {**s.monitoring, "withdrawn_at": now,
                    "features": {k: False for k in (s.monitoring.get("features") or {})}}
    db.add(IntegrityEvent(session_id=s.id, event_type="monitoring_withdrawn", t_ms=max(0, min(t_ms or 0, 21_600_000)),
                          severity="info", confidence_sufficient=True))
    db.commit()
    return {"monitoring": s.monitoring}


@router.post("/api/student/interviews/{session_id}/integrity-events")
def report_events(session_id: int, body: IntegrityEventsIn, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    m = s.monitoring or {}
    features = m.get("features") or {}
    if not m or m.get("withdrawn_at"):
        raise HTTPException(409, "Monitoring is not active for this interview.")
    done_at = s.completed_at.replace(tzinfo=s.completed_at.tzinfo or timezone.utc) if s.completed_at else None
    if s.status != "in_progress" and not (done_at and datetime.now(timezone.utc) - done_at < LATE_EVENTS_GRACE):
        raise HTTPException(400, "This interview is already finished")
    have = db.scalar(select(func.count(IntegrityEvent.id)).where(IntegrityEvent.session_id == s.id)) or 0
    long_pastes = db.scalar(select(func.count(IntegrityEvent.id)).where(
        IntegrityEvent.session_id == s.id, IntegrityEvent.event_type == "paste_long")) or 0
    stored = 0
    for e in body.events:
        if have + stored >= MAX_EVENTS_PER_SESSION:
            break
        if not features.get(integrity.EVENT_FEATURE.get(e.event_type, "camera")):
            continue  # only what the candidate agreed to is recorded
        level, sure = integrity.severity(e.event_type, e.duration_ms, e.confidence)
        if e.event_type == "paste_long":
            level = integrity.paste_severity(level, long_pastes)
            long_pastes += 1
        db.add(IntegrityEvent(session_id=s.id, event_type=e.event_type, t_ms=e.t_ms, duration_ms=e.duration_ms,
                              confidence=round(e.confidence, 3) if e.confidence is not None else None,
                              confidence_sufficient=sure, severity=level))
        stored += 1
    db.commit()
    return {"stored": stored, "ignored": len(body.events) - stored}


@router.get("/api/student/interviews/{session_id}/integrity-events")
def my_events(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id == s.id)
                        .order_by(IntegrityEvent.t_ms)).all()
    return {"summary": monitoring_summary(db, s), "events": [event_out(e) for e in events]}


@router.put("/api/student/interviews/{session_id}/integrity-events/{event_id}/explanation")
def explain_event(session_id: int, event_id: int, body: ExplanationIn, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    e = db.get(IntegrityEvent, event_id)
    if not e or e.session_id != s.id:
        raise HTTPException(404, "Event not found")
    e.candidate_explanation = body.text.strip()
    db.commit()
    return event_out(e)


# --------------------------------------------------------------------------- reviewers

def _reviewer(user: User = Depends(get_current_user)) -> User:
    if user.role == "admin" or (user.role == "mentor" and "review_integrity" in (user.permissions or [])):
        return user
    raise HTTPException(403, "You are not authorised to review interview monitoring.")


def _may_review(db: Session, user: User, student_id: int) -> bool:
    return user.role == "admin" or mentor_can_access(db, user, student_id)


@router.get("/api/monitoring/sessions")
def review_list(request: Request, status: str | None = None, page: int = 1, user: User = Depends(_reviewer),
                db: Session = Depends(get_db)):
    purge_expired(db)
    rows = db.scalars(select(InterviewSession).where(InterviewSession.monitoring.is_not(None))
                      .order_by(InterviewSession.id.desc()).limit(500)).all()
    items = []
    for s in rows:
        if not _may_review(db, user, s.student_id):
            continue
        summ = monitoring_summary(db, s)
        if status and summ["status"]["code"] != status:
            continue
        student = db.get(User, s.student_id)
        items.append({"id": s.id, "student_id": s.student_id, "student_name": student.full_name if student else "?",
                      "job_role": s.job_role, "interviewer": s.interviewer or "aria", "status": s.status,
                      "created_at": s.created_at.isoformat(), "monitoring": summ})
    page_size = 20
    audit(db, user.id, "monitoring.list", "interview", None, {"count": len(items)}, client_ip(request))
    db.commit()
    start = (max(page, 1) - 1) * page_size
    return {"items": items[start:start + page_size], "total": len(items), "page": max(page, 1),
            "pages": max(1, (len(items) + page_size - 1) // page_size)}


@router.get("/api/monitoring/sessions/{session_id}")
def review_detail(session_id: int, request: Request, user: User = Depends(_reviewer), db: Session = Depends(get_db)):
    s = db.get(InterviewSession, session_id)
    if not s or not s.monitoring or not _may_review(db, user, s.student_id):
        raise HTTPException(404, "Monitored interview not found")
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id == s.id)
                        .order_by(IntegrityEvent.t_ms)).all()
    student = db.get(User, s.student_id)
    audit(db, user.id, "monitoring.view", "interview", s.id, {"events": len(events)}, client_ip(request))
    db.commit()
    return {"id": s.id, "student_name": student.full_name if student else "?", "job_role": s.job_role,
            "interview_status": s.status, "created_at": s.created_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "monitoring": monitoring_summary(db, s), "events": [event_out(e, reviewer=True) for e in events],
            "note": "Signals are approximate and are reviewed separately from interview performance. They are not "
                    "evidence of misconduct on their own and never change interview scores."}


@router.patch("/api/monitoring/events/{event_id}")
def review_event(event_id: int, body: IntegrityReviewIn, request: Request, user: User = Depends(_reviewer),
                 db: Session = Depends(get_db)):
    e = db.get(IntegrityEvent, event_id)
    s = db.get(InterviewSession, e.session_id) if e else None
    if not e or not s or not _may_review(db, user, s.student_id):
        raise HTTPException(404, "Event not found")
    e.review_status = body.review_status
    e.reviewer_notes = (body.reviewer_notes or "").strip() or None
    e.reviewer_id = user.id
    e.reviewed_at = datetime.now(timezone.utc)
    audit(db, user.id, "monitoring.review", "integrity_event", e.id, {"status": body.review_status},
          client_ip(request))
    db.commit()
    return event_out(e, reviewer=True)


# --------------------------------------------------------------------------- performance

@router.post("/api/perf/client")
def client_metrics(body: ClientMetricsIn, user: User = Depends(get_current_user)):
    """Timings measured in the browser (e.g. answer submitted → next question audible). Names are whitelisted."""
    stored = 0
    for m in body.metrics:
        if m.metric in perf.CLIENT_METRICS:
            perf.record(m.metric, m.duration_ms, m.ok, source="client", **(m.meta or {}))
            stored += 1
    return {"stored": stored}


@router.get("/api/admin/performance")
def performance(hours: int = 24, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    hours = max(1, min(hours, 24 * 30))
    return {"hours": hours, "metrics": perf.summary(db, hours),
            "note": "Durations of successful steps (failed ones are counted separately). Only timings are stored - "
                    "no questions, answers, transcripts or media."}

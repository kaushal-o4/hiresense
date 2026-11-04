"""Disclosed, opt-in interview integrity / security monitoring, security settings and the performance dashboard API.

Who may see what (least privilege):
  * the student: their own consent, events, risk summary and explanations;
  * admins: all monitored interviews, the full review history, and the security settings;
  * mentors: only with the extra permission `review_integrity`, and only for students they may access
    (assigned, or `view_all_students`);
  * recruiters: only COMPLETED interviews of candidates who applied to one of their jobs, and only when the candidate
    consented under a policy that disclosed recruiter access (setting `recruiters_can_view`, also re-checked now).
    There is no footage to share - none is ever recorded.
Every reviewer view and review is written to the audit log (ids only, no candidate content). Reviews never change the
detected fields of an event; each review is appended to integrity_reviews.

Browser-generated events are useful signals, but a browser client can be modified. The server therefore validates
everything it can (consented feature, time window, size, rate, duplicates) and assigns severity itself - see README.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from ..odm import delete, func, select
from ..odm import IntegrityError
from ..odm import Session

from ..database import get_db
from ..deps import client_ip, get_current_user, mentor_can_access, require_admin, require_student
from ..models import IntegrityEvent, IntegrityReview, InterviewSession, PlatformSetting, User
from ..schemas import (
    AttentionIn, ClientMetricsIn, ExplanationIn, IntegrityEventsIn, IntegrityReviewIn, MonitoringConsentIn,
)
from ..services import attention, integrity, limiter, perf
from ..services.access import recruiter_has_applicant
from ..services.common import audit, get_setting

router = APIRouter(tags=["monitoring"])

MAX_EVENTS_PER_SESSION = 500
LATE_EVENTS_GRACE = timedelta(minutes=3)  # events flushed by the browser right after the interview ended
CLOCK_SLACK_MS = 60_000  # an event may not claim to be later than "now" by more than this (clock drift, queueing)
RATE_LIMIT = (30, 60.0)  # at most 30 event batches per interview per 60 s (the browser sends one every ~8 s)


def _rate_ok(session_id: int) -> bool:
    limit, window = RATE_LIMIT
    return limiter.hit(f"monitoring:{session_id}", limit, window)


def _retention(db: Session) -> int:
    return int(get_setting(db, "monitoring_retention_days") or 90)


def security_config(db: Session) -> integrity.SecurityConfig:
    row = db.get(PlatformSetting, integrity.SECURITY_CONFIG_KEY)
    return integrity.load_config(row.value if row else None)


def _session_config(s: InterviewSession) -> integrity.SecurityConfig:
    """The settings that applied when the candidate consented (interview-specific), else the defaults."""
    return integrity.load_config((s.monitoring or {}).get("config"))


def purge_expired(db: Session) -> int:
    """Delete integrity events older than the retention period. Called on reviewer list views and at startup."""
    cutoff = integrity.retention_cutoff(_retention(db))
    r = db.execute(delete(IntegrityEvent).where(IntegrityEvent.created_at < cutoff))
    for s in db.scalars(select(InterviewSession).where(InterviewSession.created_at < cutoff,
                                                       InterviewSession.monitoring.is_not(None))):
        if (s.monitoring or {}).get("attention"):  # the attention summary has the same retention as the events
            s.monitoring = {k: v for k, v in s.monitoring.items() if k != "attention"}
    db.commit()
    return r.rowcount or 0


def _own_session(db: Session, user: User, session_id: int) -> InterviewSession:
    s = db.get(InterviewSession, session_id)
    if not s or s.student_id != user.id:
        raise HTTPException(404, "Interview not found")
    return s


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=dt.tzinfo or timezone.utc) if dt else None


def _clock_origin(s: InterviewSession) -> datetime | None:
    raw = (s.monitoring or {}).get("clock_origin")
    try:
        return _aware(datetime.fromisoformat(raw)) if raw else None
    except ValueError:
        return None


def _elapsed_ms(s: InterviewSession) -> int | None:
    origin = _clock_origin(s)
    return max(0, int((datetime.now(timezone.utc) - origin).total_seconds() * 1000)) if origin else None


def event_out(e: IntegrityEvent, reviewer: bool = False, origin: datetime | None = None) -> dict:
    d = {"id": e.id, "event_type": e.event_type, "category": integrity.CATEGORIES.get(e.event_type, "OTHER"),
         "label": integrity.LABELS.get(e.event_type, e.event_type),
         "description": integrity.describe(e.event_type, e.duration_ms, e.details),
         "t_ms": e.t_ms, "duration_ms": e.duration_ms, "confidence": e.confidence,
         "confidence_sufficient": e.confidence_sufficient, "severity": e.severity,
         "detection_source": integrity.SOURCES.get(e.event_type, e.source), "details": e.details,
         "candidate_explanation": e.candidate_explanation, "review_status": e.review_status,
         "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
         "created_at": e.created_at.isoformat() if e.created_at else None}
    if origin:  # wall-clock start/end (the interview clock started at the first consent)
        start = origin + timedelta(milliseconds=e.t_ms)
        d["start_timestamp"] = start.isoformat()
        d["end_timestamp"] = (start + timedelta(milliseconds=e.duration_ms)).isoformat() if e.duration_ms else None
    if reviewer:
        d["reviewer_notes"] = e.reviewer_notes
        d["reviewer_id"] = e.reviewer_id
    return d


def _summary(s: InterviewSession, events: list[IntegrityEvent]) -> dict:
    counts: dict[str, int] = {}
    for e in events:
        counts[e.severity] = counts.get(e.severity, 0) + 1
    serious = sum(1 for e in events if e.severity in ("medium", "high") and e.review_status in ("pending", "needs_review"))
    return {"config": {k: v for k, v in (s.monitoring or {}).items() if k != "attention"}, "counts": counts, "total": len(events),
            "categories": sorted({integrity.CATEGORIES.get(e.event_type, "OTHER") for e in events}),
            "status": integrity.session_status(s.monitoring, counts, serious),
            "risk": integrity.risk_summary(events, _session_config(s))}


# --------------------------------------------------------------------------- student

@router.get("/api/monitoring/policy")
def monitoring_policy(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {**integrity.policy(_retention(db), bool(get_setting(db, "monitoring_camera_required")), security_config(db)),
            "enabled": bool(get_setting(db, "monitoring_enabled"))}


@router.post("/api/student/interviews/{session_id}/monitoring/consent")
def give_consent(session_id: int, body: MonitoringConsentIn, user: User = Depends(require_student),
                 db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    if s.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    if body.policy_version != integrity.POLICY_VERSION:
        raise HTTPException(409, "The monitoring policy has changed. Please reload the page and read it again.")
    cfg = security_config(db)
    f = body.features.model_dump()
    if not get_setting(db, "monitoring_enabled"):
        f = {k: False for k in f}
    for k, on in cfg.detectors.model_dump().items():  # a detector switched off by an admin cannot be consented to
        if not on and k in f:
            f[k] = False
    if not f["camera"]:  # camera features need the camera
        f.update(face_presence=False, multiple_faces=False, attention=False, objects=False, audio=False)
    if get_setting(db, "monitoring_camera_required") and (not f["camera"] or body.camera_permission != "granted"):
        raise HTTPException(403, "This assessment requires the camera. It cannot start without camera access. "
                                 "If you cannot use a camera, contact your placement cell for an alternative.")
    prev = s.monitoring or {}
    now = datetime.now(timezone.utc)
    s.monitoring = {"policy_version": body.policy_version, "features": f, "camera_permission": body.camera_permission,
                    "accepted_at": prev.get("accepted_at") or now.isoformat(),
                    "clock_origin": prev.get("clock_origin") or prev.get("accepted_at") or now.isoformat(),
                    "updated_at": now.isoformat(), "withdrawn_at": None,
                    "recruiters_can_view": cfg.recruiters_can_view,
                    "config": cfg.model_dump(exclude={"recruiters_can_view"})}
    if prev.get("attention"):  # a reload must not lose the attention totals measured so far
        s.monitoring["attention"] = prev["attention"]
    elapsed = _elapsed_ms(s) or 0
    # Consent again for the same interview = the page was reloaded or reopened. Recorded by the server itself.
    if prev.get("accepted_at") and any(f.values()):
        db.add(IntegrityEvent(session_id=s.id, event_type="session_reconnected", t_ms=min(elapsed, 21_600_000),
                              severity="info", confidence_sufficient=True, source="server",
                              details={"reason": "page_reload"}))
    db.commit()
    return {"monitoring": {k: v for k, v in s.monitoring.items() if k != "attention"}, "elapsed_ms": elapsed}


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
    return {"monitoring": {k: v for k, v in s.monitoring.items() if k != "attention"}}


def _event_rows(s: InterviewSession, body: IntegrityEventsIn, existing_ids: set[str], have: int, long_pastes: int,
                features: dict, cfg: integrity.SecurityConfig, latest_ms: int | None) -> list[IntegrityEvent]:
    rows, seen = [], set()
    for e in body.events:
        if have + len(rows) >= MAX_EVENTS_PER_SESSION:
            break
        if e.client_event_id and (e.client_event_id in existing_ids or e.client_event_id in seen):
            continue  # already stored (retry / page-close flush)
        if not integrity.event_allowed(e.event_type, features):
            continue  # only what the candidate agreed to is recorded
        if latest_ms is not None and e.t_ms > latest_ms + CLOCK_SLACK_MS:
            continue  # claims to have happened in the future of this interview
        level, sure = integrity.severity(e.event_type, e.duration_ms, e.confidence, cfg)
        if e.event_type == "paste_long":
            level = integrity.paste_severity(level, long_pastes)
            long_pastes += 1
        if e.client_event_id:
            seen.add(e.client_event_id)
        rows.append(IntegrityEvent(session_id=s.id, event_type=e.event_type, t_ms=e.t_ms, duration_ms=e.duration_ms,
                                   confidence=round(e.confidence, 3) if e.confidence is not None else None,
                                   confidence_sufficient=sure, severity=level, client_event_id=e.client_event_id,
                                   source="browser", details=integrity.clean_details(e.details)))
    return rows


@router.post("/api/student/interviews/{session_id}/integrity-events")
def report_events(session_id: int, body: IntegrityEventsIn, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    m = s.monitoring or {}
    features = m.get("features") or {}
    if not m or m.get("withdrawn_at"):
        raise HTTPException(409, "Monitoring is not active for this interview.")
    done_at = _aware(s.completed_at)
    if s.status != "in_progress" and not (done_at and datetime.now(timezone.utc) - done_at < LATE_EVENTS_GRACE):
        raise HTTPException(400, "This interview is already finished")
    if not _rate_ok(s.id):
        raise HTTPException(429, "Too many monitoring updates. They will be sent again shortly.")
    cfg = _session_config(s)
    have = db.scalar(select(func.count(IntegrityEvent.id)).where(IntegrityEvent.session_id == s.id)) or 0
    long_pastes = db.scalar(select(func.count(IntegrityEvent.id)).where(
        IntegrityEvent.session_id == s.id, IntegrityEvent.event_type == "paste_long")) or 0
    ids = [e.client_event_id for e in body.events if e.client_event_id]
    existing = set(db.scalars(select(IntegrityEvent.client_event_id).where(
        IntegrityEvent.session_id == s.id, IntegrityEvent.client_event_id.in_(ids))).all()) if ids else set()
    rows = _event_rows(s, body, existing, have, long_pastes, features, cfg, _elapsed_ms(s))
    db.add_all(rows)
    try:
        db.commit()
        stored = len(rows)
    except IntegrityError:
        # a concurrent request stored some of the same client ids first: insert one by one, skipping duplicates
        db.rollback()
        stored = 0
        for r in rows:
            try:
                with db.begin_nested():
                    db.add(IntegrityEvent(**{c: getattr(r, c) for c in (
                        "session_id", "event_type", "t_ms", "duration_ms", "confidence", "confidence_sufficient",
                        "severity", "client_event_id", "source", "details")}))
                stored += 1
            except IntegrityError:
                pass
        db.commit()
    return {"stored": stored, "ignored": len(body.events) - stored}


@router.put("/api/student/interviews/{session_id}/attention")
def report_attention(session_id: int, body: AttentionIn, user: User = Depends(require_student),
                     db: Session = Depends(get_db)):
    """Cumulative attention time totals from the browser (see services/attention.py). Idempotent: resending the same
    or a newer total for the same monitor run is fine; an older total is ignored."""
    s = _own_session(db, user, session_id)
    m = s.monitoring or {}
    if not m or m.get("withdrawn_at") or not (m.get("features") or {}).get("attention"):
        raise HTTPException(409, "Attention tracking is not active for this interview.")
    done_at = _aware(s.completed_at)
    if s.status != "in_progress" and not (done_at and datetime.now(timezone.utc) - done_at < LATE_EVENTS_GRACE):
        raise HTTPException(400, "This interview is already finished")
    if not _rate_ok(-s.id):  # separate counter from event batches
        raise HTTPException(429, "Too many monitoring updates. They will be sent again shortly.")
    record, why = attention.merge(m, body.epoch, body.model_dump(), _elapsed_ms(s))
    if record is None:
        return {"accepted": False, "reason": why}
    s.monitoring = {**m, "attention": record}  # new dict: the stored one stays untouched until commit
    db.commit()
    return {"accepted": True}


def _attention_report(s: InterviewSession, events: list[IntegrityEvent]) -> dict | None:
    end = _aware(s.completed_at) or datetime.now(timezone.utc)
    origin = _clock_origin(s)
    return attention.report(s.monitoring, events, int((end - origin).total_seconds() * 1000) if origin else None)


@router.get("/api/student/interviews/{session_id}/integrity-events")
def my_events(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id == s.id)
                        .order_by(IntegrityEvent.t_ms)).all()
    origin = _clock_origin(s)
    return {"summary": _summary(s, events), "events": [event_out(e, origin=origin) for e in events],
            "attention": _attention_report(s, events)}


@router.put("/api/student/interviews/{session_id}/integrity-events/{event_id}/explanation")
def explain_event(session_id: int, event_id: int, body: ExplanationIn, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    e = db.get(IntegrityEvent, event_id)
    if not e or e.session_id != s.id:
        raise HTTPException(404, "Event not found")
    e.candidate_explanation = body.text.strip()
    db.commit()
    return event_out(e, origin=_clock_origin(s))


# --------------------------------------------------------------------------- reviewers

def _reviewer(user: User = Depends(get_current_user)) -> User:
    if user.role in ("admin", "recruiter") or (user.role == "mentor" and "review_integrity" in (user.permissions or [])):
        return user
    raise HTTPException(403, "You are not authorised to review interview monitoring.")


def _may_review(db: Session, user: User, s: InterviewSession, recruiters_on: bool | None = None) -> bool:
    if user.role == "admin":
        return True
    if user.role == "mentor":
        return mentor_can_access(db, user, s.student_id)
    if user.role == "recruiter":
        if recruiters_on is None:
            recruiters_on = security_config(db).recruiters_can_view
        return (recruiters_on and s.status == "completed" and bool((s.monitoring or {}).get("recruiters_can_view"))
                and recruiter_has_applicant(db, user.id, s.student_id))
    return False


BAND_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3}


def integrity_overview(db: Session, viewer: User, student_id: int) -> dict:
    """Per-candidate roll-up of monitored, completed interviews that `viewer` may review (same rule as the review
    pages: for recruiters, only applicants who consented under a policy that disclosed recruiter access). Counts
    only, never event content. Not a performance signal and never a basis for a decision on its own."""
    sessions = db.scalars(select(InterviewSession).where(
        InterviewSession.student_id == student_id, InterviewSession.status == "completed")).all()
    monitored = [s for s in sessions if s.monitoring]
    recruiters_on = security_config(db).recruiters_can_view if viewer.role == "recruiter" else None
    visible = [s for s in monitored if _may_review(db, viewer, s, recruiters_on)]
    out = {"visible": bool(visible), "monitored_sessions": len(visible), "hidden_sessions": len(monitored) - len(visible),
           "needs_review": 0, "highest_band": None, "sessions": [],
           "disclaimer": "Integrity signals are approximate, reviewed separately from performance, and must never be "
                         "the sole basis for any hiring decision."}
    if not visible:
        out["reason"] = ("No monitored interviews yet." if not monitored else
                         "Not shared with recruiters (the candidate's consent or the platform setting does not allow it).")
        return out
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id.in_([s.id for s in visible]))).all()
    by_session: dict[int, list] = {}
    for e in events:
        by_session.setdefault(e.session_id, []).append(e)
    best = "none"
    for s in sorted(visible, key=lambda x: x.id, reverse=True):
        summ = _summary(s, by_session.get(s.id, []))
        band = summ["risk"]["band"]
        if BAND_ORDER.get(band["code"], 0) > BAND_ORDER[best]:
            best = band["code"]
        if summ["status"]["code"] == "review":
            out["needs_review"] += 1
        out["sessions"].append({"session_id": s.id, "job_role": s.job_role, "band": band,
                                "status": summ["status"], "events": summ["total"]})
    out["highest_band"] = {"code": best, "label": integrity.BAND_LABELS[best]}
    return out


def _parse_date(v: str | None, end: bool = False) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-10-23")
    d = _aware(d)
    return d + timedelta(days=1) if end and len(v) <= 10 else d


@router.get("/api/monitoring/sessions")
def review_list(request: Request, status: str | None = None, q: str | None = None, date_from: str | None = None,
                date_to: str | None = None, category: str | None = None, severity: str | None = None,
                review_status: str | None = None, risk: str | None = None, page: int = 1,
                user: User = Depends(_reviewer), db: Session = Depends(get_db)):
    purge_expired(db)
    stmt = select(InterviewSession).where(InterviewSession.monitoring.is_not(None))
    if (start := _parse_date(date_from)) is not None:
        stmt = stmt.where(InterviewSession.created_at >= start)
    if (end := _parse_date(date_to, end=True)) is not None:
        stmt = stmt.where(InterviewSession.created_at < end)
    if user.role == "recruiter":
        stmt = stmt.where(InterviewSession.status == "completed")
    rows = db.scalars(stmt.order_by(InterviewSession.id.desc()).limit(500)).all()
    recruiters_on = security_config(db).recruiters_can_view
    rows = [s for s in rows if _may_review(db, user, s, recruiters_on)]
    students = {u.id: u for u in db.scalars(select(User).where(User.id.in_({s.student_id for s in rows})))} if rows else {}
    if q:
        needle = q.strip().lower()
        rows = [s for s in rows if needle in (getattr(students.get(s.student_id), "full_name", "") or "").lower()
                or needle in (str(s.student_id), str(s.id))]
    by_session: dict[int, list[IntegrityEvent]] = {s.id: [] for s in rows}
    if rows:
        for e in db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id.in_(list(by_session)))):
            by_session[e.session_id].append(e)
    items = []
    for s in rows:
        events = by_session[s.id]
        if category or severity or review_status:
            match = [e for e in events if (not category or integrity.CATEGORIES.get(e.event_type) == category)
                     and (not severity or e.severity == severity)
                     and (not review_status or e.review_status == review_status)]
            if not match:
                continue
        summ = _summary(s, events)
        if status and summ["status"]["code"] != status:
            continue
        if risk and summ["risk"]["band"]["code"] != risk:
            continue
        student = students.get(s.student_id)
        if user.role == "recruiter":
            summ.pop("config", None)  # consent details and thresholds are for admins / mentors
        items.append({"id": s.id, "student_id": s.student_id, "student_name": student.full_name if student else "?",
                      "job_role": s.job_role, "interviewer": s.interviewer or "aria", "status": s.status,
                      "created_at": s.created_at.isoformat(),
                      "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                      "duration_s": int((_aware(s.completed_at) - _aware(s.created_at)).total_seconds())
                      if s.completed_at else None, "monitoring": summ})
    page_size = 20
    audit(db, user.id, "monitoring.list", "interview", None, {"count": len(items)}, client_ip(request))
    db.commit()
    start_i = (max(page, 1) - 1) * page_size
    return {"items": items[start_i:start_i + page_size], "total": len(items), "page": max(page, 1),
            "pages": max(1, (len(items) + page_size - 1) // page_size),
            "categories": integrity.ALL_CATEGORIES}


@router.get("/api/monitoring/sessions/{session_id}")
def review_detail(session_id: int, request: Request, user: User = Depends(_reviewer), db: Session = Depends(get_db)):
    s = db.get(InterviewSession, session_id)
    if not s or not s.monitoring or not _may_review(db, user, s):
        raise HTTPException(404, "Monitored interview not found")
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.session_id == s.id)
                        .order_by(IntegrityEvent.t_ms)).all()
    student = db.get(User, s.student_id)
    origin = _clock_origin(s)
    out_events = [event_out(e, reviewer=True, origin=origin) for e in events]
    if user.role == "admin" and events:  # full review history (who reviewed, in which role, when)
        hist: dict[int, list] = {}
        for r in db.scalars(select(IntegrityReview).where(IntegrityReview.event_id.in_([e.id for e in events]))
                            .order_by(IntegrityReview.id)):
            hist.setdefault(r.event_id, []).append({"status": r.review_status, "notes": r.notes,
                                                    "reviewer_id": r.reviewer_id, "role": r.reviewer_role,
                                                    "at": r.created_at.isoformat()})
        for d in out_events:
            d["review_history"] = hist.get(d["id"], [])
    summary = _summary(s, events)
    if user.role == "recruiter":
        summary.pop("config", None)
    audit(db, user.id, "monitoring.view", "interview", s.id, {"events": len(events)}, client_ip(request))
    db.commit()
    return {"id": s.id, "student_id": s.student_id, "student_name": student.full_name if student else "?",
            "job_role": s.job_role, "interview_status": s.status, "created_at": s.created_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "clock_origin": origin.isoformat() if origin else None,
            "monitoring": summary, "events": out_events, "attention": _attention_report(s, events),
            "note": "Signals are approximate and are reviewed separately from interview performance. They are not "
                    "evidence of misconduct on their own and never change interview scores."}


@router.patch("/api/monitoring/events/{event_id}")
def review_event(event_id: int, body: IntegrityReviewIn, request: Request, user: User = Depends(_reviewer),
                 db: Session = Depends(get_db)):
    e = db.get(IntegrityEvent, event_id)
    s = db.get(InterviewSession, e.session_id) if e else None
    if not e or not s or not _may_review(db, user, s):
        raise HTTPException(404, "Event not found")
    notes = (body.reviewer_notes or "").strip() or None
    # Only the review fields change; type, times, duration, confidence and severity stay as detected.
    e.review_status = body.review_status
    e.reviewer_notes = notes
    e.reviewer_id = user.id
    e.reviewed_at = datetime.now(timezone.utc)
    db.add(IntegrityReview(event_id=e.id, reviewer_id=user.id, reviewer_role=user.role,
                           review_status=body.review_status, notes=notes))
    audit(db, user.id, "monitoring.review", "integrity_event", e.id, {"status": body.review_status},
          client_ip(request))
    db.commit()
    return event_out(e, reviewer=True, origin=_clock_origin(s))


# --------------------------------------------------------------------------- admin security settings

def _flat(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and k != "severity_caps":
            out.update(_flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


@router.get("/api/admin/security-settings")
def get_security_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"config": security_config(db).model_dump(), "defaults": integrity.SecurityConfig().model_dump(),
            "global": {k: get_setting(db, k) for k in
                       ("monitoring_enabled", "monitoring_camera_required", "monitoring_retention_days")},
            "event_types": sorted(integrity.LABELS), "labels": integrity.LABELS,
            "categories": integrity.ALL_CATEGORIES, "risk_rules": {k: v[0] for k, v in integrity.RISK_RULES.items()},
            "note": "These are global defaults. Each interview keeps a copy of the settings that applied when the "
                    "candidate consented, so changes affect new interviews only."}


@router.put("/api/admin/security-settings")
def put_security_settings(body: dict, request: Request, admin: User = Depends(require_admin),
                          db: Session = Depends(get_db)):
    try:
        cfg = integrity.SecurityConfig.model_validate(body)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))
    bad = [k for k in cfg.severity_caps if k not in integrity.LABELS]
    if bad:
        raise HTTPException(400, f"Unknown event type(s): {', '.join(bad)}")
    b = cfg.risk_bands
    if not (b.low <= b.moderate <= b.high):
        raise HTTPException(400, "Risk bands must be in order: low <= moderate <= high")
    if cfg.thresholds.gaze_warn_ms < cfg.thresholds.gaze_record_ms:
        raise HTTPException(400, "The gaze reminder cannot come before the gaze event is recorded")
    before = _flat(security_config(db).model_dump())
    after = _flat(cfg.model_dump())
    changes = {k: {"from": before.get(k), "to": v} for k, v in after.items() if before.get(k) != v}
    row = db.get(PlatformSetting, integrity.SECURITY_CONFIG_KEY)
    if row:
        row.value = cfg.model_dump()
    else:
        db.add(PlatformSetting(key=integrity.SECURITY_CONFIG_KEY, value=cfg.model_dump(),
                               description="Interview security module settings (admin -> Security settings)"))
    audit(db, admin.id, "security_settings.update", "setting", None, {"changes": changes}, client_ip(request))
    db.commit()
    return {"config": cfg.model_dump(), "changed": sorted(changes)}


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

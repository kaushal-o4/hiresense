"""Admin portal: jobs, flagged activity and logs, platform settings, placement drives, announcements."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ...odm import func, or_, select
from ...odm import Session
from ...database import get_db
from ...deps import client_ip, require_admin
from ...models import (
    AIUsageLog, Announcement, AssessmentResult, AuditLog, ErrorLog, InterviewSession, Job, JobApplication,
    PlacementDrive, PlatformSetting, User,
)
from ...schemas import FlagReview, SettingUpdate
from ...serializers import drive_out, interview_out, iso, job_out, result_out
from ...services.ai import ai_status
from ...services.common import DEFAULT_SETTINGS, SETTING_OPTIONS, audit, get_setting, notify, paginate
from ...services.insights import student_summary
from ...services.rewards import revoke_for_source

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --------------------------------------------------------------------------- jobs

@router.get("/jobs")
def list_jobs(status: str | None = None, q: str | None = None, page: int = 1, page_size: int = 20,
              admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Job)
    if status:
        stmt = stmt.where(Job.status == status)
    if q:
        stmt = stmt.where(or_(Job.title.ilike(f"%{q}%"), Job.company_name.ilike(f"%{q}%")))
    items, meta = paginate(db, stmt.order_by(Job.id.desc()), page, page_size)
    out = []
    for j in items:
        d = job_out(j)
        d["recruiter_name"] = j.recruiter.full_name
        d["application_count"] = db.scalar(select(func.count(JobApplication.id)).where(JobApplication.job_id == j.id)) or 0
        d["selected_count"] = db.scalar(select(func.count(JobApplication.id)).where(
            JobApplication.job_id == j.id, JobApplication.status == "selected")) or 0
        out.append(d)
    return {"items": out, **meta}


@router.post("/jobs/{job_id}/close")
def close_job(job_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    j.status = "closed"
    notify(db, j.recruiter_id, "Job closed by admin", f"'{j.title}' was closed by the placement office.", "info",
           "/recruiter/jobs")
    audit(db, admin.id, "job.admin_close", "job", j.id, {"title": j.title}, client_ip(request))
    db.commit()
    return job_out(j)

# --------------------------------------------------------------------------- monitoring

@router.get("/flagged")
def flagged(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    interviews = db.scalars(select(InterviewSession).where(InterviewSession.flagged.is_(True))
                            .order_by(InterviewSession.id.desc())).all()
    results = db.scalars(select(AssessmentResult).where(AssessmentResult.flagged.is_(True))
                         .order_by(AssessmentResult.id.desc())).all()
    return {
        "interviews": [{**interview_out(i), "student_name": db.get(User, i.student_id).full_name} for i in interviews],
        "assessment_results": [{**result_out(r), "student_name": db.get(User, r.student_id).full_name} for r in results],
    }


@router.get("/interviews/{session_id}")
def view_interview(session_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Interview not found")
    return interview_out(s, detail=True)


@router.post("/flagged/{kind}/{item_id}")
def review_flag(kind: str, item_id: int, body: FlagReview, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    model = {"interview": InterviewSession, "assessment": AssessmentResult}.get(kind)
    if not model:
        raise HTTPException(404, "Unknown item type")
    item = db.get(model, item_id)
    if not item or not item.flagged:
        raise HTTPException(404, "Flagged item not found")
    revoked = 0
    if body.action == "clear":
        item.flagged = False
        item.flag_reason = (item.flag_reason or "") + f" [cleared by admin{': ' + body.note if body.note else ''}]"
    else:
        source_type = "interview" if kind == "interview" else "assessment"
        source_id = item.id if kind == "interview" else item.assessment_id
        revoked = revoke_for_source(db, item.student_id, source_type, source_id)
        item.flag_reason = (item.flag_reason or "") + f" [confirmed by admin{': ' + body.note if body.note else ''}]"
        notify(db, item.student_id, "Activity under review",
               "One of your activities was found to break the platform's fair-use rules; related points were removed.",
               "alert")
    audit(db, admin.id, f"flag.{body.action}", kind, item.id, {"note": body.note, "points_revoked": revoked},
          client_ip(request))
    db.commit()
    return {"ok": True, "points_revoked": revoked}


@router.get("/ai-usage")
def ai_usage(days: int = 7, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=min(max(days, 1), 90))
    rows = db.execute(select(AIUsageLog.feature, AIUsageLog.status, func.count(AIUsageLog.id),
                             func.avg(AIUsageLog.latency_ms), func.sum(AIUsageLog.input_tokens),
                             func.sum(AIUsageLog.output_tokens))
                      .where(AIUsageLog.created_at >= since).group_by(AIUsageLog.feature, AIUsageLog.status)).all()
    errors = db.scalars(select(AIUsageLog).where(AIUsageLog.created_at >= since,
                                                 AIUsageLog.status != "success").order_by(AIUsageLog.id.desc()).limit(50)).all()
    # Quality signal: distribution of interview answer scores (all-identical or extreme scores warrant review).
    from ...models import InterviewAnswer
    score_rows = db.scalars(select(InterviewAnswer.score).where(InterviewAnswer.score.is_not(None),
                                                                InterviewAnswer.created_at >= since)).all()
    buckets = Counter(min(int(s // 20), 4) for s in score_rows)
    return {
        "status": ai_status(db),
        "by_feature": [{"feature": f, "status": s, "count": c, "avg_latency_ms": round(l) if l else None,
                        "input_tokens": it or 0, "output_tokens": ot or 0} for f, s, c, l, it, ot in rows],
        "recent_errors": [{"id": e.id, "feature": e.feature, "status": e.status, "error": e.error,
                           "user_id": e.user_id, "created_at": iso(e.created_at)} for e in errors],
        "answer_score_distribution": [{"range": f"{i * 20}-{i * 20 + 20}", "count": buckets.get(i, 0)} for i in range(5)],
    }


@router.get("/errors")
def errors(page: int = 1, page_size: int = 50, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    items, meta = paginate(db, select(ErrorLog).order_by(ErrorLog.id.desc()), page, page_size)
    return {"items": [{"id": e.id, "path": e.path, "method": e.method, "error": e.error, "user_id": e.user_id,
                       "created_at": iso(e.created_at)} for e in items], **meta}


@router.get("/audit-logs")
def audit_logs(action: str | None = None, actor_id: int | None = None, page: int = 1, page_size: int = 50,
               admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    items, meta = paginate(db, stmt.order_by(AuditLog.id.desc()), page, page_size)
    return {"items": [{"id": a.id, "actor": a.actor.full_name if a.actor else None, "actor_id": a.actor_id,
                       "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
                       "details": a.details, "ip_address": a.ip_address, "created_at": iso(a.created_at)}
                      for a in items], **meta}


# --------------------------------------------------------------------------- settings

@router.get("/settings")
def settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"key": k, "value": get_setting(db, k), "description": desc, "options": SETTING_OPTIONS.get(k)}
            for k, (_, desc) in DEFAULT_SETTINGS.items()]


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingUpdate, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(404, "Unknown setting")
    default = DEFAULT_SETTINGS[key][0]
    if isinstance(default, bool) and not isinstance(body.value, bool):
        raise HTTPException(400, "This setting must be true or false")
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(body.value, bool) or not isinstance(body.value, (int, float)) or body.value < 0:
            raise HTTPException(400, "This setting must be a non-negative number")
    if isinstance(default, str) and body.value not in SETTING_OPTIONS.get(key, []):
        raise HTTPException(400, f"Choose one of: {', '.join(SETTING_OPTIONS.get(key, []))}")
    row = db.get(PlatformSetting, key)
    if row:
        row.value = body.value
    else:
        db.add(PlatformSetting(key=key, value=body.value, description=DEFAULT_SETTINGS[key][1]))
    audit(db, admin.id, "setting.update", "setting", None, {"key": key, "value": body.value}, client_ip(request))
    db.commit()
    return {"ok": True}

# --------------------------------------------------------------------------- placement drives

class DriveIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    company_name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    drive_date: datetime
    location: str = Field(default="", max_length=200)
    min_cgpa: float | None = Field(default=None, ge=0, le=10)
    eligible_branches: list[str] = Field(default_factory=list, max_length=30)
    status: Literal["upcoming", "completed", "cancelled"] = "upcoming"
    notify_students: bool = True


@router.get("/drives")
def list_drives(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [drive_out(d) for d in db.scalars(select(PlacementDrive).order_by(PlacementDrive.drive_date.desc()))]


def _eligible_students(db: Session, d: PlacementDrive) -> list[User]:
    out = []
    for st in db.scalars(select(User).where(User.role == "student", User.status == "active")):
        p = st.student_profile
        if d.min_cgpa is not None and (not p or p.cgpa is None or p.cgpa < d.min_cgpa):
            continue
        if d.eligible_branches and (not p or not p.branch or p.branch.lower() not in {b.lower() for b in d.eligible_branches}):
            continue
        out.append(st)
    return out


@router.post("/drives", status_code=201)
def create_drive(body: DriveIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"notify_students"})
    d = PlacementDrive(**data, created_by=admin.id)
    db.add(d)
    db.flush()
    notified = 0
    if body.notify_students and d.status == "upcoming":
        for st in _eligible_students(db, d):
            notify(db, st.id, f"Placement drive: {d.company_name}",
                   f"{d.title} on {d.drive_date.strftime('%d %b %Y')}. Register from the Placement Drives page.",
                   "drive", "/student/drives")
            notified += 1
    audit(db, admin.id, "drive.create", "placement_drive", d.id, {"title": d.title, "notified": notified}, client_ip(request))
    db.commit()
    return {"id": d.id, "notified": notified}


@router.put("/drives/{drive_id}")
def update_drive(drive_id: int, body: DriveIn, request: Request, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    d = db.get(PlacementDrive, drive_id)
    if not d:
        raise HTTPException(404, "Drive not found")
    old_status, old_date = d.status, d.drive_date
    for k, v in body.model_dump(exclude={"notify_students"}).items():
        setattr(d, k, v)
    if body.notify_students and (old_status != d.status or old_date != d.drive_date):
        for reg in d.registrations:
            notify(db, reg.student_id, f"Drive update: {d.company_name}",
                   f"{d.title} is now {d.status}, scheduled for {d.drive_date.strftime('%d %b %Y')}.", "drive", "/student/drives")
    audit(db, admin.id, "drive.update", "placement_drive", d.id, {"title": d.title}, client_ip(request))
    db.commit()
    return drive_out(d)


@router.get("/drives/{drive_id}/registrations")
def drive_registrations(drive_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(PlacementDrive, drive_id)
    if not d:
        raise HTTPException(404, "Drive not found")
    out = []
    for r in d.registrations:
        s = student_summary(db, r.student)
        out.append({"student_id": r.student_id, "name": r.student.full_name, "email": r.student.email,
                    "branch": s["student"]["branch"], "cgpa": s["student"]["cgpa"], "readiness": s["readiness"]["score"],
                    "registered_at": iso(r.created_at)})
    return out


# --------------------------------------------------------------------------- announcements

class AnnouncementIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=3, max_length=4000)
    audience: Literal["all", "student", "recruiter", "mentor"] = "all"
    link: str | None = Field(default=None, max_length=300)


@router.get("/announcements")
def list_announcements(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": a.id, "title": a.title, "message": a.message, "audience": a.audience, "link": a.link,
             "recipients": a.recipients, "created_at": iso(a.created_at)}
            for a in db.scalars(select(Announcement).order_by(Announcement.id.desc()).limit(100))]


@router.post("/announcements", status_code=201)
def send_announcement(body: AnnouncementIn, request: Request, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    stmt = select(User.id).where(User.status == "active", User.role != "admin")
    if body.audience != "all":
        stmt = stmt.where(User.role == body.audience)
    ids = list(db.scalars(stmt))
    for uid in ids:
        notify(db, uid, f"📢 {body.title}", body.message, "announcement", body.link)
    a = Announcement(title=body.title, message=body.message, audience=body.audience, link=body.link,
                     recipients=len(ids), created_by=admin.id)
    db.add(a)
    db.flush()
    audit(db, admin.id, "announcement.send", "announcement", a.id, {"audience": body.audience, "recipients": len(ids)},
          client_ip(request))
    db.commit()
    return {"id": a.id, "recipients": len(ids)}

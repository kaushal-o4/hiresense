"""Placement opportunities, student side: browse and apply to jobs, my applications, messages with recruiters."""

from fastapi import APIRouter, Depends, HTTPException

from ...odm import func, or_, select
from ...odm import Session
from ...database import get_db
from ...deps import require_student
from ...models import (
    ApplicationMessage, ApplicationStatusHistory, Assessment, Job, JobApplication, JobRequirement, User,
)
from ...schemas import ApplyIn, MessageIn
from ...serializers import application_out, job_out
from ...services.common import notify, paginate
from .common import STATUS_LABELS, _assignments_out, _thread, eligibility, semantic_match


student_router = APIRouter(prefix="/api/student", tags=["student jobs"])

# =========================================================================== student

@student_router.get("/jobs")
def browse_jobs(q: str | None = None, location: str | None = None, job_type: str | None = None,
                skill: str | None = None, eligible_only: bool = False, page: int = 1, page_size: int = 12,
                user: User = Depends(require_student), db: Session = Depends(get_db)):
    stmt = select(Job).where(Job.status == "published")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.company_name.ilike(like), Job.description.ilike(like)))
    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    if skill:
        stmt = stmt.where(Job.id.in_(select(JobRequirement.job_id).where(JobRequirement.skill.ilike(f"%{skill}%"))))
    stmt = stmt.order_by(Job.published_at.desc().nullslast(), Job.id.desc())
    profile = user.student_profile
    my_skills = {s.lower() for s in (profile.skills if profile else [])}
    applied = dict(db.execute(select(JobApplication.job_id, JobApplication.status)
                              .where(JobApplication.student_id == user.id)).all())

    def decorate(j: Job) -> dict:
        d = job_out(j)
        ok, reasons = eligibility(j, profile)
        d["eligible"], d["ineligible_reasons"] = ok, reasons
        d["skill_match"] = [s for s in d["required_skills"] + d["preferred_skills"] if s.lower() in my_skills]
        d["application_status"] = applied.get(j.id)
        return d

    if eligible_only:
        jobs = [decorate(j) for j in db.scalars(stmt).all()]
        jobs = [j for j in jobs if j["eligible"]]
        total = len(jobs)
        start = (max(page, 1) - 1) * page_size
        return {"items": jobs[start:start + page_size], "total": total, "page": page, "page_size": page_size,
                "pages": max((total + page_size - 1) // page_size, 1)}
    items, meta = paginate(db, stmt, page, page_size)
    return {"items": [decorate(j) for j in items], **meta}


@student_router.get("/jobs/{job_id}")
def job_detail(job_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status == "draft":
        raise HTTPException(404, "Job not found")
    d = job_out(job)
    d["eligible"], d["ineligible_reasons"] = eligibility(job, user.student_profile)
    app = db.scalar(select(JobApplication).where(JobApplication.job_id == job.id, JobApplication.student_id == user.id))
    d["application"] = application_out(app) if app else None
    d["assessments"] = [{"id": a.id, "title": a.title} for a in db.scalars(
        select(Assessment).where(Assessment.job_id == job.id, Assessment.active.is_(True)))]
    return d


@student_router.post("/jobs/{job_id}/apply", status_code=201)
def apply(job_id: int, body: ApplyIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != "published":
        raise HTTPException(404, "This job is not open for applications")
    ok, reasons = eligibility(job, user.student_profile)
    if not ok:
        raise HTTPException(400, "You are not eligible: " + "; ".join(reasons))
    existing = db.scalar(select(JobApplication).where(JobApplication.job_id == job.id,
                                                      JobApplication.student_id == user.id))
    if existing and existing.status != "withdrawn":
        raise HTTPException(409, "You have already applied to this job")
    if existing:
        existing.status = "applied"
        existing.cover_letter = body.cover_letter
        existing.history.append(ApplicationStatusHistory(from_status="withdrawn", to_status="applied",
                                                         changed_by=user.id, note="Re-applied"))
        app = existing
    else:
        app = JobApplication(job_id=job.id, student_id=user.id, cover_letter=body.cover_letter, status="applied")
        app.history.append(ApplicationStatusHistory(to_status="applied", changed_by=user.id))
        db.add(app)
    app.match = semantic_match(db, job, user)
    notify(db, job.recruiter_id, "New application", f"{user.full_name} applied for {job.title}.", "application",
           f"/recruiter/jobs/{job.id}")
    db.commit()
    return application_out(app)


@student_router.get("/applications")
def my_applications(status: str | None = None, user: User = Depends(require_student), db: Session = Depends(get_db)):
    stmt = select(JobApplication).where(JobApplication.student_id == user.id)
    if status:
        stmt = stmt.where(JobApplication.status == status)
    out = []
    for a in db.scalars(stmt.order_by(JobApplication.updated_at.desc())):
        d = application_out(a)
        d["unread_messages"] = db.scalar(select(func.count(ApplicationMessage.id)).where(
            ApplicationMessage.application_id == a.id, ApplicationMessage.sender_id != user.id,
            ApplicationMessage.read.is_(False))) or 0
        d["message_count"] = db.scalar(select(func.count(ApplicationMessage.id)).where(
            ApplicationMessage.application_id == a.id)) or 0
        d["assignments"] = _assignments_out(db, a)
        out.append(d)
    return out


@student_router.post("/applications/{application_id}/withdraw")
def withdraw(application_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    app = db.get(JobApplication, application_id)
    if not app or app.student_id != user.id:
        raise HTTPException(404, "Application not found")
    if app.status in ("selected", "rejected", "withdrawn"):
        raise HTTPException(400, f"Cannot withdraw an application that is {STATUS_LABELS[app.status].lower()}")
    app.history.append(ApplicationStatusHistory(from_status=app.status, to_status="withdrawn", changed_by=user.id))
    app.status = "withdrawn"
    notify(db, app.job.recruiter_id, "Application withdrawn", f"{user.full_name} withdrew from {app.job.title}.",
           "application", f"/recruiter/jobs/{app.job_id}")
    db.commit()
    return application_out(app)

def _student_application(db: Session, user: User, application_id: int) -> JobApplication:
    app = db.get(JobApplication, application_id)
    if not app or app.student_id != user.id:
        raise HTTPException(404, "Application not found")
    return app


@student_router.get("/applications/{application_id}/messages")
def student_messages(application_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return _thread(db, _student_application(db, user, application_id), user)


@student_router.post("/applications/{application_id}/messages", status_code=201)
def student_send(application_id: int, body: MessageIn, user: User = Depends(require_student),
                 db: Session = Depends(get_db)):
    app = _student_application(db, user, application_id)
    if app.status == "withdrawn":
        raise HTTPException(400, "This application was withdrawn")
    db.add(ApplicationMessage(application_id=app.id, sender_id=user.id, kind="message", body=body.body.strip()))
    notify(db, app.job.recruiter_id, f"Message from {user.full_name}", body.body[:140], "message",
           f"/recruiter/jobs/{app.job_id}")
    db.commit()
    return _thread(db, app, user)

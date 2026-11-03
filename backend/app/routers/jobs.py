"""Placement opportunities (student side) and recruiter job/candidate management."""
import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..odm import func, or_, select
from ..odm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import client_ip, require_recruiter, require_student
from ..models import (
    ApplicationMessage, ApplicationStatusHistory, Assessment, AssessmentAssignment,
    InterviewSession, Job, JobApplication, JobRequirement, StudentProfile, User,
)
from ..schemas import ApplicationStatusIn, ApplyIn, AssignAssessmentIn, CompareIn, JobIn, MessageIn
from ..serializers import application_out, interview_out, iso, job_out, resume_out
from ..services import ai, mailer, matching
from ..services.access import recruiter_has_applicant
from ..services.common import audit, normalize_skills, notify, paginate
from ..services.insights import current_resume, student_summary

student_router = APIRouter(prefix="/api/student", tags=["student jobs"])
recruiter_router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

STATUS_LABELS = {"applied": "Applied", "shortlisted": "Shortlisted", "interview_scheduled": "Interview scheduled",
                 "on_hold": "On hold", "selected": "Selected", "rejected": "Not selected", "withdrawn": "Withdrawn"}


def _email_student(student: User, subject: str, text: str) -> None:
    """Email a recruitment update too (only when SMTP is configured; the in-app notification is always created)."""
    url = f"{get_settings().frontend_url.rstrip('/')}/student/applications"
    mailer.send(student.email, subject, f"Hello {student.full_name},\n\n{text}\n\nView your applications: {url}\n")


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


AI_METHODS = ("semantic+ai", "ai")


def semantic_match(db: Session, job: Job, student: User) -> dict:
    """Deterministic semantic match (services/matching.py). Works without the language model."""
    _ok, reasons = eligibility(job, student.student_profile)
    reasons = [r for r in reasons if "deadline" not in r.lower()]  # deadline is about the job, not the candidate
    try:
        return matching.compute_match(matching.job_profile(job), matching.candidate_profile(db, student),
                                      eligibility_issues=reasons)
    except matching.MatchInputError as exc:
        return {"score": 0, "method": "unavailable", "matched_skills": [], "missing_skills": [],
                "explanation": str(exc), "generated_at": datetime.now(timezone.utc).isoformat()}


def match_with_review(db: Session, job: Job, app: JobApplication, reviewer_id: int) -> tuple[dict, str | None]:
    """Semantic match plus a local-LLM explanation. The LLM never changes the score.

    Returns (match, ai_error). When the LLM is unavailable the semantic match is still returned.
    """
    m = semantic_match(db, job, app.student)
    if m["method"] == "unavailable":
        return m, m["explanation"]
    try:
        review = ai.match_review(db, reviewer_id, job=_job_payload(job), candidate=_candidate_payload(db, app.student),
                                 computed=m)
    except ai.AIUnavailable as exc:
        m["ai_note"] = f"AI explanation unavailable: {exc.message}"
        return m, exc.message
    m["score_explanation"] = m["explanation"]
    m["explanation"] = review["explanation"]
    m["strengths"] = review["strengths"] or m["strengths"]
    # Keep the computed concerns (e.g. missing required skills) so the model can never hide a gap.
    m["concerns"] = m["concerns"] + [c for c in review["concerns"] if c not in m["concerns"]]
    m["method"] = "semantic+ai"
    return m, None


def eligibility(job: Job, profile: StudentProfile | None) -> tuple[bool, list[str]]:
    reasons = []
    if job.min_cgpa is not None and (not profile or profile.cgpa is None or profile.cgpa < job.min_cgpa):
        reasons.append(f"Minimum CGPA {job.min_cgpa} required")
    if job.eligible_branches:
        allowed = {b.lower() for b in job.eligible_branches}
        if not profile or not profile.branch or profile.branch.lower() not in allowed:
            reasons.append("Open to branches: " + ", ".join(job.eligible_branches))
    if job.graduation_years and (not profile or profile.graduation_year not in job.graduation_years):
        reasons.append("Open to graduation years: " + ", ".join(map(str, job.graduation_years)))
    if job.deadline and _aware(job.deadline) < datetime.now(timezone.utc):
        reasons.append("Application deadline has passed")
    return not reasons, reasons


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


# =========================================================================== recruiter

def _own_job(db: Session, user: User, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.recruiter_id != user.id:
        raise HTTPException(404, "Job not found")
    return job


def _own_application(db: Session, user: User, application_id: int) -> JobApplication:
    app = db.get(JobApplication, application_id)
    if not app or app.job.recruiter_id != user.id:
        raise HTTPException(404, "Application not found")
    return app


@recruiter_router.get("/dashboard")
def recruiter_dashboard(user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    jobs = db.scalars(select(Job).where(Job.recruiter_id == user.id)).all()
    job_ids = [j.id for j in jobs]
    counts = dict(db.execute(select(JobApplication.status, func.count(JobApplication.id))
                             .where(JobApplication.job_id.in_(job_ids)).group_by(JobApplication.status)).all()) if job_ids else {}
    recent = db.scalars(select(JobApplication).where(JobApplication.job_id.in_(job_ids))
                        .order_by(JobApplication.created_at.desc()).limit(8)).all() if job_ids else []
    upcoming = db.scalars(select(JobApplication).where(
        JobApplication.job_id.in_(job_ids), JobApplication.status == "interview_scheduled",
        JobApplication.interview_at >= datetime.now(timezone.utc)).order_by(JobApplication.interview_at).limit(8)).all() if job_ids else []
    per_job = []
    for j in jobs:
        c = dict(db.execute(select(JobApplication.status, func.count(JobApplication.id))
                            .where(JobApplication.job_id == j.id).group_by(JobApplication.status)).all())
        per_job.append({"id": j.id, "title": j.title, "status": j.status, "applications": sum(c.values()),
                        "shortlisted": c.get("shortlisted", 0) + c.get("interview_scheduled", 0),
                        "selected": c.get("selected", 0)})
    return {
        "jobs": {"total": len(jobs), "published": sum(1 for j in jobs if j.status == "published"),
                 "draft": sum(1 for j in jobs if j.status == "draft"), "closed": sum(1 for j in jobs if j.status == "closed")},
        "applications": {"total": sum(v for k, v in counts.items() if k != "withdrawn"), "by_status": counts},
        "per_job": per_job,
        "recent_applications": [application_out(a, include_student=True) for a in recent],
        "upcoming_interviews": [application_out(a, include_student=True) for a in upcoming],
    }


@recruiter_router.get("/jobs")
def list_jobs(status: str | None = None, q: str | None = None, page: int = 1, page_size: int = 20,
              user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    stmt = select(Job).where(Job.recruiter_id == user.id)
    if status:
        stmt = stmt.where(Job.status == status)
    if q:
        stmt = stmt.where(Job.title.ilike(f"%{q}%"))
    items, meta = paginate(db, stmt.order_by(Job.id.desc()), page, page_size)
    out = []
    for j in items:
        d = job_out(j)
        d["application_count"] = db.scalar(select(func.count(JobApplication.id)).where(
            JobApplication.job_id == j.id, JobApplication.status != "withdrawn")) or 0
        out.append(d)
    return {"items": out, **meta}


def _apply_job_fields(job: Job, body: JobIn) -> None:
    job.title, job.description, job.location = body.title.strip(), body.description.strip(), body.location.strip()
    job.job_type, job.experience_years, job.salary = body.job_type, body.experience_years, body.salary
    job.min_cgpa = body.min_cgpa
    job.eligible_branches = normalize_skills(body.eligible_branches)
    job.graduation_years = sorted(set(body.graduation_years))
    job.deadline = body.deadline
    required = normalize_skills(body.required_skills)
    preferred = [s for s in normalize_skills(body.preferred_skills) if s.lower() not in {r.lower() for r in required}]
    job.requirements.clear()
    for s in required:
        job.requirements.append(JobRequirement(skill=s, importance="required"))
    for s in preferred:
        job.requirements.append(JobRequirement(skill=s, importance="preferred"))


@recruiter_router.post("/jobs", status_code=201)
def create_job(body: JobIn, request: Request, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    company = user.recruiter_profile.company_name if user.recruiter_profile else "Company"
    job = Job(recruiter_id=user.id, company_name=company, title="", description="", location="")
    _apply_job_fields(job, body)
    job.status = body.status
    if body.status == "published":
        job.published_at = datetime.now(timezone.utc)
    db.add(job)
    db.flush()
    audit(db, user.id, "job.create", "job", job.id, {"title": job.title, "status": job.status}, client_ip(request))
    db.commit()
    return job_out(job)


@recruiter_router.get("/jobs/{job_id}")
def get_job(job_id: int, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    return job_out(_own_job(db, user, job_id))


@recruiter_router.put("/jobs/{job_id}")
def update_job(job_id: int, body: JobIn, request: Request, user: User = Depends(require_recruiter),
               db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    if job.status == "closed":
        raise HTTPException(400, "Closed jobs cannot be edited. Re-open it first.")
    db.flush()
    _apply_job_fields(job, body)
    audit(db, user.id, "job.update", "job", job.id, {"title": job.title}, client_ip(request))
    db.commit()
    return job_out(job)


@recruiter_router.post("/jobs/{job_id}/status/{action}")
def job_action(job_id: int, action: str, request: Request, user: User = Depends(require_recruiter),
               db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    transitions = {"publish": ("draft", "closed"), "close": ("published",), "unpublish": ("published",)}
    if action not in transitions:
        raise HTTPException(404, "Unknown action")
    if job.status not in transitions[action]:
        raise HTTPException(400, f"Cannot {action} a job that is {job.status}")
    if action == "publish":
        job.status = "published"
        job.published_at = job.published_at or datetime.now(timezone.utc)
    elif action == "close":
        job.status = "closed"
        for app in db.scalars(select(JobApplication).where(JobApplication.job_id == job.id,
                                                           JobApplication.status.in_(("applied", "shortlisted")))):
            notify(db, app.student_id, "Job closed", f"{job.title} at {job.company_name} is no longer accepting "
                   "applications. Your application remains under review.", "application", "/student/applications")
    else:
        job.status = "draft"
    audit(db, user.id, f"job.{action}", "job", job.id, {"title": job.title}, client_ip(request))
    db.commit()
    return job_out(job)


@recruiter_router.delete("/jobs/{job_id}")
def delete_job(job_id: int, request: Request, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    has_apps = db.scalar(select(func.count(JobApplication.id)).where(JobApplication.job_id == job.id)) or 0
    if has_apps:
        raise HTTPException(400, "Jobs with applications cannot be deleted; close the job instead")
    audit(db, user.id, "job.delete", "job", job.id, {"title": job.title}, client_ip(request))
    db.delete(job)
    db.commit()
    return {"ok": True}


@recruiter_router.get("/jobs/{job_id}/applications")
def job_applications(job_id: int, status: str | None = None, sort: str = "match",
                     user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    stmt = select(JobApplication).where(JobApplication.job_id == job.id)
    if status:
        stmt = stmt.where(JobApplication.status == status)
    apps = db.scalars(stmt).all()
    out = []
    for a in apps:
        d = application_out(a, include_student=True)
        s = student_summary(db, a.student)
        d["scores"] = {"interview_avg": s["interviews"]["average_score"], "english_avg": s["english"]["average_score"],
                       "assessment_avg": s["assessments"]["average_score"],
                       "resume_score": (s["resume"] or {}).get("resume_score"),
                       "readiness": s["readiness"]["score"]}
        d["assignments"] = _assignments_out(db, a)
        d["unread_messages"] = db.scalar(select(func.count(ApplicationMessage.id)).where(
            ApplicationMessage.application_id == a.id, ApplicationMessage.sender_id == a.student_id,
            ApplicationMessage.read.is_(False))) or 0
        out.append(d)
    if sort == "match":
        out.sort(key=lambda d: -((d["match"] or {}).get("score") or 0))
    else:
        out.sort(key=lambda d: d["created_at"], reverse=True)
    return {"job": job_out(job), "items": out}


@recruiter_router.patch("/applications/{application_id}/status")
def update_status(application_id: int, body: ApplicationStatusIn, request: Request,
                  user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    app = _own_application(db, user, application_id)
    if app.status == "withdrawn":
        raise HTTPException(400, "The candidate withdrew this application")
    if body.status == "interview_scheduled" and not body.interview_at:
        raise HTTPException(400, "Provide the interview date and time")
    old = app.status
    app.status = body.status
    if body.interview_at:
        app.interview_at = body.interview_at
    if body.note:
        app.recruiter_notes = body.note
    app.history.append(ApplicationStatusHistory(from_status=old, to_status=body.status, changed_by=user.id, note=body.note))
    msg = f"Your application for {app.job.title} at {app.job.company_name} is now: {STATUS_LABELS[body.status]}."
    if body.status == "interview_scheduled":
        msg += f" Interview on {body.interview_at.strftime('%d %b %Y, %H:%M')} (UTC)."
    if body.note:
        msg += f"\n\n{body.note}"
    db.add(ApplicationMessage(application_id=app.id, sender_id=user.id,
                              kind="invitation" if body.status == "interview_scheduled" else "update", body=msg))
    notify(db, app.student_id, "Application update", msg.split("\n")[0], "application", "/student/applications")
    audit(db, user.id, "application.status", "application", app.id, {"from": old, "to": body.status},
          client_ip(request))
    db.commit()
    _email_student(app.student, f"Application update: {app.job.title}", msg)
    return application_out(app, include_student=True)


def _candidate_payload(db: Session, student: User) -> dict:
    s = student_summary(db, student)
    resume = current_resume(db, student.id)
    p = student.student_profile
    return {
        "education": {"college": s["student"]["college"], "branch": s["student"]["branch"],
                      "graduation_year": s["student"]["graduation_year"], "cgpa": s["student"]["cgpa"]},
        "skills": s["student"]["skills"],
        "projects": (p.projects if p else []) or [],
        "experience": (p.experience if p else []) or [],
        "resume_analysis": {k: (resume.analysis or {}).get(k) for k in
                            ("candidate_summary", "skills", "projects", "experience", "certifications")}
        if resume and resume.analysis else None,
        "interview_performance": s["interviews"], "english": s["english"], "assessments": s["assessments"],
    }


@recruiter_router.post("/applications/{application_id}/match")
def ai_match(application_id: int, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    app = _own_application(db, user, application_id)
    app.match, ai_error = match_with_review(db, app.job, app, user.id)
    db.commit()
    return {**application_out(app, include_student=True), "ai_error": ai_error}


@recruiter_router.post("/jobs/{job_id}/compare")
def compare(job_id: int, body: CompareIn, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    rows = []
    for aid in body.application_ids:
        app = _own_application(db, user, aid)
        if app.job_id != job.id:
            raise HTTPException(400, "All applications must belong to this job")
        s = student_summary(db, app.student)
        req = {r.skill.lower() for r in job.requirements if r.importance == "required"}
        have = {x.lower() for x in s["student"]["skills"]}
        rows.append({
            "application_id": app.id, "student_id": app.student_id, "name": app.student.full_name,
            "status": app.status, "cgpa": s["student"]["cgpa"], "branch": s["student"]["branch"],
            "match_score": (app.match or {}).get("score"), "match_method": (app.match or {}).get("method"),
            "recommendation": (app.match or {}).get("recommendation"),
            "required_skills_covered": f"{len(req & have)}/{len(req)}" if req else "n/a",
            "missing_skills": (app.match or {}).get("missing_skills", []),
            "interview_avg": s["interviews"]["average_score"], "interview_best": s["interviews"]["best_score"],
            "technical_avg": s["interviews"]["by_category"].get("technical"),
            "english_avg": s["english"]["average_score"], "assessment_avg": s["assessments"]["average_score"],
            "resume_score": (s["resume"] or {}).get("resume_score"),
            "strengths": (app.match or {}).get("strengths", []), "concerns": (app.match or {}).get("concerns", []),
            "explanation": (app.match or {}).get("explanation"),
        })
    return {"job": job_out(job), "candidates": rows,
            "note": "Comparison is advisory. Scores come from recorded platform activity; the final decision is yours."}


@recruiter_router.get("/candidates")
def search_candidates(skill: str | None = None, branch: str | None = None, min_cgpa: float | None = None,
                      graduation_year: int | None = None, min_interview_score: float | None = None,
                      q: str | None = None, job_id: int | None = None, page: int = 1, page_size: int = 20,
                      user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    # Only students who opted in to sharing, plus students who applied to this recruiter's jobs.
    applicants = select(JobApplication.student_id).join(Job).where(Job.recruiter_id == user.id,
                                                                    JobApplication.status != "withdrawn")
    stmt = select(User).join(StudentProfile).where(
        User.role == "student", User.status == "active",
        or_(StudentProfile.share_with_recruiters.is_(True), User.id.in_(applicants)))
    if q:
        stmt = stmt.where(or_(User.full_name.ilike(f"%{q}%"), StudentProfile.college.ilike(f"%{q}%")))
    if branch:
        stmt = stmt.where(StudentProfile.branch.ilike(f"%{branch}%"))
    if min_cgpa is not None:
        stmt = stmt.where(StudentProfile.cgpa >= min_cgpa)
    if graduation_year:
        stmt = stmt.where(StudentProfile.graduation_year == graduation_year)
    students = db.scalars(stmt.order_by(User.full_name)).all()
    job = _own_job(db, user, job_id) if job_id else None
    results = []
    for st in students:
        p = st.student_profile
        skills = p.skills or []
        if skill and not any(skill.lower() in s.lower() for s in skills):
            continue
        avg = db.scalar(select(func.avg(InterviewSession.overall_score)).where(
            InterviewSession.student_id == st.id, InterviewSession.status == "completed",
            InterviewSession.flagged.is_(False)))
        avg = round(avg, 1) if avg is not None else None
        if min_interview_score is not None and (avg is None or avg < min_interview_score):
            continue
        row = {"id": st.id, "full_name": st.full_name, "college": p.college, "branch": p.branch, "cgpa": p.cgpa,
               "graduation_year": p.graduation_year, "skills": skills, "target_role": p.target_role,
               "interview_avg": avg, "has_applied_to_you": recruiter_has_applicant(db, user.id, st.id)}
        if job:
            ok, reasons = eligibility(job, p)
            row["eligible"], row["ineligible_reasons"] = ok, reasons
            row["skill_match"] = semantic_match(db, job, st)["score"]
        results.append(row)
    if job:
        results.sort(key=lambda r: (not r["eligible"], -r["skill_match"]))
    total = len(results)
    start = (max(page, 1) - 1) * page_size
    return {"items": results[start:start + page_size], "total": total, "page": page, "page_size": page_size,
            "pages": max((total + page_size - 1) // page_size, 1)}


@recruiter_router.get("/candidates/{student_id}")
def candidate_detail(student_id: int, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    student = db.get(User, student_id)
    if not student or student.role != "student" or student.status != "active":
        raise HTTPException(404, "Candidate not found")
    full_access = recruiter_has_applicant(db, user.id, student_id)
    if not full_access and not (student.student_profile and student.student_profile.share_with_recruiters):
        raise HTTPException(404, "Candidate not found")  # no consent and no application
    s = student_summary(db, student)
    p = student.student_profile
    data = {"summary": s, "full_access": full_access,
            "profile": {"projects": p.projects or [], "experience": p.experience or [], "bio": p.bio,
                        "career_interests": p.career_interests, "linkedin_url": p.linkedin_url,
                        "github_url": p.github_url} if p else None}
    if full_access:
        resume = current_resume(db, student_id)
        data["resume"] = resume_out(resume) if resume else None
        data["interviews"] = [interview_out(i, detail=True) for i in db.scalars(
            select(InterviewSession).where(InterviewSession.student_id == student_id,
                                           InterviewSession.status == "completed")
            .order_by(InterviewSession.id.desc()).limit(10))]
        data["applications"] = [application_out(a, include_student=False) for a in db.scalars(
            select(JobApplication).join(Job).where(JobApplication.student_id == student_id,
                                                   Job.recruiter_id == user.id))]
    else:
        data["summary"]["student"]["email"] = None
        data["notice"] = "Detailed resume and interview reports are visible once this candidate applies to one of your jobs."
    return data


# =========================================================================== screening, assignments, messages, export

def _assignments_out(db: Session, app: JobApplication) -> list[dict]:
    rows = db.scalars(select(AssessmentAssignment).where(AssessmentAssignment.application_id == app.id)).all()
    return [{"id": r.id, "assessment_id": r.assessment_id, "title": r.assessment.title, "status": r.status,
             "due_at": iso(r.due_at), "score": r.result.score if r.result else None,
             "passed": r.result.passed if r.result else None} for r in rows]


def _job_payload(job: Job) -> dict:
    return {"title": job.title, "description": job.description, "experience_years": job.experience_years,
            "min_cgpa": job.min_cgpa, "eligible_branches": job.eligible_branches,
            "required_skills": [r.skill for r in job.requirements if r.importance == "required"],
            "preferred_skills": [r.skill for r in job.requirements if r.importance == "preferred"]}


@recruiter_router.post("/jobs/{job_id}/screen")
def screen_all(job_id: int, force: bool = False, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """AI resume screening for every active applicant of a job (up to 25 per request)."""
    job = _own_job(db, user, job_id)
    apps = db.scalars(select(JobApplication).where(JobApplication.job_id == job.id,
                                                   JobApplication.status != "withdrawn")).all()
    todo = [a for a in apps if force or (a.match or {}).get("method") not in AI_METHODS][:25]
    screened, error = 0, None
    for a in todo:
        m, ai_error = match_with_review(db, job, a, user.id)
        a.match = m
        db.commit()
        if ai_error:  # semantic score was refreshed, but the AI explanation is unavailable - stop calling it
            error = ai_error
            break
        screened += 1
    remaining = sum(1 for a in apps if (a.match or {}).get("method") not in AI_METHODS)
    if error and screened == 0:
        raise HTTPException(503, error + " Semantic match scores are still shown.")
    return {"screened": screened, "remaining": remaining, "error": error}


@recruiter_router.post("/applications/{application_id}/assessments", status_code=201)
def assign_assessment(application_id: int, body: AssignAssessmentIn, request: Request,
                      user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    app = _own_application(db, user, application_id)
    a = db.get(Assessment, body.assessment_id)
    if not a or a.created_by != user.id or a.job_id != app.job_id:
        raise HTTPException(400, "Choose one of your assessments linked to this job")
    if not a.active:
        raise HTTPException(400, "This assessment is inactive")
    if db.scalar(select(AssessmentAssignment.id).where(AssessmentAssignment.assessment_id == a.id,
                                                       AssessmentAssignment.application_id == app.id)):
        raise HTTPException(409, "This assessment is already assigned to the candidate")
    db.add(AssessmentAssignment(assessment_id=a.id, application_id=app.id, student_id=app.student_id,
                                assigned_by=user.id, due_at=body.due_at))
    text = f"You have been assigned the assessment '{a.title}' for {app.job.title}."
    if body.due_at:
        text += f" Please complete it by {body.due_at.strftime('%d %b %Y, %H:%M')} (UTC)."
    if body.message:
        text += f"\n\n{body.message}"
    db.add(ApplicationMessage(application_id=app.id, sender_id=user.id, kind="assessment", body=text))
    notify(db, app.student_id, "Assessment assigned", text.split("\n")[0], "assessment", "/student/assessments")
    audit(db, user.id, "assessment.assign", "application", app.id, {"assessment_id": a.id}, client_ip(request))
    db.commit()
    return {"assignments": _assignments_out(db, app)}


def message_out(m: ApplicationMessage) -> dict:
    return {"id": m.id, "sender_id": m.sender_id, "sender_name": m.sender.full_name if m.sender else "System",
            "kind": m.kind, "body": m.body, "read": m.read, "created_at": iso(m.created_at)}


def _thread(db: Session, app: JobApplication, viewer: User) -> list[dict]:
    msgs = db.scalars(select(ApplicationMessage).where(ApplicationMessage.application_id == app.id)
                      .order_by(ApplicationMessage.id)).all()
    for m in msgs:
        if m.sender_id != viewer.id and not m.read:
            m.read = True
    db.commit()
    return [message_out(m) for m in msgs]


@recruiter_router.get("/applications/{application_id}/messages")
def recruiter_messages(application_id: int, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    return _thread(db, _own_application(db, user, application_id), user)


@recruiter_router.post("/applications/{application_id}/messages", status_code=201)
def recruiter_send(application_id: int, body: MessageIn, user: User = Depends(require_recruiter),
                   db: Session = Depends(get_db)):
    app = _own_application(db, user, application_id)
    db.add(ApplicationMessage(application_id=app.id, sender_id=user.id, kind=body.kind, body=body.body.strip()))
    title = "Interview invitation" if body.kind == "invitation" else f"Message from {app.job.company_name}"
    notify(db, app.student_id, title, body.body[:140], "message", "/student/applications")
    db.commit()
    _email_student(app.student, f"{title} - {app.job.title}", body.body.strip())
    return _thread(db, app, user)


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


def _csv(rows: list[dict], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["empty"])
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@recruiter_router.get("/jobs/{job_id}/export")
def export_applicants(job_id: int, request: Request, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    rows = []
    for a in db.scalars(select(JobApplication).where(JobApplication.job_id == job.id)):
        s = student_summary(db, a.student)
        st = s["student"]
        rows.append({"application_id": a.id, "name": st["full_name"], "email": st["email"], "college": st["college"] or "",
                     "branch": st["branch"] or "", "graduation_year": st["graduation_year"] or "",
                     "cgpa": st["cgpa"] if st["cgpa"] is not None else "", "status": a.status,
                     "match_score": (a.match or {}).get("score", ""), "match_method": (a.match or {}).get("method", ""),
                     "interview_avg": s["interviews"]["average_score"] or "", "english_avg": s["english"]["average_score"] or "",
                     "assessment_avg": s["assessments"]["average_score"] or "", "readiness": s["readiness"]["score"],
                     "skills": "; ".join(st["skills"]), "applied_on": iso(a.created_at)})
    audit(db, user.id, "export.applicants", "job", job.id, {"rows": len(rows)}, client_ip(request))
    db.commit()
    return _csv(rows, f"applicants_job_{job.id}.csv")

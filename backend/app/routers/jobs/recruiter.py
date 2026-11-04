"""Recruiter portal: dashboard, jobs, applicants, AI match, compare, candidate report, candidate search."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from ...odm import func, or_, select
from ...odm import Session
from ...database import get_db
from ...deps import client_ip, require_recruiter
from ...models import (
    ApplicationMessage, ApplicationStatusHistory, InterviewSession, Job, JobApplication, JobRequirement,
    StudentProfile, User,
)
from ...schemas import ApplicationStatusIn, CompareIn, JobIn
from ...serializers import application_out, interview_out, iso, job_out, resume_out
from ...services.access import recruiter_has_applicant
from ...services.common import audit, normalize_skills, notify, paginate
from ...services.insights import current_resume, student_summary
from .common import STATUS_LABELS, _assignments_out, _candidate_payload, _email_student, eligibility, match_with_review, semantic_match


recruiter_router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

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

@recruiter_router.post("/applications/{application_id}/match")
def ai_match(application_id: int, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    app = _own_application(db, user, application_id)
    app.match, ai_error = match_with_review(db, app.job, app, user.id)
    db.commit()
    return {**application_out(app, include_student=True), "ai_error": ai_error}


def _match_breakdown(match: dict | None) -> dict:
    m = match or {}
    return {k: m.get(k) for k in ("criteria_scores", "weights", "matched_skills", "partially_matched_skills",
                                  "missing_required_skills", "missing_preferred_skills", "eligible",
                                  "eligibility_issues", "relevant_projects")}


def _recent_interviews(db: Session, student_id: int, limit: int = 5) -> list[dict]:
    rows = db.scalars(select(InterviewSession).where(InterviewSession.student_id == student_id,
                                                     InterviewSession.status == "completed")
                      .order_by(InterviewSession.id.desc()).limit(limit)).all()
    return [{"id": i.id, "job_role": i.job_role, "category": i.category, "difficulty": i.difficulty,
             "score": i.overall_score, "flagged": bool(i.flagged), "completed_at": iso(i.completed_at)} for i in rows]


def _compare_row(db: Session, user: User, job: Job, app: JobApplication) -> dict:
    from ..monitoring import integrity_overview  # late import: monitoring is a sibling router

    s = student_summary(db, app.student)
    req = {r.skill.lower() for r in job.requirements if r.importance == "required"}
    have = {x.lower() for x in s["student"]["skills"]}
    m = app.match or {}
    return {
        "application_id": app.id, "student_id": app.student_id, "name": app.student.full_name,
        "status": app.status, "applied_at": iso(app.created_at), "college": s["student"]["college"],
        "cgpa": s["student"]["cgpa"], "branch": s["student"]["branch"],
        "graduation_year": s["student"]["graduation_year"],
        "match_score": m.get("score"), "match_method": m.get("method"), "recommendation": m.get("recommendation"),
        "required_skills_covered": f"{len(req & have)}/{len(req)}" if req else "n/a",
        "missing_skills": m.get("missing_skills", []),
        "match_breakdown": _match_breakdown(app.match),
        "interview_avg": s["interviews"]["average_score"], "interview_best": s["interviews"]["best_score"],
        "interview_count": s["interviews"]["completed"],
        "interview_criteria": s["interviews"]["criteria"], "assessments_taken": s["assessments"]["taken"],
        "assessments_passed": s["assessments"]["passed"], "assessments_by_topic": s["assessments"]["by_topic"],
        "technical_avg": s["interviews"]["by_category"].get("technical"),
        "interviews_by_category": s["interviews"]["by_category"],
        "recent_interviews": _recent_interviews(db, app.student_id, 3),
        "english_avg": s["english"]["average_score"], "assessment_avg": s["assessments"]["average_score"],
        "job_assessments": _assignments_out(db, app),
        "resume_score": (s["resume"] or {}).get("resume_score"), "readiness": s["readiness"]["score"],
        "strengths": m.get("strengths", []), "concerns": m.get("concerns", []),
        "explanation": m.get("explanation"),
        "integrity": integrity_overview(db, user, app.student_id),
    }


@recruiter_router.post("/jobs/{job_id}/compare")
def compare(job_id: int, body: CompareIn, user: User = Depends(require_recruiter), db: Session = Depends(get_db)):
    """Side-by-side view of 2-4 applicants to one of this recruiter's jobs (advisory)."""
    job = _own_job(db, user, job_id)
    ids = list(dict.fromkeys(body.application_ids))
    if len(ids) < 2:
        raise HTTPException(400, "Pick at least two different applications")
    rows = []
    for aid in ids:
        app = _own_application(db, user, aid)
        if app.job_id != job.id:
            raise HTTPException(400, "All applications must belong to this job")
        if app.status == "withdrawn":
            raise HTTPException(400, f"{app.student.full_name} withdrew this application")
        rows.append(_compare_row(db, user, job, app))
    return {"job": job_out(job), "candidates": rows,
            "note": "Comparison is advisory. Scores come from recorded platform activity; the final decision is yours. "
                    "Integrity signals are shown separately and are never a basis for a decision on their own."}


@recruiter_router.get("/applications/{application_id}/report")
def candidate_report(application_id: int, request: Request, user: User = Depends(require_recruiter),
                     db: Session = Depends(get_db)):
    """Everything a recruiter may see about one applicant to one of their jobs, for the printable report page.
    Scoped to the application, so the access rule (applied to this recruiter's job) is enforced by construction."""
    app = _own_application(db, user, application_id)
    if app.status == "withdrawn":
        raise HTTPException(404, "Application not found")
    job, student = app.job, app.student
    p = student.student_profile
    resume = current_resume(db, student.id)
    row = _compare_row(db, user, job, app)
    row["recent_interviews"] = _recent_interviews(db, student.id, 10)
    audit(db, user.id, "candidate.report", "application", app.id, None, client_ip(request))
    db.commit()
    return {
        "generated_at": iso(datetime.now(timezone.utc)), "job": job_out(job), "candidate": row,
        "contact": {"email": student.email, "linkedin_url": p.linkedin_url if p else None,
                    "github_url": p.github_url if p else None},
        "profile": _candidate_payload(db, student),
        "resume": {"filename": resume.filename, "analysis_summary": (resume.analysis or {}).get("candidate_summary"),
                   "strengths": (resume.analysis or {}).get("strengths", []),
                   "improvement_areas": (resume.analysis or {}).get("improvement_areas", [])}
        if resume else None,
        "cover_letter": app.cover_letter,
        "history": [{"from": h.from_status, "to": h.to_status, "note": h.note, "at": iso(h.created_at)}
                    for h in sorted(app.history, key=lambda h: h.id or 0)],
        "interview_at": iso(app.interview_at),
        "note": "Generated from recorded HireSense activity. Scores are practice estimates; AI match explanations are "
                "advisory. Integrity signals are approximate and never a basis for a hiring decision on their own.",
    }


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

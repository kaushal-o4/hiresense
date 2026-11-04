"""Helpers shared by the student and recruiter job endpoints: matching, eligibility, payloads, email, message threads."""
from datetime import datetime, timezone

from ...odm import select
from ...odm import Session
from ...config import get_settings
from ...models import ApplicationMessage, AssessmentAssignment, Job, JobApplication, StudentProfile, User
from ...serializers import iso
from ...services import ai, mailer, matching
from ...services.insights import current_resume, student_summary


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

"""Recruiter portal: bulk screening, assessment assignments, messages to applicants, CSV export."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...odm import select
from ...odm import Session
from ...database import get_db
from ...deps import client_ip, require_recruiter
from ...models import ApplicationMessage, Assessment, AssessmentAssignment, JobApplication, User
from ...schemas import AssignAssessmentIn, MessageIn
from ...serializers import iso
from ...services.common import audit, notify
from ...services.insights import student_summary
from .common import AI_METHODS, _assignments_out, _email_student, _thread, match_with_review
from .recruiter import _own_application, _own_job


recruiter_router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

# =========================================================================== screening, assignments, messages, export

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

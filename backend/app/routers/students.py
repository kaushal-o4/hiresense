"""Student portal: dashboard, resume, progress, rewards, mentoring and recommendations."""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from ..odm import select
from ..odm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_student
from ..odm import func

from ..models import (
    AssessmentResult, Badge, Challenge, ChallengeCompletion, DriveRegistration, ImprovementPlan, InterviewSession,
    Job, JobApplication, MentorAssignment, MentorFeedback, MentorSession, PlacementDrive, PlanGoal,
    PointTransaction, Resume, ResumeSkill, StudentBadge, User,
)
from ..schemas import ResumeAnalysisCorrection
from ..serializers import application_out, drive_out, iso, mentor_session_out, plan_out, resume_out
from ..services import ai
from ..services.access import ensure_can_view_student
from ..services.common import normalize_skills
from ..services.insights import (
    attempt_comparison, practice_history, progress_series, student_summary, weekly_progress,
)
from ..services.resume_parser import ResumeParseError, detect_kind, extract_text
from ..services.rewards import (
    badge_stats, challenge_progress, complete_goal, goal_progress, period_bounds, total_points,
)

router = APIRouter(prefix="/api/student", tags=["student"])
shared = APIRouter(prefix="/api", tags=["resumes"])


# --------------------------------------------------------------------------- dashboard

@router.get("/dashboard")
def dashboard(user: User = Depends(require_student), db: Session = Depends(get_db)):
    summary = student_summary(db, user)
    apps = db.scalars(select(JobApplication).where(JobApplication.student_id == user.id)
                      .order_by(JobApplication.updated_at.desc()).limit(5)).all()
    upcoming = db.scalars(select(MentorSession).where(
        MentorSession.student_id == user.id, MentorSession.status == "scheduled",
        MentorSession.scheduled_at >= datetime.now(timezone.utc)).order_by(MentorSession.scheduled_at).limit(5)).all()
    interviews_upcoming = [a for a in apps if a.status == "interview_scheduled" and a.interview_at]
    pending_goals = db.scalars(select(PlanGoal).join(ImprovementPlan).where(
        ImprovementPlan.student_id == user.id, ImprovementPlan.status == "active",
        PlanGoal.status == "pending").order_by(PlanGoal.deadline.is_(None), PlanGoal.deadline).limit(5)).all()
    recent_badges = db.scalars(select(StudentBadge).where(StudentBadge.student_id == user.id)
                               .order_by(StudentBadge.awarded_at.desc()).limit(4)).all()
    return {
        "summary": summary,
        "profile_completeness": summary["readiness"]["components"]["profile"],
        "challenges": challenges_for(db, user.id),
        "recent_applications": [application_out(a) for a in apps],
        "upcoming": {
            "mentor_sessions": [mentor_session_out(s) for s in upcoming],
            "job_interviews": [{"application_id": a.id, "job_title": a.job.title, "company": a.job.company_name,
                                "interview_at": iso(a.interview_at)} for a in interviews_upcoming],
            "goals": [{"id": g.id, "title": g.title, "goal_type": g.goal_type, "deadline": iso(g.deadline)}
                      for g in pending_goals],
        },
        "recent_badges": [{"name": b.badge.name, "icon": b.badge.icon, "awarded_at": iso(b.awarded_at)}
                          for b in recent_badges],
        "progress": progress_series(db, user.id),
    }


@router.get("/progress")
def progress(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return {"summary": student_summary(db, user), "series": progress_series(db, user.id)}


@router.post("/recommendations")
def recommendations(user: User = Depends(require_student), db: Session = Depends(get_db)):
    summary = student_summary(db, user)
    try:
        return {"method": "ai", **ai.student_recommendations(db, user.id, snapshot=summary)}
    except ai.AIUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)


@router.post("/role-recommendations")
def role_recommendations(user: User = Depends(require_student), db: Session = Depends(get_db)):
    summary = student_summary(db, user)
    p = user.student_profile
    snapshot = {**summary, "projects": (p.projects if p else []) or [], "experience": (p.experience if p else []) or []}
    try:
        rec = ai.job_role_recommendations(db, user.id, snapshot=snapshot, interests=p.career_interests if p else None)
    except ai.AIUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)
    # Link each suggested role to currently open jobs with a similar title.
    open_jobs = db.scalars(select(Job).where(Job.status == "published")).all()
    for r in rec["roles"]:
        words = {w for w in r["role"].lower().split() if len(w) > 3}
        r["open_jobs"] = [{"id": j.id, "title": j.title, "company_name": j.company_name}
                          for j in open_jobs if words & set(j.title.lower().split())][:3]
    return {"method": "ai", **rec}


@router.get("/report")
def performance_report(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Scores, strengths, weaknesses and specific mistakes to review."""
    summary = student_summary(db, user)
    strengths, weaknesses, mistakes = [], list(summary["weak_areas"]), []
    if summary["resume"]:
        strengths += summary["resume"]["strengths"][:5]
    for s in db.scalars(select(InterviewSession).where(
            InterviewSession.student_id == user.id, InterviewSession.status == "completed")
            .order_by(InterviewSession.completed_at.desc()).limit(10)):
        if s.report:
            strengths += s.report.get("strengths", [])[:2]
            weaknesses += s.report.get("weaknesses", [])[:2]
        for q in s.questions:
            if q.answer and q.answer.score is not None and q.answer.score < 60:
                mistakes.append({"type": "interview", "source": f"{s.job_role} interview", "question": q.text,
                                 "your_answer": q.answer.text, "score": q.answer.score, "feedback": q.answer.feedback,
                                 "sample_answer": q.answer.sample_answer, "date": iso(s.completed_at),
                                 "link": f"/student/interviews/{s.id}"})
    for r in db.scalars(select(AssessmentResult).where(
            AssessmentResult.student_id == user.id, AssessmentResult.submitted_at.is_not(None))
            .order_by(AssessmentResult.submitted_at.desc()).limit(10)):
        for i, q in enumerate(r.assessment.questions or []):
            d = (r.details or [None] * (i + 1))[i] or {}
            ans = r.answers[i] if i < len(r.answers) else None
            if (q.get("type") or "mcq") == "mcq" and d.get("status") == "completed" and not d.get("correct"):
                mistakes.append({"type": "assessment", "source": r.assessment.title, "question": q["question"],
                                 "your_answer": q["options"][ans] if isinstance(ans, int) and 0 <= ans < len(q["options"]) else "(not answered)",
                                 "correct_answer": q["options"][q["answer_index"]], "explanation": q.get("explanation"),
                                 "date": iso(r.submitted_at)})
            elif q.get("type") == "coding" and d.get("status") == "completed" and (d.get("score") or 0) < 60:
                mistakes.append({"type": "coding", "source": r.assessment.title, "question": q["question"],
                                 "score": d.get("score"), "feedback": d.get("feedback"),
                                 "sample_answer": d.get("improved_solution"), "date": iso(r.submitted_at)})
    dedupe = lambda xs: list(dict.fromkeys(x for x in xs if x))[:10]
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "summary": summary,
            "strengths": dedupe(strengths), "weaknesses": dedupe(weaknesses), "mistakes": mistakes[:40],
            "attempts": attempt_comparison(db, user.id), "weekly": weekly_progress(db, user.id)}


@router.get("/history")
def history(type: str | None = None, user: User = Depends(require_student), db: Session = Depends(get_db)):
    items = practice_history(db, user.id, limit=500)
    if type:
        items = [i for i in items if i["type"] == type]
    return items


# --------------------------------------------------------------------------- challenges

def challenges_for(db: Session, student_id: int) -> list[dict]:
    out = []
    for ch in db.scalars(select(Challenge).where(Challenge.active.is_(True)).order_by(Challenge.period, Challenge.id)):
        _, key = period_bounds(ch.period)
        done = db.scalar(select(ChallengeCompletion.id).where(
            ChallengeCompletion.challenge_id == ch.id, ChallengeCompletion.student_id == student_id,
            ChallengeCompletion.period_key == key)) is not None
        value = challenge_progress(db, student_id, ch)
        out.append({"id": ch.id, "title": ch.title, "description": ch.description, "metric": ch.metric,
                    "target": ch.target, "period": ch.period, "points": ch.points, "progress": value,
                    "percent": min(100, round(100 * value / ch.target)) if ch.target else 100, "completed": done})
    return out


@router.get("/challenges")
def challenges(user: User = Depends(require_student), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(ChallengeCompletion.id)).where(ChallengeCompletion.student_id == user.id)) or 0
    return {"challenges": challenges_for(db, user.id), "completed_total": total}


# --------------------------------------------------------------------------- placement drives

def _drive_eligible(d: PlacementDrive, p) -> tuple[bool, list[str]]:
    reasons = []
    if d.min_cgpa is not None and (not p or p.cgpa is None or p.cgpa < d.min_cgpa):
        reasons.append(f"Minimum CGPA {d.min_cgpa}")
    if d.eligible_branches and (not p or not p.branch or p.branch.lower() not in {b.lower() for b in d.eligible_branches}):
        reasons.append("Branches: " + ", ".join(d.eligible_branches))
    return not reasons, reasons


@router.get("/drives")
def drives(user: User = Depends(require_student), db: Session = Depends(get_db)):
    mine = set(db.scalars(select(DriveRegistration.drive_id).where(DriveRegistration.student_id == user.id)))
    out = []
    for d in db.scalars(select(PlacementDrive).where(PlacementDrive.status != "cancelled")
                        .order_by(PlacementDrive.drive_date.desc())):
        ok, reasons = _drive_eligible(d, user.student_profile)
        out.append({**drive_out(d), "registered": d.id in mine, "eligible": ok, "ineligible_reasons": reasons})
    return out


@router.post("/drives/{drive_id}/register")
def register_drive(drive_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    d = db.get(PlacementDrive, drive_id)
    if not d or d.status != "upcoming":
        raise HTTPException(404, "This drive is not open for registration")
    ok, reasons = _drive_eligible(d, user.student_profile)
    if not ok:
        raise HTTPException(400, "You are not eligible: " + "; ".join(reasons))
    if db.scalar(select(DriveRegistration.id).where(DriveRegistration.drive_id == d.id,
                                                    DriveRegistration.student_id == user.id)):
        raise HTTPException(409, "You are already registered for this drive")
    db.add(DriveRegistration(drive_id=d.id, student_id=user.id))
    db.commit()
    return {"ok": True}


@router.delete("/drives/{drive_id}/register")
def unregister_drive(drive_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    reg = db.scalar(select(DriveRegistration).where(DriveRegistration.drive_id == drive_id,
                                                    DriveRegistration.student_id == user.id))
    if not reg:
        raise HTTPException(404, "Registration not found")
    db.delete(reg)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- resume

@router.get("/resumes")
def list_resumes(user: User = Depends(require_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(Resume).where(Resume.student_id == user.id).order_by(Resume.id.desc())).all()
    return [resume_out(r) for r in rows]


def _run_analysis(db: Session, user: User, resume: Resume) -> str | None:
    target = user.student_profile.target_role if user.student_profile else None
    try:
        analysis = ai.analyze_resume(db, user.id, resume.raw_text, target)
    except ai.AIUnavailable as exc:
        resume.analysis_status = "unavailable"
        resume.analysis_error = exc.message
        db.commit()
        return exc.message
    resume.analysis = analysis
    resume.analysis_status = "completed"
    resume.analysis_error = None
    resume.analyzed_at = datetime.now(timezone.utc)
    resume.skills.clear()
    db.flush()
    seen = set()
    for s in analysis.get("skills", []):
        name = (s.get("name") or "").strip()[:100]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            resume.skills.append(ResumeSkill(name=name, category=s.get("category")))
    db.commit()
    return None


RESUME_HISTORY = 10  # older versions beyond this are deleted together with their files


def _prune_resume_history(db: Session, student_id: int) -> None:
    """Keep the newest RESUME_HISTORY resumes (and always the current one); delete older ones and their files."""
    rows = list(db.scalars(select(Resume).where(Resume.student_id == student_id).order_by(Resume.id.desc())))
    old = [r for r in rows[RESUME_HISTORY:] if not r.is_current]
    paths = [Path(r.stored_path) for r in old]
    for r in old:
        db.delete(r)
    if old:
        db.commit()
        for p in paths:
            p.unlink(missing_ok=True)


@router.post("/resumes", status_code=201)
def upload_resume(file: UploadFile = File(...), user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    # Sync endpoint: FastAPI runs it in a worker thread, so the blocking AI call doesn't stall the server.
    settings = get_settings()
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "The uploaded file is empty")
    try:
        kind = detect_kind(file.filename or "", file.content_type, data)
        text = extract_text(kind, data)
    except ResumeParseError as exc:
        raise HTTPException(400, str(exc))
    folder = Path(settings.upload_dir) / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}.{kind}"
    stored.write_bytes(data)
    for old in db.scalars(select(Resume).where(Resume.student_id == user.id, Resume.is_current.is_(True))):
        old.is_current = False
    resume = Resume(student_id=user.id, filename=(file.filename or f"resume.{kind}")[:255], stored_path=str(stored),
                    content_type="application/pdf" if kind == "pdf" else
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    raw_text=text, is_current=True, analysis_status="pending")
    db.add(resume)
    try:
        db.commit()
    except Exception:
        stored.unlink(missing_ok=True)  # don't leave an orphan file if the record couldn't be saved
        raise
    _prune_resume_history(db, user.id)
    error = _run_analysis(db, user, resume)
    db.refresh(resume)
    return {"resume": resume_out(resume), "ai_error": error}


@router.post("/resumes/{resume_id}/analyze")
def reanalyze(resume_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume or resume.student_id != user.id:
        raise HTTPException(404, "Resume not found")
    error = _run_analysis(db, user, resume)
    if error:
        raise HTTPException(503, error)
    db.refresh(resume)
    return resume_out(resume)


@router.patch("/resumes/{resume_id}/analysis")
def correct_analysis(resume_id: int, body: ResumeAnalysisCorrection, user: User = Depends(require_student),
                     db: Session = Depends(get_db)):
    """Let the student fix details the AI extracted incorrectly. The completeness score is recalculated."""
    resume = db.get(Resume, resume_id)
    if not resume or resume.student_id != user.id:
        raise HTTPException(404, "Resume not found")
    if resume.analysis_status != "completed" or not resume.analysis:
        raise HTTPException(400, "This resume has not been analysed yet")
    a = dict(resume.analysis)
    clean = lambda xs, n: [" ".join(x.split())[:100] for x in xs if x and x.strip()][:n]  # noqa: E731
    if body.full_name is not None:
        a["full_name"] = " ".join(body.full_name.split()) or None
    old_cats = {s["name"].lower(): s.get("category") for s in a.get("skills", [])}
    if body.technical_skills is not None:
        tech = [{"name": n, "category": old_cats.get(n.lower()) if old_cats.get(n.lower()) not in (None, "soft_skill")
                 else "other"} for n in normalize_skills(clean(body.technical_skills, 100))]
    else:
        tech = [s for s in a.get("skills", []) if s.get("category") != "soft_skill"]
    soft = clean(body.soft_skills, 30) if body.soft_skills is not None else a.get("soft_skills", [])
    a["soft_skills"] = soft
    a["skills"] = tech + [{"name": s, "category": "soft_skill"} for s in soft
                          if s.lower() not in {t["name"].lower() for t in tech}]
    if body.certifications is not None:
        a["certifications"] = clean(body.certifications, 30)
    for field in ("projects", "experience", "internships"):
        value = getattr(body, field)
        if value is not None:
            a[field] = [x.model_dump(exclude={"link"}) for x in value]
    a.setdefault("internships", [])
    a["resume_score"], a["score_breakdown"] = ai.resume_completeness(a)
    a["edited_by_student"] = True
    a["edited_at"] = datetime.now(timezone.utc).isoformat()
    resume.analysis = a
    resume.skills.clear()
    db.flush()
    seen = set()
    for s in a["skills"]:
        if s["name"].lower() not in seen:
            seen.add(s["name"].lower())
            resume.skills.append(ResumeSkill(name=s["name"][:100], category=s.get("category")))
    db.commit()
    db.refresh(resume)
    return resume_out(resume)


@router.post("/resumes/{resume_id}/apply-skills")
def apply_skills(resume_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume or resume.student_id != user.id:
        raise HTTPException(404, "Resume not found")
    prof = user.student_profile
    prof.skills = normalize_skills(list(prof.skills or []) + [s.name for s in resume.skills])
    if resume.analysis:
        if not prof.projects and resume.analysis.get("projects"):
            prof.projects = [{"name": p["name"], "description": p.get("description", ""),
                              "technologies": p.get("technologies", [])} for p in resume.analysis["projects"]
                             if p.get("name")][:30]
        if not prof.experience and resume.analysis.get("experience"):
            prof.experience = [{"organization": e["organization"], "role": e.get("role") or "-",
                                "duration": e.get("duration", ""), "summary": e.get("summary", "")}
                               for e in resume.analysis["experience"] if e.get("organization")][:30]
    db.commit()
    return {"skills": prof.skills, "message": "Profile updated with skills from your resume"}


@router.post("/resumes/{resume_id}/make-current")
def make_current(resume_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume or resume.student_id != user.id:
        raise HTTPException(404, "Resume not found")
    for r in db.scalars(select(Resume).where(Resume.student_id == user.id)):
        r.is_current = r.id == resume.id
    db.commit()
    return {"ok": True}


@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume or resume.student_id != user.id:
        raise HTTPException(404, "Resume not found")
    was_current = resume.is_current
    path = Path(resume.stored_path)
    db.delete(resume)
    db.flush()
    if was_current:
        latest = db.scalar(select(Resume).where(Resume.student_id == user.id).order_by(Resume.id.desc()))
        if latest:
            latest.is_current = True
    db.commit()
    path.unlink(missing_ok=True)
    return {"ok": True}


@shared.get("/resumes/{resume_id}")
def view_resume(resume_id: int, viewer: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    ensure_can_view_student(db, viewer, resume.student_id)
    return resume_out(resume)


@shared.get("/resumes/{resume_id}/download")
def download_resume(resume_id: int, viewer: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    ensure_can_view_student(db, viewer, resume.student_id)
    path = Path(resume.stored_path)
    if not path.exists():
        raise HTTPException(404, "The resume file is no longer available")
    return FileResponse(path, media_type=resume.content_type, filename=resume.filename)


# --------------------------------------------------------------------------- rewards

@router.get("/rewards")
def rewards(user: User = Depends(require_student), db: Session = Depends(get_db)):
    owned = {sb.badge_id: sb for sb in db.scalars(select(StudentBadge).where(StudentBadge.student_id == user.id))}
    stats = badge_stats(db, user.id)
    badges = []
    for b in db.scalars(select(Badge).where(Badge.active.is_(True)).order_by(Badge.threshold)):
        value = stats.get(b.criteria_type, 0) or 0
        badges.append({"id": b.id, "code": b.code, "name": b.name, "description": b.description, "icon": b.icon,
                       "criteria_type": b.criteria_type, "threshold": b.threshold, "points": b.points,
                       "earned": b.id in owned, "awarded_at": iso(owned[b.id].awarded_at) if b.id in owned else None,
                       "progress": min(100, round(100 * value / b.threshold)) if b.threshold else 100,
                       "current_value": value})
    txs = db.scalars(select(PointTransaction).where(PointTransaction.student_id == user.id)
                     .order_by(PointTransaction.id.desc()).limit(50)).all()
    return {"points": total_points(db, user.id), "stats": stats, "badges": badges,
            "earned_count": len(owned),
            "transactions": [{"id": t.id, "points": t.points, "reason": t.reason, "activity_type": t.activity_type,
                              "revoked": t.revoked, "created_at": iso(t.created_at)} for t in txs]}


@router.get("/leaderboard")
def leaderboard(user: User = Depends(require_student), db: Session = Depends(get_db)):
    from ..odm import func
    rows = db.execute(select(User.id, User.full_name, func.sum(PointTransaction.points).label("pts"))
                      .join(PointTransaction, PointTransaction.student_id == User.id)
                      .where(PointTransaction.revoked.is_(False), User.status == "active")
                      .group_by(User.id, User.full_name).order_by(func.sum(PointTransaction.points).desc())
                      .limit(10)).all()
    return [{"rank": i + 1, "name": r.full_name if r.id == user.id else r.full_name.split()[0],
             "points": r.pts, "is_me": r.id == user.id} for i, r in enumerate(rows)]


# --------------------------------------------------------------------------- mentoring (student view)

@router.get("/mentoring")
def mentoring(user: User = Depends(require_student), db: Session = Depends(get_db)):
    mentors = db.scalars(select(MentorAssignment).where(MentorAssignment.student_id == user.id,
                                                        MentorAssignment.active.is_(True))).all()
    feedback = db.scalars(select(MentorFeedback).where(MentorFeedback.student_id == user.id,
                                                       MentorFeedback.kind == "feedback")
                          .order_by(MentorFeedback.id.desc())).all()
    plans = db.scalars(select(ImprovementPlan).where(ImprovementPlan.student_id == user.id,
                                                     ImprovementPlan.status != "archived")
                       .order_by(ImprovementPlan.id.desc())).all()
    sessions = db.scalars(select(MentorSession).where(MentorSession.student_id == user.id)
                          .order_by(MentorSession.scheduled_at.desc())).all()
    return {
        "mentors": [{"id": a.mentor.id, "full_name": a.mentor.full_name, "email": a.mentor.email,
                     "department": a.mentor.mentor_profile.department if a.mentor.mentor_profile else None}
                    for a in mentors],
        "feedback": [{"id": f.id, "mentor_name": f.mentor.full_name, "category": f.category, "content": f.content,
                      "created_at": iso(f.created_at)} for f in feedback],
        "plans": [plan_out(p, {g.id: goal_progress(db, user.id, g) for g in p.goals}) for p in plans],
        "sessions": [mentor_session_out(s) for s in sessions],
    }


@router.post("/goals/{goal_id}/complete")
def complete_goal_endpoint(goal_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    goal = db.get(PlanGoal, goal_id)
    if not goal or goal.plan.student_id != user.id:
        raise HTTPException(404, "Goal not found")
    if goal.status == "completed":
        return {"ok": True}
    if goal.goal_type in ("mock_interview", "english_practice", "assessment"):
        progress_value = goal_progress(db, user.id, goal)
        if progress_value < goal.target_count:
            raise HTTPException(400, f"This goal is tracked automatically: {progress_value}/{goal.target_count} done so far")
    complete_goal(db, user.id, goal)
    db.commit()
    return {"ok": True}

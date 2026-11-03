"""Admin portal: users, platform configuration, analytics, monitoring."""
import csv
import io
import os
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from ..odm import func, or_, select
from ..odm import Session
from starlette.background import BackgroundTask

from ..config import get_settings
from ..database import get_db
from ..deps import client_ip, require_admin
from ..models import (
    AIUsageLog, Announcement, Assessment, AssessmentResult, AuditLog, Badge, BankQuestion, Challenge,
    ChallengeCompletion, EnglishSession, ErrorLog, EvaluationRubric, InterviewCategory, InterviewSession, Job,
    JobApplication, MentorAssignment, MentorProfile, PlacementDrive, PlatformSetting, PracticeExercise,
    RecruiterProfile, RewardRule, StudentProfile, User,
)
from ..schemas import (
    AdminUserCreate, AdminUserUpdate, AssignmentIn, BadgeIn, BankQuestionIn, CategoryIn, FlagReview,
    RewardRuleUpdate, RubricIn, SettingUpdate,
)
from ..security import hash_password
from ..serializers import drive_out, interview_out, iso, job_out, profile_out, result_out, user_out
from ..services.ai import ai_status
from ..services.common import DEFAULT_SETTINGS, SETTING_OPTIONS, audit, get_setting, notify, paginate
from ..services.insights import student_summary
from ..services.rewards import revoke_for_source

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --------------------------------------------------------------------------- analytics

def _daily_counts(db: Session, column, days: int = 30, *filters) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.scalars(select(column).where(column >= since, *filters)).all()
    c = Counter(r.date().isoformat() for r in rows if r)
    return c


@router.get("/dashboard")
def dashboard(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    role_counts = dict(db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all())
    status_counts = dict(db.execute(select(User.status, func.count(User.id)).group_by(User.status)).all())
    week = datetime.now(timezone.utc) - timedelta(days=7)
    active_students = db.scalar(select(func.count(User.id)).where(User.role == "student",
                                                                  User.last_active_at >= week)) or 0
    app_counts = dict(db.execute(select(JobApplication.status, func.count(JobApplication.id))
                                 .group_by(JobApplication.status)).all())
    days = [(datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat() for i in range(29, -1, -1)]
    interviews_daily = _daily_counts(db, InterviewSession.completed_at)
    english_daily = _daily_counts(db, EnglishSession.ended_at)
    signups_daily = _daily_counts(db, User.created_at)
    apps_daily = _daily_counts(db, JobApplication.created_at)
    avg_interview = db.scalar(select(func.avg(InterviewSession.overall_score)).where(
        InterviewSession.status == "completed", InterviewSession.flagged.is_(False)))
    ai_24h = dict(db.execute(select(AIUsageLog.status, func.count(AIUsageLog.id)).where(
        AIUsageLog.created_at >= datetime.now(timezone.utc) - timedelta(days=1)).group_by(AIUsageLog.status)).all())
    flagged = (db.scalar(select(func.count(InterviewSession.id)).where(InterviewSession.flagged.is_(True))) or 0) + \
              (db.scalar(select(func.count(AssessmentResult.id)).where(AssessmentResult.flagged.is_(True))) or 0)
    branch_scores = db.execute(select(StudentProfile.branch, func.avg(InterviewSession.overall_score))
                               .join(InterviewSession, InterviewSession.student_id == StudentProfile.user_id)
                               .where(InterviewSession.status == "completed", InterviewSession.overall_score.is_not(None))
                               .group_by(StudentProfile.branch)).all()
    return {
        "users": {"students": role_counts.get("student", 0), "recruiters": role_counts.get("recruiter", 0),
                  "mentors": role_counts.get("mentor", 0), "admins": role_counts.get("admin", 0),
                  "active_students_7d": active_students, "pending_approval": status_counts.get("pending", 0),
                  "suspended": status_counts.get("suspended", 0)},
        "activity": {
            "interviews_completed": db.scalar(select(func.count(InterviewSession.id)).where(InterviewSession.status == "completed")) or 0,
            "english_sessions": db.scalar(select(func.count(EnglishSession.id)).where(EnglishSession.status == "completed")) or 0,
            "english_minutes": round((db.scalar(select(func.sum(EnglishSession.active_seconds))) or 0) / 60),
            "assessments_taken": db.scalar(select(func.count(AssessmentResult.id)).where(AssessmentResult.submitted_at.is_not(None))) or 0,
            "average_interview_score": round(avg_interview, 1) if avg_interview is not None else None,
        },
        "placements": {"jobs_published": db.scalar(select(func.count(Job.id)).where(Job.status == "published")) or 0,
                       "jobs_total": db.scalar(select(func.count(Job.id))) or 0,
                       "applications": sum(app_counts.values()), "by_status": app_counts,
                       "selected": app_counts.get("selected", 0)},
        "timeline": [{"date": d, "interviews": interviews_daily.get(d, 0), "english": english_daily.get(d, 0),
                      "signups": signups_daily.get(d, 0), "applications": apps_daily.get(d, 0)} for d in days],
        "branch_scores": [{"branch": b or "Unspecified", "avg_score": round(s, 1)} for b, s in branch_scores],
        "ai": {**ai_status(db), "last_24h": ai_24h},
        "flagged_items": flagged,
        "readiness": _readiness_distribution(db),
        "popular_activities": _popular_activities(db),
    }


def _readiness_distribution(db: Session) -> dict:
    levels = {"ready": 0, "almost": 0, "not_ready": 0}
    scores = []
    for st in db.scalars(select(User).where(User.role == "student", User.status == "active")):
        r = student_summary(db, st)["readiness"]
        levels[r["level"]] += 1
        scores.append(r["score"])
    buckets = Counter(min(int(s // 20), 4) for s in scores)
    return {"levels": levels, "average": round(sum(scores) / len(scores), 1) if scores else None,
            "distribution": [{"range": f"{i * 20}-{i * 20 + 20}", "students": buckets.get(i, 0)} for i in range(5)]}


def _popular_activities(db: Session, days: int = 30) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = Counter()
    for (cat,) in db.execute(select(InterviewSession.category).where(InterviewSession.created_at >= since)):
        out[f"{cat} interview"] += 1
    out["English conversation"] += db.scalar(select(func.count(EnglishSession.id)).where(EnglishSession.created_at >= since)) or 0
    for (kind,) in db.execute(select(PracticeExercise.kind).where(PracticeExercise.created_at >= since,
                                                                   PracticeExercise.status == "completed")):
        out[f"{kind} drill"] += 1
    for (cat,) in db.execute(select(Assessment.category).join(AssessmentResult, AssessmentResult.assessment_id == Assessment.id)
                             .where(AssessmentResult.started_at >= since)):
        out[f"{cat} test"] += 1
    return [{"activity": k, "count": v} for k, v in out.most_common(10) if v]


@router.get("/reports/placements")
def placement_report(format: str = "json", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = []
    for st in db.scalars(select(User).where(User.role == "student").order_by(User.full_name)):
        s = student_summary(db, st)
        apps = db.scalars(select(JobApplication).where(JobApplication.student_id == st.id)).all()
        selected = [a.job.company_name for a in apps if a.status == "selected"]
        rows.append({"student_id": st.id, "name": st.full_name, "email": st.email,
                     "branch": s["student"]["branch"] or "", "graduation_year": s["student"]["graduation_year"] or "",
                     "cgpa": s["student"]["cgpa"] if s["student"]["cgpa"] is not None else "",
                     "interviews": s["interviews"]["completed"],
                     "interview_avg": s["interviews"]["average_score"] if s["interviews"]["average_score"] is not None else "",
                     "english_minutes": s["english"]["minutes"],
                     "assessment_avg": s["assessments"]["average_score"] if s["assessments"]["average_score"] is not None else "",
                     "points": s["rewards"]["points"], "readiness": s["readiness"]["score"],
                     "readiness_level": s["readiness"]["level"], "applications": len(apps),
                     "selected": "; ".join(selected), "trend": s["trend"]})
    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["student_id"])
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=placement_report.csv"})
    placed = sum(1 for r in rows if r["selected"])
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "students": len(rows), "placed": placed,
            "placement_rate": round(100 * placed / len(rows), 1) if rows else 0, "rows": rows}


# --------------------------------------------------------------------------- users

@router.get("/users")
def list_users(role: str | None = None, status: str | None = None, q: str | None = None, page: int = 1,
               page_size: int = 20, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if status:
        stmt = stmt.where(User.status == status)
    if q:
        stmt = stmt.where(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    items, meta = paginate(db, stmt.order_by(User.id.desc()), page, page_size)
    out = []
    for u in items:
        d = user_out(u)
        if u.role == "recruiter" and u.recruiter_profile:
            d["company_name"] = u.recruiter_profile.company_name
            d["company_verified"] = u.recruiter_profile.company_verified
            d["industry"] = u.recruiter_profile.industry
            d["job_count"] = db.scalar(select(func.count(Job.id)).where(Job.recruiter_id == u.id)) or 0
        if u.role == "student" and u.student_profile:
            d["branch"] = u.student_profile.branch
            d["mentors"] = [a.mentor.full_name for a in db.scalars(select(MentorAssignment).where(
                MentorAssignment.student_id == u.id, MentorAssignment.active.is_(True)))]
        if u.role == "mentor":
            d["assigned_count"] = db.scalar(select(func.count(MentorAssignment.id)).where(
                MentorAssignment.mentor_id == u.id, MentorAssignment.active.is_(True))) or 0
        out.append(d)
    return {"items": out, **meta}


@router.get("/users/{user_id}")
def get_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = profile_out(u)
    if u.role == "student":
        data["summary"] = student_summary(db, u)
    data["recent_activity"] = [{"action": a.action, "created_at": iso(a.created_at), "details": a.details}
                               for a in db.scalars(select(AuditLog).where(AuditLog.actor_id == u.id)
                                                   .order_by(AuditLog.id.desc()).limit(20))]
    return data


@router.post("/users", status_code=201)
def create_user(body: AdminUserCreate, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    u = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name,
             role=body.role, status="active")
    if body.role == "student":
        u.student_profile = StudentProfile(skills=[], projects=[], experience=[])
    elif body.role == "recruiter":
        if not body.company_name:
            raise HTTPException(400, "Company name is required for recruiters")
        u.recruiter_profile = RecruiterProfile(company_name=body.company_name)
    elif body.role == "mentor":
        u.mentor_profile = MentorProfile(department=body.department, expertise=[])
    db.add(u)
    db.flush()
    audit(db, admin.id, "user.create", "user", u.id, {"role": u.role, "email": u.email}, client_ip(request))
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: AdminUserUpdate, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if u.id == admin.id and (data.get("status", "active") != "active" or data.get("role", "admin") != "admin"):
        raise HTTPException(400, "You cannot suspend, deactivate or demote your own account")
    if "role" in data and data["role"] != u.role:
        new_role = data["role"]
        if new_role == "student" and not u.student_profile:
            u.student_profile = StudentProfile(skills=[], projects=[], experience=[])
        if new_role == "mentor" and not u.mentor_profile:
            u.mentor_profile = MentorProfile(expertise=[])
        if new_role == "recruiter" and not u.recruiter_profile:
            u.recruiter_profile = RecruiterProfile(company_name="(not set)")
    old_status = u.status
    for k, v in data.items():
        setattr(u, k, v)
    if "status" in data and data["status"] != old_status:
        if old_status == "pending" and data["status"] == "active":
            notify(db, u.id, "Account approved", "Your HireSense account has been approved. Welcome!", "info")
        else:
            notify(db, u.id, "Account status changed", f"Your account is now {data['status']}.", "info")
    audit(db, admin.id, "user.update", "user", u.id, data, client_ip(request))
    db.commit()
    return user_out(u)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Soft delete: deactivates the account so historical records stay consistent."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    u.status = "deactivated"
    audit(db, admin.id, "user.deactivate", "user", u.id, {"email": u.email}, client_ip(request))
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- mentor assignments

@router.get("/assignments")
def list_assignments(mentor_id: int | None = None, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(MentorAssignment).where(MentorAssignment.active.is_(True))
    if mentor_id:
        stmt = stmt.where(MentorAssignment.mentor_id == mentor_id)
    return [{"id": a.id, "mentor_id": a.mentor_id, "mentor_name": a.mentor.full_name, "student_id": a.student_id,
             "student_name": a.student.full_name, "student_email": a.student.email, "created_at": iso(a.created_at)}
            for a in db.scalars(stmt.order_by(MentorAssignment.id.desc()))]


@router.post("/assignments", status_code=201)
def assign(body: AssignmentIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    mentor = db.get(User, body.mentor_id)
    if not mentor or mentor.role != "mentor":
        raise HTTPException(400, "Selected user is not a mentor")
    created = 0
    for sid in set(body.student_ids):
        st = db.get(User, sid)
        if not st or st.role != "student":
            raise HTTPException(400, f"User {sid} is not a student")
        existing = db.scalar(select(MentorAssignment).where(MentorAssignment.mentor_id == mentor.id,
                                                            MentorAssignment.student_id == sid))
        if existing:
            if not existing.active:
                existing.active = True
                created += 1
            continue
        db.add(MentorAssignment(mentor_id=mentor.id, student_id=sid, assigned_by=admin.id))
        notify(db, sid, "Mentor assigned", f"{mentor.full_name} is now your placement mentor.", "info", "/student/mentoring")
        created += 1
    if created:
        notify(db, mentor.id, "New students assigned", f"{created} student(s) were assigned to you.", "info", "/mentor/students")
    audit(db, admin.id, "mentor.assign", "user", mentor.id, {"students": body.student_ids}, client_ip(request))
    db.commit()
    return {"assigned": created}


@router.delete("/assignments/{assignment_id}")
def unassign(assignment_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.get(MentorAssignment, assignment_id)
    if not a:
        raise HTTPException(404, "Assignment not found")
    a.active = False
    audit(db, admin.id, "mentor.unassign", "mentor_assignment", a.id,
          {"mentor_id": a.mentor_id, "student_id": a.student_id}, client_ip(request))
    db.commit()
    return {"ok": True}


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


# --------------------------------------------------------------------------- interview configuration

@router.get("/categories")
def categories(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(InterviewCategory).order_by(InterviewCategory.id)):
        out.append({"id": c.id, "code": c.code, "name": c.name, "description": c.description,
                    "default_question_count": c.default_question_count, "active": c.active,
                    "question_count": db.scalar(select(func.count(BankQuestion.id)).where(BankQuestion.category_id == c.id)) or 0})
    return out


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(InterviewCategory.id).where(InterviewCategory.code == body.code)):
        raise HTTPException(409, "Category code already exists")
    c = InterviewCategory(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, admin.id, "category.create", "interview_category", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"id": c.id}


@router.put("/categories/{category_id}")
def update_category(category_id: int, body: CategoryIn, request: Request, admin: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    c = db.get(InterviewCategory, category_id)
    if not c:
        raise HTTPException(404, "Category not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, admin.id, "category.update", "interview_category", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/questions")
def list_questions(category_id: int | None = None, q: str | None = None, page: int = 1, page_size: int = 20,
                   admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(BankQuestion)
    if category_id:
        stmt = stmt.where(BankQuestion.category_id == category_id)
    if q:
        stmt = stmt.where(BankQuestion.question.ilike(f"%{q}%"))
    items, meta = paginate(db, stmt.order_by(BankQuestion.id.desc()), page, page_size)
    return {"items": [{"id": b.id, "category_id": b.category_id, "category": b.category.name, "question": b.question,
                       "difficulty": b.difficulty, "role_tag": b.role_tag, "active": b.active} for b in items], **meta}


@router.post("/questions", status_code=201)
def create_question(body: BankQuestionIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(InterviewCategory, body.category_id):
        raise HTTPException(400, "Category not found")
    b = BankQuestion(**body.model_dump(), created_by=admin.id)
    db.add(b)
    db.flush()
    audit(db, admin.id, "question.create", "question", b.id, {}, client_ip(request))
    db.commit()
    return {"id": b.id}


@router.put("/questions/{question_id}")
def update_question(question_id: int, body: BankQuestionIn, request: Request, admin: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    b = db.get(BankQuestion, question_id)
    if not b:
        raise HTTPException(404, "Question not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, admin.id, "question.update", "question", b.id, {}, client_ip(request))
    db.commit()
    return {"ok": True}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    b = db.get(BankQuestion, question_id)
    if not b:
        raise HTTPException(404, "Question not found")
    db.delete(b)
    audit(db, admin.id, "question.delete", "question", question_id, {}, client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/rubrics")
def rubrics(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": r.id, "name": r.name, "applies_to": r.applies_to, "criteria": r.criteria, "active": r.active}
            for r in db.scalars(select(EvaluationRubric).order_by(EvaluationRubric.id))]


def _validate_rubric(body: RubricIn) -> None:
    total = round(sum(c.weight for c in body.criteria), 3)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(400, f"Criterion weights must add up to 1.0 (currently {total})")


@router.post("/rubrics", status_code=201)
def create_rubric(body: RubricIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _validate_rubric(body)
    r = EvaluationRubric(name=body.name, applies_to=body.applies_to,
                         criteria=[c.model_dump() for c in body.criteria], active=body.active)
    db.add(r)
    db.flush()
    audit(db, admin.id, "rubric.create", "rubric", r.id, {"name": r.name}, client_ip(request))
    db.commit()
    return {"id": r.id}


@router.put("/rubrics/{rubric_id}")
def update_rubric(rubric_id: int, body: RubricIn, request: Request, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    _validate_rubric(body)
    r = db.get(EvaluationRubric, rubric_id)
    if not r:
        raise HTTPException(404, "Rubric not found")
    r.name, r.applies_to, r.active = body.name, body.applies_to, body.active
    r.criteria = [c.model_dump() for c in body.criteria]
    audit(db, admin.id, "rubric.update", "rubric", r.id, {"name": r.name}, client_ip(request))
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- rewards configuration

@router.get("/badges")
def badges(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..models import StudentBadge
    out = []
    for b in db.scalars(select(Badge).order_by(Badge.id)):
        out.append({"id": b.id, "code": b.code, "name": b.name, "description": b.description, "icon": b.icon,
                    "criteria_type": b.criteria_type, "threshold": b.threshold, "points": b.points, "active": b.active,
                    "awarded": db.scalar(select(func.count(StudentBadge.id)).where(StudentBadge.badge_id == b.id)) or 0})
    return out


@router.post("/badges", status_code=201)
def create_badge(body: BadgeIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Badge.id).where(Badge.code == body.code)):
        raise HTTPException(409, "Badge code already exists")
    b = Badge(**body.model_dump())
    db.add(b)
    db.flush()
    audit(db, admin.id, "badge.create", "badge", b.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"id": b.id}


@router.put("/badges/{badge_id}")
def update_badge(badge_id: int, body: BadgeIn, request: Request, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    b = db.get(Badge, badge_id)
    if not b:
        raise HTTPException(404, "Badge not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, admin.id, "badge.update", "badge", b.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/reward-rules")
def reward_rules(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": r.id, "activity_type": r.activity_type, "description": r.description, "points": r.points,
             "daily_cap": r.daily_cap, "requirements": r.requirements, "active": r.active}
            for r in db.scalars(select(RewardRule).order_by(RewardRule.id))]


@router.patch("/reward-rules/{rule_id}")
def update_reward_rule(rule_id: int, body: RewardRuleUpdate, request: Request, admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    r = db.get(RewardRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    data = body.model_dump(exclude_unset=True)
    if "requirements" in data:
        for k, v in (data["requirements"] or {}).items():
            if not isinstance(v, (int, float)) or v < 0:
                raise HTTPException(400, f"Requirement '{k}' must be a non-negative number")
    for k, v in data.items():
        setattr(r, k, v)
    audit(db, admin.id, "reward_rule.update", "reward_rule", r.id, data, client_ip(request))
    db.commit()
    return {"ok": True}


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
    from ..models import InterviewAnswer
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


# --------------------------------------------------------------------------- student overview

@router.get("/students")
def students_overview(q: str | None = None, branch: str | None = None, readiness: str | None = None,
                      page: int = 1, page_size: int = 25, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    stmt = select(User).outerjoin(StudentProfile).where(User.role == "student")
    if q:
        stmt = stmt.where(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if branch:
        stmt = stmt.where(StudentProfile.branch.ilike(f"%{branch}%"))
    rows = []
    for st in db.scalars(stmt.order_by(User.full_name)):
        s = student_summary(db, st)
        if readiness and s["readiness"]["level"] != readiness:
            continue
        rows.append({"id": st.id, "full_name": st.full_name, "email": st.email, "status": st.status,
                     "branch": s["student"]["branch"], "graduation_year": s["student"]["graduation_year"],
                     "readiness": s["readiness"]["score"], "readiness_level": s["readiness"]["level"],
                     "trend": s["trend"], "interviews": s["interviews"]["completed"],
                     "interview_avg": s["interviews"]["average_score"], "assessments": s["assessments"]["taken"],
                     "assessment_avg": s["assessments"]["average_score"], "english_minutes": s["english"]["minutes"],
                     "points": s["rewards"]["points"], "badges": s["rewards"]["badges"],
                     "last_active_at": s["student"]["last_active_at"]})
    total = len(rows)
    start = (max(page, 1) - 1) * page_size
    return {"items": rows[start:start + page_size], "total": total, "page": page, "page_size": page_size,
            "pages": max((total + page_size - 1) // page_size, 1)}


# --------------------------------------------------------------------------- recruiter verification

class VerifyIn(BaseModel):
    verified: bool


@router.post("/recruiters/{user_id}/verify")
def verify_recruiter(user_id: int, body: VerifyIn, request: Request, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.role != "recruiter" or not u.recruiter_profile:
        raise HTTPException(404, "Recruiter not found")
    u.recruiter_profile.company_verified = body.verified
    if body.verified:
        notify(db, u.id, "Company verified ✔", f"{u.recruiter_profile.company_name} is now shown as a verified company.", "info")
    audit(db, admin.id, "recruiter.verify", "user", u.id, {"verified": body.verified}, client_ip(request))
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- challenges

class ChallengeIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=1000)
    metric: Literal["english_minutes", "english_sessions", "speaking_exercises", "pronunciation_drills",
                    "interviews_completed", "assessments_passed"]
    target: float = Field(gt=0, le=10000)
    period: Literal["daily", "weekly"] = "daily"
    points: int = Field(default=10, ge=0, le=10000)
    active: bool = True


@router.get("/challenges")
def list_challenges(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(Challenge).order_by(Challenge.id)):
        completions = db.scalar(select(func.count(ChallengeCompletion.id)).where(ChallengeCompletion.challenge_id == c.id)) or 0
        out.append({"id": c.id, "title": c.title, "description": c.description, "metric": c.metric, "target": c.target,
                    "period": c.period, "points": c.points, "active": c.active, "completions": completions})
    return out


@router.post("/challenges", status_code=201)
def create_challenge(body: ChallengeIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = Challenge(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, admin.id, "challenge.create", "challenge", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"id": c.id}


@router.put("/challenges/{challenge_id}")
def update_challenge(challenge_id: int, body: ChallengeIn, request: Request, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    c = db.get(Challenge, challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, admin.id, "challenge.update", "challenge", c.id, body.model_dump(), client_ip(request))
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


# --------------------------------------------------------------------------- AI report monitoring

@router.get("/ai-reports")
def ai_reports(kind: str = "interview", page: int = 1, page_size: int = 20, admin: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    """Recent AI-generated feedback for quality review."""
    if kind == "english":
        stmt = select(EnglishSession).where(EnglishSession.evaluation_status == "completed").order_by(EnglishSession.id.desc())
        items, meta = paginate(db, stmt, page, page_size)
        return {"items": [{"id": e.id, "student_name": db.get(User, e.student_id).full_name, "title": e.topic,
                           "score": e.overall_score, "summary": (e.feedback or {}).get("summary"),
                           "date": iso(e.ended_at)} for e in items], **meta}
    stmt = select(InterviewSession).where(InterviewSession.report_status.in_(("completed", "partial"))) \
        .order_by(InterviewSession.id.desc())
    items, meta = paginate(db, stmt, page, page_size)
    return {"items": [{"id": s.id, "student_name": db.get(User, s.student_id).full_name,
                       "title": f"{s.job_role} ({s.category}, {s.difficulty})", "score": s.overall_score,
                       "summary": (s.report or {}).get("summary"), "date": iso(s.completed_at)} for s in items], **meta}


# --------------------------------------------------------------------------- backup

@router.get("/backup")
def backup(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Every MongoDB collection as MongoDB Extended JSON (one file per collection) in a zip. Restore one with
    `mongoimport --db hiresense --collection <name> --file <name>.json --jsonArray`. Uploaded files are not
    included: copy backend/uploads separately."""
    from bson import json_util

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    mongo = db.database
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(mongo.list_collection_names()):
            zf.writestr(f"{name}.json", json_util.dumps(list(mongo[name].find()), indent=1))
    audit(db, admin.id, "system.backup", None, None, {}, client_ip(request))
    db.commit()
    name = f"hiresense_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    return FileResponse(tmp.name, filename=name, media_type="application/zip",
                        background=BackgroundTask(os.unlink, tmp.name))

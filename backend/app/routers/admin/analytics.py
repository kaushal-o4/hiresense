"""Admin portal: dashboard, placement report, student overview, AI report monitoring, backup."""
import csv
import io
import os
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse

from ...odm import func, or_, select
from ...odm import Session
from starlette.background import BackgroundTask
from ...database import get_db
from ...deps import client_ip, require_admin
from ...models import (
    AIUsageLog, Assessment, AssessmentResult, EnglishSession, InterviewSession, Job, JobApplication,
    PracticeExercise, StudentProfile, User,
)
from ...serializers import iso
from ...services.ai import ai_status
from ...services.common import audit, paginate
from ...services.insights import student_summary

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

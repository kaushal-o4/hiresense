"""Small shared helpers: audit logging, notifications, pagination, platform settings."""
from typing import Any

from ..odm import func, select
from ..odm import Session

from ..models import AuditLog, Notification, PlatformSetting

DEFAULT_SETTINGS: dict[str, tuple[Any, str]] = {
    "student_registration_open": (True, "Allow new students to register"),
    "recruiter_registration_open": (True, "Allow new recruiters to register"),
    "recruiter_requires_approval": (True, "New recruiter accounts must be approved by an admin"),
    "max_interview_questions": (10, "Maximum questions a student may request in one mock interview"),
    "ai_features_enabled": (True, "Master switch for AI features"),
    "struggling_score_threshold": (50, "Students averaging below this interview score are marked as struggling"),
    "readiness_threshold": (70, "Placement readiness score (0-100) at which a student counts as 'placement ready'"),
    "inactive_days_alert": (7, "Alert mentors when an assigned student has not practised for this many days"),
    "default_interview_difficulty": ("medium", "Default difficulty for new mock interviews"),
    "evaluation_strictness": ("standard", "How strictly the AI scores interview and coding answers"),
    "resume_question_count": (8, "Number of personalised interview questions generated from a resume"),
    "monitoring_enabled": (True, "Offer disclosed, opt-in camera/browser integrity monitoring in live interviews"),
    # On by default (product decision 2026-10-11); admins can switch it off for practice-only use.
    "monitoring_camera_required": (True, "Live interviews require the camera with face visibility and multiple-face "
                                         "checks (students who cannot or will not enable it are told so instead of "
                                         "starting)"),
    "monitoring_retention_days": (90, "Days integrity events are kept before automatic deletion"),
}

# Allowed values for text settings.
SETTING_OPTIONS: dict[str, list[str]] = {
    "default_interview_difficulty": ["easy", "medium", "hard"],
    "evaluation_strictness": ["lenient", "standard", "strict"],
}


def audit(db: Session, actor_id: int | None, action: str, entity_type: str | None = None,
          entity_id: int | None = None, details: dict | None = None, ip: str | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type,
                    entity_id=entity_id, details=details or {}, ip_address=ip))


def notify(db: Session, user_id: int, title: str, message: str, kind: str = "info", link: str | None = None) -> None:
    """Queue an in-app notification. Open browser tabs of that user are told once the caller commits."""
    db.add(Notification(user_id=user_id, title=title, message=message, kind=kind, link=link))
    signal_notifications(db, user_id, "notification")


def signal_notifications(db: Session, user_id: int, kind: str = "sync") -> None:
    """After the next commit, tell the user's open notification streams to re-fetch (services/live_events.py)."""
    from . import live_events

    hook = getattr(db, "after_commit", None)
    if hook:
        hook(lambda: live_events.publish(user_id, {"type": kind}))


def paginate(db: Session, stmt, page: int, page_size: int):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return items, {"total": total, "page": page, "page_size": page_size,
                   "pages": max((total + page_size - 1) // page_size, 1)}


def get_setting(db: Session, key: str):
    row = db.get(PlatformSetting, key)
    if row is not None:
        return row.value
    return DEFAULT_SETTINGS.get(key, (None, ""))[0]


def normalize_skills(skills: list[str] | None) -> list[str]:
    seen, out = set(), []
    for s in skills or []:
        s = " ".join(str(s).split()).strip()
        if s and s.lower() not in seen and len(s) <= 100:
            seen.add(s.lower())
            out.append(s)
    return out[:100]

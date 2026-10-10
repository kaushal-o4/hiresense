"""Endpoints shared by every role: profile and notifications."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_ip, get_current_user
from ..models import MentorProfile, Notification, RecruiterProfile, StudentProfile, User
from ..schemas import AdminProfileUpdate, MentorProfileUpdate, RecruiterProfileUpdate, StudentProfileUpdate
from ..serializers import notification_out, profile_out
from ..services.common import audit, normalize_skills, paginate

router = APIRouter(prefix="/api", tags=["common"])


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return profile_out(user)


@router.put("/profile")
def update_profile(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    schema = {"student": StudentProfileUpdate, "recruiter": RecruiterProfileUpdate,
              "mentor": MentorProfileUpdate, "admin": AdminProfileUpdate}[user.role]
    try:
        body = schema.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_context=False))
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"]:
        user.full_name = data.pop("full_name").strip()
    else:
        data.pop("full_name", None)
    if user.role == "student":
        prof = user.student_profile or StudentProfile(user_id=user.id, skills=[], projects=[], experience=[])
        if "skills" in data:
            data["skills"] = normalize_skills(data["skills"])
        for k, v in data.items():
            setattr(prof, k, v)
        user.student_profile = prof
    elif user.role == "recruiter":
        prof = user.recruiter_profile or RecruiterProfile(user_id=user.id, company_name=data.get("company_name") or "")
        if data.get("company_name") and data["company_name"] != prof.company_name:
            prof.company_verified = False  # a renamed company must be verified again
        for k, v in data.items():
            setattr(prof, k, v)
        user.recruiter_profile = prof
    elif user.role == "mentor":
        prof = user.mentor_profile or MentorProfile(user_id=user.id, expertise=[])
        if "expertise" in data:
            data["expertise"] = normalize_skills(data["expertise"])
        for k, v in data.items():
            setattr(prof, k, v)
        user.mentor_profile = prof
    db.commit()
    return profile_out(user)


SPEECH_LANGS = ("en-IN", "en-US", "en-GB", "en-AU")


class PreferencesIn(BaseModel):
    speech_lang: Literal["en-IN", "en-US", "en-GB", "en-AU"] | None = None
    subtitles: bool | None = None
    speech_rate: float | None = Field(default=None, ge=0.5, le=1.5)
    # Students only: consent to appear in the recruiter student database.
    share_with_recruiters: bool | None = None


def _prefs(user: User) -> dict:
    p = {"speech_lang": "en-IN", "subtitles": True, "speech_rate": 1.0, **(user.preferences or {})}
    if user.role == "student" and user.student_profile:
        p["share_with_recruiters"] = user.student_profile.share_with_recruiters
    return p


@router.get("/settings")
def get_preferences(user: User = Depends(get_current_user)):
    return _prefs(user)


@router.put("/settings")
def update_preferences(body: PreferencesIn, request: Request, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    consent = data.pop("share_with_recruiters", None)
    if consent is not None:
        if user.role != "student" or not user.student_profile:
            raise HTTPException(400, "Only students can change profile sharing")
        user.student_profile.share_with_recruiters = consent
        audit(db, user.id, "consent.share_with_recruiters", "user", user.id, {"value": consent}, client_ip(request))
    user.preferences = {**(user.preferences or {}), **{k: v for k, v in data.items() if v is not None}}
    db.commit()
    return _prefs(user)


@router.get("/notifications")
def list_notifications(page: int = 1, page_size: int = 20, unread_only: bool = False,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    items, meta = paginate(db, stmt.order_by(Notification.id.desc()), page, page_size)
    unread = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.read.is_(False))) or 0
    return {"items": [notification_out(n) for n in items], "unread": unread, **meta}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))
               .values(read=True))
    db.commit()
    return {"ok": True}


@router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    db.delete(n)
    db.commit()
    return {"ok": True}

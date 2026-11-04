"""Endpoints shared by every role: profile and notifications."""
import asyncio
import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from ..odm import func, select, update
from ..odm import Session

from ..config import get_settings
from ..database import SessionLocal, get_db
from ..deps import _token_from_request, client_ip, get_current_user
from ..models import MentorProfile, Notification, RecruiterProfile, StudentProfile, User
from ..schemas import AdminProfileUpdate, MentorProfileUpdate, RecruiterProfileUpdate, StudentProfileUpdate
from ..serializers import notification_out, profile_out
from ..security import decode_access_token
from ..services import live_events
from ..services.common import audit, normalize_skills, paginate, signal_notifications

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
    signal_notifications(db, user.id)  # other open tabs update their badge
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))
               .values(read=True))
    signal_notifications(db, user.id)
    db.commit()
    return {"ok": True}


@router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    db.delete(n)
    signal_notifications(db, user.id)
    db.commit()
    return {"ok": True}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/notifications/stream")
async def notification_stream(request: Request):
    """Server-Sent Events: `ready` once, then `notification` (a new one arrived) or `sync` (read/deleted elsewhere)
    whenever the signed-in user's notifications change. Events carry no content; the client re-fetches
    GET /api/notifications. Heartbeat comments keep proxies from closing the connection, and the stream ends after
    NOTIFICATIONS_STREAM_MAX_SECONDS (and when the login token expires) so the browser reconnects and is
    re-authenticated. In-process only: see services/live_events.py for the multi-worker limit."""
    db = SessionLocal()  # short-lived: the stream must not hold a database session open for minutes
    try:
        user = get_current_user(request, db)  # 401/403 exactly like every other endpoint
        user_id = user.id
    finally:
        db.close()
    exp = (decode_access_token(_token_from_request(request) or "") or {}).get("exp")
    cfg = get_settings()
    if live_events.stream_count(user_id) >= live_events.MAX_STREAMS_PER_USER:
        raise HTTPException(429, "Too many open notification streams. Close some tabs.")

    async def events():
        deadline = time.monotonic() + cfg.notifications_stream_max_seconds
        if exp:
            deadline = min(deadline, time.monotonic() + max(0.0, exp - time.time()))
        try:
            with live_events.subscribe(user_id) as q:
                yield "retry: 3000\n" + _sse("ready", {"heartbeat_seconds": cfg.notifications_heartbeat_seconds})
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        yield _sse("bye", {"reason": "reconnect"})
                        return
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=min(cfg.notifications_heartbeat_seconds, left))
                        yield _sse(ev.get("type", "sync"), {})
                    except asyncio.TimeoutError:
                        if await request.is_disconnected():
                            return
                        yield ": ping\n\n"
        except live_events.TooManyStreams:
            yield _sse("bye", {"reason": "too_many_streams"})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})

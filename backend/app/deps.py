from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import MentorAssignment, User
from .security import COOKIE_NAME, decode_access_token


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _token_from_request(request)
    payload = decode_access_token(token) if token else None
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Account is {user.status}")
    now = datetime.now(timezone.utc)
    last = user.last_active_at
    if last is None or (now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))) > timedelta(minutes=5):
        user.last_active_at = now
        db.commit()
    request.state.user_id = user.id
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to access this resource")
        return user
    return checker


require_student = require_roles("student")
require_recruiter = require_roles("recruiter")
require_mentor = require_roles("mentor")
require_admin = require_roles("admin")


def mentor_can_access(db: Session, mentor: User, student_id: int) -> bool:
    if "view_all_students" in (mentor.permissions or []):
        return True
    return db.scalar(
        select(MentorAssignment.id).where(
            MentorAssignment.mentor_id == mentor.id,
            MentorAssignment.student_id == student_id,
            MentorAssignment.active.is_(True),
        )
    ) is not None


def ensure_mentor_access(db: Session, mentor: User, student_id: int) -> None:
    if not mentor_can_access(db, mentor, student_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This student is not assigned to you")


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None

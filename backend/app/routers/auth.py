"""Authentication routes: register, login, logout and password reset.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from ..odm import delete as sa_delete
from ..odm import select
from ..odm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import client_ip, get_current_user
from ..models import RecruiterProfile, Resume, StudentProfile, User
from ..schemas import ChangePassword, LoginIn, RecruiterRegister, StudentRegister, _strong_password
from ..security import (
    COOKIE_NAME, create_access_token, create_reset_token, hash_password, read_reset_token, reset_token_matches,
    verify_password,
)
from ..serializers import profile_out
from ..services import mailer
from ..services.ai import ai_status
from ..services.common import audit, get_setting, notify

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("hiresense.auth")

# Simple in-memory brute-force protection: email -> [failed attempt timestamps]
_failed: dict[str, list[float]] = {}
MAX_FAILED, WINDOW_SECONDS = 8, 15 * 60


def _set_cookie(response: Response, token: str) -> None:
    """Store the session JWT in the httpOnly, SameSite=Lax cookie (JavaScript cannot read it)."""
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=settings.cookie_secure,
                        max_age=settings.access_token_minutes * 60, path="/")


def _email_taken(db: Session, email: str) -> bool:
    """True if an account with this email exists (emails are stored lower-case)."""
    return db.scalar(select(User.id).where(User.email == email.lower())) is not None


@router.post("/register/student", status_code=201)
def register_student(body: StudentRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create an active student account with an empty profile, then sign the student in (sets the
    cookie). 403 if student registration is closed in admin settings, 409 if the email is taken.
    """
    if not get_setting(db, "student_registration_open"):
        raise HTTPException(403, "Student registration is currently closed")
    if _email_taken(db, body.email):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name.strip(),
                role="student", status="active")
    user.student_profile = StudentProfile(college=body.college, branch=body.branch,
                                          graduation_year=body.graduation_year, skills=[], projects=[], experience=[],
                                          share_with_recruiters=body.share_with_recruiters)
    db.add(user)
    db.flush()
    audit(db, user.id, "user.register", "user", user.id, {"role": "student"}, client_ip(request))
    notify(db, user.id, "Welcome to HireSense!", "Upload your resume to get personalised interview practice.",
           "info", "/student/resume")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    _set_cookie(response, create_access_token(user.id, user.role))
    return {"user": profile_out(user)}


@router.post("/register/recruiter", status_code=201)
def register_recruiter(body: RecruiterRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create a recruiter account. If admin approval is required (setting `recruiter_requires_approval`)
    the account stays "pending", admins are notified and the recruiter is NOT signed in; otherwise signs them in.
    """
    if not get_setting(db, "recruiter_registration_open"):
        raise HTTPException(403, "Recruiter registration is currently closed")
    if _email_taken(db, body.email):
        raise HTTPException(409, "An account with this email already exists")
    needs_approval = bool(get_setting(db, "recruiter_requires_approval"))
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name.strip(),
                role="recruiter", status="pending" if needs_approval else "active")
    user.recruiter_profile = RecruiterProfile(company_name=body.company_name.strip(), designation=body.designation,
                                              company_website=body.company_website, industry=body.industry)
    db.add(user)
    db.flush()
    audit(db, user.id, "user.register", "user", user.id, {"role": "recruiter"}, client_ip(request))
    if needs_approval:
        for admin_id in db.scalars(select(User.id).where(User.role == "admin", User.status == "active")):
            notify(db, admin_id, "Recruiter awaiting approval",
                   f"{user.full_name} ({body.company_name}) registered as a recruiter.", "approval", "/admin/users?status=pending")
        db.commit()
        return {"user": profile_out(user), "pending_approval": True,
                "message": "Registration received. An administrator must approve your account before you can sign in."}
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    _set_cookie(response, create_access_token(user.id, user.role))
    return {"user": profile_out(user), "pending_approval": False}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Check email and password and set the session cookie.

    Brute-force protection: after MAX_FAILED wrong passwords for one email within WINDOW_SECONDS, further attempts
    get 429 (kept in memory, so it resets when the server restarts). Pending, suspended and deactivated accounts get
    403 with a reason. Returns the user's profile; the token is also returned for API clients.
    """
    email = body.email.lower()
    now = datetime.now(timezone.utc).timestamp()
    attempts = [t for t in _failed.get(email, []) if now - t < WINDOW_SECONDS]
    if len(attempts) >= MAX_FAILED:
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        attempts.append(now)
        _failed[email] = attempts
        if user:
            audit(db, user.id, "auth.login_failed", "user", user.id, {}, client_ip(request))
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    _failed.pop(email, None)
    if user.status == "pending":
        raise HTTPException(403, "Your account is awaiting administrator approval")
    if user.status in ("suspended", "deactivated"):
        raise HTTPException(403, f"Your account has been {user.status}. Contact the placement office.")
    user.last_login_at = datetime.now(timezone.utc)
    user.last_active_at = user.last_login_at
    audit(db, user.id, "auth.login", "user", user.id, {}, client_ip(request))
    db.commit()
    token = create_access_token(user.id, user.role)
    _set_cookie(response, token)
    return {"user": profile_out(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie. (JWTs are stateless, so there is no server-side session to delete.)"""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current user's profile plus AI availability. The frontend calls this on load (auth.jsx) to restore the session."""
    return {"user": profile_out(user), "ai": ai_status(db)}


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=2000)
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_strong_password)


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(max_length=20)


# per-email limit on reset requests (in memory, like the login limiter)
_reset_requests: dict[str, list[float]] = {}
MAX_RESET_REQUESTS = 3
GENERIC_RESET_REPLY = {"ok": True, "message": "If an account exists for that email, a reset link has been sent. "
                       "If email is not set up on this server, ask the placement office for the link."}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Start a password reset. Always returns the same reply, so it can't be used to find out who has an account."""
    email = body.email.lower()
    now = datetime.now(timezone.utc).timestamp()
    recent = [t for t in _reset_requests.get(email, []) if now - t < WINDOW_SECONDS]
    if len(recent) >= MAX_RESET_REQUESTS:
        return GENERIC_RESET_REPLY  # silently ignore floods; same reply as always
    _reset_requests[email] = recent + [now]
    user = db.scalar(select(User).where(User.email == email))
    if not user or user.status in ("deactivated", "pending"):
        return GENERIC_RESET_REPLY
    settings = get_settings()
    link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={create_reset_token(user.id, user.password_hash)}"
    sent = mailer.send(user.email, "Reset your HireSense password",
                       f"Hello {user.full_name},\n\nSomeone (hopefully you) asked to reset your HireSense password. "
                       f"Open this link within {settings.password_reset_minutes} minutes to choose a new one:\n\n{link}\n\n"
                       "If you didn't ask for this, ignore this email - your password stays the same.")
    if not sent:  # email is off: the link goes to the server log so the placement office can pass it on
        logger.warning("Password reset requested for %s (email disabled). Reset link, valid %d min: %s",
                       user.email, settings.password_reset_minutes, link)
    audit(db, user.id, "auth.password_reset_requested", "user", user.id, {"emailed": sent}, client_ip(request))
    db.commit()
    return GENERIC_RESET_REPLY


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Set a new password from a reset-link token. The token must be valid, unexpired and issued for the
    current password; changing the password makes this and any older link stop working. Clears the login lockout.
    """
    payload = read_reset_token(body.token)
    user = db.get(User, int(payload["sub"])) if payload and str(payload.get("sub", "")).isdigit() else None
    if not user or not reset_token_matches(payload, user.password_hash) or user.status in ("deactivated", "pending"):
        raise HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    user.password_hash = hash_password(body.new_password)  # also invalidates this and any older reset link
    _failed.pop(user.email, None)
    audit(db, user.id, "auth.password_reset", "user", user.id, {}, client_ip(request))
    notify(db, user.id, "Your password was changed",
           "Your password was reset using a reset link. If this wasn't you, contact the placement office.", "warning")
    db.commit()
    return {"ok": True, "message": "Password updated. You can now sign in with your new password."}


@router.delete("/me")
def delete_my_account(body: DeleteAccountIn, request: Request, response: Response,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently delete a student's own account and personal data (resumes and their files, interviews, English
    practice, applications, rewards, notifications). Audit entries keep only the anonymous user id."""
    if user.role != "student":
        raise HTTPException(403, "Only student accounts can be deleted here. Contact an administrator.")
    if body.confirm != "DELETE":
        raise HTTPException(400, 'Type DELETE to confirm')
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Password is incorrect")
    files = [Path(p) for p in db.scalars(select(Resume.stored_path).where(Resume.student_id == user.id)) if p]
    uid = user.id
    audit(db, None, "user.self_delete", "user", uid, {"role": "student"}, client_ip(request))
    db.flush()
    db.expunge(user)
    db.execute(sa_delete(User).where(User.id == uid))  # the database cascades to every table that references it
    db.commit()
    for f in files:
        f.unlink(missing_ok=True)
    folder = Path(get_settings().upload_dir) / str(uid)
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True, "message": "Your account and data have been deleted."}


@router.post("/change-password")
def change_password(body: ChangePassword, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Change the signed-in user's password after checking the current one."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit(db, user.id, "auth.password_changed", "user", user.id, {}, client_ip(request))
    db.commit()
    return {"ok": True, "message": "Password updated"}

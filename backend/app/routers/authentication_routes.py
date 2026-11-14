# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/routers/authentication_routes.py
#
# FILE PURPOSE:
# All account-access endpoints: student and recruiter registration, login, logout, the current user,
# password reset and change, AI data consent and account deletion.
#
# MAIN RESPONSIBILITY:
# Registration and login (Stage 1 of the workflow).
#
# WHAT THIS FILE DOES:
# 1. Registers students (signed in immediately) and recruiters (may wait for admin approval).
# 2. Logs users in: checks the Argon2 password hash and sets the JWT in an httpOnly cookie.
# 3. Blocks brute force: too many wrong passwords for one email locks login for a while
#    (rate_limiter).
# 4. Returns the signed-in user on page load (GET /api/auth/me) so the session survives a refresh.
# 5. Handles forgot/reset password with signed one-time tokens sent by email (or logged if email is
#    off).
# 6. Lets a student delete their own account and data; records consent to hosted-AI processing.
#
# HOW THIS FILE WORKS:
# Each function is a FastAPI route under the prefix /api/auth. Input is validated by schemas such as
# StudentRegister and LoginIn. Passwords and tokens are handled by password_and_token_security.py, and
# important actions are written to the audit log.
#
# IMPORTANT FUNCTIONS:
#    - register_student()
#        POST /api/auth/register/student - create a student account and sign in.
#    - register_recruiter()
#        POST /api/auth/register/recruiter - create a recruiter (pending if approval is
#        required).
#    - login()
#        POST /api/auth/login - verify email/password, apply lockout, set the session cookie.
#    - me()
#        GET /api/auth/me - current user + AI availability (used by AuthContext.jsx on load).
#    - forgot_password()
#        POST /api/auth/forgot-password - email a reset link (same reply whether or not the
#        account exists).
#    - reset_password()
#        POST /api/auth/reset-password - set a new password from a valid token.
#    - delete_my_account()
#        DELETE /api/auth/me - remove a student's own data permanently.
#    - logout()
#        Clear the session cookie.
#    - privacy_info()
#        Public: which AI provider processes data on this server, and the consent notice when
#        it is hosted.
#    - set_ai_consent()
#        Give (accept=true) or withdraw (accept=false) consent to the hosted-AI data notice.
#    - change_password()
#        Change the signed-in user's password after checking the current one.
#    Other helper functions: _login_key, _set_cookie, _clear_cookie, _email_taken
#
# IMPORTANT CLASSES:
#    - AIConsentIn
#    - ForgotPasswordIn
#    - ResetPasswordIn
#    - DeleteAccountIn
#
# API ENDPOINTS DEFINED HERE:
#    - POST /api/auth/register/student
#        register_student() - public - Create an active student account with an empty profile,
#        then sign the student in (sets the cookie). 403 if student registration is closed in
#        admin settings, 409 if the email is taken.
#    - POST /api/auth/register/recruiter
#        register_recruiter() - public - Create a recruiter account.
#    - POST /api/auth/login
#        login() - public - Check email and password and set the session cookie.
#    - POST /api/auth/logout
#        logout() - public - Clear the session cookie.
#    - GET /api/auth/me
#        me() - any signed-in user - Current user's profile plus AI availability.
#    - GET /api/auth/privacy
#        privacy_info() - public - Public: which AI provider processes data on this server, and
#        the consent notice when it is hosted.
#    - POST /api/auth/ai-consent
#        set_ai_consent() - any signed-in user - Give (accept=true) or withdraw (accept=false)
#        consent to the hosted-AI data notice.
#    - POST /api/auth/forgot-password
#        forgot_password() - public - Start a password reset.
#    - POST /api/auth/reset-password
#        reset_password() - public - Set a new password from a reset-link token.
#    - DELETE /api/auth/me
#        delete_my_account() - any signed-in user - Permanently delete a student's own account
#        and personal data (resumes and their files, interviews, English practice,
#        applications, rewards, notifications).
#    - POST /api/auth/change-password
#        change_password() - any signed-in user - Change the signed-in user's password after
#        checking the current one.
#
# IMPORTANT VARIABLES / SETTINGS:
#    MAX_RESET_REQUESTS, GENERIC_RESET_REPLY
#
# INPUT:
# JSON bodies (email, password, name, role details), the session cookie.
#
# OUTPUT:
# User JSON, the hs_session cookie, success/error messages.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/api_response_serializers.py, app/application_configuration.py,
#    app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
#    app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
#    app/request_validation_schemas.py, app/services/interview/ai_interview_service.py,
#    app/services/platform_support/audit_and_notification_helpers.py,
#    app/services/platform_support/email_sender.py,
#    app/services/platform_support/hosted_ai_consent.py,
#    app/services/platform_support/rate_limiter.py
#    Used by: app/main.py
#    Tested by: tests/test_account_security.py, tests/test_deploy.py
#
# EXECUTION FLOW:
#    Login form posts email + password
#       |
#       v
#    User looked up, password hash verified
#       |
#       v
#    Failed attempts counted (lockout)
#       |
#       v
#    JWT created and set as httpOnly cookie
#       |
#       v
#    User JSON returned
#
# IMPORTANT DEPENDENCIES:
#    fastapi, pydantic
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Authentication routes: register, login, logout and password reset.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from ..mongodb_data_layer import delete as sa_delete
from ..mongodb_data_layer import select
from ..mongodb_data_layer import Session

from ..application_configuration import get_settings
from ..database_connection import get_db
from ..authentication_dependencies import client_ip, get_current_user
from ..database_models import RecruiterProfile, Resume, StudentProfile, User
from ..request_validation_schemas import ChangePassword, LoginIn, RecruiterRegister, StudentRegister, _strong_password
from ..password_and_token_security import (
    COOKIE_NAME,
    create_access_token,
    create_reset_token,
    hash_password,
    read_reset_token,
    reset_token_matches,
    verify_password,
)
from ..api_response_serializers import profile_out
from ..services.platform_support import hosted_ai_consent as consent, rate_limiter as limiter, email_sender as mailer
from ..services.interview.ai_interview_service import ai_status
from ..services.platform_support.audit_and_notification_helpers import audit, get_setting, notify

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("hiresense.auth")

# Brute-force protection: failed attempts per email (services/platform_support/rate_limiter.py: memory, or Redis when REDIS_URL is set)
MAX_FAILED, WINDOW_SECONDS = 8, 15 * 60


def _login_key(email: str) -> str:
    return f"login:{email.lower()}"


def _set_cookie(response: Response, token: str) -> None:
    """Store the session JWT in an httpOnly cookie (JavaScript cannot read it). SameSite=Lax by default; "None" (with
    Secure) only when the frontend calls the API on another domain (COOKIE_SAMESITE=none)."""
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite=settings.samesite,
                        secure=settings.cookie_secure or settings.samesite == "none",
                        max_age=settings.access_token_minutes * 60, path="/")


def _clear_cookie(response: Response) -> None:
    # must repeat SameSite/Secure, or browsers ignore the deletion of a SameSite=None cookie
    settings = get_settings()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite=settings.samesite,
                           secure=settings.cookie_secure or settings.samesite == "none")


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
    if body.ai_consent and consent.required():
        user.ai_data_consent_at = datetime.now(timezone.utc)
    db.add(user)
    db.flush()
    audit(db, user.id, "user.register", "user", user.id, {"role": "student"}, client_ip(request))
    if user.ai_data_consent_at:
        audit(db, user.id, "user.ai_consent_given", "user", user.id, {"provider": "gemini", "at": "registration"},
              client_ip(request))
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
    get 429 (in memory, or in Redis when REDIS_URL is set). Pending, suspended and deactivated accounts get
    403 with a reason. Returns the user's profile; the token is also returned for API clients.
    """
    # Emails are stored in lower case, so compare in lower case too.
    email = body.email.lower()
    # Step 1 - brute-force protection: refuse early if this email already had too many recent failures.
    if limiter.count(_login_key(email), WINDOW_SECONDS) >= MAX_FAILED:
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    # Step 2 - find the account and compare the typed password with the stored Argon2 hash.
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        # Count the failure (for the lockout) and audit it; the message never says which part was wrong.
        limiter.add(_login_key(email), WINDOW_SECONDS)
        if user:
            audit(db, user.id, "auth.login_failed", "user", user.id, {}, client_ip(request))
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    # Step 3 - correct password: reset the failure counter, then check the account status.
    limiter.clear(_login_key(email))
    if user.status == "pending":
        raise HTTPException(403, "Your account is awaiting administrator approval")
    if user.status in ("suspended", "deactivated"):
        raise HTTPException(403, f"Your account has been {user.status}. Contact the placement office.")
    user.last_login_at = datetime.now(timezone.utc)
    user.last_active_at = user.last_login_at
    audit(db, user.id, "auth.login", "user", user.id, {}, client_ip(request))
    db.commit()
    # Step 4 - create the signed JWT (user id + role) and store it in an httpOnly cookie that JavaScript cannot read.
    token = create_access_token(user.id, user.role)
    _set_cookie(response, token)
    return {"user": profile_out(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie. (JWTs are stateless, so there is no server-side session to delete.)"""
    _clear_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current user's profile plus AI availability. The frontend calls this on load (AuthContext.jsx) to restore the session."""
    return {"user": profile_out(user), "ai": ai_status(db)}


@router.get("/privacy")
def privacy_info():
    """Public: which AI provider processes data on this server, and the consent notice when it is hosted."""
    return consent.info()


class AIConsentIn(BaseModel):
    accept: bool


@router.post("/ai-consent")
def set_ai_consent(body: AIConsentIn, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Give (accept=true) or withdraw (accept=false) consent to the hosted-AI data notice. Stored with the time."""
    if body.accept:
        if user.ai_data_consent_at is None:
            user.ai_data_consent_at = datetime.now(timezone.utc)
            audit(db, user.id, "user.ai_consent_given", "user", user.id, {"provider": consent.info()["provider"]},
                  client_ip(request))
    elif user.ai_data_consent_at is not None:
        user.ai_data_consent_at = None
        audit(db, user.id, "user.ai_consent_withdrawn", "user", user.id, {}, client_ip(request))
    db.commit()
    return {"user": profile_out(user), "privacy": consent.info()}


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=2000)
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_strong_password)


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(max_length=20)


# per-email limit on reset requests (same limiter as the login lockout)
MAX_RESET_REQUESTS = 3
GENERIC_RESET_REPLY = {"ok": True, "message": "If an account exists for that email, a reset link has been sent. "
                       "If email is not set up on this server, ask the placement office for the link."}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Start a password reset. Always returns the same reply, so it can't be used to find out who has an account."""
    email = body.email.lower()
    if not limiter.hit(f"reset:{email}", MAX_RESET_REQUESTS, WINDOW_SECONDS):
        return GENERIC_RESET_REPLY  # silently ignore floods; same reply as always
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
    limiter.clear(_login_key(user.email))
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
    _clear_cookie(response)
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

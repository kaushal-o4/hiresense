from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import client_ip, get_current_user
from ..models import RecruiterProfile, StudentProfile, User
from ..schemas import ChangePassword, LoginIn, RecruiterRegister, StudentRegister
from ..security import COOKIE_NAME, create_access_token, hash_password, verify_password
from ..serializers import profile_out
from ..services.ai import ai_status
from ..services.common import audit, get_setting, notify

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory brute-force protection: email -> [failed attempt timestamps]
_failed: dict[str, list[float]] = {}
MAX_FAILED, WINDOW_SECONDS = 8, 15 * 60


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=settings.cookie_secure,
                        max_age=settings.access_token_minutes * 60, path="/")


def _email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == email.lower())) is not None


@router.post("/register/student", status_code=201)
def register_student(body: StudentRegister, request: Request, response: Response, db: Session = Depends(get_db)):
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
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"user": profile_out(user), "ai": ai_status(db)}


@router.post("/change-password")
def change_password(body: ChangePassword, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit(db, user.id, "auth.password_changed", "user", user.id, {}, client_ip(request))
    db.commit()
    return {"ok": True, "message": "Password updated"}

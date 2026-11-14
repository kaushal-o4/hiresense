# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/routers/admin/admin_user_management_routes.py
#
# FILE PURPOSE:
# Admin management of user accounts, mentor-student assignments and recruiter verification.
#
# WHAT THIS FILE DOES:
# 1. List, view, create (staff), update and deactivate users.
# 2. Assign students to mentors and remove assignments.
# 3. Approve/verify recruiter accounts.
#
# HOW THIS FILE WORKS:
# Deleting a user is a soft delete (deactivation) so historical records stay consistent.
#
# IMPORTANT FUNCTIONS:
#    - delete_user()
#        Soft delete: deactivates the account so historical records stay consistent.
#    Other helper functions: list_users, get_user, create_user, update_user, list_assignments,
#    assign, unassign, verify_recruiter
#
# IMPORTANT CLASSES:
#    - VerifyIn
#
# API ENDPOINTS DEFINED HERE:
#    - GET /api/admin/users
#        list_users() - admin
#    - GET /api/admin/users/{user_id}
#        get_user() - admin
#    - POST /api/admin/users
#        create_user() - admin
#    - PATCH /api/admin/users/{user_id}
#        update_user() - admin
#    - DELETE /api/admin/users/{user_id}
#        delete_user() - admin - Soft delete: deactivates the account so historical records
#        stay consistent.
#    - GET /api/admin/assignments
#        list_assignments() - admin
#    - POST /api/admin/assignments
#        assign() - admin
#    - DELETE /api/admin/assignments/{assignment_id}
#        unassign() - admin
#    - POST /api/admin/recruiters/{user_id}/verify
#        verify_recruiter() - admin
#
# INPUT:
# User data, assignment pairs, verification decisions.
#
# OUTPUT:
# User JSON; audit log entries.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
#    app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
#    app/password_and_token_security.py, app/request_validation_schemas.py,
#    app/services/platform_support/audit_and_notification_helpers.py,
#    app/services/student_progress/student_performance_insights.py
#    Used by: app/routers/admin/__init__.py
#
# EXECUTION FLOW:
#    Recruiter registers (pending)
#       |
#       v
#    Admin verifies
#       |
#       v
#    Recruiter can sign in
#
# IMPORTANT DEPENDENCIES:
#    fastapi, pydantic
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Admin portal: user accounts, mentor assignments, recruiter verification."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...mongodb_data_layer import func, or_, select
from ...mongodb_data_layer import Session
from ...database_connection import get_db
from ...authentication_dependencies import client_ip, require_admin
from ...database_models import AuditLog, Job, MentorAssignment, MentorProfile, RecruiterProfile, StudentProfile, User
from ...request_validation_schemas import AdminUserCreate, AdminUserUpdate, AssignmentIn
from ...password_and_token_security import hash_password
from ...api_response_serializers import iso, profile_out, user_out
from ...services.platform_support.audit_and_notification_helpers import audit, notify, paginate
from ...services.student_progress.student_performance_insights import student_summary

router = APIRouter(prefix="/api/admin", tags=["admin"])


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

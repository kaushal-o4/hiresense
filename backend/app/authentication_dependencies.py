# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/authentication_dependencies.py
#
# FILE PURPOSE:
# Reusable FastAPI checks that find out who is calling an endpoint and whether they are allowed to.
#
# MAIN RESPONSIBILITY:
# Authentication (who are you?) and authorisation (are you allowed?) for every protected endpoint.
#
# WHAT THIS FILE DOES:
# 1. Reads the login token from the httpOnly `hs_session` cookie or an `Authorization: Bearer`
#    header.
# 2. Decodes the JWT and loads the user from the database (401 if missing/invalid, 403 if not
#    active).
# 3. Builds role checks: require_student, require_recruiter, require_mentor, require_admin.
# 4. Checks whether a mentor may see a particular student (assignment or view_all_students
#    permission).
# 5. Gets the client IP for the audit log.
#
# HOW THIS FILE WORKS:
# Route functions declare `user: User = Depends(require_student)`. FastAPI runs the dependency first;
# if it raises HTTPException the route never runs.
#
# IMPORTANT FUNCTIONS:
#    - get_current_user()
#        Decodes the session JWT and returns the signed-in User (401/403 otherwise).
#    - require_roles()
#        Creates a dependency that only lets the given roles through.
#    - ensure_mentor_access()
#        Raises 403 unless the mentor is allowed to see this student.
#    - mentor_can_access()
#        True if the mentor may see this student: an active MentorAssignment exists, or the
#        mentor has the `view_all_students` permission.
#    - client_ip()
#        Client IP address for the audit log (None when unknown, e.g. in tests).
#    Other helper functions: _token_from_request
#
# INPUT:
# The incoming HTTP request (cookie or header) and the database session.
#
# OUTPUT:
# The current User object, or an HTTP 401/403 error.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
#    app/password_and_token_security.py
#    Used by: app/routers/admin/admin_analytics_routes.py,
#    app/routers/admin/admin_content_routes.py, app/routers/admin/admin_operations_routes.py,
#    app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
#    app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
#    app/routers/interview_routes.py, app/routers/jobs/recruiter_job_routes.py,
#    app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
#    app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
#    app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
#    app/routers/student_portal_routes.py, app/routers/voice_speech_routes.py,
#    app/services/platform_support/student_record_access.py
#
# EXECUTION FLOW:
#    Request with cookie
#       |
#       v
#    _token_from_request() reads JWT
#       |
#       v
#    decode_access_token() verifies it
#       |
#       v
#    User loaded and status checked
#       |
#       v
#    Role check -> route runs or 403
#
# IMPORTANT DEPENDENCIES:
#    fastapi
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""FastAPI dependencies for authentication, role checks and mentor-assignment checks.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from .mongodb_data_layer import select
from .mongodb_data_layer import Session

from .database_connection import get_db
from .database_models import MentorAssignment, User
from .password_and_token_security import COOKIE_NAME, decode_access_token


def _token_from_request(request: Request) -> str | None:
    """The session JWT: an `Authorization: Bearer ...` header if present (API clients, tests), otherwise
    the httpOnly `hs_session` cookie the browser sends.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency for every signed-in endpoint: decode the JWT and load the user.

    401 if the token is missing, invalid or expired, or the account no longer exists; 403 if the account is not
    active (pending, suspended, deactivated). Updates `last_active_at` at most every 5 minutes and stores the user id
    on `request.state` so the global error handler can log who hit an error.
    """
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
    """Build a dependency that allows only the given roles (403 otherwise) and returns the current user.
    Used as `require_student`, `require_recruiter`, `require_mentor` and `require_admin` below.
    """
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
    """True if the mentor may see this student: an active MentorAssignment exists, or the mentor has
    the `view_all_students` permission.
    """
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
    """Raise 403 unless `mentor_can_access()`; called at the start of mentor endpoints about one student."""
    if not mentor_can_access(db, mentor, student_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This student is not assigned to you")


def client_ip(request: Request) -> str | None:
    """Client IP address for the audit log (None when unknown, e.g. in tests)."""
    return request.client.host if request.client else None

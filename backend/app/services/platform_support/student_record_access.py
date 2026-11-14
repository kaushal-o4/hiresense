# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/services/platform_support/student_record_access.py
#
# FILE PURPOSE:
# Decides who may view a student's detailed records (the student, admins, assigned mentors, recruiters
# with an application from that student).
#
# WHAT THIS FILE DOES:
# 1. recruiter_has_applicant()
# 2. can_view_student_detail()
# 3. ensure_can_view_student(): 403 otherwise.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: recruiter_has_applicant, can_view_student_detail,
#    ensure_can_view_student
#
# INPUT:
# Viewer and student id.
#
# OUTPUT:
# True/False or 403.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/authentication_dependencies.py, app/database_models.py,
#    app/mongodb_data_layer/__init__.py
#    Used by: app/routers/interview_monitoring_routes.py, app/routers/jobs/recruiter_job_routes.py,
#    app/routers/student_portal_routes.py
#
# EXECUTION FLOW:
#    Request
#       |
#       v
#    Access check
#       |
#       v
#    Data or 403
#
# IMPORTANT DEPENDENCIES:
#    fastapi
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Who may view which student's detailed records."""
from fastapi import HTTPException
from ...mongodb_data_layer import select
from ...mongodb_data_layer import Session

from ...authentication_dependencies import mentor_can_access
from ...database_models import Job, JobApplication, User


def recruiter_has_applicant(db: Session, recruiter_id: int, student_id: int) -> bool:
    return db.scalar(select(JobApplication.id).join(Job).where(
        Job.recruiter_id == recruiter_id, JobApplication.student_id == student_id,
        JobApplication.status != "withdrawn")) is not None


def can_view_student_detail(db: Session, viewer: User, student_id: int) -> bool:
    if viewer.role == "admin":
        return True
    if viewer.role == "student":
        return viewer.id == student_id
    if viewer.role == "mentor":
        return mentor_can_access(db, viewer, student_id)
    if viewer.role == "recruiter":
        return recruiter_has_applicant(db, viewer.id, student_id)
    return False


def ensure_can_view_student(db: Session, viewer: User, student_id: int) -> User:
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(404, "Student not found")
    if not can_view_student_detail(db, viewer, student_id):
        raise HTTPException(403, "You do not have access to this student's records")
    return student

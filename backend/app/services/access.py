"""Who may view which student's detailed records."""
from fastapi import HTTPException
from ..odm import select
from ..odm import Session

from ..deps import mentor_can_access
from ..models import Job, JobApplication, User


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

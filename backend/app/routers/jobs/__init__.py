"""Placement opportunities (student side) and recruiter job/candidate management.

  common     shared helpers: semantic match + AI review, eligibility, payloads, email, message threads
  student    /api/student: browse and apply to jobs, my applications, messages with recruiters
  recruiter  /api/recruiter: dashboard, jobs, applicants, AI match, compare, candidate report, candidate search
  screening  /api/recruiter: bulk screening, assessment assignments, messages to applicants, CSV export
"""
from fastapi import APIRouter

from . import recruiter, screening, student

student_router = APIRouter()
student_router.include_router(student.student_router)

recruiter_router = APIRouter()
for _part in (recruiter, screening):
    recruiter_router.include_router(_part.recruiter_router)

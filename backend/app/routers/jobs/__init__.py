# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/routers/jobs/__init__.py
#
# FILE PURPOSE:
# Combines the student job routes and recruiter job routes into two routers for main.py.
#
# WHAT THIS FILE DOES:
# 1. Exposes student_router (/api/student) and recruiter_router (/api/recruiter).
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/routers/jobs/recruiter_job_routes.py,
#    app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py
#    Used by: app/main.py
#
# IMPORTANT DEPENDENCIES:
#    fastapi
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Placement opportunities (student side) and recruiter job/candidate management.

  common     shared helpers: semantic match + AI review, eligibility, payloads, email, message threads
  student    /api/student: browse and apply to jobs, my applications, messages with recruiters
  recruiter  /api/recruiter: dashboard, jobs, applicants, AI match, compare, candidate report, candidate search
  screening  /api/recruiter: bulk screening, assessment assignments, messages to applicants, CSV export
"""
from fastapi import APIRouter

from . import (
    recruiter_job_routes as recruiter,
    recruiter_screening_routes as screening,
    student_job_routes as student,
)

student_router = APIRouter()
student_router.include_router(student.student_router)

recruiter_router = APIRouter()
for _part in (recruiter, screening):
    recruiter_router.include_router(_part.recruiter_router)

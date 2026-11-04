"""Admin portal: users, platform configuration, analytics, monitoring.

All endpoints live under /api/admin and require the admin role. They are split by area:
  analytics   dashboard, placement report, student overview, AI report monitoring, backup
  people      user accounts, mentor assignments, recruiter verification
  content     interview categories, question bank, rubrics, badges, reward rules, challenges
  operations  jobs, flagged activity and logs, platform settings, placement drives, announcements
"""
from fastapi import APIRouter

from . import analytics, content, operations, people

router = APIRouter()
for _part in (analytics, people, content, operations):
    router.include_router(_part.router)

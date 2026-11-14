# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/routers/admin/__init__.py
#
# FILE PURPOSE:
# Combines the four admin route files into one router mounted under /api/admin.
#
# WHAT THIS FILE DOES:
# 1. Imports analytics, user management, content and operations routes.
# 2. Exposes `router` for main.py.
#
# HOW THIS FILE WORKS:
# Each part has its own APIRouter; this file includes them all into one.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
#    app/routers/admin/admin_operations_routes.py,
#    app/routers/admin/admin_user_management_routes.py
#    Used by: app/main.py
#
# IMPORTANT DEPENDENCIES:
#    fastapi
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Admin portal: users, platform configuration, analytics, monitoring.

All endpoints live under /api/admin and require the admin role. They are split by area:
  analytics   dashboard, placement report, student overview, AI report monitoring, backup
  people      user accounts, mentor assignments, recruiter verification
  content     interview categories, question bank, rubrics, badges, reward rules, challenges
  operations  jobs, flagged activity and logs, platform settings, placement drives, announcements
"""
from fastapi import APIRouter

from . import (
    admin_analytics_routes as analytics,
    admin_content_routes as content,
    admin_operations_routes as operations,
    admin_user_management_routes as people,
)

router = APIRouter()
for _part in (analytics, people, content, operations):
    router.include_router(_part.router)

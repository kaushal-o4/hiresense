# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/services/platform_support/hosted_ai_consent.py
#
# FILE PURPOSE:
# Asks students to agree once before their data is sent to a hosted AI (Gemini). Not needed with the
# local model.
#
# WHAT THIS FILE DOES:
# 1. required(), info(), has(user)
# 2. check(user): returns HTTP 428 if consent is required but missing.
#
# IMPORTANT FUNCTIONS:
#    - check()
#        428 Precondition Required when a student must agree to the AI data notice before this
#        action.
#    Other helper functions: required, info, has
#
# IMPORTANT VARIABLES / SETTINGS:
#    NOTICE, REQUIRED_MESSAGE
#
# INPUT:
# User.
#
# OUTPUT:
# Consent status / 428 error.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py, app/database_models.py
#    Used by: app/routers/authentication_routes.py, app/routers/english_practice_routes.py,
#    app/routers/interview_routes.py, app/routers/student_portal_routes.py
#    Tested by: tests/test_deploy.py
#
# EXECUTION FLOW:
#    AI feature called
#       |
#       v
#    check()
#       |
#       v
#    Continue or 428
#
# IMPORTANT DEPENDENCIES:
#    fastapi
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Consent for sending a student's data to the hosted AI (Google Gemini).

With LOCAL_AI_PROVIDER=gemini, resumes, interview answers (text, and voice recordings when STT_ENGINE=gemini) and
English practice messages are sent to Google to be processed. A student must agree to that once, at registration or
before their first AI feature; the time of agreement is stored on the account (users.ai_data_consent_at) and in the
audit log. With the local Ollama provider nothing leaves the server, so no consent is asked for.
"""
from __future__ import annotations

from fastapi import HTTPException

from ...application_configuration import get_settings
from ...database_models import User

NOTICE = ("HireSense uses Google's Gemini AI. When you analyse a resume, take an AI interview or practise English, "
          "the text you provide (resume contents, your answers, your messages) and, for spoken answers, the audio "
          "recording are sent to Google to be processed. Google offers this service under its Gemini API terms. "
          "HireSense does not sell your data. You can withdraw consent at any time in Settings; AI features are then "
          "unavailable until you agree again.")
REQUIRED_MESSAGE = "Please agree to the AI data notice first (your data is processed by Google Gemini)."


def required() -> bool:
    return get_settings().sends_data_to_google


def info() -> dict:
    s = get_settings()
    hosted = required()
    return {"provider": "gemini" if hosted else ("ollama" if s.ai_enabled else "none"),
            "data_leaves_server": hosted, "consent_required": hosted,
            "speech_to_google": hosted and s.stt_enabled and s.stt_engine.strip().lower() == "gemini",
            "notice": NOTICE if hosted else None}


def has(user: User) -> bool:
    return user.role != "student" or not required() or user.ai_data_consent_at is not None


def check(user: User) -> None:
    """428 Precondition Required when a student must agree to the AI data notice before this action."""
    if not has(user):
        raise HTTPException(428, REQUIRED_MESSAGE)

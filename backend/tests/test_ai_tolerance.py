# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/tests/test_ai_tolerance.py
#
# FILE PURPOSE:
# Model-output tolerance: a display-only label the model invents must not discard a whole analysis.
#
# WHAT THIS FILE DOES:
# 1. Automated test (pytest, mocked AI - no real model needed).
# 2. Contains 1 test(s), e.g.: unknown skill category is mapped not rejected.
# 3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: test_unknown_skill_category_is_mapped_not_rejected
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/services/interview/ai_interview_service.py
#
# IMPORTANT NOTE:
# Test/tool file: it checks or measures the application and is not used by the running app.
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Model-output tolerance: a display-only label the model invents must not discard a whole analysis."""
from app.services.interview.ai_interview_service import ResumeSkillItem


def test_unknown_skill_category_is_mapped_not_rejected():
    assert ResumeSkillItem(name="Docker", category="DevOps").category == "tool"
    assert ResumeSkillItem(name="Python", category="Language").category == "programming_language"
    assert ResumeSkillItem(name="X", category="something new").category == "other"
    assert ResumeSkillItem(name="AWS", category="cloud").category == "cloud"

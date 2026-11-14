# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/services/ai_models/ai_task_model_router.py
#
# FILE PURPOSE:
# Decides which model name handles which AI task (fast tier for chat, strong tier for scoring and
# reports, default otherwise).
#
# WHAT THIS FILE DOES:
# 1. Maps each feature name (e.g. 'answer_scoring') to a tier.
# 2. Returns the configured model for that tier.
# 3. Describes the routing table for the admin AI page.
#
# IMPORTANT FUNCTIONS:
#    - configured_model()
#        The model named in the settings for this feature (not checked for availability).
#    - describe()
#        Routing table for the admin AI page: tier -> model, and the features in each tier.
#    Other helper functions: tier_of, _models
#
# IMPORTANT VARIABLES / SETTINGS:
#    FAST_TASKS, STRONG_TASKS
#
# INPUT:
# Feature name.
#
# OUTPUT:
# Model name.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py
#    Used by: app/main.py, app/services/ai_models/ai_structured_call_base.py
#    Tested by: tests/test_gemini.py, tests/test_health_and_routing.py
#
# EXECUTION FLOW:
#    Feature name
#       |
#       v
#    Tier
#       |
#       v
#    Model from settings
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Which model handles which AI task (for the active provider: Ollama or Gemini).

Every language-model call in ai_interview_service.py has a feature name ("english_chat", "answer_scoring", ...). Each feature belongs
to a tier, and each tier maps to a model name from the settings:

  fast   - short conversational turns (English companion chat)       OLLAMA_MODEL_FAST
  strong - scoring, extraction and long structured output            OLLAMA_MODEL_STRONG
  (any feature not listed uses OLLAMA_MODEL)

Both tier settings are empty by default, so every task uses OLLAMA_MODEL and nothing changes until a model has been
benchmarked (tests_perf/bench_models.py) and the admin sets the variables. A tier whose model is not downloaded
falls back to the main model. With LOCAL_AI_PROVIDER=gemini the same tiers use GEMINI_MODEL / _FAST / _STRONG.

On a 4 GB GPU two different models cannot both stay loaded; Ollama swaps them, and a swap costs several seconds.
Only split tiers if the benchmark shows the fast model's saving is larger than the swap cost for your hardware.
"""
from __future__ import annotations

from ...application_configuration import get_settings

FAST_TASKS = frozenset({"english_chat"})
STRONG_TASKS = frozenset({"answer_scoring", "answer_feedback", "interview_report", "resume_analysis",
                          "code_review", "assessment_generation", "english_evaluation"})


def tier_of(feature: str) -> str:
    if feature in FAST_TASKS:
        return "fast"
    if feature in STRONG_TASKS:
        return "strong"
    return "default"


def _models() -> tuple[str, str, str]:
    """(default, fast, strong) model settings of the active provider (GEMINI_MODEL* or OLLAMA_MODEL*)."""
    s = get_settings()
    if s.local_ai_provider.strip().lower() == "gemini":
        return s.gemini_model, s.gemini_model_fast, s.gemini_model_strong
    return s.ollama_model, s.ollama_model_fast, s.ollama_model_strong


def configured_model(feature: str) -> str:
    """The model named in the settings for this feature (not checked for availability)."""
    default, fast, strong = _models()
    chosen = {"fast": fast, "strong": strong}.get(tier_of(feature), "")
    return (chosen or "").strip() or default


def describe() -> dict:
    """Routing table for the admin AI page: tier -> model, and the features in each tier."""
    default, fast, strong = _models()
    return {"provider": get_settings().local_ai_provider, "default": default,
            "fast": (fast or "").strip() or default,
            "strong": (strong or "").strip() or default,
            "fast_tasks": sorted(FAST_TASKS), "strong_tasks": sorted(STRONG_TASKS)}

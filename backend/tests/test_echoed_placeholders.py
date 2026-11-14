# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/tests/test_echoed_placeholders.py
#
# FILE PURPOSE:
# The model copying the prompt's instructions back as content (seen 2026-11-05 on the interview report
# with the Ollama fallback) is treated as invalid output: retried once, then reported as unavailable.
#
# WHAT THIS FILE DOES:
# 1. Automated test (pytest, mocked AI - no real model needed).
# 2. Contains 7 test(s), e.g.: exact bad payload is detected; genuine report with one count phrase
#    is not flagged; conversation reply repeating the students words is not flagged; identical list
#    items are flagged; report retries once after an echo and uses the real answer; report echoed
#    twice is unavailable not shown; report prompt has no copyable count phrases.
# 3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: test_exact_bad_payload_is_detected,
#    test_genuine_report_with_one_count_phrase_is_not_flagged,
#    test_conversation_reply_repeating_the_students_words_is_not_flagged,
#    test_identical_list_items_are_flagged, ai_on, _fake,
#    test_report_retries_once_after_an_echo_and_uses_the_real_answer,
#    test_report_echoed_twice_is_unavailable_not_shown,
#    test_report_prompt_has_no_copyable_count_phrases
#
# IMPORTANT VARIABLES / SETTINGS:
#    ECHOED_REPORT, GOOD_REPORT, QA
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/services/ai_models/ai_structured_call_base.py,
#    app/services/ai_models/language_model_client.py,
#    app/services/interview/ai_interview_service.py
#
# IMPORTANT DEPENDENCIES:
#    pytest
#
# IMPORTANT NOTE:
# Test/tool file: it checks or measures the application and is not used by the running app.
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""The model copying the prompt's instructions back as content (seen 2026-11-05 on the interview report with the
Ollama fallback) is treated as invalid output: retried once, then reported as unavailable."""
import json

import pytest

from app.services.interview import ai_interview_service as ai
from app.services.ai_models import ai_structured_call_base as ai_base, language_model_client as local_llm

# Exact payload stored for interview session 1 in the screenshot run (Gemini at quota -> Ollama fallback).
ECHOED_REPORT = {
    "summary": "2-4 sentence summary",
    "strengths": ["2-4 specific strengths"] * 3,
    "weaknesses": ["2-4 specific weaknesses"] * 3,
    "suggestions": ["3-5 concrete improvement suggestions"] * 3,
    "recommended_practice": ["2-3 recommended practice activities"] * 2,
    "closing_remarks": "2-3 short spoken sentences (plain text, under 60 words)",
}

GOOD_REPORT = {
    "summary": "You explained your FastAPI project clearly and showed real ownership. Your debugging answer was "
               "structured, but the threads vs processes answer missed the GIL and when to choose each.",
    "strengths": ["Q1: concrete numbers when describing the background-task speed-up.",
                  "Q2: a clear reproduce-test-bisect-fix sequence."],
    "weaknesses": ["Q3: no mention of Python's GIL.", "Q1: did not explain how the background job is retried."],
    "suggestions": ["Add one trade-off to each design answer.", "Name the tool you would use to bisect (git bisect).",
                    "Give a real example of a race condition you fixed."],
    "recommended_practice": ["Practise 3 concurrency questions on threads, processes and asyncio.",
                             "2-3 mock interviews per week on system design."],
    "closing_remarks": "Thanks for your time today. Your project story was strong. Work on concurrency and you will "
                       "be ready.",
}

QA = [{"type": "technical", "question": "Tell me about a FastAPI project.", "answer": "I built a placement portal.",
       "score": 78}]


def test_exact_bad_payload_is_detected():
    bad = ai_base.echoed_placeholders(ECHOED_REPORT)
    assert {"summary", "closing_remarks", "strengths", "weaknesses", "suggestions", "recommended_practice"} <= {
        p.split("[")[0] for p in bad}


def test_genuine_report_with_one_count_phrase_is_not_flagged():
    assert ai_base.echoed_placeholders(GOOD_REPORT) == []  # "2-3 mock interviews per week" alone is fine


def test_conversation_reply_repeating_the_students_words_is_not_flagged():
    assert ai_base.echoed_placeholders({"reply": "You said you went to college yesterday.",
                                        "corrections": [{"original": "I go college yesterday",
                                                         "corrected": "I went to college yesterday"}],
                                        "current_topic": "Your hobbies and weekends"}) == []


def test_identical_list_items_are_flagged():
    assert ai_base.echoed_placeholders({"tips": ["Speak slowly.", "speak slowly"]}) == ["tips"]


@pytest.fixture()
def ai_on(monkeypatch, db):
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": "mock", "running": True, "model_ready": True, "error": None})
    return db


def _fake(replies, prompts):
    def chat_json(system, prompt, schema, **kw):
        prompts.append(prompt)
        return local_llm.LLMResult(content=json.dumps(replies.pop(0)), prompt_tokens=1, output_tokens=1, latency_ms=1)
    return chat_json


def test_report_retries_once_after_an_echo_and_uses_the_real_answer(monkeypatch, ai_on):
    prompts = []
    monkeypatch.setattr(local_llm, "chat_json", _fake([ECHOED_REPORT, GOOD_REPORT], prompts))
    out = ai.interview_report(ai_on, None, job_role="Backend Developer", category="technical", qa=QA)
    assert out["summary"].startswith("You explained your FastAPI project")
    assert len(prompts) == 2 and "copied these instructions" in prompts[1]


def test_report_echoed_twice_is_unavailable_not_shown(monkeypatch, ai_on):
    monkeypatch.setattr(local_llm, "chat_json", _fake([ECHOED_REPORT, ECHOED_REPORT], []))
    with pytest.raises(ai.AIUnavailable):
        ai.interview_report(ai_on, None, job_role="Backend Developer", category="technical", qa=QA)


def test_report_prompt_has_no_copyable_count_phrases(monkeypatch, ai_on):
    import re
    prompts = []
    monkeypatch.setattr(local_llm, "chat_json", _fake([GOOD_REPORT], prompts))
    ai.interview_report(ai_on, None, job_role="Backend Developer", category="technical", qa=QA)
    assert not re.search(r"\d+-\d+ (sentence|specific|strengths|weaknesses|concrete|recommended|short)", prompts[0])

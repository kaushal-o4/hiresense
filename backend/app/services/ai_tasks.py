"""Smaller AI tasks: match narrative, recommendations, MCQ generation, code review, role suggestions."""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel
from ..odm import Session

from .ai_base import AIUnavailable, _clamp, _clean_list, _strictness, _structured_call, fence


# =========================================================================== job match narrative

class MatchReview(BaseModel):
    explanation: str
    strengths: list[str]
    concerns: list[str]


def match_review(db: Session, user_id: int, *, job: dict, candidate: dict, computed: dict) -> dict:
    """Plain-language review of a match that was already scored by services.matching.

    The model may NOT change the score or skill lists; it only explains them using the evidence.
    """
    system = ("You are an impartial hiring assistant. Explain a candidate-job match using ONLY job-relevant "
              "evidence: skills, projects, experience, assessment and interview performance, and eligibility. "
              "Never consider gender, religion, caste, age, ethnicity, name or other protected characteristics. "
              "Never claim the candidate has a skill or qualification that is not in the evidence. Your output is "
              "advisory; a human recruiter makes the final decision.")
    facts = {k: computed.get(k) for k in ("score", "recommendation", "matched_skills", "missing_required_skills",
                                          "missing_preferred_skills", "partially_matched_skills",
                                          "relevant_projects", "criteria_scores", "eligible", "eligibility_issues")}
    prompt = (f"{fence('job', json.dumps(job, default=str, indent=1))}\n\n"
              f"{fence('candidate', json.dumps(candidate, default=str, indent=1))}\n\n"
              f"Computed match (fixed - do not change these numbers or lists):\n{json.dumps(facts, default=str, indent=1)}\n\n"
              "Write a 3-5 sentence explanation a recruiter can verify, 2-4 strengths and 1-4 concerns. Clearly "
              "mention every missing required skill as a concern.")
    r = _structured_call(db, user_id, "job_match", system, prompt, MatchReview, max_tokens=900).model_dump()
    r["strengths"], r["concerns"] = _clean_list(r["strengths"], 5), _clean_list(r["concerns"], 5)
    return r


# =========================================================================== recommendations

class Recommendation(BaseModel):
    title: str
    activity_type: Literal["mock_interview", "english_practice", "assessment", "resume_update", "resource", "custom"]
    reason: str


class StudentRecommendations(BaseModel):
    summary: str
    weak_areas: list[str]
    recommendations: list[Recommendation]


def student_recommendations(db: Session, user_id: int, *, snapshot: dict) -> dict:
    system = ("You are a placement mentor. Based on a student's real performance data, identify weak areas "
              "(technical skills, communication, interview technique) and recommend 3-6 concrete practice "
              "activities. Ground every point in the data provided.")
    # Measured 2026-11-04 with qwen3:4b: without these rules the weak areas came back as category labels
    # ("technical_skills") and every activity was a mock interview, even for weak assessment topics.
    system += (" Name each weak area specifically, using the topic or criterion from the data (for example "
               "'SQL joins' or 'answer completeness'), never a bare category. Pick the activity_type that fits each "
               "weakness: assessment for weak test topics, english_practice for language scores, mock_interview "
               "for interview technique, resume_update for resume gaps.")
    prompt = fence("student_data", json.dumps(snapshot, default=str, indent=1))
    return _structured_call(db, user_id, "recommendations", system, prompt, StudentRecommendations).model_dump()


# =========================================================================== assessment generation

class MCQ(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str


class GeneratedAssessment(BaseModel):
    questions: list[MCQ]


_OPTION_LABEL = re.compile(r"^\s*(?:\(?[A-Da-d1-4][\.\):]|\([A-Da-d1-4]\))\s+")


def generate_assessment(db: Session, user_id: int, *, topic: str, count: int, difficulty: str) -> list[dict]:
    system = "You write accurate multiple-choice questions for campus placement aptitude and technical tests."
    prompt = (f"Topic: {topic}\nDifficulty: {difficulty}\nWrite exactly {count} questions, each with exactly 4 "
              "options, the 0-based index of the single correct option, and a one-sentence explanation. Before answering, "
              "check every question: exactly one option is correct, the marked index points to it, and the "
              "explanation agrees with it. Rewrite any question that fails this check.")
    qs = _structured_call(db, user_id, "assessment_generation", system, prompt, GeneratedAssessment,
                          max_tokens=4096).questions
    out = []
    for q in qs:
        # Small models sometimes number the options themselves ("1: LEFT JOIN", "B) ..."); the UI adds its own.
        q.options = [_OPTION_LABEL.sub("", o).strip() for o in q.options]
        if len(q.options) >= 2 and 0 <= q.answer_index < len(q.options) and all(q.options):
            out.append(q.model_dump())
    if not out:
        raise AIUnavailable("The AI did not return valid questions. Please try again.")
    return out


# =========================================================================== coding questions

class TestCaseVerdict(BaseModel):
    case: int
    # Asked for BEFORE the verdict so the model traces the code first (2026-11-04: without it Gemini Flash-Lite
    # passed a buggy solution on a case it fails).
    traced_output: str
    likely_passes: bool
    reason: str


class CodeReview(BaseModel):
    score: int
    verdicts: list[TestCaseVerdict]
    feedback: str
    improved_solution: str


def evaluate_code(db: Session, user_id: int, *, question: str, language: str, code: str,
                  test_cases: list[dict]) -> dict:
    """AI code review. The code is NOT executed; the model reasons about each test case."""
    system = ("You are a programming instructor grading a student's solution for a placement coding test. The code "
              "is not executed; reason carefully about whether it would produce the expected output for each test "
              "case, including edge cases and syntax errors. For each test case, trace the code by hand on that "
              "exact input, write down the value it returns, and compare it with the expected output; the case "
              "passes only if they are equal. " + _strictness(db))
    cases = "\n".join(f"{i + 1}. input={json.dumps(t.get('input'))} expected={json.dumps(t.get('expected'))}"
                      for i, t in enumerate(test_cases)) or "(no test cases given - judge correctness from the task)"
    prompt = (f"Task:\n{question}\n\nLanguage: {language}\nTest cases:\n{cases}\n\n"
              f"{fence('student_code', code)}\n\n"
              "Give a 0-100 correctness/quality score, a verdict per test case, 2-4 sentences of feedback and a "
              "short improved reference solution in the same language.")
    r = _structured_call(db, user_id, "code_review", system, prompt, CodeReview).model_dump()
    r["score"] = int(_clamp(r["score"], 0, 100))
    return r


# =========================================================================== job role recommendations

class RoleSuggestion(BaseModel):
    role: str
    fit_score: int
    reasons: list[str]
    skills_to_learn: list[str]


class RoleRecommendations(BaseModel):
    summary: str
    roles: list[RoleSuggestion]


def job_role_recommendations(db: Session, user_id: int, *, snapshot: dict, interests: str | None) -> dict:
    system = ("You are a career counsellor for engineering and science graduates in India. Suggest realistic "
              "entry-level job roles that fit the student's demonstrated skills, projects, performance and interests.")
    prompt = (f"{fence('student_data', json.dumps(snapshot, default=str, indent=1))}\n"
              f"Stated career interests: {interests or 'not provided'}\n\n"
              "Suggest 3-5 roles, each with a 0-100 fit score, 2-3 reasons grounded in the data and the most "
              "important skills to learn next. Add a 2-sentence summary.")
    r = _structured_call(db, user_id, "role_recommendations", system, prompt, RoleRecommendations).model_dump()
    for x in r["roles"]:
        x["fit_score"] = int(_clamp(x["fit_score"], 0, 100))
    r["roles"].sort(key=lambda x: -x["fit_score"])
    return r

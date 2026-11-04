"""AI features: the interview prompts and scoring live here; the other features are in sibling modules.

  ai_base     the model gateway (_structured_call), ai_status, AIUnavailable, shared helpers
  ai_resume   resume analysis
  ai_english  spoken-English practice with Aria
  ai_tasks    match narrative, recommendations, MCQ generation, code review, role suggestions

Everything is re-exported here, so callers keep using `from ..services import ai` and `ai.<name>`. Tests patch
interview functions and tunables (SCORE_ANCHORS, answer_similarity, ...) on this module, which is why the interview
code itself stays in this file.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel
from ..odm import Session

from . import local_llm, scoring_bands  # noqa: F401 - local_llm is used as ai.local_llm by tests

from .ai_base import AIUnavailable, _clamp, _clean_list, _strictness, _structured_call, fence
from .ai_english import _speakable


# =========================================================================== interview

QuestionType = Literal["technical", "hr", "behavioral", "communication", "project"]


Aspect = Literal["overview", "objective", "personal_contribution", "architecture", "decision", "error_handling",
                 "testing", "scaling", "limitations", "result", "lessons", "concept", "scenario", "teamwork",
                 "conflict", "feedback", "adaptability", "motivation", "learning"]


class NextQuestion(BaseModel):
    # Field order matters: the reply is streamed and spoken from `question` onwards, so the short metadata used for
    # coverage and duplicate checks comes AFTER it (it is generated while the first sentence is being spoken).
    # Only ONE short enum is added (~5 output tokens): every output token costs ~55 ms on the test laptop. The topic
    # is derived from the resume in code (interview_engine.derive_topic), not generated.
    preface: str
    question: str
    question_type: QuestionType
    is_followup: bool
    aspect: Aspect = "overview"

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        schema = super().model_json_schema(*args, **kwargs)
        schema["required"] = list(schema["properties"])  # defaults only keep older/mocked replies valid
        return schema


DIFFICULTY_GUIDE = {
    "easy": "Beginner level: definitions, fundamentals and confidence-building questions.",
    "medium": "Standard campus-placement level: apply concepts, compare options, explain how something works.",
    "hard": "Challenging: deeper reasoning, trade-offs, edge cases and design decisions.",
}
_GREETING = re.compile(
    # "Hi there, what's ..." (regression from the real-model eval): greeting + comma directly before the question
    # also "Hi Priya, how did you ..." (live interview, 2026-10-11): greeting + a name + comma before the question
    r"^(?:(?:hi|hello|hey)(?: there| [a-z]+)?,\s*(?=(?:what|how|why|which|who|when|where|can|could|would|tell|describe|"
    r"walk|explain|in|do|did|have|is|are|let'?s)\b)"
    r"|(?:hi|hello|hey|good (?:morning|afternoon|evening|day)|welcome)\b[^.!?]*[.!?]\s*"
    r"|(?:i'?m|i am|my name is) [A-Z][a-z]+\b[^.!?]*[.!?]\s*)+", re.IGNORECASE)


def strip_greeting(question: str) -> str:
    """The interviewer's greeting is spoken separately; drop any greeting/self-introduction the model adds."""
    rest = _GREETING.sub("", question).strip()
    return rest if len(rest.split()) >= 4 else question


RESPONSE_MODES = ("fast", "coaching")
RECENT_TURNS = 3  # previous answers sent in full; older turns are summarised as a list of questions
ANSWER_CHARS_IN_PROMPT = 700


def _transcript(history: list[dict], coaching: bool) -> str:
    """Compact interview context: the last few answers in full (they drive follow-ups), earlier ones only as the
    questions already asked (enough to avoid repeats). Keeps prompts short as the interview grows."""
    if not history:
        return "(no questions asked yet)"
    older, recent = history[:-RECENT_TURNS], history[-RECENT_TURNS:]
    lines = []
    if older:
        lines.append("Earlier questions (already asked, do not repeat):\n" +
                     "\n".join(f"- {h['question']}" for h in older[-10:]))
    first = len(history) - len(recent)
    for i, h in enumerate(recent):
        answer = (h.get("answer") or "(not answered)")[:ANSWER_CHARS_IN_PROMPT]
        line = (f"Q{first + i + 1} [{h['type']}, {h.get('difficulty') or '?'}]: {h['question']}\n"
                f"{fence('answer', answer)}\n"
                f"Score: {h['score'] if h.get('score') is not None else 'not scored'}/100")
        if coaching and i == len(recent) - 1 and h.get("communication") is not None:
            line += f" (communication {h['communication']}/10)"
        lines.append(line)
    return "\n".join(lines)


def next_interview_question(db: Session, user_id: int, *, job_role: str, category: str, position: int,
                            total: int, resume_summary: str, skills: list[str], history: list[dict],
                            difficulty: str = "medium", subject: str | None = None,
                            projects: list[str] | None = None, topics: list[str] | None = None,
                            struggling: bool = False, avoid: list[str] | None = None,
                            interviewer: str = "aria", response_mode: str = "fast", on_delta=None,
                            candidate_facts: str | None = None, signals: list[dict] | None = None,
                            coverage: dict | None = None, stage: str | None = None) -> dict:
    """on_delta(json_text_so_far) streams the reply (the router turns it into spoken sentences).

    candidate_facts / signals / coverage / stage come from services/interview_engine.py: the resume facts the
    question may rely on, what the last answer left unclear, which topics were already explored, and where in the
    interview we are."""
    from . import interviewers
    p = interviewers.get(interviewer)
    coaching = response_mode == "coaching"
    hints = p.gives_hints or coaching  # coaching mode was chosen by the student: hints for every interviewer
    system = (f"{p.persona_prompt}\nYou are interviewing a final-year student or fresh graduate. Ask exactly one "
              f"clear question at a time, answerable verbally in 1-3 minutes.\nQuestion strategy: "
              f"{p.question_strategy}\n{p.behaviour_prompt()}\n{interviewers.BOUNDARIES}\n"
              "React to what the candidate actually said. Only refer to experience in the candidate facts or the "
              "answers; if something is missing or unclear, ask about it instead of assuming. Imperfect English or "
              "hesitation is not a lack of knowledge. No stock phrases ('Great answer!', 'Excellent!').")
    transcript = _transcript(history, coaching)
    focus = {"mixed": "rotate across technical, project, behavioral and hr questions",
             "technical": "technical questions; you may also ask about the candidate's projects (type 'project')"}
    if struggling and hints:
        guidance = ("The candidate struggled with the previous answer. In 'preface', give a short, kind 1-2 "
                    "sentence explanation of the key idea they missed. Then ask a SIMPLER follow-up question on the "
                    "same concept and set is_followup=true.")
    elif struggling:
        guidance = ("The candidate struggled with the previous answer. Leave 'preface' empty and do not explain the "
                    "answer. Either ask them to clarify one specific point of what they said, or move on to a "
                    "different, slightly easier question.")
    elif coaching and history:
        guidance = ("COACHING MODE. In 'preface', give 1-2 short spoken sentences of feedback on the previous answer: "
                    "one specific thing that was good and the most important thing that was missing. If its "
                    "communication score was below 6/10, add one short tip on how to phrase it in English. Do not "
                    "give the full answer. Then " + p.followup_policy[0].lower() + p.followup_policy[1:] +
                    " When you do not follow up, ask a new question grounded in the candidate's skills, projects and "
                    "the role.")
    else:
        guidance = ("Leave 'preface' empty. " + p.followup_policy + " When you do not follow up, ask a new question "
                    "grounded in the candidate's skills, projects and the role.")
    words = min(p.max_question_words, 25) if not coaching else p.max_question_words
    length = (f"one or two short sentences, about {words} words at most" if not coaching
              else f"at most 2 short sentences and about {words} words")
    facts = candidate_facts or (
        f"Summary: {resume_summary or 'not available'}\n"
        f"Skills: {', '.join(skills[:25]) or 'not available'}\n"
        f"Projects: {', '.join((projects or [])[:6]) or 'not available'}\n"
        f"Topics worth checking: {', '.join((topics or [])[:10]) or 'not available'}")
    analysis = ""
    if signals:
        # the personality decides which gap to pursue first when the last answer had several
        ranked = sorted(signals, key=lambda s: (p.followup_preference.index(s["followup_kind"])
                                                if s["followup_kind"] in p.followup_preference else 99))
        analysis = ("The last answer left open (pick ONE, or move on):\n"
                    + "\n".join(f"- {s['hint']}" for s in ranked[:2]) + "\n")
    plan = ""
    if coverage and (coverage.get("covered") or coverage.get("open")):
        plan = ((f"Already explored: {'; '.join(coverage['covered'][-6:])}\n" if coverage.get("covered") else "")
                + ("Not yet explored: " + " | ".join(coverage["open"][:2]) + "\n" if coverage.get("open") else ""))
    prompt = (
        f"Role: {job_role}\n"
        f"Interview focus: {category} - {focus.get(category, category + ' questions')}\n"
        f"Technical subject requested by the student: {subject or 'none - choose from their skills'}\n"
        f"This is question {position} of {total}" + (f" ({stage})" if stage else "") + ".\n"
        f"Required difficulty: {difficulty} - {DIFFICULTY_GUIDE.get(difficulty, DIFFICULTY_GUIDE['medium'])}\n"
        f"Candidate facts (from the resume - the only experience you may refer to):\n{facts}\n\n"
        f"Transcript so far:\n{transcript}\n\n"
        f"{analysis}{plan}"
        f"{guidance}\n"
        f"The question will be spoken aloud by {p.name}, so phrase it the way {p.name} talks, in {p.name}'s style: "
        f"natural spoken English, {length}, no lists, no brackets, no "
        "markdown. Never greet the candidate, use their name or introduce yourself - the greeting is spoken "
        "separately, so go straight to the question. After the first question you may start with a brief natural "
        "transition in your style, but do not praise a weak answer.\n"
        "Never repeat or rephrase an earlier question; a follow-up must explore a DIFFERENT side of the topic "
        "(e.g. their own contribution, a decision, error handling, testing, a limitation or the result).\n"
        "Set aspect to the side of the topic the question explores."
        + ("\nDo NOT ask anything similar to: " + " | ".join(avoid) + ". Choose a different topic or aspect."
           if avoid else "")
    )
    # Output tokens are the slow part (~20/s locally): keep the limit close to what a short question needs.
    nq = _structured_call(db, user_id, "interview_question", system, prompt, NextQuestion,
                          max_tokens=450 if coaching else 300, on_delta=on_delta).model_dump()
    from .interview_engine import strip_robotic
    nq["question"] = strip_robotic(strip_greeting(" ".join(nq["question"].split())))[:1000]
    keep_preface = (struggling and hints) or (coaching and bool(history))
    nq["preface"] = _speakable(" ".join(nq["preface"].split()))[:600] if keep_preface else ""
    if not nq["question"].strip():
        raise AIUnavailable("The local AI returned an empty question. Please try again.", 502)
    return nq


class QuickScore(BaseModel):
    answers_the_question: bool
    # Named BEFORE the scores so the model looks for gaps first (calibration 2026-11-04). "none" for a complete
    # answer. Default "" keeps older stored/mocked outputs valid.
    missing_point: str = ""
    relevance: int
    correctness: int
    completeness: int
    clarity: int
    communication: int
    # (No "recommended next difficulty" field: the adaptive rule is deterministic, and every output token costs
    # ~50 ms on the local model.)


class AnswerFeedback(BaseModel):
    strengths: list[str]
    missing_concepts: list[str]
    improvements: list[str]
    feedback: str
    better_answer_hint: str
    sample_answer: str


# Off-topic check with sentence embeddings, calibrated on real examples (README "Answer evaluation"):
# technical/project answers that address the question score 0.37-0.80 similarity to it, off-topic ones
# -0.01-0.13. HR/behavioural answers can be on-topic with very low similarity ("Tell me about yourself" 0.07),
# so the check is only used for technical and project questions.
OFF_TOPIC_SIMILARITY = 0.20
SIMILARITY_CHECKED_TYPES = {"technical", "project"}
# Open questions ("Walk me through your most significant project") share almost no words with a good, concrete
# answer: calibration (eval/calibration_set.json, 2026-11-04) measured 0.13-0.17 similarity for strong on-topic
# project answers, inside the off-topic range. A question is "open" when it is close to these generic prompts
# (measured: open 0.72-0.74, specific questions 0.11-0.49); for open questions only the model's own
# answers_the_question judgement is used.
OPEN_QUESTION_TEMPLATES = ("Tell me about a project you have worked on.",
                           "Describe your most important project and your role in it.")
OPEN_QUESTION_SIMILARITY = 0.60


def question_is_open(question: str) -> bool:
    from . import embeddings
    try:
        v = embeddings.embed([question, *OPEN_QUESTION_TEMPLATES])
    except embeddings.EmbeddingUnavailable:
        return False
    return max(float(v[0] @ t) for t in v[1:]) >= OPEN_QUESTION_SIMILARITY
_side_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-side")


def answer_similarity(question: str, answer: str) -> float | None:
    from . import embeddings
    try:
        v = embeddings.embed([question, answer])
        return round(float(v[0] @ v[1]), 3)
    except embeddings.EmbeddingUnavailable:
        return None


CRITERIA = ("relevance", "correctness", "completeness", "clarity", "communication")
_NON_ANSWERS = re.compile(r"^\s*(i\s*(do\s*not|don'?t)\s*know|no\s*idea|not\s*sure|pass|skip|n/?a|idk|-+|\.+)\s*[.!]*\s*$",
                          re.IGNORECASE)


def apply_answer_rules(ev: dict, question: str, answer: str, *, question_type: str = "technical",
                       similarity: float | None = None, open_question: bool = False) -> list[str]:
    """Deterministic checks layered on top of the model's scores. Mutates `ev`; returns notes for the student."""
    notes = []
    for k in CRITERIA:
        ev[k] = int(_clamp(ev.get(k, 0), 0, 10))
    off_topic_by_meaning = (question_type in SIMILARITY_CHECKED_TYPES and not open_question
                            and similarity is not None and similarity < OFF_TOPIC_SIMILARITY)
    if off_topic_by_meaning or ev.get("answers_the_question") is False:
        ev["relevance"] = min(ev["relevance"], 2)
        ev["completeness"] = min(ev["completeness"], 2)
        notes.append("Your answer does not seem to address the question that was asked, so relevance and "
                     "completeness were capped at 2/10." +
                     (f" (meaning similarity to the question: {similarity:.2f})" if off_topic_by_meaning else ""))
    words = len(answer.split())
    if _NON_ANSWERS.match(answer) or words == 0:
        for k in CRITERIA:
            ev[k] = min(ev[k], 1)
        notes.append("No real answer was given, so all criteria were capped at 1/10.")
    elif words < 8:
        for k in CRITERIA:
            ev[k] = min(ev[k], 3)
        notes.append(f"The answer is very short ({words} words), so scores were capped at 3/10.")
    elif words < 25:
        ev["completeness"] = min(ev["completeness"], 5)
        notes.append("Short answer: completeness capped at 5/10.")
    q_norm, a_norm = " ".join(question.lower().split()), " ".join(answer.lower().split())
    if a_norm and (a_norm == q_norm or (len(a_norm) > 20 and a_norm in q_norm)):
        for k in CRITERIA:
            ev[k] = min(ev[k], 1)
        notes.append("The answer repeats the question, so it was not given credit.")
    if ev["correctness"] > ev["relevance"] + 3:
        ev["correctness"] = ev["relevance"] + 3
        notes.append("Correctness was limited because the answer was only partly relevant to the question.")
    # A mostly wrong technical answer can't be "relevant, complete and clear" (calibration 2026-11-04: qwen3:4b gave
    # "PUT is for putting, PATCH is for patching, I use POST for everything" relevance 8 and 51/100).
    if (WRONG_ANSWER_CAP and question_type == "technical" and ev["correctness"] <= 3
            and max(ev["relevance"], ev["completeness"], ev["clarity"]) > ev["correctness"] + 2):
        for k in ("relevance", "completeness", "clarity"):
            ev[k] = min(ev[k], ev["correctness"] + 2)
        notes.append("The answer is mostly incorrect, so relevance, completeness and clarity were limited too.")
    # The model named something important that is missing: the answer can't be complete (9-10).
    gap = str(ev.get("missing_point") or "").strip().strip(".").lower()
    if MISSING_POINT_CAP and gap and gap not in _NO_GAP and ev["completeness"] > 7:
        ev["completeness"] = 7
    return notes


_NO_GAP = {"none", "nothing", "n/a", "na", "-", "nothing important", "nothing important is missing", "no"}
MISSING_POINT_CAP = True
WRONG_ANSWER_CAP = True  # eval/calibrate_scoring.py --baseline switches the 2026-11-04 rules off for comparison


def next_difficulty(current: str, score: float | None, *, up: float = 75, down: float = 45) -> str:
    """Adaptive rule: >= `up` moves up a level, < `down` moves down, otherwise stays. The thresholds depend on the
    interviewer (services/interviewers.py); the defaults are the standard ones documented in the README."""
    levels = ["easy", "medium", "hard"]
    i = levels.index(current) if current in levels else 1
    if score is None:
        return levels[i]
    if score >= up:
        i = min(i + 1, 2)
    elif score < down:
        i = max(i - 1, 0)
    return levels[i]


EVALUATOR_SYSTEM = ("You are a fair, rigorous interview evaluator. Score honestly - short, off-topic or incorrect "
                    "answers must receive low scores, and an answer that talks about something else than the "
                    "question must get relevance 0-2 even if it is well written. Judge only the content and "
                    "structure of the answer: never consider accent, spelling caused by speech recognition, "
                    "gender, ethnicity, disability or any other personal characteristic. Keep knowledge separate "
                    "from language: grammar mistakes and imperfect English must NOT lower relevance, correctness "
                    "or completeness - they may only affect the communication criterion. The interviewer's "
                    "personality never changes how you score. ")


# Anchors for every 0-10 criterion. Before them (calibration 2026-11-04, Gemini Flash-Lite) 4 of 16 hand-labelled
# answers got 100, including one labelled "good" (a key point missing), and "fair" answers averaged 62.
SCORE_ANCHORS = ("Use the whole scale: 10 = flawless, an expert would add nothing; 8-9 = strong, only a minor gap; "
                 "6-7 = right idea but a key point, trade-off or concrete example is missing; 4-5 = partly right, "
                 "vague or generic; 1-3 = mostly wrong, off-topic or empty; 0 = no answer. Give 10 only when nothing "
                 "important is missing. A short correct answer without depth is a 5-6 on completeness, not 8.")
# Completeness is scored but is not one of the four default rubric criteria, so without this it never moved the
# total: a correct-but-shallow answer scored like a complete one. When the rubric gives it no weight, it is blended
# in at this share of the 0-100 score.
COMPLETENESS_SHARE = 0.20
MISSING_POINT_PROMPT = ("Then write missing_point: the single most important thing a top candidate would have added "
                        "(a key concept, trade-off, concrete example or result), in at most 12 words, or \"none\" if "
                        "nothing important is missing.\n")


def weighted_score(ev: dict, rubric: list[dict]) -> float:
    """0-100 from the 0-10 criteria: the rubric-weighted average, with completeness blended in when the rubric
    leaves it out (COMPLETENESS_SHARE)."""
    weights = {c["name"].lower(): float(c.get("weight", 0)) for c in rubric}
    if not any(weights.get(k) for k in CRITERIA):
        weights = {k: 1.0 for k in ("relevance", "correctness", "clarity", "communication")}
    total_w = sum(weights.get(k, 0) for k in CRITERIA)
    base = sum(ev[k] * weights.get(k, 0) for k in CRITERIA) / total_w * 10
    if not weights.get("completeness") and "completeness" in ev:
        base = base * (1 - COMPLETENESS_SHARE) + ev["completeness"] * 10 * COMPLETENESS_SHARE
    return round(base, 1)


def score_answer(db: Session, user_id: int, *, job_role: str, question: str, question_type: str,
                 answer: str, rubric: list[dict], difficulty: str = "medium", interviewer: str = "aria") -> dict:
    """FAST step (scores only, ~60 output tokens): used to choose the next question right away.

    The model scores relevance, correctness, completeness, clarity and communication (0-10); rule-based checks
    (`apply_answer_rules`) then cap scores for off-topic or very short answers. The 0-100 `score` is the
    rubric-weighted average. `interviewer` only sets how quickly the NEXT question gets harder/easier; the scores
    never depend on it.
    """
    from . import interviewers
    persona = interviewers.get(interviewer)
    criteria = "\n".join(f"- {c['name']} (weight {c.get('weight', 0)}): {c.get('description', '')}" for c in rubric)
    prompt = (
        f"Role: {job_role}\nQuestion type: {question_type}\nQuestion difficulty: {difficulty}\n"
        f"Question: {question}\n{fence('answer', answer)}\n\n"
        f"Evaluation rubric:\n{criteria}\n\n"
        "First decide answers_the_question: does the answer actually respond to THIS question (true/false)?\n"
        f"{MISSING_POINT_PROMPT}"
        "Then score each criterion as an integer 0-10:\n"
        "- relevance: does it answer the question asked?\n"
        "- correctness: are the facts/reasoning right? (for HR/behavioral: soundness and honesty)\n"
        "- completeness: are the key points covered?\n"
        "- clarity: is it well structured, with examples?\n"
        "- communication: professional, concise language (ignore transcription errors).\n"
        f"{SCORE_ANCHORS}"
    )
    # The meaning-similarity check (embeddings, CPU) runs while the model is scoring instead of after it.
    sim_future = _side_pool.submit(lambda: answer_similarity(question, answer))
    open_future = (_side_pool.submit(lambda: question_is_open(question))
                   if question_type in SIMILARITY_CHECKED_TYPES else None)
    ev = _structured_call(db, user_id, "answer_scoring", EVALUATOR_SYSTEM + _strictness(db), prompt, QuickScore,
                          max_tokens=200).model_dump()
    sim = sim_future.result()
    open_q = bool(open_future and open_future.result())
    notes = apply_answer_rules(ev, question, answer, question_type=question_type, similarity=sim,
                               open_question=open_q)
    ev["score"] = weighted_score(ev, rubric)
    ev["details"] = {
        "completeness": ev["completeness"],
        "content_score": round((ev["relevance"] + ev["correctness"] + ev["completeness"]) / 3 * 10, 1),
        "communication_score": round((ev["clarity"] + ev["communication"]) / 2 * 10, 1),
        "answers_the_question": ev["answers_the_question"],
        "question_answer_similarity": sim,
        "open_question": open_q,
        "band": scoring_bands.band(ev["score"]),
        "next_difficulty": next_difficulty(difficulty, ev["score"], up=persona.difficulty_up,
                                           down=persona.difficulty_down),
        "rule_notes": notes,
        "feedback_status": "pending",
        "disclaimer": "AI-estimated score from a local model. It is practice feedback, not proof that the answer "
                      "is factually correct.",
    }
    ev.update(feedback="", better_answer_hint="", sample_answer="")
    return ev


def _feedback_voice(interviewer: str) -> str:
    from . import interviewers
    p = interviewers.get(interviewer)
    return f"Write the feedback in the voice of {p.name}, the interviewer. Tone: {p.feedback_style}"


def answer_feedback(db: Session, user_id: int, *, job_role: str, question: str, question_type: str,
                    answer: str, scored: dict, interviewer: str = "aria", priority: str = "interactive") -> dict:
    """SLOW step (tips + sample answer, ~900 tokens): runs in the background after the next question is ready, at
    background priority so it gives way whenever the candidate is waiting for the interviewer."""
    scores = ", ".join(f"{k} {scored[k]}/10" for k in CRITERIA)
    prompt = (
        f"Role: {job_role}\nQuestion type: {question_type}\nQuestion: {question}\n"
        f"{fence('answer', (answer or '')[:1500])}\n\n"
        f"The answer has already been scored: {scores}. Do not re-score it.\n"
        "Give 1-3 strengths (empty only if there are none), the missing_concepts a strong answer would include "
        "(at least one unless the answer is complete), 2-4 specific improvements (never empty), 2-3 sentences of "
        "feedback, a one-sentence better_answer_hint, and a concise sample_answer (60-120 words) a "
        "well-prepared fresh graduate could give.\n" + _feedback_voice(interviewer)
    )
    fb = _structured_call(db, user_id, "answer_feedback", EVALUATOR_SYSTEM, prompt, AnswerFeedback,
                          max_tokens=900, priority=priority).model_dump()
    improvements = _clean_list(fb["improvements"], 5)
    if not improvements and scored.get("score", 0) < 90:  # never leave a student without guidance
        improvements = _clean_list([fb.get("better_answer_hint")], 1) or \
            ["Compare your answer with the sample answer below and add the points you missed."]
    return {"strengths": _clean_list(fb["strengths"], 4), "missing_concepts": _clean_list(fb["missing_concepts"], 6),
            "improvements": improvements, "feedback": fb["feedback"].strip(),
            "better_answer_hint": fb["better_answer_hint"].strip(), "sample_answer": fb["sample_answer"].strip()}


def evaluate_answer(db: Session, user_id: int, *, job_role: str, question: str, question_type: str,
                    answer: str, rubric: list[dict], difficulty: str = "medium", interviewer: str = "aria") -> dict:
    """Score + feedback in one go (used by 'Retry evaluation')."""
    ev = score_answer(db, user_id, job_role=job_role, question=question, question_type=question_type,
                      answer=answer, rubric=rubric, difficulty=difficulty, interviewer=interviewer)
    fb = answer_feedback(db, user_id, job_role=job_role, question=question, question_type=question_type,
                         answer=answer, scored=ev, interviewer=interviewer)
    ev["details"].update({k: fb[k] for k in ("strengths", "missing_concepts", "improvements")},
                         feedback_status="completed")
    ev.update(feedback=fb["feedback"], better_answer_hint=fb["better_answer_hint"], sample_answer=fb["sample_answer"])
    return ev


class InterviewReport(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    recommended_practice: list[str]
    closing_remarks: str


def interview_report(db: Session, user_id: int, *, job_role: str, category: str, qa: list[dict],
                     interviewer: str = "aria") -> dict:
    """Final interview report from all questions, answers and scores: summary, strengths, weaknesses,
    improvement suggestions, recommended practice, and short closing remarks in the interviewer's voice.
    """
    from . import interviewers
    p = interviewers.get(interviewer)
    system = ("You are a senior placement coach writing a concise, honest post-interview report for a student. "
              "Give actionable feedback about the answers only - never psychological conclusions or guesses about "
              "personality, intelligence or emotions. Keep technical knowledge separate from English fluency.")
    body = "\n\n".join(
        f"Q{i + 1} [{x['type']}]: {x['question']}\n{fence('answer', (x['answer'] or '')[:ANSWER_CHARS_IN_PROMPT])}"
        f"\nScore: {x.get('score')}/100"
        for i, x in enumerate(qa))
    prompt = (f"Role: {job_role}\nFocus: {category}\n\n{body}\n\n"
              "Write a 2-4 sentence summary, 2-4 strengths, 2-4 weaknesses, 3-5 concrete improvement suggestions "
              "and 2-3 recommended practice activities (e.g. 'Practise 3 SQL join questions'). Each list item is ONE "
              "specific sentence naming the question or topic it refers to. Base everything on the answers above.\n"
              f"Also write closing_remarks: 2-3 short spoken sentences (plain text, under 60 words) that {p.name}, "
              f"the interviewer, says to the candidate at the end. Tone: {p.feedback_style}")
    out = _structured_call(db, user_id, "interview_report", system, prompt, InterviewReport,
                           max_tokens=900).model_dump()
    out["closing_remarks"] = _speakable(out["closing_remarks"])[:600]
    out["interviewer"] = p.id
    return out


# --------------------------------------------------------------------------- re-exports (public API of this module)
from .ai_base import (  # noqa: E402,F401
    STRICTNESS_GUIDE, UNTRUSTED_NOTE, ai_status,
)
from .ai_english import (  # noqa: E402,F401
    ARIA_INTERVIEW_PERSONA, ARIA_SYSTEM, AVATAR_REPLY_MODES, CHAT_TEMPERATURE, ENGLISH_RULES, ENGLISH_STYLES,
    SEMANTIC_REPEAT, STYLE_GUIDE, Correction, EnglishEvaluation, EnglishReply, apply_correction_policy,
    clean_english_reply, drop_repeated_opener, english_evaluate, english_reply, english_system, repeats_earlier_turn,
)
from .ai_resume import (  # noqa: E402,F401
    RESUME_SCORE_RULES, SOFT_SKILL_EVIDENCE, ResumeEducation, ResumeExperience, ResumeExtraction, ResumeProject,
    ResumeSkillItem, analyze_resume, resume_completeness, validate_resume_extraction,
)
from .ai_tasks import (  # noqa: E402,F401
    MCQ, CodeReview, GeneratedAssessment, MatchReview, Recommendation, RoleRecommendations, RoleSuggestion,
    StudentRecommendations, TestCaseVerdict, evaluate_code, generate_assessment, job_role_recommendations,
    match_review, student_recommendations,
)

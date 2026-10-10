"""Interview intelligence that does not depend on the language model.

The model writes each question; this module decides what it should be about and checks what comes back:
  * candidate_context()  - the resume facts a question may use (projects WITH description, technologies and the
                           candidate's role, internships, education, skills). Nothing else may be presented as fact.
  * answer_signals()     - deterministic reading of the last answer: vague contribution ("we did it"), unmeasured
                           claims ("improved the performance"), unexplained AI, very short, self-correction,
                           uncertainty, a request to repeat. Each signal suggests the most useful follow-up.
  * coverage()           - which (topic, aspect) pairs were already assessed and which still need assessment, so a
                           topic plan guides the interview without turning it into a checklist.
  * is_duplicate()       - repeated-question detection at three levels: wording, canonical form ("Tell me about /
                           Explain / Describe the X project" are the same question) and meaning (sentence embeddings,
                           threshold calibrated on real paraphrases), plus a same-topic-same-aspect concept check.
  * validate_question(), strip_robotic() - output checks (length, no JSON/metadata, one question, no stock praise).
  * fallback_question()  - resume-grounded template questions used when generation keeps failing, so an interview
                           can never get stuck.
"""
from __future__ import annotations

import difflib
import logging
import re

log = logging.getLogger("hiresense.interview_engine")

ASPECTS = ("overview", "objective", "personal_contribution", "architecture", "decision", "error_handling", "testing",
           "scaling", "limitations", "result", "lessons", "concept", "scenario", "teamwork", "conflict", "feedback",
           "adaptability", "motivation", "learning")
FOLLOWUP_KINDS = ("deepen", "example", "clarify", "test_understanding", "tradeoff", "result_lesson", "new_topic")

SEMANTIC_DUPLICATE = 0.78  # MiniLM cosine. Real paraphrases measured 0.81-0.94; distinct follow-ups <= 0.69.


# --------------------------------------------------------------------------- candidate context

def _short(s, n=220) -> str:
    return " ".join(str(s or "").split())[:n]


def candidate_context(analysis: dict | None, profile_skills: list[str] | None = None) -> dict:
    a = analysis or {}
    skills = list(profile_skills or [])
    skills += [s["name"] for s in a.get("skills", []) if s.get("name") and s.get("category") != "soft_skill"
               and s["name"] not in skills]
    return {
        "summary": _short(a.get("candidate_summary"), 500),
        "projects": [{"name": _short(p.get("name"), 80), "description": _short(p.get("description")),
                      "technologies": [t for t in (p.get("technologies") or [])][:8]}
                     for p in a.get("projects", []) if p.get("name")][:5],
        "work": [{"organization": _short(e.get("organization"), 80), "role": _short(e.get("role"), 60),
                  "summary": _short(e.get("summary"), 160)}
                 for e in (a.get("internships", []) + a.get("experience", [])) if e.get("organization")][:4],
        "education": [_short(f"{e.get('degree', '')} {e.get('field', '')}, {e.get('institution', '')}", 120)
                      for e in a.get("education", [])][:2],
        "skills": skills[:25],
        "topics": list(a.get("recommended_topics") or [])[:10],
    }


def context_block(ctx: dict) -> str:
    """Resume facts for the prompt. Only these may be referred to as the candidate's experience."""
    lines = [f"Summary: {ctx['summary'] or 'not available'}"]
    for p in ctx["projects"]:
        tech = f" [{', '.join(p['technologies'])}]" if p["technologies"] else ""
        lines.append(f"Project: {p['name']}{tech} - {p['description'] or 'no description given'}")
    for w in ctx["work"]:
        lines.append(f"Internship/work: {w['role'] or 'role not stated'} at {w['organization']} - {w['summary']}")
    if ctx["education"]:
        lines.append("Education: " + "; ".join(ctx["education"]))
    lines.append(f"Skills: {', '.join(ctx['skills']) or 'not available'}")
    if ctx["topics"]:
        lines.append(f"Topics worth checking: {', '.join(ctx['topics'])}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- the last answer

_WE = re.compile(r"\b(we|our|team|us|group)\b", re.IGNORECASE)
_I_DID = re.compile(r"\bI\s+(?:\w+\s+)?(built|wrote|made|designed|implemented|created|developed|added|fixed|used|"
                    r"handled|tested|set up|configured|was responsible|worked on|did)\b", re.IGNORECASE)
_CLAIM = re.compile(r"\b(improv\w*|faster|optimi[sz]\w*|better performance|more efficient|reduc\w+|increas\w+|"
                    r"reliable|scalable|secure)\b", re.IGNORECASE)
_MEASURE = re.compile(r"\d|percent|%|\bms\b|second|measured|benchmark|load test|profil", re.IGNORECASE)
_AI = re.compile(r"\b(AI|artificial intelligence|machine learning|ML|deep learning|chatgpt|LLM|model)\b")
_AI_DETAIL = re.compile(r"\b(classif\w+|predict\w*|train\w*|dataset|accuracy|regression|embedding|prompt|api)\b",
                        re.IGNORECASE)
_CORRECTION = re.compile(r"\b(sorry|actually|i mean|correction|to correct|i was wrong|i said earlier|i mentioned "
                         r"earlier|not what i meant)\b", re.IGNORECASE)
_UNSURE = re.compile(r"\b(not (?:fully |very |really )?sure|i think|maybe|probably|i guess|i don'?t remember)\b",
                     re.IGNORECASE)
_REPEAT = re.compile(r"\b(repeat (?:the |that |your )?question|say (?:that|it) again|didn'?t (?:understand|get)|"
                     r"what do you mean|can you rephrase|pardon)\b", re.IGNORECASE)
_NON_ANSWER = re.compile(r"^\s*(i\s*(do\s*not|don'?t)\s*know|no\s*idea|not\s*sure|pass|skip|n/?a|idk)\W*$", re.IGNORECASE)


def answer_signals(answer: str | None) -> list[dict]:
    """What is missing or notable in the last answer, each with the follow-up that would help most.
    Codes are stored with the next question for auditing; the hints go into the prompt."""
    text = " ".join((answer or "").split())
    words = len(text.split())
    out: list[dict] = []

    def add(code, kind, hint):
        out.append({"code": code, "followup_kind": kind, "hint": hint})

    if not text or _NON_ANSWER.match(text):
        add("no_answer", "new_topic", "No real answer was given. Do not drill the same point: ask a simpler, "
                                      "different question the candidate can answer from their own experience.")
        return out
    if _REPEAT.search(text) and words < 25:
        add("repeat_request", "clarify", "The candidate asked to repeat or explain the question. Ask the SAME thing "
                                         "again in simpler words (this is allowed; set is_followup=true).")
        return out
    if _CORRECTION.search(text):
        add("self_correction", "clarify", "The candidate corrected something they said earlier. Accept the corrected "
                                          "fact without judgement and, if useful, ask one question that uses it.")
    if words < 8:
        add("very_short", "example", "The answer was very short. Invite one concrete example or detail, or make "
                                     "the question easier to start.")
    if _WE.search(text) and not _I_DID.search(text):
        add("vague_contribution", "clarify", "The candidate described team work without saying what THEY did. Ask "
                                             "which part they were personally responsible for.")
    if _CLAIM.search(text) and not _MEASURE.search(text):
        add("unmeasured_claim", "deepen", "The candidate made a claim (improved / faster / reliable ...) without "
                                          "evidence. Ask how they measured or know it.")
    if _AI.search(text) and not _AI_DETAIL.search(text):
        add("unexplained_ai", "clarify", "The candidate mentioned AI/ML without detail. Ask what exactly the AI "
                                         "component did and which part they implemented themselves.")
    if _UNSURE.search(text) and words >= 8:
        add("partly_unsure", "test_understanding", "The candidate was unsure about part of the answer. Probe that "
                                                   "specific unclear part instead of treating the whole answer as wrong.")
    if 8 <= words < 20 and not out:
        add("thin", "example", "The answer is thin. Ask for one specific example, decision or result.")
    return out


# --------------------------------------------------------------------------- history & coverage

def norm_topic(t: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (t or "").lower()))[:60]


def history_block(history: list[dict], full_last: int = 3) -> str:
    """Last `full_last` exchanges in full, earlier ones as one line each (topic, aspect, gist)."""
    if not history:
        return "(no questions asked yet)"
    lines = []
    cut = max(0, len(history) - full_last)
    for i, h in enumerate(history):
        m = h.get("meta") or {}
        tag = f"[{h.get('type') or '?'}, {h.get('difficulty') or '?'}"
        if m.get("topic"):
            tag += f", topic: {m['topic']}/{m.get('aspect') or '?'}"
        tag += "]"
        if i < cut:
            gist = " ".join((h.get("answer") or "(not answered)").split()[:20])
            lines.append(f"Q{i + 1} {tag}: {h['question']} -> answer gist: {gist}")
        else:
            lines.append(f"Q{i + 1} {tag}: {h['question']}\n<answer>\n{h.get('answer') or '(not answered)'}\n</answer>"
                         + (f"\nScore: {h['score']}/100" if h.get("score") is not None else ""))
    return "\n".join(lines)


def covered_pairs(history: list[dict]) -> set[tuple[str, str]]:
    return {(norm_topic((h.get("meta") or {}).get("topic")), (h.get("meta") or {}).get("aspect") or "")
            for h in history if (h.get("meta") or {}).get("topic")}


def coverage(history: list[dict], ctx: dict, aspect_order: tuple[str, ...], category: str,
             subject: str | None = None) -> dict:
    """Topics already explored and the most useful ones still open (guidance, not a script)."""
    done = covered_pairs(history)
    done_topics = {t for t, _ in done}
    open_items: list[str] = []
    subjects = []
    if category in ("technical", "mixed"):
        subjects += [p["name"] for p in ctx["projects"][:3]]
        subjects += [w["organization"] for w in ctx["work"][:1]]
    if subject:
        subjects.insert(0, subject)
    for name in subjects:
        t = norm_topic(name)
        missing = [a for a in aspect_order if (t, a) not in done]
        if missing:
            open_items.append(f"{name}: not yet asked about {', '.join(missing[:3]).replace('_', ' ')}")
    untouched_skills = [s for s in ctx["skills"] if norm_topic(s) not in done_topics
                        and not any(norm_topic(s) in t for t in done_topics)][:6]
    if untouched_skills and category in ("technical", "mixed"):
        open_items.append("Skills not yet checked: " + ", ".join(untouched_skills))
    if category in ("behavioral", "hr", "mixed", "communication"):
        behav = [a for a in ("teamwork", "conflict", "feedback", "adaptability", "learning", "motivation")
                 if not any(asp == a for _, asp in done)]
        if behav:
            open_items.append("Behavioural areas not yet explored: " + ", ".join(behav[:4]))
    return {"covered": sorted(f"{t} / {a}" for t, a in done if t), "open": open_items}


def stage(position: int, total: int) -> str:
    if position <= 1:
        return "opening - an approachable first question that helps the candidate settle in"
    if position >= total:
        return "closing - the last question: a reflective or forward-looking one (lessons learned, what next)"
    return "core - explore depth: decisions, trade-offs, problems, results"


# --------------------------------------------------------------------------- duplicates

_LEADS = re.compile(
    r"^(?:(?:so|okay|ok|now|next|alright|right|and|well|great|thanks|thank you)[, ]+)*"
    r"(?:(?:can|could|would|will) you (?:please )?|please |i'?d like you to |i want you to |let'?s |let me ask )?"
    r"(?:tell me (?:a (?:bit|little) )?(?:more )?about|talk (?:me )?(?:through|about)|walk me through|explain|describe|"
    r"give (?:me )?an overview of|share|elaborate on|what can you tell me about|speak about)\s+", re.IGNORECASE)
_GENERIC = {"the", "a", "an", "your", "you", "my", "me", "this", "that", "of", "for", "in", "on", "to", "and", "about",
            "project", "projects", "system", "app", "application", "built", "build", "made", "make", "developed",
            "created", "did", "do", "work", "worked", "please", "briefly", "detail", "details", "more", "bit",
            "little", "some", "with", "which", "one", "it", "is", "was", "are", "were", "have", "had", "used"}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split())


def canonical(text: str) -> frozenset[str]:
    """Content stems after removing the request wording: 'Tell me about your hospital management project' and
    'Describe the project you built for hospital management' both become {hospi, manag}."""
    t = _LEADS.sub("", " ".join((text or "").split()))
    return frozenset(w[:5] for w in _norm(t).split() if w not in _GENERIC and len(w) > 1)


def lexical_repeat(text: str, previous: list[str]) -> bool:
    a = _norm(text)
    a_words = {w for w in a.split() if len(w) > 3}
    for p in previous:
        b = _norm(p)
        if not a or not b:
            continue
        if difflib.SequenceMatcher(None, a, b).ratio() >= 0.8:
            return True
        b_words = {w for w in b.split() if len(w) > 3}
        if a_words and b_words and len(a_words & b_words) / len(a_words | b_words) >= 0.7:
            return True
    return False


def is_duplicate(text: str, previous: list[str], *, meta: dict | None = None, previous_meta: list[dict] | None = None,
                 similarity=None, allow_repeat: bool = False) -> tuple[bool, str | None]:
    """(duplicate?, reason code). `similarity(a, list_b) -> list[float]` is optional (embeddings may be off).

    `allow_repeat` is set when the candidate asked for the question to be repeated."""
    if allow_repeat or not previous:
        return False, None
    if lexical_repeat(text, previous):
        return True, "same_wording"
    c = canonical(text)
    for p in previous:
        pc = canonical(p)
        if c and c == pc:
            return True, "same_request"
    if similarity is not None:
        try:
            sims = similarity(text, previous)
        except Exception:  # embeddings are an optional check; never block an interview on them
            log.warning("semantic duplicate check unavailable")
            sims = []
        if any(s >= SEMANTIC_DUPLICATE for s in sims):
            return True, "same_meaning"
    if meta and previous_meta:
        t, asp = norm_topic(meta.get("topic")), meta.get("aspect")
        if t and asp and asp != "overview" and any(
                norm_topic(m.get("topic")) == t and m.get("aspect") == asp for m in previous_meta if m):
            return True, "same_concept"
    return False, None


def embedding_similarity(text: str, previous: list[str]) -> list[float]:
    from . import embeddings
    v = embeddings.embed([text] + previous)  # raises EmbeddingUnavailable -> caller treats as "no check"
    return [float(x) for x in (v[1:] @ v[0])]


# --------------------------------------------------------------------------- output checks

_ROBOTIC = re.compile(
    r"^(?:(?:(?:that'?s|that is|what)\s+)?(?:an?\s+)?(?:really\s+)?(?:great|excellent|good|wonderful|fantastic|"
    r"interesting) (?:answer|point|response|question)[.!,]?\s*|(?:great|excellent|interesting|wonderful|fantastic|awesome|perfect|nice)[.!,]+\s*|"
    r"let'?s move on to the next question[.!,]?\s*|moving on to the next question[.!,]?\s*)+", re.IGNORECASE)


def strip_robotic(question: str) -> str:
    rest = _ROBOTIC.sub("", question or "").strip()
    rest = re.sub(r"\blet'?s move on to the next question[.!]?\s*", "", rest, flags=re.IGNORECASE).strip()
    return (rest[:1].upper() + rest[1:]) if len(rest.split()) >= 2 else (question or "").strip()


def validate_question(q: str, max_words: int) -> list[str]:
    problems = []
    if not q.strip():
        return ["empty"]
    if re.search(r"[{}\[\]<>]|\"\w+\"\s*:", q) or re.search(r"\b(json|question_type|is_followup)\b", q, re.I):
        problems.append("metadata_leak")
    if len(q.split()) > max_words:
        problems.append("too_long")
    if q.count("?") > 2:
        problems.append("several_questions")
    if re.search(r"\bas an ai\b|\blanguage model\b", q, re.I):
        problems.append("breaks_role")
    return problems


# --------------------------------------------------------------------------- fallback

PROJECT_TEMPLATES = {
    "objective": "What problem were you trying to solve with {p}?",
    "personal_contribution": "Which part of {p} did you build yourself?",
    "error_handling": "In {p}, how did you handle incorrect or incomplete input?",
    "testing": "How did you test that {p} worked correctly?",
    "scaling": "If the number of users of {p} grew a lot, what would you improve first?",
    "decision": "What was one technical decision you made in {p}, and why?",
    "limitations": "What are the main limitations of {p} today?",
    "lessons": "Looking back at {p}, what would you do differently now?",
}
GENERAL_TEMPLATES = (
    ("behavioral", "teamwork", "Tell me about a time you had to work closely with a teammate to solve a problem. "
                               "What did you do?"),
    ("behavioral", "conflict", "How would you handle a disagreement with a teammate about how to build something?"),
    ("behavioral", "feedback", "Tell me about a time you received feedback you initially disagreed with."),
    ("behavioral", "learning", "Describe a time you had to learn something new quickly. How did you approach it?"),
    ("hr", "motivation", "What kind of work in the {role} role are you most looking forward to, and why?"),
    ("technical", "scenario", "Your application works locally but fails after deployment. How would you investigate?"),
    ("technical", "scenario", "A bug appears shortly before a release. How would you decide what to do?"),
)


def fallback_question(ctx: dict, history: list[dict], *, role: str, category: str,
                      aspect_order: tuple[str, ...]) -> dict | None:
    """A resume-grounded question that is not a duplicate. Used only when generation keeps failing."""
    previous = [h["question"] for h in history]
    previous_meta = [h.get("meta") or {} for h in history]
    candidates: list[dict] = []
    if category in ("technical", "mixed"):
        for p in ctx["projects"][:3]:
            for asp in aspect_order:
                if asp in PROJECT_TEMPLATES:
                    candidates.append({"question": PROJECT_TEMPLATES[asp].format(p=p["name"]), "question_type": "project",
                                       "topic": p["name"], "aspect": asp, "skill": asp})
    for qtype, asp, text in GENERAL_TEMPLATES:
        if category == "mixed" or category == qtype or (category in ("hr", "communication") and qtype != "technical"):
            candidates.append({"question": text.format(role=role), "question_type": qtype, "topic": asp,
                               "aspect": asp, "skill": asp})
    for c in candidates:
        dup, _ = is_duplicate(c["question"], previous, meta=c, previous_meta=previous_meta)
        if not dup:
            return c
    return None

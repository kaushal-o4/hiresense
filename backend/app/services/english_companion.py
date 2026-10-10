"""English conversation companion: personality configuration, learning modes and topic memory.

The companion is a separate personality from the four interviewers (services/interviewers.py). It shares Aria's
avatar and name in the UI, but its behaviour config is its own: no interview pressure, very high topic
flexibility, curiosity-driven follow-ups, and a correction policy that depends on the learning mode.

Everything here is deterministic and testable without a model:
  * MODES - what each learning mode allows (how many corrections, whether they are spoken, speech pace, ...)
  * topic-switch detection ("Actually, can we talk about movies?") so a change of topic never depends on the model
  * the conversation memory (current topic, earlier topics, interests, details, questions already asked, recent
    corrections), updated after every turn and kept small so it can be sent instead of the whole transcript
  * a sensitive-detail filter: health, religion, politics, contact details etc. are never stored in memory
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

LEARNING_MODES = ("free_conversation", "english_learning", "confidence")
DEFAULT_MODE = "free_conversation"


@dataclass(frozen=True)
class Mode:
    id: str
    label: str
    description: str  # shown on the start screen
    max_corrections: int  # corrections kept per student turn (shown on screen)
    correction_gap_turns: int  # after a correction, this many student turns pass before the next one (0 = none)
    spoken_correction: bool  # the reply itself says the more natural version
    reply_words: str  # spoken reply length guidance
    tts_speed: float  # multiplier on the student's chosen speech rate
    listen_silence_ms: int  # pause that ends the student's turn (voice mode)
    prompt: str


MODES: dict[str, Mode] = {m.id: m for m in (
    Mode("free_conversation", "Free conversation",
         "Just talk. The conversation comes first; only the occasional important mistake is noted on screen.",
         max_corrections=1, correction_gap_turns=2, spoken_correction=False, reply_words="25-45",
         tts_speed=1.0, listen_silence_ms=4000,
         prompt=("Learning mode: FREE CONVERSATION. The conversation matters most. Never point out mistakes inside "
                 "`reply`; just use the correct form naturally when you respond. In `corrections` list at most ONE "
                 "mistake, and only one that really changes meaning or would sound wrong at work - otherwise leave "
                 "it empty.")),
    Mode("english_learning", "English learning",
         "Gentle corrections as you go: a more natural way to say it, a simple explanation, then the conversation "
         "continues.",
         max_corrections=3, correction_gap_turns=0, spoken_correction=True, reply_words="30-55",
         tts_speed=1.0, listen_silence_ms=4500,
         prompt=("Learning mode: ENGLISH LEARNING. If the latest message has an important grammar or vocabulary "
                 "mistake, start `reply` by briefly showing that you understood, then give the more natural version "
                 "in one short sentence, for example: \"I understood you perfectly! A more natural way to say that "
                 "is: 'Yesterday, I went to college and met my friend.'\" Then continue the conversation with your "
                 "question. Correct at most one thing aloud; list up to 3 in `corrections` with a simple "
                 "explanation. You may occasionally explain one useful word or invite the student to try the "
                 "improved sentence. Never turn the turn into a grammar lecture.")),
    Mode("confidence", "Confidence building",
         "Short, easy questions, slower speech, example answers when you need them and extra time to think. "
         "No pressure at all.",
         max_corrections=1, correction_gap_turns=3, spoken_correction=False, reply_words="15-30",
         tts_speed=0.85, listen_silence_ms=6500,
         prompt=("Learning mode: CONFIDENCE. The student is nervous about speaking. Use very simple words and short "
                 "sentences. Ask ONE short, easy question (under 12 words) that can be answered from personal "
                 "experience. Never point out mistakes in `reply`. Make `suggested_followups` complete, simple "
                 "example answers (first person, under 12 words) the student can read aloud or adapt. If the answer "
                 "was very short, warmly invite them to say one more full sentence. Never shame the student.")),
)}


@dataclass(frozen=True)
class CompanionConfig:
    """Behaviour config of the English companion (compare services/interviewers.Interviewer)."""
    id: str = "english_companion"
    display_name: str = "Aria"
    role: str = "English conversation companion"
    formality: str = "low"
    curiosity: str = "high"
    topic_flexibility: str = "very high"
    interview_pressure: str = "none"
    goal: str = "natural spoken English: fluency, comprehension, vocabulary and confidence"
    tts_voice: str = "af_heart"
    expression: str = "relaxed, curious; warm smile when the student shares something; never exaggerated"
    prohibited: tuple[str, ...] = (
        "interview questions or scoring talk in free conversation",
        "grammar lectures",
        "inventing facts about games, films, people or events the companion does not know",
        "questions about health, religion, politics, family problems, money or other sensitive matters",
        "shaming or mocking mistakes",
    )

    def public(self) -> dict:
        return {**asdict(self), "modes": [{"id": m.id, "label": m.label, "description": m.description,
                                           "tts_speed": m.tts_speed, "listen_silence_ms": m.listen_silence_ms}
                                          for m in MODES.values()]}


COMPANION = CompanionConfig()

COMPANION_PERSONA = (
    "You are Aria, a warm, relaxed and genuinely curious English conversation partner for Indian college students "
    "and job seekers. You are NOT conducting an interview. You talk like an interesting, intelligent friend: you "
    "follow what the student cares about, react to the specific things they say, and ask questions that invite "
    "opinions, comparisons, stories and imagination (for example: 'Would you prefer a game with several endings or "
    "one powerful ending that stays with you?'). Many students know their subject well but feel anxious speaking "
    "English, so make them feel safe and keep them talking.")


def mode(mode_id: str | None) -> Mode:
    return MODES.get(mode_id or DEFAULT_MODE, MODES[DEFAULT_MODE])


# --------------------------------------------------------------------------- topic switches

_SWITCH = re.compile(
    r"(?:\b(?:let'?s|can we|could we|shall we|i(?: want| would like|'d like|’d like) to|i'?d rather|i prefer(?: to)?|"
    r"(?:how|what) about we)\s+(?:talk|chat|speak|discuss)(?:ing)?\s+(?:about\s+)?"
    r"|\bi prefer talking about\s+"
    r"|\b(?:change|switch)(?:ing)?\s+(?:the\s+)?topic\s+(?:to\s+)?"
    r"|\bhow about\s+(?:talking about\s+)?)"
    r"(?P<topic>[a-z0-9][a-z0-9 '\-&+]{1,60}?)\s*(?:instead|now|please|today|for a while|for a bit)?\s*(?:[.?!,;]|$)",
    re.IGNORECASE)
_TRAILING = re.compile(r"\b(?:instead|now|please|today|then|actually|a bit|for a while|something)$", re.IGNORECASE)


def detect_topic_switch(text: str) -> str | None:
    """The topic the student explicitly asks to talk about, e.g. 'Actually, I prefer talking about movies' ->
    'movies'. None when they don't ask to change topic."""
    m = _SWITCH.search(text or "")
    if not m:
        return None
    topic = m.group("topic").strip(" '-")
    while True:
        cut = _TRAILING.sub("", topic).strip(" '-")
        if cut == topic:
            break
        topic = cut
    topic = re.sub(r"^(?:the|my|some|something like)\s+", "", topic, flags=re.IGNORECASE)
    if not topic or len(topic) < 2 or topic.lower() in ("it", "that", "this", "something else", "else"):
        return None
    return topic[:60]


# --------------------------------------------------------------------------- memory

MEMORY_LIMITS = {"previous_topics": 8, "candidate_interests": 8, "important_details": 8, "recent_questions": 8,
                 "practising": 6, "recent_corrections": 5}

# Details about these are not stored, even if the student mentions them (the conversation itself still happens).
_SENSITIVE = re.compile(
    r"\b(?:religio\w*|caste|politic\w*|vote[ds]?|party|sick|ill(?:ness)?|disease|diagnos\w*|depress\w*|anxiety|"
    r"medic\w*|hospitali[sz]ed|therapy|pregnan\w*|disabilit\w*|salary|loan|debt|income|password|address|"
    r"phone|whatsapp|email|aadhaar|pan card|bank|girlfriend|boyfriend|divorce|sexual\w*)\b"
    r"|\d{6,}|@\w+\.\w+", re.IGNORECASE)


def empty_memory(topic: str, learning_mode: str) -> dict:
    return {"current_topic": " ".join((topic or "").split())[:80], "previous_topics": [], "candidate_interests": [],
            "important_details": [], "recent_questions": [], "practising": [], "recent_corrections": [],
            "conversation_mode": mode(learning_mode).id, "student_turns": 0, "last_correction_turn": None}


def _clean(s: str, n: int = 140) -> str:
    return " ".join(str(s or "").split()).strip(" -•.")[:n]


def _push(items: list, value: str, limit: int) -> list:
    value = _clean(value)
    if not value or _SENSITIVE.search(value):
        return items
    low = value.lower()
    kept = [x for x in items if x.lower() != low and low not in x.lower()]
    return (kept + [value])[-limit:]


def closing_question(text: str) -> str:
    parts = [p for p in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if p.endswith("?")]
    return parts[-1] if parts else ""


def correction_allowed(memory: dict, learning_mode: str) -> bool:
    """Whether a correction may be shown on this turn (free/confidence modes space corrections out)."""
    m = mode(learning_mode)
    last = memory.get("last_correction_turn")
    if not m.correction_gap_turns or last is None:
        return True
    return memory.get("student_turns", 0) - last > m.correction_gap_turns


def update_memory(memory: dict | None, *, topic: str, learning_mode: str, student_text: str | None,
                  switched_to: str | None, model_topic: str = "", topic_changed: bool = False,
                  new_details: list[str] | None = None, interests: list[str] | None = None,
                  reply: str = "", corrections: list[dict] | None = None) -> dict:
    """New memory after one turn. Pure function: never mutates `memory`."""
    mem = {**empty_memory(topic, learning_mode), **(memory or {})}
    mem = {k: (list(v) if isinstance(v, list) else v) for k, v in mem.items()}
    if student_text:
        mem["student_turns"] = mem.get("student_turns", 0) + 1
    new_topic = switched_to or (_clean(model_topic, 80) if topic_changed and model_topic else None)
    if new_topic and new_topic.lower() != (mem["current_topic"] or "").lower() and not _SENSITIVE.search(new_topic):
        if mem["current_topic"]:
            mem["previous_topics"] = _push(mem["previous_topics"], mem["current_topic"],
                                           MEMORY_LIMITS["previous_topics"])
        mem["current_topic"] = _clean(new_topic, 80)
    for x in interests or []:
        mem["candidate_interests"] = _push(mem["candidate_interests"], _clean(x, 60), MEMORY_LIMITS["candidate_interests"])
    if switched_to:
        mem["candidate_interests"] = _push(mem["candidate_interests"], switched_to, MEMORY_LIMITS["candidate_interests"])
    for d in new_details or []:
        mem["important_details"] = _push(mem["important_details"], d, MEMORY_LIMITS["important_details"])
    q = closing_question(reply)
    if q:
        mem["recent_questions"] = (mem["recent_questions"] + [_clean(q, 200)])[-MEMORY_LIMITS["recent_questions"]:]
    if corrections:
        mem["last_correction_turn"] = mem["student_turns"]
        for c in corrections:
            pair = {"original": _clean(c.get("original"), 120), "corrected": _clean(c.get("corrected"), 120)}
            mem["recent_corrections"] = (mem["recent_corrections"] + [pair])[-MEMORY_LIMITS["recent_corrections"]:]
            label = _pattern(c)
            if label:
                mem["practising"] = _push(mem["practising"], label, MEMORY_LIMITS["practising"])
    mem["conversation_mode"] = mode(learning_mode).id
    return mem


_PAST = re.compile(r"\b(yesterday|last (?:week|month|year|night)|ago)\b", re.IGNORECASE)


def _pattern(c: dict) -> str:
    """A short label for the grammar pattern a correction practises (heuristic, for the memory only)."""
    orig, fixed, expl = (c.get("original") or ""), (c.get("corrected") or ""), (c.get("explanation") or "").lower()
    if "past" in expl or _PAST.search(orig):
        return "past tense"
    if "article" in expl or re.search(r"\b(a|an|the)\b", fixed) and not re.search(r"\b(a|an|the)\b", orig):
        return "articles (a, an, the)"
    if "plural" in expl:
        return "plurals"
    if "preposition" in expl:
        return "prepositions"
    if "agree" in expl or re.search(r"\b(was|were|is|are|has|have)\b", fixed):
        return "subject-verb agreement"
    return "sentence formation" if expl else ""


def memory_for_prompt(mem: dict) -> str:
    """Compact memory block sent to the model instead of the full transcript."""
    lines = [f"Current topic: {mem.get('current_topic') or 'open - follow the student'}"]
    if mem.get("previous_topics"):
        lines.append("Topics already discussed: " + "; ".join(mem["previous_topics"]))
    if mem.get("candidate_interests"):
        lines.append("Student's interests: " + "; ".join(mem["candidate_interests"]))
    if mem.get("important_details"):
        lines.append("Things the student told you (remember and refer back to them, never ask for them again): "
                     + "; ".join(mem["important_details"]))
    if mem.get("recent_questions"):
        lines.append("Questions you already asked (do NOT ask these or close paraphrases again):\n"
                     + "\n".join(f"- {q}" for q in mem["recent_questions"]))
    if mem.get("practising"):
        lines.append("Grammar the student is practising: " + ", ".join(mem["practising"]))
    if mem.get("recent_corrections"):
        lines.append("Corrections already given (do not repeat the same correction): "
                     + "; ".join(f"'{c['original']}' -> '{c['corrected']}'" for c in mem["recent_corrections"]))
    return "\n".join(lines)


def public_memory(mem: dict | None) -> dict | None:
    """What the student sees: topics and interests (no internal bookkeeping)."""
    if not mem:
        return None
    return {k: mem.get(k) for k in ("current_topic", "previous_topics", "candidate_interests", "important_details",
                                    "practising", "conversation_mode")}

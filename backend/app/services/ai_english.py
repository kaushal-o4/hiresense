"""Spoken-English practice with Aria: reply generation, cleanup of the reply, corrections, evaluation."""
from __future__ import annotations

import re

from pydantic import BaseModel
from ..odm import Session


from .ai_base import AIUnavailable, _clamp, _clean_list, _structured_call, fence


# =========================================================================== english

class Correction(BaseModel):
    original: str
    corrected: str
    explanation: str


class EnglishReply(BaseModel):
    reply: str
    avatar_mode: str
    encouragement: str
    corrections: list[Correction]
    suggested_followups: list[str]
    # conversation memory (stored server-side, never spoken)
    current_topic: str = ""
    topic_changed: bool = False
    new_details: list[str] = []
    interests: list[str] = []

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        # The model must fill every field; the defaults above only keep older stored/mocked replies valid.
        schema = super().model_json_schema(*args, **kwargs)
        schema["required"] = list(schema["properties"])
        return schema


ENGLISH_STYLES = ("free_talk", "interview")
AVATAR_REPLY_MODES = ("speaking", "encouraging")

ARIA_INTERVIEW_PERSONA = (
    "You are Aria, a warm, empathetic and encouraging AI interviewer and spoken-English coach for Indian college "
    "students and job seekers. Many of them know their subject well but feel anxious speaking English. Your job is "
    "to make them feel safe and keep them talking.")

ENGLISH_RULES = (
    "- Never judge, mock or intimidate. Treat every attempt with genuine warmth and patience.\n"
    "- `reply` is spoken aloud: about {reply_words} words, plain text, no lists, no emojis, and it always ends with "
    "one open, engaging question.\n"
    "- React to the SPECIFIC things the student just said (mention a detail from their latest message), then move "
    "the conversation forward with a NEW question. Never repeat or closely paraphrase one of your earlier turns, and "
    "never ask a question you already asked. When it fits, refer back to something the student told you earlier.\n"
    "- Prefer questions that invite opinions, comparisons, stories or imagination. Do not ask a bare 'Why?', "
    "'Anything else?' or 'Tell me more' without adding something specific.\n"
    "- Vary how you acknowledge answers and keep it natural; do not start every turn with praise such as 'Great!' "
    "or 'Excellent!'. Never quote the student's mistakes or filler words ('um', 'uh') back to them.\n"
    "- If the student mentions a game, film, player, show or anything you are not sure about, ask them about it "
    "instead of inventing facts.\n"
    "- If the student asks you to repeat or explain the question, say your previous question again in simpler words.\n"
    "- If the latest message looks garbled, off-topic or like a speech-recognition mistake (for example a random "
    "sentence that does not fit), kindly say you did not quite catch that and ask them to say it again.\n"
    "- Never ask about health, religion, politics, family problems, money or other sensitive personal matters.\n"
    "- `corrections`: real grammar/vocabulary ERRORS in the student's LATEST message only - never contractions, "
    "punctuation, style preferences, or rewrites of correct sentences, and none for a garbled message. `original` "
    "must be copied exactly from that message; `explanation` is one friendly, simple sentence. Most useful first. "
    "Empty list if the message was fine or the student has not spoken yet.\n"
    "- `encouragement`: one short line praising something specific (effort, a good word, clarity, a longer answer). "
    "Empty string before the student has spoken.\n"
    "- `avatar_mode`: 'encouraging' when the student sounds hesitant or nervous, gave a very short answer, or said "
    "something inspiring; otherwise 'speaking'.\n"
    "- `suggested_followups`: 2-3 short sentence starters (under 10 words each) the student could use to answer "
    "your question if they get stuck, written in first person.\n"
    "- Memory fields (never spoken): `current_topic` is a short noun phrase for what the conversation is about NOW; "
    "`topic_changed` is true only if the student moved to a different topic in the latest message; `new_details` "
    "lists 0-2 short facts the student just shared that are worth remembering (third person, e.g. 'prefers games "
    "where choices change the ending'; nothing sensitive); `interests` lists 0-2 short interest names from the "
    "latest message.")

STYLE_GUIDE = {
    "free_talk": ("Mode: English Free Talk. Follow the student's interests: start from the chosen topic, but if they "
                  "bring up something else (games, films, cricket, technology, food, travel, anything), go with it "
                  "naturally and never force the original topic. No interview questions."),
    "interview": ("Mode: Job Interview Practice. Act as a kind HR interviewer: ask one question at a time (for example "
                  "'Tell me about yourself', strengths and weaknesses, a conflict you resolved, a project walkthrough, "
                  "behavioural scenarios), react briefly to each answer, then move to a natural next question."),
}


def english_system(style: str, learning_mode: str) -> str:
    """System prompt for one English session: persona + shared rules + practice style + learning mode."""
    from . import english_companion as ec
    m = ec.mode(learning_mode)
    persona = ARIA_INTERVIEW_PERSONA if style == "interview" else ec.COMPANION_PERSONA
    return (persona + "\n" + ENGLISH_RULES.format(reply_words=m.reply_words) + "\n\n"
            + STYLE_GUIDE.get(style, STYLE_GUIDE["free_talk"]) + "\n" + m.prompt)


# Kept for callers/tests that read the base persona.
ARIA_SYSTEM = english_system("free_talk", "free_conversation")


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _words(s: str) -> str:
    """Lower-case words only: punctuation in a transcript comes from the speech recogniser, not the student."""
    return " ".join(re.findall(r"[a-z0-9']+", s.lower()))


# Emoji and pictographs: a TTS voice would read them out ("smiling face"), so spoken text never contains them.
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]+")


def _speakable(s: str) -> str:
    return " ".join(_EMOJI.sub(" ", s or "").split())


_UK_US = ((r"\bpractis", "practic"), (r"is(e|es|ed|ing|ation)\b", r"iz\1"), (r"(?<=[a-z]{2})our", "or"), (r"tre\b", "ter"),
          (r"ogue\b", "og"), (r"lled\b", "led"), (r"lling\b", "ling"))


def _spelling_neutral(s: str) -> str:
    """Words only, with British and American spellings mapped together (both are correct)."""
    w = _words(s)
    for pat, rep in _UK_US:
        w = re.sub(pat, rep, w)
    return w


def clean_english_reply(raw: dict, latest_student: str | None) -> dict:
    """Keep the model's output within the contract the UI relies on."""
    said = _norm(latest_student or "")
    corrections = []
    for c in raw.get("corrections") or []:
        orig, fixed = (c.get("original") or "").strip(), (c.get("corrected") or "").strip()
        # Drop invented quotes, no-op / punctuation-only / British-vs-American spelling "fixes" (the real-model eval
        # 'corrected' the correct British verb "practise"), and rewrites far longer than what was said.
        if (said and orig and fixed and _spelling_neutral(orig) != _spelling_neutral(fixed)
                and _norm(orig) in said and len(fixed.split()) <= 2 * len(orig.split()) + 3):
            corrections.append({"original": orig, "corrected": fixed, "explanation": (c.get("explanation") or "").strip()})
    mode = (raw.get("avatar_mode") or "").strip().lower()
    return {
        "reply": _speakable(raw.get("reply")),
        "avatar_mode": mode if mode in AVATAR_REPLY_MODES else "speaking",
        "encouragement": _speakable(raw.get("encouragement"))[:200] if said else "",
        "corrections": corrections[:3],
        "suggested_followups": [s for s in _clean_list(map(_speakable, raw.get("suggested_followups") or []), 6)
                                if len(s) <= 90][:3],
    }


CHAT_TEMPERATURE = 0.7  # conversation needs variety; scoring keeps the low default temperature


def _similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _words(a), _words(b)).ratio()


def repeats_earlier_turn(reply: str, earlier: list[str], threshold: float = 0.75) -> bool:
    """True when `reply` (or its closing question) is a near-copy of one of Aria's earlier turns."""
    def question(t: str) -> str:
        parts = [p for p in re.split(r"(?<=[.!?])\s+", t.strip()) if p.endswith("?")]
        return parts[-1] if parts else ""
    q = question(reply)
    return any(_similar(reply, e) >= threshold or (q and _similar(q, question(e)) >= 0.85) for e in earlier)


SEMANTIC_REPEAT = 0.80  # MiniLM cosine between two closing questions; paraphrases measured 0.81-0.94 (README)


def _semantic_repeat(question: str, earlier: list[str]) -> bool:
    """Paraphrased repeat of an earlier closing question, judged by meaning (skipped if embeddings are off)."""
    from . import embeddings
    earlier = [e for e in earlier if e][-8:]
    if not question or not earlier:
        return False
    try:
        v = embeddings.embed([question] + earlier)
    except embeddings.EmbeddingUnavailable:
        return False
    return bool(((v[1:] @ v[0]) >= SEMANTIC_REPEAT).any())


def _mentions_topic(reply: str, topic: str) -> bool:
    stems = [w[:5] for w in re.findall(r"[a-z]+", topic.lower()) if len(w) > 3] or \
        [w for w in re.findall(r"[a-z]+", topic.lower()) if len(w) > 1]  # e.g. "AI"
    words = re.findall(r"[a-z]+", reply.lower())
    return not stems or any(w.startswith(s) or (len(w) >= 4 and s.startswith(w)) for s in stems for w in words)


def _opener(text: str) -> str:
    return " ".join(_words(text).split()[:3])


_LEADING_FILLER = re.compile(r"^(?:u+h*m+|u+h+|e+r+m*)\b[,.!?]?\s*", re.IGNORECASE)


def drop_repeated_opener(reply: str, earlier: list[str]) -> str:
    """Real-model eval: replies kept starting 'I love that you mentioned...' / 'That's such a cool detail...'. If the
    first sentence opens like one of the last replies, drop it (when enough of the reply is left). A leading 'Um'
    echoed from the student ('Um yes one match? ...') is removed too - it can sound like mockery."""
    reply = _LEADING_FILLER.sub("", reply.strip())
    reply = reply[:1].upper() + reply[1:]
    parts = re.split(r"(?<=[.!?])\s+", reply.strip(), maxsplit=1)
    if len(parts) == 2 and len(parts[1].split()) >= 6 and _opener(parts[0]) in {_opener(e) for e in earlier if e}:
        return parts[1]
    return reply


def apply_correction_policy(out: dict, *, learning_mode: str, memory: dict) -> dict:
    """Learning-mode rules enforced in code: how many corrections, how often, and whether one is spoken."""
    from . import english_companion as ec
    m = ec.mode(learning_mode)
    given = {_words(c.get("original", "")) for c in memory.get("recent_corrections") or []}
    fixes = [c for c in out["corrections"] if _words(c["original"]) not in given]  # never the same correction twice
    if not ec.correction_allowed(memory, learning_mode):
        fixes = []
    out = {**out, "corrections": fixes[:m.max_corrections]}
    if m.spoken_correction and out["corrections"]:
        first = out["corrections"][0]["corrected"].strip().rstrip(".!?,;")
        if _words(first) not in _words(out["reply"]):  # the model forgot to say it: add it, briefly
            out["reply"] = f"A more natural way to say that is: \"{first}.\" {out['reply']}"
    return out


def english_reply(db: Session, user_id: int, *, topic: str, history: list[dict], style: str = "free_talk",
                  learning_mode: str = "free_conversation", memory: dict | None = None,
                  synthetic_opening: bool = False, on_delta=None, focus: list[str] | None = None) -> dict:
    """Aria's next turn plus the updated conversation memory (`out["memory"]`).

    The model gets a compact memory (topics, interests, details, questions already asked, corrections given) and
    only the last few messages instead of the whole transcript. A topic change requested by the student is detected
    in code, and repeated questions are rejected by wording AND meaning, then regenerated once."""
    from . import english_companion as ec
    mem = {**ec.empty_memory(topic, learning_mode), **(memory or {})}
    system = english_system(style, learning_mode)
    recent = history[-8:]
    latest = recent[-1]["content"] if recent and recent[-1]["sender"] == "student" else None
    student_text = None if synthetic_opening else latest
    switched_to = ec.detect_topic_switch(student_text) if student_text else None
    earlier_ai = [m["content"] for m in history if m["sender"] == "ai"]
    earlier_questions = [ec.closing_question(t) for t in earlier_ai] + list(mem.get("recent_questions") or [])
    convo = "\n".join(
        (fence("student_message", m["content"]) if m["sender"] == "student" else f"Aria: {m['content']}")
        for m in (recent[:-1] if latest else recent))
    asked = "\n".join(f"- {q}" for q in earlier_ai[-4:])
    openers = sorted({" ".join(t.split()[:4]) for t in earlier_ai[-3:] if t})
    prompt = (f"Starting topic chosen by the student: {topic}\n\nConversation memory:\n{ec.memory_for_prompt(mem)}\n\n"
              + (f"Do not start your reply the way your recent replies started ({' / '.join(openers)}...).\n\n"
                 if openers else "")
              + f"Recent conversation:\n{convo or '(none)'}\n\n"
              + (f"Things you (Aria) already said - do NOT repeat them or ask the same questions again:\n{asked}\n\n"
                 if asked else "")
              + (f"The student's LATEST message - respond to exactly this:\n{fence('student_message', latest)}\n\n"
                 if latest else "")
              + (f"The student wants to talk about {switched_to} now. Switch to {switched_to} immediately: acknowledge "
                 f"it in a few words and ask an interesting first question about {switched_to}. Do not go back to "
                 "the previous topic.\n\n" if switched_to else "")
              + (f"The student keeps making mistakes with: {'; '.join(focus)}. When it fits naturally, favour a "
                 "correction or a short model sentence in that area; never lecture, and do not mention this note.\n\n"
                 if focus else "")
              + "Write Aria's next turn.")
    out = raw = None
    for attempt in (1, 2):
        raw = _structured_call(db, user_id, "english_chat", system, prompt, EnglishReply, max_tokens=800,
                               temperature=CHAT_TEMPERATURE + 0.2 * (attempt - 1),
                               on_delta=on_delta).model_dump()
        out = clean_english_reply(raw, latest)
        q = ec.closing_question(out["reply"])
        if not out["reply"]:
            problem = None  # empty: reported below
        elif repeats_earlier_turn(out["reply"], earlier_ai) or _semantic_repeat(q, earlier_questions):
            # A small local model sometimes copies its previous turn: ask once more, explicitly.
            problem = ("Your previous draft repeated something you already said. Write a DIFFERENT reply that "
                       "responds to the student's latest message and asks a new question.")
        elif switched_to and not _mentions_topic(out["reply"], switched_to):
            problem = f"Your previous draft ignored the student's request. Talk about {switched_to} now."
        else:
            problem = None
        if not problem:
            break
        prompt += "\n\n" + problem
    if not out["reply"]:
        raise AIUnavailable("The local AI returned an empty reply. Please try again.", 502)
    if synthetic_opening:
        out["corrections"] = []
    out["reply"] = drop_repeated_opener(out["reply"], earlier_ai[-3:])
    out = apply_correction_policy(out, learning_mode=learning_mode, memory=mem)
    out["memory"] = ec.update_memory(
        mem, topic=topic, learning_mode=learning_mode, student_text=student_text, switched_to=switched_to,
        model_topic=raw.get("current_topic") or "", topic_changed=bool(raw.get("topic_changed")) and bool(student_text),
        new_details=(raw.get("new_details") or [])[:2] if student_text else [],
        interests=(raw.get("interests") or [])[:2] if student_text else [],
        reply=out["reply"], corrections=out["corrections"])
    return out


class EnglishEvaluation(BaseModel):
    grammar: int
    vocabulary: int
    fluency: int
    sentence_formation: int
    summary: str
    strengths: list[str]
    suggestions: list[str]


def english_evaluate(db: Session, user_id: int, *, topic: str, student_messages: list[str]) -> dict:
    """Score a finished English conversation (grammar, vocabulary, fluency, sentence formation, 0-10) from
    the student's own messages only, with a short summary, strengths and suggestions.
    """
    system = ("You assess spoken/written English of college students for workplace communication. Score honestly "
              "on a 0-10 integer scale. Very short sessions should be scored conservatively. Never consider "
              "accent or personal characteristics.")
    joined = "\n".join(fence("student_message", m) for m in student_messages)
    prompt = (f"Topic: {topic}\nThe student's messages (transcribed from speech when voice mode was used):\n"
              f"{joined}\n\nScore grammar, vocabulary, fluency and sentence_formation (0-10). Give a 2-3 sentence "
              "summary, 2-4 strengths and 3-5 specific suggestions.")
    ev = _structured_call(db, user_id, "english_evaluation", system, prompt, EnglishEvaluation).model_dump()
    for k in ("grammar", "vocabulary", "fluency", "sentence_formation"):
        ev[k] = int(_clamp(ev[k], 0, 10))
    return ev

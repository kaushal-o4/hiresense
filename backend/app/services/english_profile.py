"""Recurring English mistakes, counted from the corrections the companion has already given.

No extra model call is made. Each correction (original -> corrected) is given a rough category by comparing the two
sentences word by word. A category only counts as a *recurring pattern* after it has been corrected at least
`MIN_COUNT` times in at least `MIN_SESSIONS` different practice sessions, so one slip is never labelled a weakness.
The categories are approximate (rule-based), the student can dismiss any pattern or clear them all, and the profile
only ever contains the student's own corrections.
"""
from __future__ import annotations

import difflib
import re
from datetime import datetime, timezone

from ..odm import delete, select
from ..odm import Session

from ..models import EnglishMistakePattern

MIN_COUNT = 3
MIN_SESSIONS = 2
MAX_CHANGED_WORDS = 4  # a bigger change is a rewrite of the sentence, not one identifiable mistake

LABELS = {
    "verb_tense": "Verb tense (e.g. past tense)",
    "articles": "Articles (a / an / the)",
    "prepositions": "Prepositions (in / on / at / to ...)",
    "subject_verb_agreement": "Subject-verb agreement",
}
_ARTICLES = {"a", "an", "the"}
_PREPOSITIONS = {"in", "on", "at", "to", "for", "of", "with", "by", "from", "about", "into", "during", "since"}
_AGREEMENT = {"is", "are", "am", "was", "were", "has", "have", "do", "does", "don't", "doesn't"}
_IRREGULAR_PAST = {
    "go": "went", "meet": "met", "see": "saw", "eat": "ate", "have": "had", "do": "did", "make": "made",
    "take": "took", "come": "came", "buy": "bought", "get": "got", "say": "said", "write": "wrote", "give": "gave",
    "know": "knew", "think": "thought", "tell": "told", "run": "ran", "speak": "spoke", "leave": "left",
    "feel": "felt", "find": "found", "bring": "brought", "begin": "began",
}
_WORD = re.compile(r"[a-z']+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("’", "'"))


def _is_tense_pair(a: str, b: str) -> bool:
    if _IRREGULAR_PAST.get(a) == b or _IRREGULAR_PAST.get(b) == a:
        return True
    for base, past in ((a, b), (b, a)):  # regular -ed / -d
        if len(base) >= 3 and past.endswith(("ed", "d")) and past[:3] == base[:3] and past != base:
            return True
    return False


def classify(original: str, corrected: str) -> str | None:
    """Category of a correction, or None if it is not a single identifiable mistake (rewrite, spelling, unclear)."""
    a, b = _words(original), _words(corrected)
    if not a or not b or a == b:
        return None
    old: list[str] = []
    new: list[str] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op != "equal":
            old += a[i1:i2]
            new += b[j1:j2]
    if not old and not new:
        return None
    if len(old) + len(new) > 2 * MAX_CHANGED_WORDS:
        return None
    touched = set(old) | set(new)
    if touched <= _ARTICLES:
        return "articles"
    if len(old) == len(new) == 1:
        x, y = old[0], new[0]
        if _is_tense_pair(x, y):
            return "verb_tense"
        if (x in _AGREEMENT and y in _AGREEMENT) or y in (x + "s", x + "es") or x in (y + "s", y + "es"):
            return "subject_verb_agreement"
        if x in _PREPOSITIONS and y in _PREPOSITIONS:
            return "prepositions"
        return None
    if touched <= _PREPOSITIONS:
        return "prepositions"
    if len(old) == len(new) and all(_is_tense_pair(x, y) for x, y in zip(old, new)):
        return "verb_tense"  # several verbs fixed in one sentence ("go ... meet" -> "went ... met")
    return None


def record_corrections(db: Session, student_id: int, session_id: int, corrections: list[dict]) -> None:
    """Count the categories of the corrections just given (called when a message is saved; does not commit)."""
    now = datetime.now(timezone.utc)
    seen_here: set[str] = set()
    for c in corrections or []:
        cat = classify(c.get("original", ""), c.get("corrected", ""))
        if not cat or cat in seen_here:  # one count per category per message
            continue
        seen_here.add(cat)
        row = db.scalar(select(EnglishMistakePattern).where(
            EnglishMistakePattern.student_id == student_id, EnglishMistakePattern.category == cat))
        if row is None:
            row = EnglishMistakePattern(student_id=student_id, category=cat, count=0, sessions=0, dismissed=False)
            db.add(row)
        row.count += 1
        if row.last_session_id != session_id:
            row.sessions += 1
            row.last_session_id = session_id
        row.last_seen = now
        row.example_original = (c.get("original") or "")[:300]
        row.example_corrected = (c.get("corrected") or "")[:300]


def is_recurring(row: EnglishMistakePattern) -> bool:
    return not row.dismissed and row.count >= MIN_COUNT and row.sessions >= MIN_SESSIONS


def _active(db: Session, student_id: int) -> list[EnglishMistakePattern]:
    return list(db.scalars(select(EnglishMistakePattern).where(
        EnglishMistakePattern.student_id == student_id, EnglishMistakePattern.dismissed.is_(False)
    ).order_by(EnglishMistakePattern.count.desc())))


def public_profile(db: Session, student_id: int) -> dict:
    return {"rule": f"A pattern is called recurring after {MIN_COUNT} corrections in {MIN_SESSIONS} or more sessions.",
            "patterns": [{"id": r.id, "category": r.category, "label": LABELS.get(r.category, r.category),
                          "count": r.count, "sessions": r.sessions, "recurring": is_recurring(r),
                          "example_original": r.example_original, "example_corrected": r.example_corrected,
                          "last_seen": r.last_seen} for r in _active(db, student_id)]}


def focus_lines(db: Session, student_id: int, limit: int = 2) -> list[str]:
    """Names of the top recurring patterns for the prompt (empty until a pattern really is recurring)."""
    return [LABELS.get(r.category, r.category) for r in _active(db, student_id) if is_recurring(r)][:limit]


def dismiss(db: Session, student_id: int, pattern_id: int) -> bool:
    row = db.get(EnglishMistakePattern, pattern_id)
    if not row or row.student_id != student_id:
        return False
    row.dismissed = True
    return True


def clear(db: Session, student_id: int) -> int:
    return db.execute(delete(EnglishMistakePattern).where(EnglishMistakePattern.student_id == student_id)).rowcount

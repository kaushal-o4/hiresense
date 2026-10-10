"""Turn a streamed JSON reply from the local model into complete spoken sentences, in order.

The model writes {"preface": "...", "question": "...", ...} token by token. As soon as one whole sentence of the
preface or question exists, it is handed to text-to-speech, so the interviewer starts talking while the rest is
still being written. Only complete sentences are spoken: never half words or unfinished JSON.
"""
from __future__ import annotations

import json
import re

from .ai import _GREETING, _speakable

# Ends of sentences that are not ends: abbreviations a question may contain.
_ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|mr|mrs|ms|dr|prof|approx|no|fig)\.|\b[A-Z]\.)$", re.IGNORECASE)
_END = re.compile(r"[.!?](?=[\s\"')\]]|$)")
MIN_WORDS = 3  # a 1-2 word fragment ("Okay.") is merged with the next sentence for natural speech


def partial_json_string(buf: str, key: str) -> tuple[str, bool] | None:
    """Value of string field `key` in a possibly unfinished JSON object: (text so far, finished?). None if the
    field has not started yet. Handles escapes; an unfinished escape at the end is left out."""
    m = re.search(r'"' + re.escape(key) + r'"\s*:\s*"', buf)
    if not m:
        return None
    i, out = m.end(), []
    while i < len(buf):
        ch = buf[i]
        if ch == '"':
            return "".join(out), True
        if ch == "\\":
            if i + 1 >= len(buf):
                break
            nxt = buf[i + 1]
            if nxt == "u":
                if i + 6 > len(buf):
                    break
                try:
                    out.append(json.loads(f'"{buf[i:i + 6]}"'))
                except ValueError:
                    pass
                i += 6
                continue
            out.append({"n": " ", "t": " ", "r": " ", "b": "", "f": ""}.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out), False


def split_complete(text: str, final: bool) -> tuple[list[str], str]:
    """Split `text` into finished sentences and the unfinished rest. With final=True everything is finished."""
    sentences, start = [], 0
    for m in _END.finditer(text):
        end = m.end()
        candidate = text[start:end].strip()
        if _ABBREV.search(candidate) or (end < len(text) and text[end - 1] == "." and text[end:end + 1].isdigit()):
            continue
        if len(candidate.split()) < MIN_WORDS:
            continue  # keep it attached to the next sentence
        sentences.append(candidate)
        start = end
    rest = text[start:].strip()
    if final and rest:
        if sentences and len(rest.split()) < MIN_WORDS:
            sentences[-1] = f"{sentences[-1]} {rest}"
        else:
            sentences.append(rest)
        rest = ""
    return sentences, rest


class SpokenStream:
    """Feed it the model's growing JSON text; it calls `emit(sentence)` once per finished spoken sentence:
    first the preface (feedback / explanation), then the question. A greeting or self-introduction the model adds
    at the start of the question is not spoken (the greeting is said separately)."""

    def __init__(self, emit, speak_preface: bool = True):
        self.emit = emit
        self.speak_preface = speak_preface
        self.done = {"preface": 0, "question": 0}  # characters of each field already emitted
        self.question_started = False
        self.spoken: list[str] = []

    def _field(self, buf: str, key: str, final: bool) -> bool:
        got = partial_json_string(buf, key)
        if got is None:
            return False
        value, finished = got
        value = " ".join(value.split())
        pending = value[self.done[key]:]
        sentences, rest = split_complete(pending, final or finished)
        for s in sentences:
            self.done[key] += pending.index(s) + len(s)
            pending = value[self.done[key]:]
            s = _speakable(s)
            if key == "question" and not self.question_started:
                self.question_started = True
                if _GREETING.fullmatch(s + " ") or _GREETING.fullmatch(s):
                    continue  # model greeted despite instructions: don't say it twice
            if s:
                self.spoken.append(s)
                self.emit(s)
        return finished

    def feed(self, buf: str, final: bool = False) -> None:
        preface_done = True
        if self.speak_preface:
            preface_done = self._field(buf, "preface", final)
        if preface_done or final:
            self._field(buf, "question", final)

    @property
    def spoken_text(self) -> str:
        return " ".join(self.spoken)


def final_sentences(preface: str | None, question: str) -> list[str]:
    """The sentences SpokenStream would speak for the finished reply (used to finish, or correct, a stream)."""
    got: list[str] = []
    s = SpokenStream(got.append, speak_preface=bool(preface))
    s.feed(json.dumps({"preface": preface or "", "question": question}), final=True)
    return got


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", s.lower())


def remaining_after(spoken: list[str], final: list[str]) -> list[str] | None:
    """Sentences still to speak if what was already spoken matches the start of the final reply; None if it does
    not (the stream must be retracted and the final reply spoken from the beginning)."""
    if len(spoken) > len(final):
        return None
    for a, b in zip(spoken, final):
        if _words(a) != _words(b):
            return None
    return final[len(spoken):]

"""Skill-name normalisation and "is this phrase really in the text?" checks.

Shared by resume analysis (to drop skills the model invented) and job matching (to compare skills).
"""
from __future__ import annotations

import re

# Common spellings that mean the same skill. Keys and values are already normalised (lower case).
ALIASES = {
    "js": "javascript", "es6": "javascript", "ecmascript": "javascript",
    "ts": "typescript",
    "py": "python", "python3": "python",
    "reactjs": "react", "react.js": "react",
    "nodejs": "node.js", "node": "node.js",
    "expressjs": "express", "express.js": "express",
    "vuejs": "vue", "vue.js": "vue",
    "nextjs": "next.js",
    "angularjs": "angular",
    "postgres": "postgresql", "psql": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "golang": "go",
    "c sharp": "c#", "csharp": "c#",
    "cpp": "c++",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "ml": "machine learning", "dl": "deep learning", "ai": "artificial intelligence",
    "nlp": "natural language processing", "cv": "computer vision",
    "oop": "object-oriented programming", "oops": "object-oriented programming",
    "object oriented programming": "object-oriented programming",
    "dsa": "data structures and algorithms",
    "data structures & algorithms": "data structures and algorithms",
    "amazon web services": "aws", "google cloud platform": "gcp", "google cloud": "gcp",
    "microsoft azure": "azure",
    "html5": "html", "css3": "css",
    "rest api": "rest", "restful": "rest", "rest apis": "rest", "restful apis": "rest",
    "github": "git",
    "ms excel": "excel", "microsoft excel": "excel",
    "power bi": "powerbi",
    "tensorflow 2": "tensorflow",
}

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")


def tokens(text: str) -> list[str]:
    return [t.rstrip(".-") for t in _TOKEN.findall((text or "").lower()) if t.rstrip(".-")]


def normalize_skill(name: str) -> str:
    key = " ".join(tokens(name))
    return ALIASES.get(key, key)


def variants(name: str) -> set[str]:
    """The normalised skill plus every alias that maps to it."""
    canon = normalize_skill(name)
    out = {canon, " ".join(tokens(name))}
    out.update(k for k, v in ALIASES.items() if v == canon)
    return {v for v in out if v}


class TextIndex:
    """Normalised view of a document for fast phrase lookups."""

    def __init__(self, text: str):
        self.toks = tokens(text)
        self.joined = " " + " ".join(self.toks) + " "
        self.set = set(self.toks)

    def has_phrase(self, phrase: str) -> bool:
        p = " ".join(tokens(phrase))
        return bool(p) and f" {p} " in self.joined

    def has_skill(self, name: str) -> bool:
        return any(self.has_phrase(v) for v in variants(name))

    def token_coverage(self, phrase: str) -> float:
        toks = [t for t in tokens(phrase) if len(t) > 1 or t in {"c", "r"}]
        if not toks:
            return 0.0
        return sum(t in self.set for t in toks) / len(toks)

    def grounded(self, phrase: str, min_coverage: float = 0.6) -> bool:
        return self.has_phrase(phrase) or self.token_coverage(phrase) >= min_coverage

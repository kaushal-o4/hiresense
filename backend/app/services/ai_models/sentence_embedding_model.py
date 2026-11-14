# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/services/ai_models/sentence_embedding_model.py
#
# FILE PURPOSE:
# Loads a small local sentence-embedding model (all-MiniLM-L6-v2, Sentence Transformers) that turns
# text into vectors for meaning comparison.
#
# WHAT THIS FILE DOES:
# 1. Loads the model once per process (downloaded once, then offline on CPU).
# 2. embed(texts) returns unit-length vectors; short texts are cached.
# 3. Reports status and validates the vectors.
#
# IMPORTANT FUNCTIONS:
#    - validate()
#        Unit-normalised float array of shape (n, dim), or EmbeddingUnavailable if the output
#        is unusable.
#    - embed()
#        Unit-length embeddings, shape (len(texts), dim).
#    Other helper functions: _installed, status, _get_model, warmup, _check, _embed_one
#
# IMPORTANT CLASSES:
#    - EmbeddingUnavailable
#
# INPUT:
# List of texts.
#
# OUTPUT:
# Array of vectors (cosine similarity = dot product).
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py
#    Used by: app/main.py, app/services/ai_models/ai_structured_call_base.py,
#    app/services/english/ai_english_conversation.py,
#    app/services/interview/ai_interview_service.py,
#    app/services/interview/interview_intelligence_rules.py,
#    app/services/resume_and_jobs/semantic_job_matcher.py
#    Tested by: eval/run_eval.py, tests/conftest.py, tests/test_local_ai.py,
#    tests_integration/conftest.py, tests_perf/bench_interview_latency.py,
#    tests_perf/bench_models.py, tests_perf/bench_prompts.py
#
# EXECUTION FLOW:
#    Text
#       |
#       v
#    Embedding model
#       |
#       v
#    Vector
#       |
#       v
#    Similarity used by matching / off-topic checks
#
# IMPORTANT DEPENDENCIES:
#    numpy, sentence_transformers
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Local sentence-embedding model (Sentence Transformers) used for semantic job matching.

The model (~90 MB) is downloaded from Hugging Face once, then runs offline on the CPU. It is loaded a single
time per server process (thread-safe) and short texts such as skill names are cached.
"""
from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache

from ...application_configuration import get_settings

log = logging.getLogger("hiresense.embeddings")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

_model = None
_load_error: str | None = None
_lock = threading.Lock()


class EmbeddingUnavailable(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _installed() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def status() -> dict:
    s = get_settings()
    enabled = s.embedding_provider.lower() == "sentence_transformers"
    return {"enabled": enabled, "model": s.embedding_model, "installed": enabled and _installed(),
            "loaded": _model is not None, "error": _load_error}


def _get_model():
    global _model, _load_error
    s = get_settings()
    if s.embedding_provider.lower() != "sentence_transformers":
        raise EmbeddingUnavailable("Semantic matching is turned off (EMBEDDING_PROVIDER=none).")
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(s.embedding_model, device="cpu")
                _load_error = None
            except ImportError:
                _load_error = "The sentence-transformers package is not installed (pip install -r requirements.txt)."
            except Exception as exc:  # download/network/corrupt cache
                _load_error = (f"Could not load the embedding model '{s.embedding_model}' "
                               f"({type(exc).__name__}). It needs internet access the first time to download.")
                log.warning("embedding model load failed: %s", exc)
            if _model is None:
                raise EmbeddingUnavailable(_load_error)
    return _model


def warmup() -> None:
    try:
        _get_model()
    except EmbeddingUnavailable:
        pass  # status() reports the reason; matching falls back to rule-based


def validate(vectors, n: int):
    """Unit-normalised float array of shape (n, dim), or EmbeddingUnavailable if the output is unusable."""
    return _check(vectors, n)


def _check(vectors, n: int):
    import numpy as np
    arr = np.asarray(vectors, dtype="float32")
    if arr.ndim != 2 or arr.shape[0] != n or arr.shape[1] == 0 or not np.isfinite(arr).all():
        raise EmbeddingUnavailable("The embedding model returned invalid output.")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    if (norms == 0).any():
        raise EmbeddingUnavailable("The embedding model returned an empty vector.")
    return arr / norms


@lru_cache(maxsize=4096)
def _embed_one(text: str) -> tuple:
    return tuple(_check(_get_model().encode([text], show_progress_bar=False), 1)[0].tolist())


def embed(texts: list[str]):
    """Unit-length embeddings, shape (len(texts), dim). Raises EmbeddingUnavailable."""
    _get_model()  # first: EmbeddingUnavailable when turned off / not installed (cloud hosts have no numpy either)
    try:
        import numpy as np
    except ImportError:
        raise EmbeddingUnavailable("numpy is not installed.")
    if not texts:
        return np.zeros((0, 0), dtype="float32")
    clean = [" ".join((t or "").split())[:2000] or "-" for t in texts]
    short = all(len(t) <= 200 for t in clean)
    if short:  # skill names, titles - cache them
        return np.asarray([_embed_one(t) for t in clean], dtype="float32")
    return _check(_get_model().encode(clean, show_progress_bar=False, batch_size=16), len(clean))

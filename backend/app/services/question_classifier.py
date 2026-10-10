"""Runtime side of the custom ML component: predicts an interview question's type and difficulty.

The model is trained offline by `backend/ml/train_question_classifier.py` (never during a web request) and
saved with joblib. Here it is only loaded once and used to *cross-check* the language model: each generated
question stores the classifier's prediction in `InterviewQuestion.meta` so admins can spot questions whose
requested difficulty/type looks wrong. It never overrides the interview flow.

The bundled model is trained on a small, hand-labelled DEVELOPMENT dataset - see ml/README.md for metrics and
limitations. If the model file is missing or unreadable, predict() returns None and nothing else changes.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from ..config import get_settings

log = logging.getLogger("hiresense.question_classifier")
_bundle = None
_tried = False
_lock = threading.Lock()


def _load():
    global _bundle, _tried
    if _tried:
        return _bundle
    with _lock:
        if not _tried:
            path = Path(get_settings().question_classifier_path)
            if path.exists():
                try:
                    import joblib
                    _bundle = joblib.load(path)
                except Exception as exc:  # missing sklearn, version mismatch, corrupt file
                    log.warning("question classifier not loaded: %s", type(exc).__name__)
            _tried = True
    return _bundle


def status() -> dict:
    b = _load()
    return {"loaded": b is not None, "metrics": (b or {}).get("metrics"), "trained_at": (b or {}).get("trained_at")}


def predict(text: str) -> dict | None:
    b = _load()
    if not b or not (text or "").strip():
        return None
    try:
        out = {}
        for target, model in b["models"].items():  # only models that beat the rule baseline are saved
            proba = model.predict_proba([text])[0]
            i = int(proba.argmax())
            out[target] = str(model.classes_[i])
            out[f"{target}_confidence"] = round(float(proba[i]), 2)
        out["model_version"] = b.get("trained_at")
        return out
    except Exception as exc:
        log.warning("question classifier failed: %s", type(exc).__name__)
        return None

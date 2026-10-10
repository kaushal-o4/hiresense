"""Train the interview-question classifier (type + difficulty) and save it for the backend.

Run from the backend folder:
    .\\venv\\Scripts\\python.exe -m ml.train_question_classifier

Data: ml/data/interview_questions_dev.csv (hand-labelled DEVELOPMENT data written for this project) plus the
admin-labelled seed question bank in app/seed.py. This is a small dataset; the metrics printed below describe
this dataset only and do NOT show production accuracy.

Method: TF-IDF (word 1-2 grams + character 3-5 grams) -> logistic regression, one model per target.
Evaluation: stratified 75/25 hold-out split (fixed seed) and 5-fold stratified cross-validation, each compared
with two baselines: always-predict-the-most-common-class and a transparent keyword/length rule. The saved
model is refit on all data after evaluation.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
SEED = 42


def load_data() -> list[dict]:
    rows = []
    with open(HERE / "data" / "interview_questions_dev.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"question": r["question"].strip(), "type": r["type"].strip(),
                         "difficulty": r["difficulty"].strip(), "source": "dev_csv"})
    from app.seed import BANK
    for qtype, items in BANK.items():
        for q, diff, _tag in items:
            rows.append({"question": q, "type": qtype, "difficulty": diff, "source": "seed_bank"})
    seen, out = set(), []
    for r in rows:  # drop duplicates so the same question can't be in both train and test
        key = re.sub(r"[^a-z0-9]", "", r["question"].lower())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def make_model() -> Pipeline:
    features = FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, stop_words=None)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)),
    ])
    return Pipeline([("features", features),
                     ("clf", LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced"))])


TYPE_RULES = [
    ("project", r"\byour (final[- ]year |group |internship |machine learning )?project\b|\bon your resume\b"),
    ("behavioral", r"\b(tell me about a time|describe a (time|situation)|give an example of)\b"),
    ("communication", r"\b(explain .* to (a|an|your|someone)|how would you (explain|present|write)|persuade|summari[sz]e|describe your hometown|presentation)\b"),
    ("hr", r"\b(yourself|why (do you want|should we)|your (greatest|biggest|salary|strength|weakness|hobbies)|relocat|shifts?|five years|our company)\b"),
]


def rule_type(q: str) -> str:
    for label, pattern in TYPE_RULES:
        if re.search(pattern, q, re.IGNORECASE):
            return label
    return "technical"


def rule_difficulty(q: str) -> str:
    n = len(q.split())
    hard_words = re.search(r"\b(design|trade-?offs?|scale|distributed|complexity|optimi[sz]e|millions|billions)\b", q, re.I)
    return "hard" if hard_words or n > 18 else "easy" if n <= 8 else "medium"


def report(name: str, y_true, y_pred) -> dict:
    return {"model": name, "accuracy": round(accuracy_score(y_true, y_pred), 3),
            "macro_f1": round(f1_score(y_true, y_pred, average="macro", zero_division=0), 3)}


def evaluate(rows: list[dict], target: str, rule) -> dict:
    X = np.array([r["question"] for r in rows])
    y = np.array([r[target] for r in rows], dtype=object)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    model = make_model().fit(X_tr, y_tr)
    pred = model.predict(X_te)
    dummy = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr).predict(X_te)
    holdout = [report("tfidf_logreg", y_te, pred), report("majority_baseline", y_te, dummy),
               report("keyword_rule_baseline", y_te, [rule(q) for q in X_te])]
    cv_pred = cross_val_predict(make_model(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    labels = sorted(set(y))
    return {
        "target": target, "n_total": int(len(y)), "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
        "class_counts": {c: int((y == c).sum()) for c in labels},
        "holdout": holdout,
        "cv5": [report("tfidf_logreg", y, cv_pred), report("keyword_rule_baseline", y, [rule(q) for q in X])],
        "holdout_per_class": classification_report(y_te, pred, labels=labels, output_dict=True, zero_division=0),
        "holdout_confusion": {"labels": labels, "matrix": confusion_matrix(y_te, pred, labels=labels).tolist()},
    }


def main() -> None:
    rows = load_data()
    print(f"Loaded {len(rows)} labelled questions "
          f"({sum(r['source'] == 'dev_csv' for r in rows)} dev CSV, {sum(r['source'] == 'seed_bank' for r in rows)} seed bank)\n")
    metrics, models = {}, {}
    for target, rule in (("type", rule_type), ("difficulty", rule_difficulty)):
        m = evaluate(rows, target, rule)
        metrics[target] = m
        print(f"=== {target}  (classes: {m['class_counts']})")
        print(f"  hold-out test set ({m['n_test']} questions):")
        for r in m["holdout"]:
            print(f"    {r['model']:<24} accuracy {r['accuracy']:.3f}   macro-F1 {r['macro_f1']:.3f}")
        print("  5-fold cross-validation (all data):")
        for r in m["cv5"]:
            print(f"    {r['model']:<24} accuracy {r['accuracy']:.3f}   macro-F1 {r['macro_f1']:.3f}")
        print(f"  confusion matrix {m['holdout_confusion']['labels']}:")
        for lab, row in zip(m["holdout_confusion"]["labels"], m["holdout_confusion"]["matrix"]):
            print(f"    {lab:<14} {row}")
        print()
        # Deploy a model only if it beats the transparent rule in cross-validation on BOTH accuracy and macro-F1.
        ml, rule_m = m["cv5"]
        m["deployed"] = ml["accuracy"] > rule_m["accuracy"] and ml["macro_f1"] > rule_m["macro_f1"]
        verdict = (f"CV accuracy {ml['accuracy']} vs rule {rule_m['accuracy']}, "
                   f"macro-F1 {ml['macro_f1']} vs rule {rule_m['macro_f1']}")
        if m["deployed"]:
            models[target] = make_model().fit([r["question"] for r in rows], [r[target] for r in rows])
            print(f"  -> {target}: model deployed ({verdict})\n")
        else:
            print(f"  -> {target}: NOT deployed - it does not clearly beat the simple rule ({verdict})\n")

    out_dir = HERE / "models"
    out_dir.mkdir(exist_ok=True)
    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary = {t: {"holdout": metrics[t]["holdout"], "cv5": metrics[t]["cv5"], "n_total": metrics[t]["n_total"],
                   "deployed": metrics[t]["deployed"]} for t in metrics}
    joblib.dump({"models": models, "trained_at": trained_at, "metrics": summary,
                 "data": "development dataset - not production-validated"}, out_dir / "question_classifier.joblib")
    (out_dir / "metrics.json").write_text(json.dumps({"trained_at": trained_at, **metrics}, indent=2), encoding="utf-8")
    print(f"Saved model to {out_dir / 'question_classifier.joblib'} and metrics to {out_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()

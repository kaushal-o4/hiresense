"""Scoring post-processing added after the 2026-11-04 calibration run (eval/calibrate_scoring.py)."""
from app.routers.interviews import DEFAULT_RUBRIC
from app.services import ai, scoring_bands


def _ev(**kw):
    base = {k: 10 for k in ai.CRITERIA}
    base.update(kw)
    return base


def test_completeness_counts_when_rubric_leaves_it_out():
    full = ai.weighted_score(_ev(), DEFAULT_RUBRIC)
    shallow = ai.weighted_score(_ev(completeness=4), DEFAULT_RUBRIC)
    assert full == 100.0
    assert shallow == 88.0   # 100 * 0.8 + 40 * 0.2: a correct but shallow answer no longer scores 100


def test_rubric_with_completeness_is_used_as_is():
    rubric = [{"name": "Correctness", "weight": 0.5}, {"name": "Completeness", "weight": 0.5}]
    assert ai.weighted_score(_ev(correctness=8, completeness=6), rubric) == 70.0


def test_uniform_scores_unchanged():
    # every criterion 8 -> 80 regardless of the completeness blend (existing behaviour and tests)
    assert ai.weighted_score({k: 8 for k in ai.CRITERIA}, DEFAULT_RUBRIC) == 80.0


def test_open_question_skips_similarity_cap():
    """Strong project answers to an open question measured 0.13-0.17 similarity with the real MiniLM model."""
    ev = {"answers_the_question": True, "relevance": 9, "correctness": 9, "completeness": 9, "clarity": 9,
          "communication": 9}
    answer = ("My placement tracker has a React frontend that calls a Flask REST API backed by MySQL, with a nightly "
              "job that emails reminders, deployed behind Nginx.")
    ai.apply_answer_rules(ev, "Walk me through the architecture of your most significant project.", answer,
                          question_type="project", similarity=0.13, open_question=True)
    assert ev["relevance"] == 9
    ev2 = dict(ev)
    ai.apply_answer_rules(ev2, "How do students and companies interact without real-time updates?", answer,
                          question_type="project", similarity=0.13, open_question=False)
    assert ev2["relevance"] == 2   # specific question + low similarity: still capped


def test_open_question_still_trusts_the_model():
    ev = {"answers_the_question": False, "relevance": 9, "correctness": 9, "completeness": 9, "clarity": 9,
          "communication": 9}
    ai.apply_answer_rules(ev, "Tell me about your final year project.", "I like cricket and watching movies "
                          "with my friends on the weekend, especially action movies.", question_type="project",
                          similarity=0.05, open_question=True)
    assert ev["relevance"] == 2


def test_score_bands():
    assert scoring_bands.band(100)["text"] == "Outstanding (90-100)"
    assert scoring_bands.band(89.9)["text"] == "Strong (75-89)"
    assert scoring_bands.band(60)["key"] == "competent"
    assert scoring_bands.band(39.5)["text"] == "Needs work (0-39)"
    assert scoring_bands.band(None) is None


def test_prompt_has_anchors():
    assert "10 = flawless" in ai.SCORE_ANCHORS and "Give 10 only" in ai.SCORE_ANCHORS

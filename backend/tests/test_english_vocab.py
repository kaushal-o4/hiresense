"""English vocabulary review (Leitner boxes), daily plan, progress and English milestone rewards.
The language model is mocked."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from conftest import register_student
from app import seed as seed_module
from app.models import (
    Badge, Challenge, EnglishSession, PointTransaction, RewardRule, StudentBadge, User, VocabularyItem,
)
from app.odm import select
from app.services import english_vocab as ev

NOW = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- Leitner rules

def test_knowing_a_card_moves_it_up_one_box_with_a_longer_gap():
    for box in range(1, ev.MAX_BOX):
        new_box, due, mastered = ev.next_state(box, True, NOW)
        assert new_box == box + 1 and not mastered
        assert due == NOW + timedelta(days=ev.INTERVAL_DAYS[box + 1])
    gaps = [ev.INTERVAL_DAYS[b] for b in range(1, ev.MAX_BOX + 1)]
    assert gaps == sorted(gaps) and len(set(gaps)) == len(gaps)


def test_not_knowing_sends_any_card_back_to_box_one_for_tomorrow():
    for box in range(1, ev.MAX_BOX + 1):
        assert ev.next_state(box, False, NOW) == (1, NOW + timedelta(days=1), False)


def test_knowing_a_box_five_card_masters_it():
    box, due, mastered = ev.next_state(5, True, NOW)
    assert (box, mastered) == (5, True) and due == NOW + timedelta(days=ev.MASTERED_INTERVAL_DAYS)


def test_out_of_range_boxes_are_clamped():
    assert ev.next_state(0, True, NOW)[0] == 2
    assert ev.next_state(99, True, NOW)[2] is True


def test_normalise_ignores_case_spacing_and_end_punctuation():
    assert ev.normalise("  I  WENT to college. ") == ev.normalise("i went to college") == "i went to college"


# --------------------------------------------------------------------------- API

@pytest.fixture()
def llm(monkeypatch):
    from app.services import local_llm
    state = SimpleNamespace(corrections=[], scores={"grammar": 6, "vocabulary": 7, "fluency": 8,
                                                   "sentence_formation": 7})

    def chat_json(system, prompt, schema, **kw):
        props = (schema or {}).get("properties", {})
        if "grammar" in props:  # end-of-session evaluation
            return local_llm.LLMResult(content=json.dumps({
                **state.scores, "summary": "Good effort.", "strengths": ["Clear"], "suggestions": ["Past tense"]}),
                prompt_tokens=1, output_tokens=1, latency_ms=1)
        return local_llm.LLMResult(content=json.dumps({
            "reply": "That sounds good. What did you do next?", "avatar_mode": "speaking", "encouragement": "",
            "corrections": state.corrections, "suggested_followups": ["I..."], "current_topic": "",
            "topic_changed": False, "new_details": [], "interests": []}), prompt_tokens=1, output_tokens=1,
            latency_ms=1)

    monkeypatch.setattr(local_llm, "chat_json", chat_json)
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": "mock", "running": True, "model_ready": True, "error": None})
    return state


def start(c, learning_mode="english_learning"):
    r = c.post("/api/student/english", json={"topic": "weekends", "mode": "text", "learning_mode": learning_mode})
    assert r.status_code == 201, r.text
    return r.json()


def say(c, llm, s, text, corrections=()):
    llm.corrections = list(corrections)
    r = c.post(f"/api/student/english/{s['id']}/message", json={"content": text})
    assert r.status_code == 200, r.text


def backdate(db, session_id, minutes=3):
    """Verified time counts the gap before each student message, so move the session and Aria's opener back."""
    row = db.get(EnglishSession, session_id)
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    for m in row.messages:
        m.created_at = row.created_at
    db.commit()


FIX = {"original": "Yesterday I go to college.", "corrected": "Yesterday I went to college.",
       "explanation": "Use the past tense for yesterday."}


def test_corrections_become_review_cards_once(client, llm):
    register_student(client)
    s = start(client)
    say(client, llm, s, FIX["original"], [FIX])
    s2 = start(client)  # the same mistake in a later session (Aria never repeats a correction within one)
    say(client, llm, s2, FIX["original"], [FIX])
    data = client.get("/api/student/english/vocabulary").json()
    assert data["counts"]["total"] == 1 and data["counts"]["due"] == 1
    card = data["items"][0]
    assert card["front"] == FIX["original"] and card["back"] == FIX["corrected"]
    assert card["explanation"] == FIX["explanation"] and card["box"] == 1 and card["kind"] == "correction"
    assert card["source_session_id"] == s2["id"]


def test_punctuation_only_corrections_are_not_cards(client, llm):
    register_student(client)
    s = start(client)
    say(client, llm, s, "I like cricket a lot, really", [{"original": "I like games", "corrected": "I like games.",
                                                                "explanation": "Full stop."}])
    assert client.get("/api/student/english/vocabulary").json()["counts"]["total"] == 0


def test_review_moves_boxes_and_logs_answers(client, llm, db):
    register_student(client)
    s = start(client)
    say(client, llm, s, FIX["original"], [FIX])
    queue = client.get("/api/student/english/vocabulary/review").json()["items"]
    assert len(queue) == 1
    r = client.post(f"/api/student/english/vocabulary/{queue[0]['id']}/review", json={"knew": True})
    assert r.status_code == 200, r.text
    assert r.json()["item"]["box"] == 2 and r.json()["mastered_now"] is False
    assert client.get("/api/student/english/vocabulary/review").json()["items"] == []  # not due until later
    r = client.post(f"/api/student/english/vocabulary/{queue[0]['id']}/review", json={"knew": False})
    assert r.json()["item"]["box"] == 1
    p = client.get("/api/student/english/progress").json()
    assert p["reviews_recent"] == 2 and p["review_accuracy"] == 50


def test_mastering_a_card_awards_points_once(client, llm, db):
    user = register_student(client)
    item = VocabularyItem(student_id=user["id"], key="went", kind="word", front="go (past)", back="went",
                          box=5, due_at=datetime.now(timezone.utc))
    db.add(item)
    db.commit()
    r = client.post(f"/api/student/english/vocabulary/{item.id}/review", json={"knew": True})
    assert r.json()["mastered_now"] is True and r.json()["item"]["mastered"] is True
    r = client.post(f"/api/student/english/vocabulary/{item.id}/review", json={"knew": True})
    assert r.json()["mastered_now"] is False  # already mastered
    db.expire_all() if hasattr(db, "expire_all") else None
    txs = db.scalars(select(PointTransaction).where(PointTransaction.student_id == user["id"],
                                                    PointTransaction.activity_type == "english_word_mastered")).all()
    assert len(txs) == 1


def test_another_students_cards_are_invisible(client, llm, new_client):
    register_student(client)
    s = start(client)
    say(client, llm, s, FIX["original"], [FIX])
    card = client.get("/api/student/english/vocabulary").json()["items"][0]
    other = new_client()
    register_student(other, email="other@test.dev")
    assert other.get("/api/student/english/vocabulary").json()["items"] == []
    assert other.post(f"/api/student/english/vocabulary/{card['id']}/review", json={"knew": True}).status_code == 404
    assert other.delete(f"/api/student/english/vocabulary/{card['id']}").status_code == 404


def test_students_can_add_and_delete_their_own_words(client):
    register_student(client)
    r = client.post("/api/student/english/vocabulary", json={"word": "Resilient", "meaning": "able to recover quickly",
                                                             "example": "She is resilient."})
    assert r.status_code == 201 and r.json()["kind"] == "word"
    assert client.post("/api/student/english/vocabulary", json={"word": "", "meaning": "x"}).status_code == 422
    assert client.delete(f"/api/student/english/vocabulary/{r.json()['id']}").json() == {"ok": True}
    assert client.get("/api/student/english/vocabulary").json()["counts"]["total"] == 0


def test_vocabulary_filters(client, db):
    user = register_student(client)
    now = datetime.now(timezone.utc)
    for key, box, due, mastered in (("a", 1, now - timedelta(hours=1), None), ("b", 4, now + timedelta(days=3), None),
                                    ("c", 5, now + timedelta(days=9), now)):
        db.add(VocabularyItem(student_id=user["id"], key=key, kind="word", front=key, back=key, box=box, due_at=due,
                              mastered_at=mastered))
    db.commit()
    get = lambda f: [i["back"] for i in client.get("/api/student/english/vocabulary", params={"filter": f}).json()["items"]]
    assert get("due") == ["a"] and get("learning") == ["a"] and get("learned") == ["b"] and get("mastered") == ["c"]
    counts = client.get("/api/student/english/vocabulary").json()["counts"]
    assert counts["learned"] == 2 and counts["mastered"] == 1 and counts["boxes"]["4"] == 1


# --------------------------------------------------------------------------- daily plan

def test_daily_plan_without_any_data_has_conversation_and_interview(client):
    register_student(client)
    plan = client.get("/api/student/english/daily-plan").json()
    assert [i["id"] for i in plan["items"]] == ["conversation", "interview"]
    assert plan["items"][0]["learning_mode"] == "free_conversation"
    assert plan["completed"] == 0 and plan["all_done"] is False


def test_daily_plan_recommends_the_mode_for_the_weakest_skill_of_an_earlier_session(client, db):
    user = register_student(client)
    db.add(EnglishSession(student_id=user["id"], topic="x", status="completed", active_seconds=300,
                          ended_at=datetime.now(timezone.utc) - timedelta(days=1), overall_score=60,
                          scores={"grammar": 8, "vocabulary": 7, "fluency": 3, "sentence_formation": 6},
                          learning_mode="free_conversation"))
    db.commit()
    conv = client.get("/api/student/english/daily-plan").json()["items"][0]
    assert conv["learning_mode"] == "confidence" and "fluency" in conv["detail"]
    assert conv["link"] == "/student/english?mode=confidence"


def test_daily_plan_ticks_itself_and_awards_points_once(client, llm, db, monkeypatch):
    user = register_student(client)
    # Short sessions don't count as practice; make the session long enough by back-dating its start.
    s = start(client, "free_conversation")
    backdate(db, s["id"])
    say(client, llm, s, FIX["original"], [FIX])
    plan = client.get("/api/student/english/daily-plan").json()
    assert [i["id"] for i in plan["items"]] == ["review", "conversation", "interview"]
    assert plan["items"][0]["target"] == 1 and not plan["items"][0]["done"]

    card = client.get("/api/student/english/vocabulary/review").json()["items"][0]
    client.post(f"/api/student/english/vocabulary/{card['id']}/review", json={"knew": True})
    assert client.post(f"/api/student/english/{s['id']}/end").status_code == 200
    plan = client.get("/api/student/english/daily-plan").json()
    by = {i["id"]: i for i in plan["items"]}
    assert by["review"]["done"] and by["review"]["target"] == 1  # the reviewed card still counts as today's work
    assert by["conversation"]["done"] and not by["interview"]["done"]

    # Mark the interview item done by stubbing the answered-today check (interviews have their own tests).
    monkeypatch.setattr(ev, "_answered_interview_today", lambda db, sid, since: True)
    plan = client.get("/api/student/english/daily-plan").json()
    assert plan["all_done"] is True
    client.get("/api/student/english/daily-plan")
    db.expire_all() if hasattr(db, "expire_all") else None
    txs = db.scalars(select(PointTransaction).where(PointTransaction.student_id == user["id"],
                                                    PointTransaction.activity_type == "english_daily_plan")).all()
    assert len(txs) == 1 and txs[0].source_id == ev.plan_source_id(datetime.now(timezone.utc).date())
    assert client.get("/api/student/english/progress").json()["plan_days_completed"] == 1


def test_conversation_in_another_mode_does_not_tick_the_plan(client, llm, db):
    register_student(client)
    s = start(client, "english_learning")  # the plan asks for free conversation (no evaluated session yet)
    backdate(db, s["id"])
    say(client, llm, s, "I played cricket with my friends yesterday evening.")
    client.post(f"/api/student/english/{s['id']}/end")
    conv = [i for i in client.get("/api/student/english/daily-plan").json()["items"] if i["id"] == "conversation"][0]
    assert conv["done"] is False


# --------------------------------------------------------------------------- progress + rewards

def test_progress_has_score_trend_and_weekly_reviews(client, db):
    user = register_student(client)
    for i, g in enumerate((4, 6, 8)):
        db.add(EnglishSession(student_id=user["id"], topic="t", status="completed", active_seconds=120,
                              ended_at=datetime.now(timezone.utc) - timedelta(days=3 - i), overall_score=10 * g,
                              scores={"grammar": g, "vocabulary": 5, "fluency": 5, "sentence_formation": 5}))
    db.commit()
    p = client.get("/api/student/english/progress").json()
    assert [t["grammar"] for t in p["score_trend"]] == [4, 6, 8]
    assert len(p["weekly_reviews"]) == 8 and p["review_accuracy"] is None
    assert p["words"]["total"] == 0


def test_word_badges_are_awarded(client, db):
    user = register_student(client)
    now = datetime.now(timezone.utc)
    for n in range(25):
        db.add(VocabularyItem(student_id=user["id"], key=f"w{n}", kind="word", front=f"w{n}", back=f"w{n}", box=4,
                              due_at=now - timedelta(minutes=1)))
    db.commit()
    first = db.scalars(select(VocabularyItem).where(VocabularyItem.student_id == user["id"])).first()
    r = client.post(f"/api/student/english/vocabulary/{first.id}/review", json={"knew": True})
    assert "Word Collector" in r.json()["new_badges"]


def test_weekly_review_challenge_counts_reviews(client, db):
    from app.services.rewards import challenge_progress
    user = register_student(client)
    item = VocabularyItem(student_id=user["id"], key="k", kind="word", front="k", back="k", box=1,
                          due_at=datetime.now(timezone.utc))
    db.add(item)
    db.commit()
    for knew in (True, False, True):
        client.post(f"/api/student/english/vocabulary/{item.id}/review", json={"knew": knew})
    ch = db.scalar(select(Challenge).where(Challenge.metric == "english_reviews"))
    assert ch is not None and challenge_progress(db, user["id"], ch) == 3


def test_seed_adds_english_rewards_and_stays_repeatable(db):
    seed_module.seed()
    seed_module.seed()
    for code in ("word_collector", "vocabulary_builder", "daily_planner"):
        assert len(db.scalars(select(Badge).where(Badge.code == code)).all()) == 1
    for act in ("english_daily_plan", "english_word_mastered"):
        assert len(db.scalars(select(RewardRule).where(RewardRule.activity_type == act)).all()) == 1
    assert len(db.scalars(select(Challenge).where(Challenge.title == "Word workout")).all()) == 1

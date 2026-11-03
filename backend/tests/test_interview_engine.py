"""Deterministic interview intelligence (no model): context, answer signals, coverage, duplicates, fallbacks."""
import pytest

from app.services import interview_engine as ie

ANALYSIS = {
    "candidate_summary": "Final-year student who built a hospital resource management web app.",
    "skills": [{"name": "Python", "category": "programming_language"}, {"name": "Django", "category": "framework"},
               {"name": "Teamwork", "category": "soft_skill"}],
    "projects": [{"name": "Hospital Resources Management System",
                  "description": "Django app tracking beds and oxygen; built the bed-allocation module.",
                  "technologies": ["Python", "Django"]}],
    "internships": [{"organization": "WebNova", "role": "Python intern", "summary": "data cleaning scripts"}],
    "experience": [], "education": [{"degree": "B.Tech", "field": "CE", "institution": "Pune University"}],
    "recommended_topics": ["input validation"],
}


def test_context_includes_project_details_but_not_soft_skills():
    ctx = ie.candidate_context(ANALYSIS, ["Git"])
    block = ie.context_block(ctx)
    assert "bed-allocation module" in block and "[Python, Django]" in block and "Python intern at WebNova" in block
    assert ctx["skills"] == ["Git", "Python", "Django"]
    assert "Skills: not available" in ie.context_block(ie.candidate_context(None))


@pytest.mark.parametrize("answer, code", [
    ("I worked with a team and we finished it on time.", "vague_contribution"),
    ("I improved the performance a lot by changing the queries.", "unmeasured_claim"),
    ("I used AI in my project and it worked well for the users.", "unexplained_ai"),
    ("I developed a hospital management project.", "very_short"),
    ("Sorry, I said earlier that I used MySQL, but actually it was a CSV file at first.", "self_correction"),
    ("I think a left join returns all rows from the left table but I am not fully sure.", "partly_unsure"),
    ("Can you repeat the question?", "repeat_request"),
    ("I don't know", "no_answer"),
])
def test_answer_signals(answer, code):
    assert code in [s["code"] for s in ie.answer_signals(answer)]


def test_strong_answer_has_no_vagueness_signals():
    strong = ("I built the bed allocation module myself. Every endpoint validated input with a Django form, so a "
              "missing ward returned a 400 error, and I measured the allocation time at 40 ms with a load test.")
    assert ie.answer_signals(strong) == []
    # 'we' is fine when the candidate also says what they did
    assert "vague_contribution" not in [s["code"] for s in ie.answer_signals(
        "We were four people and I wrote the REST endpoints and the tests for the allocation.")]


DUPLICATES = [
    ("Explain your Hospital Management System project.", "Tell me about your hospital management project."),
    ("Tell me about your hospital management project.", "Describe the project you built for hospital management."),
    ("What is a database index?", "What is a database index?"),
    ("Can you walk me through your hospital management project?", "Explain your hospital management project."),
]
DIFFERENT = [
    ("Explain your Hospital Management System project.", "Which part of the hospital system did you personally develop?"),
    ("Explain your Hospital Management System project.", "How did you test the bed allocation module?"),
    ("How did you handle invalid input in your application?", "How would you test that failure case?"),
    ("Tell me about a time a project did not go as planned.", "What did you do when you realized there was a problem?"),
]


@pytest.mark.parametrize("a, b", DUPLICATES)
def test_paraphrases_are_duplicates_without_embeddings(a, b):
    assert ie.is_duplicate(b, [a])[0]


@pytest.mark.parametrize("a, b", DIFFERENT)
def test_different_followups_on_the_same_project_are_allowed(a, b):
    assert not ie.is_duplicate(b, [a])[0]


def test_semantic_and_concept_checks():
    sim = lambda text, prev: [0.83 for _ in prev]  # noqa: E731  (a paraphrase by meaning)
    assert ie.is_duplicate("What made you pick Django?", ["Why did you choose Django?"], similarity=sim) == \
        (True, "same_meaning")
    low = lambda text, prev: [0.2 for _ in prev]  # noqa: E731
    assert not ie.is_duplicate("What made you pick Django?", ["Why did you choose Django?"], similarity=low)[0]
    broken = lambda text, prev: 1 / 0  # noqa: E731  embeddings failing never blocks the interview
    assert not ie.is_duplicate("How did you test it?", ["Why Django?"], similarity=broken)[0]
    m = {"topic": "Hospital Resources Management System", "aspect": "testing"}
    # same topic + aspect AND fairly similar meaning -> a repeat
    mid = lambda text, prev: [0.66 for _ in prev]  # noqa: E731
    assert ie.is_duplicate("Which tests did you write for the allocation?", ["How did you test bed allocation?"],
                           meta=m, previous_meta=[dict(m)], similarity=mid) == (True, "same_concept")
    # regression (real-model eval): same labels but different questions must NOT be rejected
    assert not ie.is_duplicate("How did you test concurrent bookings?", ["How did you test the login page?"],
                               meta=m, previous_meta=[dict(m)], similarity=lambda t, p: [0.35 for _ in p])[0]
    assert "internal_numbering" in ie.validate_question("Your answer for Q3 mentioned AI. Which model?", 30)
    assert not ie.is_duplicate("Can you repeat?", ["Can you repeat?"], allow_repeat=True)[0]


def test_coverage_tracks_aspects_and_suggests_open_ones():
    ctx = ie.candidate_context(ANALYSIS)
    hist = [{"question": "q", "meta": {"topic": "Hospital Resources Management System", "aspect": "objective"}}]
    cov = ie.coverage(hist, ctx, ("objective", "personal_contribution", "testing"), "technical")
    assert cov["covered"] == ["hospital resources management system / objective"]
    assert "not yet asked about personal contribution, testing" in cov["open"][0]
    beh = ie.coverage([], ctx, ("teamwork",), "behavioral")
    assert "Behavioural areas not yet explored" in beh["open"][0]


def test_output_checks():
    assert ie.strip_robotic("Great answer! Excellent. How did you test the module?") == "How did you test the module?"
    assert ie.strip_robotic("That's a great point. Let's move on to the next question. Why Django?") == "Why Django?"
    assert ie.strip_robotic("Interesting choice of database. Why MySQL?") == "Interesting choice of database. Why MySQL?"
    assert ie.validate_question('{"question": "x"}', 30) == ["metadata_leak"]
    assert "too_long" in ie.validate_question(" ".join(["word"] * 40) + "?", 30)
    assert ie.validate_question("Which part did you build?", 30) == []


def test_fallback_is_grounded_and_never_repeats():
    ctx = ie.candidate_context(ANALYSIS)
    order = ("objective", "personal_contribution", "testing")
    first = ie.fallback_question(ctx, [], role="Python Developer", category="technical", aspect_order=order)
    assert first["question"] == "What problem were you trying to solve with Hospital Resources Management System?"
    hist = [{"question": first["question"], "meta": first}]
    second = ie.fallback_question(ctx, hist, role="Python Developer", category="technical", aspect_order=order)
    assert second["aspect"] == "personal_contribution"
    beh = ie.fallback_question(ctx, [], role="Analyst", category="behavioral", aspect_order=order)
    assert beh["question_type"] == "behavioral"
    # nothing invented: with no projects, technical fallbacks are generic scenarios
    none = ie.fallback_question(ie.candidate_context(None), [], role="Dev", category="technical", aspect_order=order)
    assert none["aspect"] == "scenario"


def test_topic_is_derived_from_the_resume_not_generated():
    ctx = ie.candidate_context(ANALYSIS)
    project = "Hospital Resources Management System"
    # regression (real-model eval): these two were the same question but the model labelled them differently
    assert ie.derive_topic("In your bed allocation module, what specific part did you code to check bed "
                           "availability?", ctx) == project
    assert ie.derive_topic("In your hospital system, what part did you write to check if beds were free?", ctx) == project
    assert ie.derive_topic("What did you clean in the data at WebNova?", ctx) == "WebNova"
    assert ie.derive_topic("Why would you pick Django over Flask?", ctx) == "Django"
    assert ie.derive_topic("Tell me about a time you disagreed with someone.", ctx) is None


def test_greeting_with_comma_is_removed():
    from app.services.ai import strip_greeting
    assert strip_greeting("Hi there, what's one thing a Python developer must understand about web apps?") == \
        "what's one thing a Python developer must understand about web apps?"
    # regression (live interview): "Hi Priya, how did you decide ..." - greeting + name
    assert strip_greeting("Hi Priya, how did you decide which alerts to build first?") == \
        "how did you decide which alerts to build first?"


def test_candidate_name_is_not_given_to_the_question_writer():
    ctx = ie.candidate_context({**ANALYSIS, "full_name": "Priya Nair",
                                "candidate_summary": "Priya Nair is a CS graduate. Priya's project is a home-lab SIEM."})
    assert "priya" not in ie.context_block(ctx).lower() and "nair" not in ie.context_block(ctx).lower()
    assert ctx["summary"].startswith("The candidate is a CS graduate")


def test_history_block_compacts_old_turns():
    hist = [{"question": f"Question {i}?", "answer": "word " * 50, "type": "technical", "difficulty": "medium",
             "score": 60, "meta": {"topic": "t", "aspect": "testing"}} for i in range(6)]
    block = ie.history_block(hist)
    assert block.count("<answer>") == 3 and "answer gist:" in block and "topic: t/testing" in block

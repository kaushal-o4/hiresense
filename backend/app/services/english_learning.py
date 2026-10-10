"""English learning drills.

Pronunciation drills are scored deterministically (no AI): the browser's speech recogniser transcribes what
the student read aloud and we align it word-by-word with the target sentence. Speaking exercises are open
answers evaluated by AI.
"""
import difflib
import random
import re

PRONUNCIATION_SENTENCES = {
    "easy": [
        "Thank you for giving me this opportunity.",
        "I am a final year computer science student.",
        "I enjoy working in a team.",
        "My strength is that I learn quickly.",
        "I have completed two internships.",
        "Could you please repeat the question?",
        "I would like to know more about this role.",
        "I am comfortable working with new people.",
        "I spend my free time reading and coding.",
        "Good morning, it is nice to meet you.",
    ],
    "medium": [
        "I developed a web application that helps students track their placement preparation.",
        "During my internship, I collaborated with developers to improve the performance of our database queries.",
        "I believe effective communication is essential for successful teamwork.",
        "My final year project focuses on machine learning techniques for image classification.",
        "I handled a difficult situation by listening carefully and proposing a practical solution.",
        "I am particularly interested in cloud computing and distributed systems.",
        "Whenever I face a challenge, I break it into smaller, manageable tasks.",
        "I regularly practise data structures and algorithms to strengthen my problem-solving skills.",
        "Our team presented the project to the faculty and received appreciation for its usability.",
        "I am confident that my technical skills align with the requirements of this position.",
    ],
    "hard": [
        "The architecture separates the presentation layer from the business logic to improve maintainability.",
        "Asynchronous programming allows applications to remain responsive while performing input and output operations.",
        "I prioritised the requirements, communicated the constraints to stakeholders, and delivered the feature on schedule.",
        "Encryption, authentication, and authorisation are fundamental pillars of application security.",
        "Thoroughly analysing the trade-offs between consistency and availability is crucial in distributed databases.",
        "My enthusiasm for entrepreneurship encouraged me to participate in several national hackathons.",
        "The organisation's sustainability initiatives particularly resonate with my personal values.",
        "Particularly in collaborative environments, articulating technical ideas clearly prevents misunderstandings.",
    ],
}

SPEAKING_PROMPTS = {
    "easy": [
        "Introduce yourself in about one minute.",
        "Describe your favourite subject and why you like it.",
        "Talk about your hometown.",
        "Describe a typical day in your college life.",
        "What are your hobbies and why do you enjoy them?",
    ],
    "medium": [
        "Explain your final-year project to an interviewer.",
        "Describe a time you worked in a team. What was your role?",
        "Why do you want to work in the technology industry?",
        "What are your strengths and one weakness you are working on?",
        "Describe a challenge you faced and how you overcame it.",
        "Where do you see yourself in five years?",
    ],
    "hard": [
        "Convince an interviewer why you are the best candidate for a software engineering role.",
        "Explain a complex technical concept, such as cloud computing, to a non-technical person.",
        "Describe a situation where you disagreed with a teammate and how you resolved it.",
        "Discuss the impact of artificial intelligence on jobs in India.",
        "Describe a failure and what it taught you about yourself.",
    ],
}

LEVELS = ("easy", "medium", "hard")
MAX_ACTIVE_SECONDS = {"pronunciation": 90, "speaking": 240}


def pick_prompt(kind: str, level: str, exclude: set[str] | None = None) -> str:
    pool = (PRONUNCIATION_SENTENCES if kind == "pronunciation" else SPEAKING_PROMPTS)[level]
    fresh = [p for p in pool if p not in (exclude or set())]
    return random.choice(fresh or pool)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))


def score_pronunciation(target: str, spoken: str, confidence: float | None) -> dict:
    """Word-level alignment of the recognised transcript against the target sentence."""
    t, s = _words(target), _words(spoken)
    matcher = difflib.SequenceMatcher(a=t, b=s, autojunk=False)
    words = []
    matched = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            matched += i2 - i1
            words += [{"word": w, "status": "correct"} for w in t[i1:i2]]
        elif tag in ("replace", "delete"):
            heard = s[j1:j2]
            for k, w in enumerate(t[i1:i2]):
                words.append({"word": w, "status": "mispronounced" if tag == "replace" else "missed",
                              "heard": heard[k] if k < len(heard) else None})
    extra = sum(j2 - j1 for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag == "insert")
    accuracy = matched / len(t) if t else 0
    # Penalise extra words lightly; blend in recogniser confidence (clarity) when available.
    word_score = max(0.0, accuracy - 0.05 * extra) * 100
    score = word_score if confidence is None else 0.8 * word_score + 0.2 * confidence * 100
    problem = [w["word"] for w in words if w["status"] != "correct"]
    return {"score": round(score, 1), "word_accuracy": round(accuracy * 100, 1), "extra_words": extra,
            "clarity": round(confidence * 100, 1) if confidence is not None else None,
            "words": words, "practice_words": problem[:10]}

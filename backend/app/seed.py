"""Initial platform data.

    python -m app.seed            # admin account + badges, reward rules, categories, rubrics, question bank
    python -m app.seed --demo     # additionally creates clearly-labelled demo accounts for trying each portal

Safe to run repeatedly (existing rows are left untouched).
"""
import secrets
import sys

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import (
    Assessment, Badge, Challenge, BankQuestion, EvaluationRubric, InterviewCategory, MentorAssignment, MentorProfile,
    RecruiterProfile, RewardRule, StudentProfile, User,
)
from .security import hash_password

# The admin password that older versions of this project shipped and documented. Never accepted for new installs,
# and the server warns at startup while an admin account still uses it.
PUBLISHED_ADMIN_PASSWORD = "Admin@12345"

BADGES = [
    ("first_interview", "First Interview", "Completed your first mock interview.", "🎤", "interviews_completed", 1, 20),
    ("communication_champion", "Communication Champion", "Practised 60+ verified minutes of spoken English.", "🗣️", "english_minutes", 60, 100),
    ("consistent_learner", "Consistent Learner", "Practised on 5 consecutive days.", "📅", "streak_days", 5, 75),
    ("technical_expert", "Technical Expert", "Scored 85+ in a technical mock interview.", "💻", "technical_best_score", 85, 100),
    ("interview_master", "Interview Master", "Scored 80+ in five mock interviews.", "🏆", "high_score_interviews", 5, 150),
    ("practice_30", "Half-Hour Speaker", "Completed 30 verified minutes of English practice.", "⏱️", "english_minutes", 30, 40),
    ("english_regular", "English Regular", "Completed 10 English practice sessions.", "📚", "english_sessions", 10, 60),
    ("assessment_ace", "Assessment Ace", "Passed 3 skill assessments.", "✅", "assessments_passed", 3, 60),
    ("interview_10", "Interview Veteran", "Completed 10 mock interviews.", "🎯", "interviews_completed", 10, 100),
]

REWARD_RULES = [
    ("interview_completed", "Complete a mock interview (all answers at least 8 words, minimum 3 answers)", 30, 3,
     {"min_answers": 3, "min_words_per_answer": 8}),
    ("english_session", "Complete an English practice session with verified active time", 20, 3, {"min_active_seconds": 300}),
    ("assessment_passed", "Pass a skill assessment (first pass of each assessment only)", 25, 5, {}),
    ("score_improvement", "Beat your previous best interview score", 40, 1, {"min_improvement": 10}),
    ("goal_completed", "Complete a goal set by your mentor", 30, 5, {}),
]

CHALLENGES = [
    ("Speak for 15 minutes", "Practise spoken English with Aria for 15 verified minutes today.",
     "english_minutes", 15, "daily", 20),
    ("Interview week", "Complete 3 mock interviews this week.", "interviews_completed", 3, "weekly", 50),
    ("Test yourself", "Pass 2 assessments this week.", "assessments_passed", 2, "weekly", 40),
]

CATEGORIES = [
    ("technical", "Technical", "Programming, CS fundamentals, projects and problem solving"),
    ("hr", "HR", "Background, motivation, career goals and company fit"),
    ("behavioral", "Behavioral", "Teamwork, conflict, leadership and situational questions (STAR)"),
    ("communication", "Communication", "Explaining ideas clearly, presenting and listening"),
]

BANK = {
    "technical": [
        ("Explain the difference between a process and a thread.", "easy", None),
        ("What happens when you type a URL into a browser and press Enter?", "medium", None),
        ("Explain the four pillars of object-oriented programming with examples.", "easy", None),
        ("What is the difference between SQL and NoSQL databases? When would you choose each?", "medium", None),
        ("How does a hash map work internally, and what is a collision?", "medium", None),
        ("Explain time complexity and give the complexity of binary search.", "easy", None),
        ("Describe the most technically challenging project on your resume. What would you change now?", "medium", None),
        ("What is REST? How is it different from GraphQL?", "medium", "web"),
        ("Explain normalisation in databases up to 3NF.", "medium", None),
        ("What is the difference between a stack and a queue? Give a real use of each.", "easy", None),
    ],
    "hr": [
        ("Tell me about yourself.", "easy", None),
        ("Why do you want to join our company?", "easy", None),
        ("Where do you see yourself in five years?", "easy", None),
        ("What are your greatest strengths and weaknesses?", "medium", None),
        ("Why should we hire you over other candidates?", "medium", None),
        ("Are you comfortable relocating or working in shifts?", "easy", None),
    ],
    "behavioral": [
        ("Tell me about a time you worked in a team that faced a conflict. How did you handle it?", "medium", None),
        ("Describe a situation where you failed. What did you learn?", "medium", None),
        ("Tell me about a time you had to meet a tight deadline.", "medium", None),
        ("Give an example of when you showed leadership.", "medium", None),
        ("Describe a time you had to learn something new quickly.", "easy", None),
    ],
    "communication": [
        ("Explain your final-year project to someone with no technical background.", "medium", None),
        ("How would you explain cloud computing to your grandparents?", "easy", None),
        ("Describe a time you had to convince someone to accept your idea.", "medium", None),
        ("Summarise a recent technology news story and why it matters.", "medium", None),
    ],
}

RUBRICS = [
    ("Default interview rubric", "interview", [
        {"name": "Relevance", "weight": 0.25, "description": "Answers the question that was asked"},
        {"name": "Correctness", "weight": 0.3, "description": "Technically accurate / sound reasoning"},
        {"name": "Clarity", "weight": 0.25, "description": "Well structured, specific, with examples"},
        {"name": "Communication", "weight": 0.2, "description": "Professional, confident, concise language"}]),
    ("Default job-match rubric", "job_match", [
        {"name": "Required skills", "weight": 0.4, "description": "Coverage of the job's required skills"},
        {"name": "Projects & experience", "weight": 0.25, "description": "Relevant hands-on work"},
        {"name": "Interview & assessment performance", "weight": 0.25, "description": "Mock interview and test scores"},
        {"name": "Eligibility", "weight": 0.1, "description": "CGPA, branch and graduation year fit"}]),
]


def _mcq(q, options, answer, explanation, marks=1):
    return {"type": "mcq", "question": q, "options": options, "answer_index": answer, "explanation": explanation, "marks": marks}


STARTER_ASSESSMENTS = [
    {"title": "Quantitative Aptitude - Basics", "topic": "Aptitude", "category": "aptitude", "difficulty": "easy",
     "time_limit_minutes": 10, "description": "Percentages, ratios, series and time-and-work.", "questions": [
        _mcq("What is 15% of 240?", ["32", "36", "38", "40"], 1, "0.15 x 240 = 36"),
        _mcq("Find the next number: 2, 6, 12, 20, 30, ?", ["40", "42", "44", "36"], 1, "Differences are 4, 6, 8, 10, 12"),
        _mcq("A can finish a job in 10 days and B in 15 days. Together they take:", ["5 days", "6 days", "8 days", "12.5 days"], 1, "1/10 + 1/15 = 1/6"),
        _mcq("The ratio of boys to girls is 3:2 in a class of 40. How many girls?", ["12", "16", "18", "24"], 1, "2/5 x 40 = 16"),
        _mcq("A train travels 300 km in 5 hours. Its speed in m/s is:", ["16.67", "60", "18", "20"], 0, "60 km/h = 60 x 5/18 = 16.67 m/s"),
        _mcq("If the cost price is 400 and profit is 25%, the selling price is:", ["450", "480", "500", "525"], 2, "400 x 1.25 = 500"),
    ]},
    {"title": "Technical Quiz - CS Fundamentals", "topic": "Computer Science", "category": "technical", "difficulty": "medium",
     "time_limit_minutes": 12, "description": "OOP, DBMS, OS and data structures.", "questions": [
        _mcq("Which data structure uses LIFO order?", ["Queue", "Stack", "Heap", "Graph"], 1, "Stacks are last-in, first-out."),
        _mcq("Time complexity of binary search on a sorted array:", ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1, "The search space halves each step."),
        _mcq("Which SQL clause filters grouped rows?", ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 1, "HAVING filters after GROUP BY."),
        _mcq("Which is NOT a pillar of OOP?", ["Encapsulation", "Inheritance", "Compilation", "Polymorphism"], 2, "Compilation is not an OOP principle."),
        _mcq("A deadlock requires which condition?", ["Preemption", "Circular wait", "Unlimited resources", "Single process"], 1, "Circular wait is one of the four Coffman conditions."),
        _mcq("Which normal form removes partial dependencies?", ["1NF", "2NF", "3NF", "BCNF"], 1, "2NF removes partial dependency on a composite key."),
    ]},
    {"title": "Coding Test - JavaScript Warm-up", "topic": "JavaScript", "category": "coding", "difficulty": "easy",
     "time_limit_minutes": 30, "description": "Write functions. You can run the sample tests in your browser before submitting.",
     "questions": [
        {"type": "coding", "question": "Write a function reverseString(s) that returns the string reversed.",
         "language": "javascript", "function_name": "reverseString", "marks": 5,
         "starter_code": "function reverseString(s) {\n  // your code here\n}\n",
         "test_cases": [{"input": ["hello"], "expected": "olleh"}, {"input": [""], "expected": ""}, {"input": ["ab"], "expected": "ba"}]},
        {"type": "coding", "question": "Write a function isPalindrome(n) that returns true if the integer n reads the same backwards.",
         "language": "javascript", "function_name": "isPalindrome", "marks": 5,
         "starter_code": "function isPalindrome(n) {\n  // your code here\n}\n",
         "test_cases": [{"input": [121], "expected": True}, {"input": [123], "expected": False}, {"input": [7], "expected": True}]},
        _mcq("What does Array.prototype.map return?", ["undefined", "A new array", "The same array", "A number"], 1, "map returns a new array.", 2),
    ]},
    {"title": "Coding Test - Python Basics", "topic": "Python", "category": "coding", "difficulty": "easy",
     "time_limit_minutes": 30, "description": "Python solutions are reviewed by AI (not executed).", "questions": [
        {"type": "coding", "question": "Write a function count_vowels(s) that returns the number of vowels (a, e, i, o, u, case-insensitive) in s.",
         "language": "python", "function_name": "count_vowels", "marks": 5,
         "starter_code": "def count_vowels(s):\n    # your code here\n    pass\n",
         "test_cases": [{"input": ["Interview"], "expected": 4}, {"input": ["xyz"], "expected": 0}]},
        {"type": "coding", "question": "Write a function second_largest(nums) that returns the second largest distinct number in a list (or None).",
         "language": "python", "function_name": "second_largest", "marks": 5,
         "starter_code": "def second_largest(nums):\n    # your code here\n    pass\n",
         "test_cases": [{"input": [[3, 1, 4, 4, 2]], "expected": 3}, {"input": [[5]], "expected": None}]},
    ]},
]


def seed(demo: bool = False) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email == settings.admin_email.lower())):
            password = settings.admin_password
            if not password or password == PUBLISHED_ADMIN_PASSWORD:
                password = secrets.token_urlsafe(12)
                print(f"Created admin account: {settings.admin_email}\n"
                      f"  Generated password (shown only now - store it safely): {password}")
            else:
                print(f"Created admin account: {settings.admin_email} (password from ADMIN_PASSWORD)")
            db.add(User(email=settings.admin_email.lower(), password_hash=hash_password(password),
                        full_name="Platform Administrator", role="admin", status="active"))
        for code, name, desc, icon, ctype, threshold, points in BADGES:
            if not db.scalar(select(Badge).where(Badge.code == code)):
                db.add(Badge(code=code, name=name, description=desc, icon=icon, criteria_type=ctype,
                             threshold=threshold, points=points))
        for activity, desc, points, cap, req in REWARD_RULES:
            if not db.scalar(select(RewardRule).where(RewardRule.activity_type == activity)):
                db.add(RewardRule(activity_type=activity, description=desc, points=points, daily_cap=cap, requirements=req))
        for code, name, desc in CATEGORIES:
            cat = db.scalar(select(InterviewCategory).where(InterviewCategory.code == code))
            if not cat:
                cat = InterviewCategory(code=code, name=name, description=desc)
                db.add(cat)
                db.flush()
                for q, diff, tag in BANK.get(code, []):
                    db.add(BankQuestion(category_id=cat.id, question=q, difficulty=diff, role_tag=tag))
        # Pronunciation/speaking drills were removed from the student portal: retire their challenge in existing
        # databases (kept, not deleted, so past completions and points stay in the history).
        for old in db.scalars(select(Challenge).where(Challenge.metric.in_(("pronunciation_drills",
                                                                             "speaking_exercises")))):
            old.active = False
        drill_rule = db.scalar(select(RewardRule).where(RewardRule.activity_type == "english_exercise"))
        if drill_rule:
            drill_rule.active = False
        speak =db.scalar(select(Challenge).where(Challenge.title == "Speak for 15 minutes"))
        if speak and "or drills" in speak.description:
            speak.description = "Practise spoken English with Aria for 15 verified minutes today."
        for title, desc, metric, target, period, points in CHALLENGES:
            if not db.scalar(select(Challenge).where(Challenge.title == title)):
                db.add(Challenge(title=title, description=desc, metric=metric, target=target, period=period,
                                 points=points))
        for name, applies, criteria in RUBRICS:
            if not db.scalar(select(EvaluationRubric).where(EvaluationRubric.applies_to == applies)):
                db.add(EvaluationRubric(name=name, applies_to=applies, criteria=criteria))
        db.flush()
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id))
        for spec in STARTER_ASSESSMENTS:
            if not db.scalar(select(Assessment).where(Assessment.title == spec["title"])):
                db.add(Assessment(created_by=admin.id if admin else None, pass_percent=60, **spec))
        db.commit()

        if demo:
            _demo_accounts(db)
        print("Seed complete.")
    finally:
        db.close()


def _demo_accounts(db) -> None:
    """Empty demo accounts (no fabricated activity) so each portal can be explored."""
    pw = hash_password("Demo@12345")
    accounts = {
        "student@demo.hiresense": ("Demo Student", "student"),
        "mentor@demo.hiresense": ("Demo Mentor", "mentor"),
        "recruiter@demo.hiresense": ("Demo Recruiter", "recruiter"),
    }
    users = {}
    for email, (name, role) in accounts.items():
        u = db.scalar(select(User).where(User.email == email))
        if not u:
            u = User(email=email, password_hash=pw, full_name=name, role=role, status="active")
            if role == "student":
                u.student_profile = StudentProfile(college="Demo Institute of Technology", degree="B.Tech",
                                                   branch="Computer Science", graduation_year=2027, cgpa=8.0,
                                                   skills=["Python", "SQL", "Git"], projects=[], experience=[],
                                                   target_role="Software Engineer")
            elif role == "mentor":
                u.mentor_profile = MentorProfile(department="Training & Placement", expertise=["Interviews", "Python"])
            else:
                u.recruiter_profile = RecruiterProfile(company_name="Demo Company (sample)", designation="HR Manager")
            db.add(u)
            db.flush()
            print(f"Created demo {role}: {email} / Demo@12345")
        users[role] = u
    if not db.scalar(select(MentorAssignment).where(MentorAssignment.mentor_id == users["mentor"].id,
                                                    MentorAssignment.student_id == users["student"].id)):
        db.add(MentorAssignment(mentor_id=users["mentor"].id, student_id=users["student"].id))
    db.commit()


if __name__ == "__main__":
    seed(demo="--demo" in sys.argv)

"""Database models for HireSense, stored in MongoDB (one collection per model, see odm.py).

Enumerated values are short strings; the allowed values below are enforced by the API schemas.
"""
from datetime import datetime, timezone

from .odm import (
    JSON, Base, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Mapped,
    String, Text, UniqueConstraint, mapped_column, relationship,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


ROLES = ("student", "recruiter", "mentor", "admin")
USER_STATUSES = ("pending", "active", "suspended", "deactivated")
JOB_STATUSES = ("draft", "published", "closed")
APP_STATUSES = ("applied", "shortlisted", "interview_scheduled", "on_hold", "selected", "rejected", "withdrawn")
SESSION_STATUSES = ("in_progress", "completed", "abandoned")
INTERVIEW_CATEGORIES = ("technical", "hr", "behavioral", "communication", "mixed")
GOAL_TYPES = ("mock_interview", "english_practice", "assessment", "resume_update", "resource", "custom")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# --------------------------------------------------------------------------- users

class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("role", ROLES), name="ck_users_role"),
        CheckConstraint(_in("status", USER_STATUSES), name="ck_users_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    # Extra grants given by an admin, e.g. ["view_all_students"] for a mentor.
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Per-user preferences, e.g. {"speech_lang": "en-IN", "subtitles": true}
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the student agreed that their data may be sent to the hosted AI (services/consent.py); None = not agreed
    ai_data_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student_profile: Mapped["StudentProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    recruiter_profile: Mapped["RecruiterProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    mentor_profile: Mapped["MentorProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    college: Mapped[str | None] = mapped_column(String(200))
    degree: Mapped[str | None] = mapped_column(String(120))
    branch: Mapped[str | None] = mapped_column(String(120), index=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer, index=True)
    cgpa: Mapped[float | None] = mapped_column(Float)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    projects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    career_interests: Mapped[str | None] = mapped_column(Text)
    target_role: Mapped[str | None] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(300))
    github_url: Mapped[str | None] = mapped_column(String(300))
    # Opt-in consent to appear in the recruiter student database.
    share_with_recruiters: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    user: Mapped[User] = relationship(back_populates="student_profile")

    __table_args__ = (CheckConstraint("cgpa IS NULL OR (cgpa >= 0 AND cgpa <= 10)", name="ck_student_cgpa"),)


class RecruiterProfile(Base):
    __tablename__ = "recruiter_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_website: Mapped[str | None] = mapped_column(String(300))
    designation: Mapped[str | None] = mapped_column(String(120))
    company_description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    industry: Mapped[str | None] = mapped_column(String(120))
    company_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    user: Mapped[User] = relationship(back_populates="recruiter_profile")


class MentorProfile(Base):
    __tablename__ = "mentor_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    department: Mapped[str | None] = mapped_column(String(120))
    expertise: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    max_students: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    user: Mapped[User] = relationship(back_populates="mentor_profile")


class MentorAssignment(TimestampMixin, Base):
    __tablename__ = "mentor_assignments"
    __table_args__ = (UniqueConstraint("mentor_id", "student_id", name="uq_mentor_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    mentor: Mapped[User] = relationship(foreign_keys=[mentor_id])
    student: Mapped[User] = relationship(foreign_keys=[student_id])


# --------------------------------------------------------------------------- resumes

class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (CheckConstraint(_in("analysis_status", ("pending", "completed", "failed", "unavailable")), name="ck_resume_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    analysis: Mapped[dict | None] = mapped_column(JSON)
    analysis_error: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    skills: Mapped[list["ResumeSkill"]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ResumeSkill(Base):
    __tablename__ = "resume_skills"
    __table_args__ = (UniqueConstraint("resume_id", "name", name="uq_resume_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))

    resume: Mapped[Resume] = relationship(back_populates="skills")


# --------------------------------------------------------------------------- interviews

class InterviewCategory(TimestampMixin, Base):
    __tablename__ = "interview_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_question_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BankQuestion(TimestampMixin, Base):
    __tablename__ = "question_bank"
    __table_args__ = (CheckConstraint(_in("difficulty", ("easy", "medium", "hard")), name="ck_bank_difficulty"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("interview_categories.id", ondelete="CASCADE"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    role_tag: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    category: Mapped[InterviewCategory] = relationship()


class EvaluationRubric(TimestampMixin, Base):
    __tablename__ = "evaluation_rubrics"
    __table_args__ = (CheckConstraint(_in("applies_to", ("interview", "english", "job_match")), name="ck_rubric_applies"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    # [{"name": "Relevance", "weight": 0.25, "description": "..."}]
    criteria: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(_in("status", SESSION_STATUSES), name="ck_interview_status"),
        CheckConstraint(_in("category", INTERVIEW_CATEGORIES), name="ck_interview_category"),
        CheckConstraint(_in("mode", ("text", "voice")), name="ck_interview_mode"),
        Index("ix_interview_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_role: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="text", nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), default="medium", server_default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    planned_questions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))
    question_source: Mapped[str] = mapped_column(String(20), default="ai", nullable=False)  # ai | question_bank
    subject: Mapped[str | None] = mapped_column(String(100))  # optional technical subject chosen by the student
    # AI interviewer personality (services/interviewers.py); null on older sessions = "aria"
    interviewer: Mapped[str | None] = mapped_column(String(20))
    # "fast" (short questions, feedback at the end) or "coaching" (spoken feedback, hints, more time); null = fast
    response_mode: Mapped[str | None] = mapped_column(String(10))
    # Camera/browser monitoring consent for this interview (routers/monitoring.py): policy version, features the
    # candidate agreed to, accepted/withdrawn times, camera permission outcome. Null = not monitored.
    monitoring: Mapped[dict | None] = mapped_column(JSON)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overall_score: Mapped[float | None] = mapped_column(Float)
    report: Mapped[dict | None] = mapped_column(JSON)
    report_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending|completed|unavailable
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flag_reason: Mapped[str | None] = mapped_column(Text)

    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewQuestion.position")


class InterviewQuestion(TimestampMixin, Base):
    __tablename__ = "interview_questions"
    __table_args__ = (UniqueConstraint("session_id", "position", name="uq_question_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(10))  # level this question was generated at
    preface: Mapped[str | None] = mapped_column(Text)  # short explanation shown before a simpler follow-up
    meta: Mapped[dict | None] = mapped_column(JSON)  # source, classifier check, etc.

    session: Mapped[InterviewSession] = relationship(back_populates="questions")
    answer: Mapped["InterviewAnswer | None"] = relationship(back_populates="question", uselist=False, cascade="all, delete-orphan")


class InterviewAnswer(TimestampMixin, Base):
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(10), default="text", nullable=False)
    response_seconds: Mapped[int | None] = mapped_column(Integer)
    # pending | scored (score known, detailed feedback still being written) | completed | unavailable
    evaluation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    scores: Mapped[dict | None] = mapped_column(JSON)  # relevance/correctness/clarity/communication 0-10
    score: Mapped[float | None] = mapped_column(Float)  # 0-100
    feedback: Mapped[str | None] = mapped_column(Text)
    sample_answer: Mapped[str | None] = mapped_column(Text)
    # strengths, missing_concepts, improvements, content/communication scores, next_difficulty, rule notes
    details: Mapped[dict | None] = mapped_column(JSON)

    question: Mapped[InterviewQuestion] = relationship(back_populates="answer")


# --------------------------------------------------------------------------- assessments

class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    # aptitude | technical | coding | english | other
    category: Mapped[str] = mapped_column(String(20), default="technical", server_default="technical", index=True, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), default="medium", server_default="medium", nullable=False)
    # MCQ:    {"type": "mcq", "question", "options": [str], "answer_index": int, "explanation", "marks"}
    # Coding: {"type": "coding", "question", "language", "function_name", "starter_code",
    #          "test_cases": [{"input": [...args], "expected": any}], "marks"}
    questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    pass_percent: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AssessmentResult(TimestampMixin, Base):
    __tablename__ = "assessment_results"
    __table_args__ = (Index("ix_assessment_result_student", "student_id", "assessment_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)  # percent
    correct_count: Mapped[int | None] = mapped_column(Integer)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    marks_obtained: Mapped[float | None] = mapped_column(Float)
    max_marks: Mapped[float | None] = mapped_column(Float)
    # completed | pending (coding answers awaiting AI review)
    evaluation_status: Mapped[str] = mapped_column(String(20), default="completed", server_default="completed", nullable=False)
    # per-question results: [{"type", "correct"|"score", "feedback", ...}]
    details: Mapped[list | None] = mapped_column(JSON)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flag_reason: Mapped[str | None] = mapped_column(Text)

    assessment: Mapped[Assessment] = relationship()


# --------------------------------------------------------------------------- english practice

class EnglishSession(TimestampMixin, Base):
    __tablename__ = "english_sessions"
    __table_args__ = (CheckConstraint(_in("status", SESSION_STATUSES), name="ck_english_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="text", nullable=False)
    # free_talk | interview (null on sessions created before practice styles existed = free_talk)
    style: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Verified active time computed server-side from message timestamps.
    active_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scores: Mapped[dict | None] = mapped_column(JSON)
    overall_score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[dict | None] = mapped_column(JSON)
    evaluation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # free_conversation | english_learning | confidence (services/english_companion.py); null on older = free
    learning_mode: Mapped[str | None] = mapped_column(String(20))
    # Compact conversation memory: topics, interests, details, questions asked, corrections given
    memory: Mapped[dict | None] = mapped_column(JSON)

    messages: Mapped[list["EnglishMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="EnglishMessage.id")


class EnglishMessage(TimestampMixin, Base):
    __tablename__ = "english_messages"
    __table_args__ = (CheckConstraint(_in("sender", ("student", "ai")), name="ck_english_sender"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("english_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    sender: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(10), default="text", nullable=False)
    speech_confidence: Mapped[float | None] = mapped_column(Float)
    corrections: Mapped[list | None] = mapped_column(JSON)
    # AI turns only: {"avatar_mode", "encouragement", "suggested_followups"}
    meta: Mapped[dict | None] = mapped_column(JSON)

    session: Mapped[EnglishSession] = relationship(back_populates="messages")


# --------------------------------------------------------------------------- progress & rewards

class ProgressRecord(TimestampMixin, Base):
    __tablename__ = "progress_records"
    __table_args__ = (Index("ix_progress_student_metric", "student_id", "metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # interview_score | technical_score | hr_score | english_score | assessment_score | english_minutes
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))


class Badge(TimestampMixin, Base):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(20), default="🏅", nullable=False)
    # interviews_completed | english_minutes | avg_interview_score | technical_best_score |
    # streak_days | assessments_passed | english_sessions | high_score_interviews
    criteria_type: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StudentBadge(Base):
    __tablename__ = "student_badges"
    __table_args__ = (UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id", ondelete="CASCADE"), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    badge: Mapped[Badge] = relationship()


class RewardRule(TimestampMixin, Base):
    __tablename__ = "reward_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    # interview_completed | english_session | assessment_passed | score_improvement | goal_completed
    activity_type: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_cap: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # max awards/day
    # e.g. {"min_answers": 3, "min_words_per_answer": 8} or {"min_active_seconds": 300}
    requirements: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (CheckConstraint("points >= 0", name="ck_reward_points"),)


class PointTransaction(TimestampMixin, Base):
    __tablename__ = "point_transactions"
    __table_args__ = (
        # A given activity can only ever earn a given reward once.
        UniqueConstraint("student_id", "activity_type", "source_type", "source_id", name="uq_point_source"),
        Index("ix_points_student_created", "student_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# --------------------------------------------------------------------------- jobs

class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUSES), name="ck_job_status"),
        CheckConstraint(_in("job_type", ("full_time", "internship", "part_time", "contract")), name="ck_job_type"),
        Index("ix_job_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), default="full_time", nullable=False)
    experience_years: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    salary: Mapped[str | None] = mapped_column(String(100))
    min_cgpa: Mapped[float | None] = mapped_column(Float)
    eligible_branches: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    graduation_years: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requirements: Mapped[list["JobRequirement"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    recruiter: Mapped[User] = relationship()


class JobRequirement(Base):
    __tablename__ = "job_requirements"
    __table_args__ = (
        UniqueConstraint("job_id", "skill", name="uq_job_skill"),
        CheckConstraint(_in("importance", ("required", "preferred")), name="ck_req_importance"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    skill: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    importance: Mapped[str] = mapped_column(String(20), default="required", nullable=False)

    job: Mapped[Job] = relationship(back_populates="requirements")


class JobApplication(TimestampMixin, Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("job_id", "student_id", name="uq_application"),
        CheckConstraint(_in("status", APP_STATUSES), name="ck_application_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="applied", index=True, nullable=False)
    cover_letter: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recruiter_notes: Mapped[str | None] = mapped_column(Text)
    # {"score": 0-100, "method": "ai"|"rule_based", "matched": [...], "missing": [...], ...}
    match: Mapped[dict | None] = mapped_column(JSON)

    job: Mapped[Job] = relationship()
    student: Mapped[User] = relationship()
    history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationStatusHistory.id")


class ApplicationStatusHistory(TimestampMixin, Base):
    __tablename__ = "application_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id", ondelete="CASCADE"), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)

    application: Mapped[JobApplication] = relationship(back_populates="history")


# --------------------------------------------------------------------------- mentoring

class MentorFeedback(TimestampMixin, Base):
    __tablename__ = "mentor_feedback"
    __table_args__ = (CheckConstraint(_in("kind", ("feedback", "note")), name="ck_feedback_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # "feedback" is shared with the student; "note" is private to mentors/admins.
    kind: Mapped[str] = mapped_column(String(10), default="feedback", nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    mentor: Mapped[User] = relationship(foreign_keys=[mentor_id])


class ImprovementPlan(TimestampMixin, Base):
    __tablename__ = "improvement_plans"
    __table_args__ = (CheckConstraint(_in("status", ("active", "completed", "archived")), name="ck_plan_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    goals: Mapped[list["PlanGoal"]] = relationship(back_populates="plan", cascade="all, delete-orphan", order_by="PlanGoal.id")
    mentor: Mapped[User] = relationship(foreign_keys=[mentor_id])


class PlanGoal(TimestampMixin, Base):
    __tablename__ = "plan_goals"
    __table_args__ = (
        CheckConstraint(_in("goal_type", GOAL_TYPES), name="ck_goal_type"),
        CheckConstraint(_in("status", ("pending", "completed")), name="ck_goal_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("improvement_plans.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal_type: Mapped[str] = mapped_column(String(30), default="custom", nullable=False)
    resource_url: Mapped[str | None] = mapped_column(String(500))
    target_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    target_score: Mapped[float | None] = mapped_column(Float)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[ImprovementPlan] = relationship(back_populates="goals")


class MentorSession(TimestampMixin, Base):
    __tablename__ = "mentor_sessions"
    __table_args__ = (CheckConstraint(_in("status", ("scheduled", "completed", "cancelled")), name="ck_msession_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agenda: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_link: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    outcome_notes: Mapped[str | None] = mapped_column(Text)

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    mentor: Mapped[User] = relationship(foreign_keys=[mentor_id])


# --------------------------------------------------------------------------- platform

class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="info", nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))

    actor: Mapped[User | None] = relationship()


class AIUsageLog(TimestampMixin, Base):
    __tablename__ = "ai_usage_logs"
    __table_args__ = (Index("ix_ai_usage_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    feature: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # success|error|unavailable|rate_limited
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)


class PerfMetric(TimestampMixin, Base):
    """One timed step of the interview pipeline (services/perf.py). Never holds candidate content: only the step
    name, its duration, success, and numeric details such as token counts."""
    __tablename__ = "perf_metrics"
    __table_args__ = (Index("ix_perf_metric_created", "metric", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    metric: Mapped[str] = mapped_column(String(60), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(10), default="server", nullable=False)  # server | client
    meta: Mapped[dict | None] = mapped_column(JSON)


INTEGRITY_EVENT_TYPES = ("face_absent", "multiple_faces", "attention_away", "camera_interrupted",
                         "camera_obstructed", "low_light", "monitoring_interrupted", "focus_change",
                         "permission_revoked", "monitoring_withdrawn", "monitoring_unavailable",
                         "paste_detected", "paste_long", "fullscreen_exit", "second_display", "phone_in_view",
                         "notes_in_view",
                         # security module (2026-10-23): partial face, repeated gaze, audio, connection, session
                         "face_partial", "attention_repeated", "background_speech", "microphone_disconnected",
                         "network_interruption", "session_reconnected", "interview_paused")
INTEGRITY_SEVERITIES = ("info", "low", "medium", "high")
# dismissed = technical / false signal (older reviews); false_positive and needs_review added 2026-10-23
INTEGRITY_REVIEW = ("pending", "no_concern", "concern_noted", "dismissed", "false_positive", "needs_review")


class IntegrityEvent(TimestampMixin, Base):
    """A camera/browser monitoring signal from a monitored interview. Signals are approximate indicators for a human
    reviewer, never proof of misconduct, and never change interview scores. No images or video are stored."""
    __tablename__ = "integrity_events"
    __table_args__ = (
        CheckConstraint(_in("event_type", INTEGRITY_EVENT_TYPES), name="ck_integrity_type"),
        CheckConstraint(_in("severity", INTEGRITY_SEVERITIES), name="ck_integrity_severity"),
        CheckConstraint(_in("review_status", INTEGRITY_REVIEW), name="ck_integrity_review"),
        Index("ix_integrity_session", "session_id", "t_ms"),
        # retried / re-sent batches carry the same client id, so an event is stored once
        UniqueConstraint("session_id", "client_event_id", name="uq_integrity_client_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    t_ms: Mapped[int] = mapped_column(Integer, nullable=False)  # milliseconds since the interview room opened
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)  # share of analysed frames that agreed (0-1)
    confidence_sufficient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="info", nullable=False)  # set by the server
    candidate_explanation: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_event_id: Mapped[str | None] = mapped_column(String(40))  # idempotency key from the browser
    source: Mapped[str] = mapped_column(String(10), default="browser", nullable=False)  # browser | server
    # small whitelisted facts about the event (e.g. max_faces, cause, count) - never media or measurements of a face
    details: Mapped[dict | None] = mapped_column(JSON)


class IntegrityReview(Base):
    """Append-only history of reviews of an integrity event. The event keeps its original detection fields; a
    review only adds a status and notes, so nobody can silently rewrite what was detected."""
    __tablename__ = "integrity_reviews"
    __table_args__ = (
        CheckConstraint(_in("review_status", INTEGRITY_REVIEW), name="ck_integrity_review_status"),
        Index("ix_integrity_review_event", "event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("integrity_events.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_role: Mapped[str] = mapped_column(String(20), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ErrorLog(TimestampMixin, Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer)


class AssessmentAssignment(TimestampMixin, Base):
    """A recruiter assigns a specific assessment to a specific applicant."""
    __tablename__ = "assessment_assignments"
    __table_args__ = (
        UniqueConstraint("assessment_id", "application_id", name="uq_assignment"),
        CheckConstraint(_in("status", ("assigned", "completed")), name="ck_assignment_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False)
    application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)
    result_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_results.id", ondelete="SET NULL"))

    assessment: Mapped[Assessment] = relationship()
    result: Mapped["AssessmentResult | None"] = relationship()


class ApplicationMessage(TimestampMixin, Base):
    """Recruiter <-> student conversation attached to a job application."""
    __tablename__ = "application_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("job_applications.id", ondelete="CASCADE"), index=True, nullable=False)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20), default="message", nullable=False)  # message|invitation|assessment|update
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sender: Mapped[User | None] = relationship()


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"
    __table_args__ = (
        CheckConstraint(_in("period", ("daily", "weekly")), name="ck_challenge_period"),
        CheckConstraint("target > 0", name="ck_challenge_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # english_minutes | english_sessions | speaking_exercises | pronunciation_drills |
    # interviews_completed | assessments_passed
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    target: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[str] = mapped_column(String(10), default="daily", nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ChallengeCompletion(TimestampMixin, Base):
    __tablename__ = "challenge_completions"
    __table_args__ = (UniqueConstraint("challenge_id", "student_id", "period_key", name="uq_challenge_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False)  # "2026-10-10" or "2026-W41"

    challenge: Mapped[Challenge] = relationship()


class PracticeExercise(TimestampMixin, Base):
    """English learning drills: pronunciation (read a sentence aloud) and speaking (answer a prompt)."""
    __tablename__ = "practice_exercises"
    __table_args__ = (
        CheckConstraint(_in("kind", ("pronunciation", "speaking")), name="ck_exercise_kind"),
        CheckConstraint(_in("status", ("in_progress", "completed")), name="ck_exercise_status"),
        Index("ix_exercise_student_kind", "student_id", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text)
    speech_confidence: Mapped[float | None] = mapped_column(Float)
    # Verified server-side from start/submit timestamps (capped).
    active_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)  # 0-100
    details: Mapped[dict | None] = mapped_column(JSON)
    evaluation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlacementDrive(TimestampMixin, Base):
    __tablename__ = "placement_drives"
    __table_args__ = (CheckConstraint(_in("status", ("upcoming", "completed", "cancelled")), name="ck_drive_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    drive_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    min_cgpa: Mapped[float | None] = mapped_column(Float)
    eligible_branches: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="upcoming", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    registrations: Mapped[list["DriveRegistration"]] = relationship(back_populates="drive", cascade="all, delete-orphan")


class DriveRegistration(TimestampMixin, Base):
    __tablename__ = "drive_registrations"
    __table_args__ = (UniqueConstraint("drive_id", "student_id", name="uq_drive_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    drive_id: Mapped[int] = mapped_column(ForeignKey("placement_drives.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    drive: Mapped[PlacementDrive] = relationship(back_populates="registrations")
    student: Mapped[User] = relationship()


class Announcement(TimestampMixin, Base):
    __tablename__ = "announcements"
    __table_args__ = (CheckConstraint(_in("audience", ("all", "student", "recruiter", "mentor")), name="ck_announcement_audience"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))
    recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EnglishMistakePattern(TimestampMixin, Base):
    """One kind of English mistake a student keeps making, counted from the corrections given in their practice
    sessions (services/english_profile.py). The category is a rough, rule-based label, not a grammar analysis.
    The student can dismiss a pattern or clear all of them."""
    __tablename__ = "english_mistake_patterns"
    __table_args__ = (UniqueConstraint("student_id", "category", name="uq_mistake_student_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # distinct practice sessions
    last_session_id: Mapped[int | None] = mapped_column(Integer)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    example_original: Mapped[str | None] = mapped_column(String(300))
    example_corrected: Mapped[str | None] = mapped_column(String(300))
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

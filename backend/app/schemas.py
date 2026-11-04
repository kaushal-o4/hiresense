"""Request validation schemas."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def _strong_password(v: str) -> str:
    if len(v) < 8 or not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
        raise ValueError("Password must be at least 8 characters and include letters and numbers")
    return v


# --------------------------------------------------------------------------- auth

class StudentRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(max_length=128)
    college: str | None = Field(default=None, max_length=200)
    branch: str | None = Field(default=None, max_length=120)
    graduation_year: int | None = Field(default=None, ge=1990, le=2100)
    share_with_recruiters: bool = False
    ai_consent: bool = False  # agreed to the hosted-AI data notice (only asked when LOCAL_AI_PROVIDER=gemini)

    _pw = field_validator("password")(_strong_password)


class RecruiterRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(max_length=128)
    company_name: str = Field(min_length=2, max_length=200)
    designation: str | None = Field(default=None, max_length=120)
    company_website: str | None = Field(default=None, max_length=300)
    industry: str | None = Field(default=None, max_length=120)

    _pw = field_validator("password")(_strong_password)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_strong_password)


# --------------------------------------------------------------------------- profiles

class ProjectItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    technologies: list[str] = Field(default_factory=list, max_length=30)
    link: str | None = Field(default=None, max_length=300)


class ExperienceItem(BaseModel):
    organization: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=120)
    duration: str = Field(default="", max_length=100)
    summary: str = Field(default="", max_length=2000)


class ResumeAnalysisCorrection(BaseModel):
    """Student's corrections to the AI-extracted resume details. Omitted fields are left unchanged."""
    full_name: str | None = Field(default=None, max_length=120)
    technical_skills: list[str] | None = Field(default=None, max_length=100)
    soft_skills: list[str] | None = Field(default=None, max_length=30)
    certifications: list[str] | None = Field(default=None, max_length=30)
    projects: list[ProjectItem] | None = Field(default=None, max_length=30)
    experience: list[ExperienceItem] | None = Field(default=None, max_length=30)
    internships: list[ExperienceItem] | None = Field(default=None, max_length=30)


class StudentProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    college: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=120)
    graduation_year: int | None = Field(default=None, ge=1990, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    skills: list[str] | None = Field(default=None, max_length=100)
    projects: list[ProjectItem] | None = Field(default=None, max_length=30)
    experience: list[ExperienceItem] | None = Field(default=None, max_length=30)
    career_interests: str | None = Field(default=None, max_length=2000)
    target_role: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    linkedin_url: str | None = Field(default=None, max_length=300)
    github_url: str | None = Field(default=None, max_length=300)


class RecruiterProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    company_website: str | None = Field(default=None, max_length=300)
    designation: str | None = Field(default=None, max_length=120)
    company_description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    industry: str | None = Field(default=None, max_length=120)


class MentorProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    expertise: list[str] | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=2000)


class AdminProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


# --------------------------------------------------------------------------- interviews

class InterviewStart(BaseModel):
    job_role: str = Field(min_length=2, max_length=120)
    category: Literal["technical", "hr", "behavioral", "communication", "mixed"] = "mixed"
    mode: Literal["text", "voice"] = "text"
    question_count: int = Field(default=5, ge=3, le=15)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    subject: str | None = Field(default=None, max_length=100)
    interviewer: Literal["aria", "victor", "marcus", "elena"] = "aria"
    # fast: short questions, feedback at the end. coaching: spoken feedback and hints, more time to answer.
    response_mode: Literal["fast", "coaching"] = "fast"
    # Live voice interviews: return at once and prepare the first question in the background while the candidate
    # goes through the monitoring disclosure and device check.
    defer_first_question: bool = False


class AnswerIn(BaseModel):
    question_id: int
    answer: str = Field(min_length=1, max_length=8000)
    input_mode: Literal["text", "voice"] = "text"
    response_seconds: int | None = Field(default=None, ge=0, le=7200)
    # voice answers: seconds of actual speech in the recording (from /transcribe), for speaking-pace indicators
    speech_seconds: float | None = Field(default=None, ge=0, le=7200)
    interrupted: bool = False  # the interviewer stopped the answer at its time limit (stress interview)


class TTSOptions(BaseModel):
    voice: str | None = Field(default=None, max_length=40)
    speed: float | None = Field(default=None, ge=0.7, le=1.4)


class TurnIn(BaseModel):
    """One conversational turn of a live interview (streamed): optionally the answer to the current question, then
    the next question, spoken sentence by sentence when `tts` is given."""
    answer: AnswerIn | None = None
    tts: TTSOptions | None = None
    client_turn_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


# --------------------------------------------------------------------------- monitoring

class MonitoringFeatures(BaseModel):
    camera: bool = False  # camera on with a self-view; required by every other camera feature
    face_presence: bool = False
    multiple_faces: bool = False
    attention: bool = False  # approximate head direction / gaze (optional, separate consent)
    focus_changes: bool = False  # browser tab/window focus changes
    paste: bool = False  # long pastes into typed answers (never the text)
    screen: bool = False  # full screen exits and extra displays
    objects: bool = False  # phone / notes in the camera view (on-device object detection; needs camera)
    audio: bool = False  # possible additional voice while answering (on-device speech + mouth movement; needs camera)


class MonitoringConsentIn(BaseModel):
    policy_version: str = Field(max_length=20)
    features: MonitoringFeatures
    camera_permission: Literal["granted", "denied", "unavailable", "not_requested"] = "not_requested"


class IntegrityEventIn(BaseModel):
    event_type: Literal["face_absent", "multiple_faces", "attention_away", "camera_interrupted", "camera_obstructed",
                        "low_light", "monitoring_interrupted", "focus_change", "permission_revoked",
                        "monitoring_unavailable", "paste_detected", "paste_long", "fullscreen_exit",
                        "second_display", "phone_in_view", "notes_in_view", "face_partial",
                        "attention_repeated", "background_speech", "microphone_disconnected",
                        "network_interruption", "interview_paused"]
    t_ms: int = Field(ge=0, le=6 * 3600 * 1000)  # interview-relative time
    duration_ms: int | None = Field(default=None, ge=0, le=6 * 3600 * 1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    # idempotency key: a re-sent event (retry after a network error, page closing) is stored only once
    client_event_id: str | None = Field(default=None, min_length=8, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    details: dict[str, int | str] | None = Field(default=None, max_length=6)  # whitelisted in integrity.clean_details


class IntegrityEventsIn(BaseModel):
    events: list[IntegrityEventIn] = Field(max_length=50)


_MS = Field(ge=0, le=86_400_000)


class AttentionIn(BaseModel):
    """Cumulative time totals of ONE monitor run (browser). No frames, landmarks or coordinates."""
    epoch: str = Field(min_length=6, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    window_ms: int = Field(ge=5_000, le=300_000)
    toward_ms: int = _MS
    away_ms: int = _MS
    unobserved_ms: int = _MS
    paused_ms: int = _MS
    calibrating_ms: int = _MS
    calibrated: bool | None = None  # False = calibration failed or was skipped: absolute limits were used
    by_reason: dict[Literal["face_not_visible", "low_confidence", "unavailable", "gap"], int] = Field(max_length=4)
    # [bucket index (10 s each), toward_ms, away_ms, unobserved_ms]
    buckets: list[tuple[int, int, int, int]] = Field(max_length=720)

    @model_validator(mode="after")
    def _plausible(self):
        if any(v < 0 or v > 86_400_000 for v in self.by_reason.values()):
            raise ValueError("by_reason out of range")
        for idx, t, a, u in self.buckets:
            if idx < 0 or idx > 8_640 or min(t, a, u) < 0 or t + a + u > 11_000:
                raise ValueError("bucket out of range")
        return self


class ExplanationIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class IntegrityReviewIn(BaseModel):
    review_status: Literal["pending", "no_concern", "concern_noted", "dismissed", "false_positive", "needs_review"]
    reviewer_notes: str | None = Field(default=None, max_length=2000)


class ClientMetric(BaseModel):
    metric: str = Field(max_length=60)
    duration_ms: float = Field(ge=0, le=3_600_000)
    ok: bool = True
    meta: dict | None = None


class ClientMetricsIn(BaseModel):
    metrics: list[ClientMetric] = Field(max_length=50)


# --------------------------------------------------------------------------- english

class EnglishStart(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    mode: Literal["text", "voice"] = "text"
    style: Literal["free_talk", "interview"] = "free_talk"
    learning_mode: Literal["free_conversation", "english_learning", "confidence"] = "free_conversation"


class EnglishMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=3000)
    input_mode: Literal["text", "voice"] = "text"
    speech_confidence: float | None = Field(default=None, ge=0, le=1)


# --------------------------------------------------------------------------- assessments

class MCQIn(BaseModel):
    type: Literal["mcq"] = "mcq"
    question: str = Field(min_length=3, max_length=2000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0)
    explanation: str = Field(default="", max_length=2000)
    marks: float = Field(default=1, gt=0, le=100)

    @field_validator("answer_index")
    @classmethod
    def _idx(cls, v, info):
        opts = info.data.get("options") or []
        if opts and v >= len(opts):
            raise ValueError("answer_index must point to one of the options")
        return v


class TestCaseIn(BaseModel):
    input: list = Field(default_factory=list, max_length=10)  # positional arguments
    expected: str | int | float | bool | list | dict | None = None


class CodingIn(BaseModel):
    type: Literal["coding"]
    question: str = Field(min_length=10, max_length=5000)
    language: Literal["python", "javascript", "java", "cpp", "c"] = "python"
    function_name: str = Field(default="solution", pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,60}$")
    starter_code: str = Field(default="", max_length=5000)
    test_cases: list[TestCaseIn] = Field(default_factory=list, max_length=10)
    marks: float = Field(default=5, gt=0, le=100)


class AssessmentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    topic: str = Field(min_length=2, max_length=100)
    category: Literal["aptitude", "technical", "coding", "english", "other"] = "technical"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    questions: list[Annotated[MCQIn | CodingIn, Field(discriminator="type")]] = Field(min_length=1, max_length=50)

    @field_validator("questions", mode="before")
    @classmethod
    def _default_type(cls, v):
        if isinstance(v, list):
            return [({**q, "type": q.get("type") or "mcq"} if isinstance(q, dict) else q) for q in v]
        return v
    time_limit_minutes: int = Field(default=15, ge=1, le=180)
    pass_percent: int = Field(default=60, ge=1, le=100)
    job_id: int | None = None
    active: bool = True


class AssessmentGenerate(BaseModel):
    topic: str = Field(min_length=2, max_length=100)
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class AssessmentSubmit(BaseModel):
    # MCQ -> option index; coding -> source code string; unanswered -> null
    answers: list[int | Annotated[str, Field(max_length=20000)] | None] = Field(max_length=50)


# --------------------------------------------------------------------------- jobs

class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=20, max_length=10000)
    location: str = Field(min_length=2, max_length=200)
    job_type: Literal["full_time", "internship", "part_time", "contract"] = "full_time"
    experience_years: float = Field(default=0, ge=0, le=30)
    salary: str | None = Field(default=None, max_length=100)
    min_cgpa: float | None = Field(default=None, ge=0, le=10)
    eligible_branches: list[str] = Field(default_factory=list, max_length=30)
    graduation_years: list[int] = Field(default_factory=list, max_length=10)
    required_skills: list[str] = Field(default_factory=list, max_length=40)
    preferred_skills: list[str] = Field(default_factory=list, max_length=40)
    deadline: datetime | None = None
    status: Literal["draft", "published"] = "draft"


class ApplyIn(BaseModel):
    cover_letter: str | None = Field(default=None, max_length=4000)


class ApplicationStatusIn(BaseModel):
    status: Literal["applied", "shortlisted", "interview_scheduled", "on_hold", "selected", "rejected"]
    note: str | None = Field(default=None, max_length=2000)
    interview_at: datetime | None = None


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    kind: Literal["message", "invitation", "update"] = "message"


class AssignAssessmentIn(BaseModel):
    assessment_id: int
    due_at: datetime | None = None
    message: str | None = Field(default=None, max_length=2000)


class CompareIn(BaseModel):
    application_ids: list[int] = Field(min_length=2, max_length=5)


# --------------------------------------------------------------------------- mentoring

class FeedbackIn(BaseModel):
    content: str = Field(min_length=2, max_length=5000)
    kind: Literal["feedback", "note"] = "feedback"
    category: Literal["general", "technical", "communication", "interview", "resume", "encouragement"] = "general"


class GoalIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    goal_type: Literal["mock_interview", "english_practice", "assessment", "resume_update", "resource", "custom"] = "custom"
    resource_url: str | None = Field(default=None, max_length=500)
    target_count: int = Field(default=1, ge=1, le=100)
    target_score: float | None = Field(default=None, ge=0, le=100)
    deadline: datetime | None = None


class PlanIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    goals: list[GoalIn] = Field(default_factory=list, max_length=20)


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    status: Literal["active", "completed", "archived"] | None = None


class MentorSessionIn(BaseModel):
    student_id: int
    scheduled_at: datetime
    agenda: str = Field(min_length=2, max_length=2000)
    meeting_link: str | None = Field(default=None, max_length=500)


class MentorSessionUpdate(BaseModel):
    scheduled_at: datetime | None = None
    agenda: str | None = Field(default=None, min_length=2, max_length=2000)
    meeting_link: str | None = Field(default=None, max_length=500)
    status: Literal["scheduled", "completed", "cancelled"] | None = None
    outcome_notes: str | None = Field(default=None, max_length=4000)


# --------------------------------------------------------------------------- admin

class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(max_length=128)
    role: Literal["student", "recruiter", "mentor", "admin"]
    company_name: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=120)

    _pw = field_validator("password")(_strong_password)


class AdminUserUpdate(BaseModel):
    status: Literal["pending", "active", "suspended", "deactivated"] | None = None
    role: Literal["student", "recruiter", "mentor", "admin"] | None = None
    # review_integrity: may review camera-monitoring integrity events of students they can access (mentors)
    permissions: list[Literal["view_all_students", "review_integrity"]] | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class AssignmentIn(BaseModel):
    mentor_id: int
    student_ids: list[int] = Field(min_length=1, max_length=200)


class CategoryIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z_]+$")
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    default_question_count: int = Field(default=5, ge=3, le=15)
    active: bool = True


class BankQuestionIn(BaseModel):
    category_id: int
    question: str = Field(min_length=5, max_length=2000)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    role_tag: str | None = Field(default=None, max_length=100)
    active: bool = True


class RubricCriterion(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    weight: float = Field(ge=0, le=1)
    description: str = Field(default="", max_length=500)


class RubricIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    applies_to: Literal["interview", "english", "job_match"]
    criteria: list[RubricCriterion] = Field(min_length=1, max_length=12)
    active: bool = True


class BadgeIn(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=500)
    icon: str = Field(default="🏅", max_length=20)
    criteria_type: Literal["interviews_completed", "english_minutes", "avg_interview_score", "technical_best_score",
                           "streak_days", "assessments_passed", "english_sessions", "high_score_interviews",
                           "english_avg_score"]
    threshold: float = Field(ge=0)
    points: int = Field(default=50, ge=0, le=10000)
    active: bool = True


class RewardRuleUpdate(BaseModel):
    points: int | None = Field(default=None, ge=0, le=10000)
    daily_cap: int | None = Field(default=None, ge=0, le=100)
    requirements: dict | None = None
    active: bool | None = None
    description: str | None = Field(default=None, max_length=500)


class SettingUpdate(BaseModel):
    value: bool | int | float | str


class FlagReview(BaseModel):
    action: Literal["clear", "confirm"]
    note: str | None = Field(default=None, max_length=1000)

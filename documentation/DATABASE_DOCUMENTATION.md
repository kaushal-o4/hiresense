# HireSense AI: Database Documentation

## 1. Database technology

- **Database:** MongoDB (MongoDB Community Server as the local "MongoDB" Windows service in development; `mongo:7` in Docker/CI; MongoDB
  Atlas when hosted).
- **Driver:** `pymongo`.
- **Data layer:** the project's own small SQLAlchemy-style layer in `backend/app/mongodb_data_layer/`. The app was
  first written with SQLAlchemy (SQL) and moved to MongoDB on 2026-10-26. To keep the code unchanged, this layer
  offers the same API (`mapped_column`, `relationship`, `select(...).where(...)`, `db.add`, `db.commit`), but
  stores data as MongoDB documents.
- **Schema definition:** `backend/app/database_models.py` has **49 model classes**, one **collection** each.

## 2. Connection

| Setting (backend/.env) | Default | Used in |
|---|---|---|
| `MONGODB_URL` | `mongodb://127.0.0.1:27017` | `app/database_connection.py` -> `mongodb_data_layer/mongo_connection.connect()` |
| `MONGODB_DB` | `hiresense` (tests use `hiresense_test`) | `get_database()` |

```
FastAPI route --Depends(get_db)--> database_connection.get_db()
                                   '-- SessionLocal() -> mongodb_data_layer.Session (one per request)
route: db.scalars(select(User).where(User.email == x))   -> pymongo find({"email": x})
route: db.add(obj); db.commit()                          -> insert_one / update_one
```

- `init_db()` runs at startup and in the seed script. It creates every index and unique constraint declared on
  the models (`ensure_indexes`).
- **Primary keys** are integers stored as the document `_id`. They come from a `_counters` collection, so URLs
  stay numeric (`/student/interviews/12`).
- **Foreign keys** are integer fields that hold another document's id (e.g. `interview_answers.question_id`). The
  data layer follows them for `relationship()` attributes. MongoDB does not enforce them, so the code maintains
  them.
- **JSON fields** (`analysis`, `scores`, `report`, `meta`, `details`, ...) are stored as nested documents.
- **Unique constraints** (e.g. one answer per question, one application per student per job) are real MongoDB
  unique indexes. A violation raises `IntegrityError`.

## 3. Main relationships (ER diagram)

```
                                   +------------------+
             +-------------------->|      users       |<---------------------------------+
             |                     | id, email, role, |                                  |
             |                     | password_hash,   |                                  |
             |                     | status           |                                  |
             |                     +------------------+                                  |
             |        1:1 |              | 1:N              | 1:N                        | 1:N
   +-------------------+  |   +-----------------+   +------------------+       +------------------+
   | student_profiles  |<-+   |    resumes      |   | interview_sessions|      |      jobs        |
   | recruiter_profiles|      | raw_text,       |<--| student_id,       |      | recruiter_id,    |
   | mentor_profiles   |      | analysis (JSON) |N:1| resume_id, role,  |      | title, status    |
   +-------------------+      +-----------------+   | category, score,  |      +------------------+
                                     | 1:N          | report (JSON)     |         | 1:N      | 1:N
                              +-------------+       +-------------------+  +----------------+ +------------------+
                              |resume_skills|              | 1:N           |job_requirements| | job_applications |
                              +-------------+       +-------------------+  +----------------+ | job_id,student_id|
                                                    |interview_questions|                     | status, match    |
                                                    | position, text,   |                     +------------------+
                                                    | type, difficulty  |                        | 1:N
                                                    +-------------------+          +---------------------------+
                                                           | 1:1                   | application_status_history|
                                                    +-------------------+          | application_messages      |
                                                    | interview_answers |          | assessment_assignments    |
                                                    | scores, score,    |          +---------------------------+
                                                    | feedback          |
                                                    +-------------------+
   interview_sessions 1:N integrity_events 1:N integrity_reviews       (optional proctoring signals)
   assessments 1:N assessment_results (student_id -> users)            (skill tests)
   english_sessions 1:N english_messages ; english_vocabulary 1:N english_vocabulary_reviews
   users 1:N mentor_assignments (mentor_id, student_id) ; improvement_plans 1:N plan_goals
   badges 1:N student_badges ; challenges 1:N challenge_completions ; placement_drives 1:N drive_registrations
   users 1:N notifications, point_transactions, progress_records, audit_logs, ai_usage_logs
```

Every foreign key in the code (62 in total) points to one of these collections:
- `users`
- `resumes`
- `interview_sessions`
- `interview_questions`
- `interview_categories`
- `jobs`
- `job_applications`
- `assessments`
- `assessment_results`
- `english_sessions`
- `english_vocabulary`
- `improvement_plans`
- `integrity_events`
- `challenges`
- `badges`
- `placement_drives`

Two links are by **code**, not by id:
- `interview_sessions.category` holds the code of an `interview_categories` entry (`technical`, `hr`, ...).
- `point_transactions.activity_type` holds the `activity_type` of a `reward_rules` entry.

## 4. Where each kind of information is stored

| Information | Collection(s) | Written by |
|---|---|---|
| User accounts (email, Argon2 password hash, role, status) | `users` | `routers/authentication_routes.py`, `routers/admin/admin_user_management_routes.py` |
| Student / recruiter / mentor profiles | `student_profiles`, `recruiter_profiles`, `mentor_profiles` | `routers/profile_and_notification_routes.py` |
| Resumes and AI analysis | `resumes` (`raw_text`, `analysis` JSON, `analysis_status`), `resume_skills`; files on disk in `backend/uploads/` | `routers/student_portal_routes.py` |
| Interview sessions | `interview_sessions` (`job_role`, `category`, `mode`, `difficulty`, `status`, `overall_score`, `report`, `flagged`) | `routers/interview_routes.py`, `routers/live_voice_interview_routes.py` |
| Questions | `interview_questions` (`text`, `question_type`, `difficulty`, `is_followup`, `preface`, `meta`) | `interview_routes._add_next_question()` |
| Answers and evaluation | `interview_answers` (`text`, `scores` 0-10 per criterion, `score` 0-100, `feedback`, `sample_answer`, `details`, `evaluation_status`) | `interview_routes._save_answer()`, `_evaluate()`, `feedback_job()` |
| Interview report | `interview_sessions.report` (AI summary + computed metrics), `report_status` | `interview_routes._finalize_scores_and_report()` |
| Question bank, categories, rubrics | `question_bank`, `interview_categories`, `evaluation_rubrics` | `seed_initial_data.py`, `routers/admin/admin_content_routes.py` |
| Skill tests | `assessments`, `assessment_results`, `assessment_assignments` | `routers/skill_assessment_routes.py` |
| English practice | `english_sessions`, `english_messages`, `english_mistake_patterns`, `english_vocabulary`, `english_vocabulary_reviews`, `practice_exercises` | `routers/english_practice_routes.py` |
| Jobs and placements | `jobs`, `job_requirements`, `job_applications`, `application_status_history`, `application_messages`, `placement_drives`, `drive_registrations` | `routers/jobs/*`, `routers/admin/admin_operations_routes.py` |
| Progress and gamification | `progress_records`, `point_transactions`, `reward_rules`, `badges`, `student_badges`, `challenges`, `challenge_completions` | `services/student_progress/*` |
| Mentoring | `mentor_assignments`, `mentor_feedback`, `improvement_plans`, `plan_goals`, `mentor_sessions` | `routers/mentor_portal_routes.py` |
| Monitoring (opt-in) | `integrity_events`, `integrity_reviews`; consent in `interview_sessions.monitoring` | `routers/interview_monitoring_routes.py` |
| Platform and logs | `notifications`, `announcements`, `platform_settings`, `audit_logs`, `ai_usage_logs`, `error_logs`, `perf_metrics` | `services/platform_support/*`, `main.py` |

## 5. Typical database operations

| Operation | Example in the code |
|---|---|
| Insert | `db.add(InterviewSession(...)); db.flush()` gives the new id, then `db.commit()` saves it (`start_interview`) |
| Read one | `db.get(InterviewSession, session_id)` (`_get_session`) |
| Filtered read | `db.scalars(select(Resume).where(Resume.student_id == user.id, Resume.is_current.is_(True)))` |
| Count | `db.scalar(select(func.count(InterviewSession.id)).where(... status == "in_progress"))` |
| Aggregate | `select(func.max(InterviewSession.overall_score))` (`_post_completion`) |
| Update | change attributes on a loaded object, then `db.commit()` |
| Relationship | `session.questions.append(InterviewQuestion(...))` sets `session_id` automatically |
| Pagination | `paginate(db, stmt, page, page_size)` (`services/platform_support/audit_and_notification_helpers.py`) |
| Backup | `GET /api/admin/backup` exports every collection as MongoDB Extended JSON in a zip |

**Privacy rules visible in the schema:**
- Passwords are stored only as Argon2 hashes.
- `ai_usage_logs` and `perf_metrics` never store prompt or answer content.
- `integrity_events` store event records only, never images, video or face landmarks.

---

# 6. Collection reference (generated from `database_models.py`)

Legend:
- **PK:** primary key (`_id`)
- **FK -> x.id:** holds the id of a document in collection x
- **unique / indexed:** a MongoDB index exists
- `created_at` is added automatically by `TimestampMixin`

### `users` (model `User`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `email` | str | unique, indexed |
| `password_hash` | str |  |
| `full_name` | str |  |
| `role` | str | indexed |
| `status` | str | indexed |
| `permissions` | list |  |
| `preferences` | dict |  |
| `last_login_at` | datetime or None |  |
| `last_active_at` | datetime or None |  |
| `ai_data_consent_at` | datetime or None |  |
| `created_at` | datetime | set automatically |

Relationships: `student_profile -> StudentProfile`, `recruiter_profile -> RecruiterProfile`, `mentor_profile -> MentorProfile`

### `student_profiles` (model `StudentProfile`)

| Field | Type | Key / notes |
|---|---|---|
| `user_id` | int | PK, FK -> users.id |
| `phone` | str or None |  |
| `college` | str or None |  |
| `degree` | str or None |  |
| `branch` | str or None | indexed |
| `graduation_year` | int or None | indexed |
| `cgpa` | float or None |  |
| `skills` | list |  |
| `projects` | list |  |
| `experience` | list |  |
| `career_interests` | str or None |  |
| `target_role` | str or None |  |
| `bio` | str or None |  |
| `linkedin_url` | str or None |  |
| `github_url` | str or None |  |
| `share_with_recruiters` | bool |  |

Relationships: `user -> User`

### `recruiter_profiles` (model `RecruiterProfile`)

| Field | Type | Key / notes |
|---|---|---|
| `user_id` | int | PK, FK -> users.id |
| `company_name` | str |  |
| `company_website` | str or None |  |
| `designation` | str or None |  |
| `company_description` | str or None |  |
| `location` | str or None |  |
| `phone` | str or None |  |
| `industry` | str or None |  |
| `company_verified` | bool |  |

Relationships: `user -> User`

### `mentor_profiles` (model `MentorProfile`)

| Field | Type | Key / notes |
|---|---|---|
| `user_id` | int | PK, FK -> users.id |
| `department` | str or None |  |
| `expertise` | list |  |
| `bio` | str or None |  |
| `max_students` | int |  |

Relationships: `user -> User`

### `mentor_assignments` (model `MentorAssignment`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `mentor_id` | int | FK -> users.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `active` | bool |  |
| `assigned_by` | int or None | FK -> users.id |
| `created_at` | datetime | set automatically |

Relationships: `mentor -> User`, `student -> User`

Constraints / indexes: Unique ('mentor_id', 'student_id')

### `resumes` (model `Resume`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `filename` | str |  |
| `stored_path` | str |  |
| `content_type` | str |  |
| `raw_text` | str |  |
| `is_current` | bool |  |
| `analysis_status` | str |  |
| `analysis` | dict or None |  |
| `analysis_error` | str or None |  |
| `analyzed_at` | datetime or None |  |
| `created_at` | datetime | set automatically |

Relationships: `skills -> ResumeSkill`

### `resume_skills` (model `ResumeSkill`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `resume_id` | int | FK -> resumes.id, indexed |
| `name` | str | indexed |
| `category` | str or None |  |

Relationships: `resume -> Resume`

Constraints / indexes: Unique ('resume_id', 'name')

### `interview_categories` (model `InterviewCategory`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `code` | str | unique |
| `name` | str |  |
| `description` | str or None |  |
| `default_question_count` | int |  |
| `active` | bool |  |
| `created_at` | datetime | set automatically |

### `question_bank` (model `BankQuestion`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `category_id` | int | FK -> interview_categories.id, indexed |
| `question` | str |  |
| `difficulty` | str |  |
| `role_tag` | str or None |  |
| `active` | bool |  |
| `created_by` | int or None | FK -> users.id |
| `created_at` | datetime | set automatically |

Relationships: `category -> InterviewCategory`

### `evaluation_rubrics` (model `EvaluationRubric`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `name` | str |  |
| `applies_to` | str | indexed |
| `criteria` | list |  |
| `active` | bool |  |
| `created_at` | datetime | set automatically |

### `interview_sessions` (model `InterviewSession`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `job_role` | str |  |
| `category` | str |  |
| `mode` | str |  |
| `difficulty` | str |  |
| `status` | str |  |
| `planned_questions` | int |  |
| `resume_id` | int or None | FK -> resumes.id |
| `question_source` | str |  |
| `subject` | str or None |  |
| `interviewer` | str or None |  |
| `response_mode` | str or None |  |
| `monitoring` | dict or None |  |
| `completed_at` | datetime or None |  |
| `overall_score` | float or None |  |
| `report` | dict or None |  |
| `report_status` | str |  |
| `flagged` | bool |  |
| `flag_reason` | str or None |  |
| `created_at` | datetime | set automatically |

Relationships: `questions -> InterviewQuestion`

Constraints / indexes: Index ('ix_interview_student_status', 'student_id', 'status')

### `interview_questions` (model `InterviewQuestion`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `session_id` | int | FK -> interview_sessions.id, indexed |
| `position` | int |  |
| `text` | str |  |
| `question_type` | str |  |
| `is_followup` | bool |  |
| `difficulty` | str or None |  |
| `preface` | str or None |  |
| `meta` | dict or None |  |
| `created_at` | datetime | set automatically |

Relationships: `session -> InterviewSession`, `answer -> InterviewAnswer`

Constraints / indexes: Unique ('session_id', 'position')

### `interview_answers` (model `InterviewAnswer`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `question_id` | int | FK -> interview_questions.id, unique |
| `text` | str |  |
| `input_mode` | str |  |
| `response_seconds` | int or None |  |
| `evaluation_status` | str |  |
| `scores` | dict or None |  |
| `score` | float or None |  |
| `feedback` | str or None |  |
| `sample_answer` | str or None |  |
| `details` | dict or None |  |
| `created_at` | datetime | set automatically |

Relationships: `question -> InterviewQuestion`

### `assessments` (model `Assessment`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `title` | str |  |
| `description` | str or None |  |
| `topic` | str | indexed |
| `category` | str | indexed |
| `difficulty` | str |  |
| `questions` | list |  |
| `time_limit_minutes` | int |  |
| `pass_percent` | int |  |
| `created_by` | int or None | FK -> users.id |
| `job_id` | int or None | FK -> jobs.id, indexed |
| `active` | bool |  |
| `created_at` | datetime | set automatically |

### `assessment_results` (model `AssessmentResult`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `assessment_id` | int | FK -> assessments.id |
| `student_id` | int | FK -> users.id |
| `started_at` | datetime |  |
| `submitted_at` | datetime or None |  |
| `answers` | list |  |
| `score` | float or None |  |
| `correct_count` | int or None |  |
| `passed` | bool or None |  |
| `marks_obtained` | float or None |  |
| `max_marks` | float or None |  |
| `evaluation_status` | str |  |
| `details` | list or None |  |
| `flagged` | bool |  |
| `flag_reason` | str or None |  |
| `created_at` | datetime | set automatically |

Relationships: `assessment -> Assessment`

Constraints / indexes: Index ('ix_assessment_result_student', 'student_id', 'assessment_id')

### `english_sessions` (model `EnglishSession`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `topic` | str |  |
| `mode` | str |  |
| `style` | str or None |  |
| `status` | str |  |
| `ended_at` | datetime or None |  |
| `active_seconds` | int |  |
| `scores` | dict or None |  |
| `overall_score` | float or None |  |
| `feedback` | dict or None |  |
| `evaluation_status` | str |  |
| `learning_mode` | str or None |  |
| `memory` | dict or None |  |
| `created_at` | datetime | set automatically |

Relationships: `messages -> EnglishMessage`

### `english_messages` (model `EnglishMessage`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `session_id` | int | FK -> english_sessions.id, indexed |
| `sender` | str |  |
| `content` | str |  |
| `input_mode` | str |  |
| `speech_confidence` | float or None |  |
| `corrections` | list or None |  |
| `meta` | dict or None |  |
| `created_at` | datetime | set automatically |

Relationships: `session -> EnglishSession`

### `progress_records` (model `ProgressRecord`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id |
| `metric` | str |  |
| `value` | float |  |
| `source_type` | str |  |
| `source_id` | int |  |
| `label` | str or None |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_progress_student_metric', 'student_id', 'metric')

### `badges` (model `Badge`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `code` | str | unique |
| `name` | str |  |
| `description` | str |  |
| `icon` | str |  |
| `criteria_type` | str |  |
| `threshold` | float |  |
| `points` | int |  |
| `active` | bool |  |
| `created_at` | datetime | set automatically |

### `student_badges` (model `StudentBadge`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `badge_id` | int | FK -> badges.id |
| `awarded_at` | datetime |  |

Relationships: `badge -> Badge`

Constraints / indexes: Unique ('student_id', 'badge_id')

### `reward_rules` (model `RewardRule`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `activity_type` | str | unique |
| `description` | str |  |
| `points` | int |  |
| `daily_cap` | int |  |
| `requirements` | dict |  |
| `active` | bool |  |
| `created_at` | datetime | set automatically |

### `point_transactions` (model `PointTransaction`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id |
| `points` | int |  |
| `activity_type` | str |  |
| `source_type` | str |  |
| `source_id` | int |  |
| `reason` | str |  |
| `revoked` | bool |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Unique ('student_id', 'activity_type', 'source_type', 'source_id'); Index ('ix_points_student_created', 'student_id', 'created_at')

### `jobs` (model `Job`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `recruiter_id` | int | FK -> users.id, indexed |
| `title` | str |  |
| `company_name` | str |  |
| `description` | str |  |
| `location` | str |  |
| `job_type` | str |  |
| `experience_years` | float |  |
| `salary` | str or None |  |
| `min_cgpa` | float or None |  |
| `eligible_branches` | list |  |
| `graduation_years` | list |  |
| `status` | str |  |
| `deadline` | datetime or None |  |
| `updated_at` | datetime |  |
| `published_at` | datetime or None |  |
| `created_at` | datetime | set automatically |

Relationships: `requirements -> JobRequirement`, `recruiter -> User`

Constraints / indexes: Index ('ix_job_status_created', 'status', 'created_at')

### `job_requirements` (model `JobRequirement`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `job_id` | int | FK -> jobs.id, indexed |
| `skill` | str | indexed |
| `importance` | str |  |

Relationships: `job -> Job`

Constraints / indexes: Unique ('job_id', 'skill')

### `job_applications` (model `JobApplication`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `job_id` | int | FK -> jobs.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `status` | str | indexed |
| `cover_letter` | str or None |  |
| `updated_at` | datetime |  |
| `interview_at` | datetime or None |  |
| `recruiter_notes` | str or None |  |
| `match` | dict or None |  |
| `created_at` | datetime | set automatically |

Relationships: `job -> Job`, `student -> User`, `history -> ApplicationStatusHistory`

Constraints / indexes: Unique ('job_id', 'student_id')

### `application_status_history` (model `ApplicationStatusHistory`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `application_id` | int | FK -> job_applications.id, indexed |
| `from_status` | str or None |  |
| `to_status` | str |  |
| `changed_by` | int or None | FK -> users.id |
| `note` | str or None |  |
| `created_at` | datetime | set automatically |

Relationships: `application -> JobApplication`

### `mentor_feedback` (model `MentorFeedback`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `mentor_id` | int | FK -> users.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `kind` | str |  |
| `category` | str |  |
| `content` | str |  |
| `created_at` | datetime | set automatically |

Relationships: `mentor -> User`

### `improvement_plans` (model `ImprovementPlan`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `mentor_id` | int | FK -> users.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `title` | str |  |
| `description` | str or None |  |
| `status` | str |  |
| `created_at` | datetime | set automatically |

Relationships: `goals -> PlanGoal`, `mentor -> User`

### `plan_goals` (model `PlanGoal`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `plan_id` | int | FK -> improvement_plans.id, indexed |
| `title` | str |  |
| `description` | str or None |  |
| `goal_type` | str |  |
| `resource_url` | str or None |  |
| `target_count` | int |  |
| `target_score` | float or None |  |
| `deadline` | datetime or None |  |
| `status` | str |  |
| `completed_at` | datetime or None |  |
| `created_at` | datetime | set automatically |

Relationships: `plan -> ImprovementPlan`

### `mentor_sessions` (model `MentorSession`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `mentor_id` | int | FK -> users.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `scheduled_at` | datetime |  |
| `agenda` | str |  |
| `meeting_link` | str or None |  |
| `status` | str |  |
| `outcome_notes` | str or None |  |
| `created_at` | datetime | set automatically |

Relationships: `student -> User`, `mentor -> User`

### `notifications` (model `Notification`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `user_id` | int | FK -> users.id |
| `title` | str |  |
| `message` | str |  |
| `kind` | str |  |
| `link` | str or None |  |
| `read` | bool |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_notifications_user_read', 'user_id', 'read')

### `audit_logs` (model `AuditLog`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `actor_id` | int or None | FK -> users.id, indexed |
| `action` | str | indexed |
| `entity_type` | str or None |  |
| `entity_id` | int or None |  |
| `details` | dict |  |
| `ip_address` | str or None |  |
| `created_at` | datetime | set automatically |

Relationships: `actor -> User`

### `ai_usage_logs` (model `AIUsageLog`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `user_id` | int or None | FK -> users.id |
| `feature` | str | indexed |
| `status` | str | indexed |
| `error` | str or None |  |
| `latency_ms` | int or None |  |
| `input_tokens` | int or None |  |
| `output_tokens` | int or None |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_ai_usage_user_created', 'user_id', 'created_at')

### `perf_metrics` (model `PerfMetric`)

One timed step of the interview pipeline (services/monitoring/performance_timing.py). Never holds candidate content: only the step name, its duration, success, and numeric details such as token counts.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `metric` | str |  |
| `duration_ms` | int |  |
| `ok` | bool |  |
| `source` | str |  |
| `meta` | dict or None |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_perf_metric_created', 'metric', 'created_at')

### `integrity_events` (model `IntegrityEvent`)

A camera/browser monitoring signal from a monitored interview. Signals are approximate indicators for a human reviewer, never proof of misconduct, and never change interview scores. No images or video are stored.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `session_id` | int | FK -> interview_sessions.id |
| `event_type` | str |  |
| `t_ms` | int |  |
| `duration_ms` | int or None |  |
| `confidence` | float or None |  |
| `confidence_sufficient` | bool |  |
| `severity` | str |  |
| `candidate_explanation` | str or None |  |
| `review_status` | str |  |
| `reviewer_id` | int or None | FK -> users.id |
| `reviewer_notes` | str or None |  |
| `reviewed_at` | datetime or None |  |
| `client_event_id` | str or None |  |
| `source` | str |  |
| `details` | dict or None |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_integrity_session', 'session_id', 't_ms'); Unique ('session_id', 'client_event_id')

### `integrity_reviews` (model `IntegrityReview`)

Append-only history of reviews of an integrity event. The event keeps its original detection fields; a review only adds a status and notes, so nobody can silently rewrite what was detected.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `event_id` | int | FK -> integrity_events.id |
| `reviewer_id` | int or None | FK -> users.id |
| `reviewer_role` | str |  |
| `review_status` | str |  |
| `notes` | str or None |  |
| `created_at` | datetime |  |

Constraints / indexes: Index ('ix_integrity_review_event', 'event_id')

### `error_logs` (model `ErrorLog`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `path` | str |  |
| `method` | str |  |
| `error` | str |  |
| `user_id` | int or None |  |
| `created_at` | datetime | set automatically |

### `assessment_assignments` (model `AssessmentAssignment`)

A recruiter assigns a specific assessment to a specific applicant.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `assessment_id` | int | FK -> assessments.id, indexed |
| `application_id` | int | FK -> job_applications.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `assigned_by` | int or None | FK -> users.id |
| `due_at` | datetime or None |  |
| `status` | str |  |
| `result_id` | int or None | FK -> assessment_results.id |
| `created_at` | datetime | set automatically |

Relationships: `assessment -> Assessment`, `result -> AssessmentResult`

Constraints / indexes: Unique ('assessment_id', 'application_id')

### `application_messages` (model `ApplicationMessage`)

Recruiter <-> student conversation attached to a job application.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `application_id` | int | FK -> job_applications.id, indexed |
| `sender_id` | int or None | FK -> users.id |
| `kind` | str |  |
| `body` | str |  |
| `read` | bool |  |
| `created_at` | datetime | set automatically |

Relationships: `sender -> User`

### `challenges` (model `Challenge`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `title` | str |  |
| `description` | str |  |
| `metric` | str |  |
| `target` | float |  |
| `period` | str |  |
| `points` | int |  |
| `active` | bool |  |
| `created_at` | datetime | set automatically |

### `challenge_completions` (model `ChallengeCompletion`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `challenge_id` | int | FK -> challenges.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `period_key` | str |  |
| `created_at` | datetime | set automatically |

Relationships: `challenge -> Challenge`

Constraints / indexes: Unique ('challenge_id', 'student_id', 'period_key')

### `practice_exercises` (model `PracticeExercise`)

English learning drills: pronunciation (read a sentence aloud) and speaking (answer a prompt).

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id |
| `kind` | str |  |
| `prompt` | str |  |
| `level` | str |  |
| `status` | str |  |
| `response_text` | str or None |  |
| `speech_confidence` | float or None |  |
| `active_seconds` | int |  |
| `score` | float or None |  |
| `details` | dict or None |  |
| `evaluation_status` | str |  |
| `completed_at` | datetime or None |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_exercise_student_kind', 'student_id', 'kind')

### `placement_drives` (model `PlacementDrive`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `title` | str |  |
| `company_name` | str |  |
| `description` | str |  |
| `drive_date` | datetime |  |
| `location` | str |  |
| `min_cgpa` | float or None |  |
| `eligible_branches` | list |  |
| `status` | str |  |
| `created_by` | int or None | FK -> users.id |
| `created_at` | datetime | set automatically |

Relationships: `registrations -> DriveRegistration`

### `drive_registrations` (model `DriveRegistration`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `drive_id` | int | FK -> placement_drives.id, indexed |
| `student_id` | int | FK -> users.id, indexed |
| `created_at` | datetime | set automatically |

Relationships: `drive -> PlacementDrive`, `student -> User`

Constraints / indexes: Unique ('drive_id', 'student_id')

### `announcements` (model `Announcement`)

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `title` | str |  |
| `message` | str |  |
| `audience` | str |  |
| `link` | str or None |  |
| `recipients` | int |  |
| `created_by` | int or None | FK -> users.id |
| `created_at` | datetime | set automatically |

### `platform_settings` (model `PlatformSetting`)

| Field | Type | Key / notes |
|---|---|---|
| `key` | str | PK |
| `value` | dict or list or str or int or float or bool or None |  |
| `description` | str or None |  |
| `updated_at` | datetime |  |

### `english_mistake_patterns` (model `EnglishMistakePattern`)

One kind of English mistake a student keeps making, counted from the corrections given in their practice sessions (services/english/english_mistake_profile.py). The category is a rough, rule-based label, not a grammar analysis. The student can dismiss a pattern or clear all of them.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `category` | str |  |
| `count` | int |  |
| `sessions` | int |  |
| `last_session_id` | int or None |  |
| `last_seen` | datetime |  |
| `example_original` | str or None |  |
| `example_corrected` | str or None |  |
| `dismissed` | bool |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Unique ('student_id', 'category')

### `english_vocabulary` (model `VocabularyItem`)

A word or phrase in a student's personal review list (services/english/english_vocabulary_trainer.py). Most come from the corrections Aria gave in practice sessions (front = what the student said, back = the corrected form); students can also add their own. Reviewed with Leitner boxes 1-5: knowing it moves the card up one box (longer gap before the next review), not knowing it sends it back to box 1.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `key` | str |  |
| `kind` | str |  |
| `front` | str |  |
| `back` | str |  |
| `explanation` | str or None |  |
| `source_session_id` | int or None |  |
| `box` | int |  |
| `due_at` | datetime |  |
| `reviews` | int |  |
| `correct` | int |  |
| `last_reviewed` | datetime or None |  |
| `mastered_at` | datetime or None |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Unique ('student_id', 'key'); Index ('ix_vocab_student_due', 'student_id', 'due_at')

### `english_vocabulary_reviews` (model `VocabularyReview`)

One answer in a review ("I knew it" / "not yet"), kept for accuracy trends, daily plans and challenges.

| Field | Type | Key / notes |
|---|---|---|
| `id` | int | PK |
| `student_id` | int | FK -> users.id, indexed |
| `item_id` | int | FK -> english_vocabulary.id, indexed |
| `knew` | bool |  |
| `box_before` | int |  |
| `box_after` | int |  |
| `created_at` | datetime | set automatically |

Constraints / indexes: Index ('ix_vocab_review_student_time', 'student_id', 'created_at')

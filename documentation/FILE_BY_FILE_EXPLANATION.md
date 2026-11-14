# File-by-file explanation

Every source file of HireSense AI, explained in simple English. The same text is at the top of each file as its comment index. Function descriptions marked with the function name come from the record written for this document or, for smaller helpers, from the function's own docstring/comment in the code.

Files explained: **275**

## Contents

- [Backend - application entry, configuration, security and data](#backend---application-entry-configuration-security-and-data)
- [Backend - MongoDB data layer](#backend---mongodb-data-layer)
- [Backend - API route files](#backend---api-route-files)
- [Backend - AI model clients](#backend---ai-model-clients)
- [Backend - interview services](#backend---interview-services)
- [Backend - resume and job services](#backend---resume-and-job-services)
- [Backend - English practice services](#backend---english-practice-services)
- [Backend - voice services](#backend---voice-services)
- [Backend - monitoring services](#backend---monitoring-services)
- [Backend - student progress services](#backend---student-progress-services)
- [Backend - platform support services](#backend---platform-support-services)
- [Backend - machine learning (question classifier)](#backend---machine-learning-question-classifier)
- [Backend - evaluation scripts (real AI model)](#backend---evaluation-scripts-real-ai-model)
- [Backend - automated tests (mocked AI)](#backend---automated-tests-mocked-ai)
- [Backend - browser end-to-end tests](#backend---browser-end-to-end-tests)
- [Backend - integration tests (real AI models)](#backend---integration-tests-real-ai-models)
- [Backend - performance benchmarks](#backend---performance-benchmarks)
- [Frontend - entry, routing, API client, styles](#frontend---entry-routing-api-client-styles)
- [Frontend - shared components](#frontend---shared-components)
- [Frontend - authentication and common pages](#frontend---authentication-and-common-pages)
- [Frontend - student pages](#frontend---student-pages)
- [Frontend - recruiter pages](#frontend---recruiter-pages)
- [Frontend - mentor pages](#frontend---mentor-pages)
- [Frontend - admin pages](#frontend---admin-pages)
- [Frontend - pages shared by several roles](#frontend---pages-shared-by-several-roles)
- [Frontend - live voice interview and avatar](#frontend---live-voice-interview-and-avatar)
- [Frontend - interview monitoring (camera, microphone, browser)](#frontend---interview-monitoring-camera-microphone-browser)
- [Frontend - English learning helpers](#frontend---english-learning-helpers)
- [Frontend - live notifications](#frontend---live-notifications)
- [Tooling - avatar conversion scripts](#tooling---avatar-conversion-scripts)
- [Tooling - team report generator](#tooling---team-report-generator)

# Backend - application entry, configuration, security and data

## File: `backend/app/__init__.py`

### 1. Purpose
Marks the `app` folder as a Python package so other files can write `from app import ...` or `python -m app.main`. It contains no code.

### 2. What does it do?
1. Turns backend/app into an importable Python package.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
When uvicorn starts `app.main:app`, Python needs this file to treat `app` as a package.

### 9. Viva explanation
> This is an empty package marker. Without it Python would not recognise the app folder as a package.

---

## File: `backend/app/api_response_serializers.py`

### 1. Purpose
Converts database objects into the JSON dictionaries returned by the API, in one place, so it is clear what each role can see.

### 2. What does it do?
Output formatting (database object -> JSON).

1. user_out / profile_out: user and profile data without the password hash.
2. resume_out, interview_out, english_out, assessment_out, result_out: practice data for the frontend.
3. job_out, application_out, plan_out, drive_out, notification_out: placement and mentoring data.
4. Formats dates as ISO strings.

### 3. How does it work?
Routers call these functions before returning. interview_out(detail=True) adds questions and answers; own=True adds the student's own monitoring settings, which recruiters and mentors never receive here.

```
Router loads objects
   |
   v
Serializer converts them
   |
   v
JSON sent to the frontend
```

### 4. Important functions
```text
   - interview_out()
       Interview session as JSON; with detail=True includes questions, answers, scores and
       report.
   - user_out()
       Safe public view of a user (never includes password_hash).
   Other helper functions: iso, student_profile_out, recruiter_profile_out, mentor_profile_out,
   profile_out, resume_out, english_out, assessment_out, result_out, job_out, application_out,
   plan_out, mentor_session_out, drive_out, notification_out
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/database_models.py
   Used by: app/routers/admin/admin_analytics_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_routes.py,
   app/routers/jobs/job_shared_helpers.py, app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
   app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
   app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
   app/routers/student_portal_routes.py,
   app/services/student_progress/student_performance_insights.py
```

### 7. Input and output
- **Input:** Model objects from database_models.py.
- **Output:** Plain dictionaries that FastAPI turns into JSON.

### 8. Real project example
After an interview is completed, interview_out(session, detail=True) builds the data shown on the interview report page.

### 9. Viva explanation
> Serializers decide what data leaves the server. Keeping them in one file makes sure, for example, that password hashes or monitoring data are never sent to the wrong user.

---

## File: `backend/app/application_configuration.py`

### 1. Purpose
Holds every configurable setting of the backend (database URL, secret key, AI provider, model names, limits, email, cookies) and loads their values from environment variables or backend/.env.

### 2. What does it do?
Single source of truth for application settings.

1. Defines the `Settings` class with a default value for every option.
2. Reads overrides from backend/.env and environment variables using pydantic-settings.
3. Provides derived helpers such as the CORS origin list and cookie SameSite mode.
4. Returns one cached Settings object through get_settings().

### 3. How does it work?
pydantic-settings maps each field (e.g. `mongodb_url`) to an environment variable (MONGODB_URL). get_settings() is wrapped in a cache so the .env file is read only once per process.

```
Module imported
   |
   v
get_settings() called
   |
   v
Values read from .env / environment
   |
   v
Same Settings object reused
```

### 4. Important functions
```text
   - get_settings()
       Returns the cached Settings object used by the whole backend.
```

**Classes:**
```text
   - Settings
```

### 5. Important variables
- Module-level constants: BASE_DIR

### 6. Connected files
```text
   Used by: app/database_connection.py, app/main.py, app/password_and_token_security.py,
   app/reset_admin_password.py, app/routers/authentication_routes.py,
   app/routers/jobs/job_shared_helpers.py, app/routers/live_voice_interview_routes.py,
   app/routers/profile_and_notification_routes.py, app/routers/student_portal_routes.py,
   app/routers/voice_speech_routes.py, app/seed_initial_data.py,
   app/services/ai_models/ai_structured_call_base.py,
   app/services/ai_models/ai_task_model_router.py, app/services/ai_models/gemini_api_client.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/question_type_classifier.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/monitoring/performance_timing.py, app/services/platform_support/email_sender.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/platform_support/rate_limiter.py,
   app/services/resume_and_jobs/ai_resume_analyzer.py,
   app/services/resume_and_jobs/semantic_job_matcher.py, app/services/voice/speech_to_text.py,
   app/services/voice/text_to_speech.py
   Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/conftest.py,
   tests/test_account_security.py, tests/test_deploy.py, tests/test_features.py,
   tests/test_gemini.py, tests/test_health_and_routing.py, tests/test_latency_and_monitoring.py,
   tests/test_live_notifications_and_recruiter.py, tests/test_voice.py,
   tests_integration/conftest.py, tests_perf/bench_interview_latency.py,
   tests_perf/bench_models.py, tests_perf/bench_prompts.py, tests_perf/bench_stt.py
```
External packages: pydantic_settings

### 7. Input and output
- **Input:** Environment variables and the backend/.env file.
- **Output:** A Settings object (e.g. settings.secret_key, settings.ollama_model, settings.mongodb_url).

### 8. Real project example
When the interview code needs the AI model name, it reads it from get_settings().

### 9. Viva explanation
> This is our configuration file. All settings such as database URL, AI model and security keys are read from the .env file into one Settings object, so nothing secret is written in the code.

**Note:** Secrets are never hard-coded here; real values live in backend/.env, which is not committed to git.

---

## File: `backend/app/authentication_dependencies.py`

### 1. Purpose
Reusable FastAPI checks that find out who is calling an endpoint and whether they are allowed to.

### 2. What does it do?
Authentication (who are you?) and authorisation (are you allowed?) for every protected endpoint.

1. Reads the login token from the httpOnly `hs_session` cookie or an `Authorization: Bearer` header.
2. Decodes the JWT and loads the user from the database (401 if missing/invalid, 403 if not active).
3. Builds role checks: require_student, require_recruiter, require_mentor, require_admin.
4. Checks whether a mentor may see a particular student (assignment or view_all_students permission).
5. Gets the client IP for the audit log.

### 3. How does it work?
Route functions declare `user: User = Depends(require_student)`. FastAPI runs the dependency first; if it raises HTTPException the route never runs.

```
Request with cookie
   |
   v
_token_from_request() reads JWT
   |
   v
decode_access_token() verifies it
   |
   v
User loaded and status checked
   |
   v
Role check -> route runs or 403
```

### 4. Important functions
```text
   - get_current_user()
       Decodes the session JWT and returns the signed-in User (401/403 otherwise).
   - require_roles()
       Creates a dependency that only lets the given roles through.
   - ensure_mentor_access()
       Raises 403 unless the mentor is allowed to see this student.
   - mentor_can_access()
       True if the mentor may see this student: an active MentorAssignment exists, or the
       mentor has the `view_all_students` permission.
   - client_ip()
       Client IP address for the audit log (None when unknown, e.g. in tests).
   Other helper functions: _token_from_request
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/password_and_token_security.py
   Used by: app/routers/admin/admin_analytics_routes.py,
   app/routers/admin/admin_content_routes.py, app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
   app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
   app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
   app/routers/student_portal_routes.py, app/routers/voice_speech_routes.py,
   app/services/platform_support/student_record_access.py
```
External packages: fastapi

### 7. Input and output
- **Input:** The incoming HTTP request (cookie or header) and the database session.
- **Output:** The current User object, or an HTTP 401/403 error.

### 8. Real project example
When a recruiter tries to open a student-only page's API, require_student returns 403 Forbidden.

### 9. Viva explanation
> This file protects our APIs. It reads the JWT from the cookie, finds the user, and checks the role, so a student cannot call admin or recruiter endpoints.

---

## File: `backend/app/database_connection.py`

### 1. Purpose
Connects the backend to MongoDB and gives each API request its own database session.

### 2. What does it do?
Database connection and per-request session handling.

1. Opens the MongoDB client using MONGODB_URL / MONGODB_DB.
2. Creates sessions (SessionLocal) from the project's MongoDB data layer.
3. Creates the indexes and unique constraints at startup (init_db).
4. Provides get_db(), a FastAPI dependency that opens a session per request and closes it afterwards.
5. Provides clear_database() for tests (refuses to wipe the main database).

### 3. How does it work?
get_db() is a generator: FastAPI calls it before a route function, passes the session in as `db`, and closes it when the request ends. Routes then read/write documents through that session.

```
Request arrives
   |
   v
get_db() creates a Session
   |
   v
Route reads/writes data
   |
   v
Session closed
```

### 4. Important functions
```text
   - get_db()
       FastAPI dependency: yields a Session for one request and always closes it.
   - init_db()
       Creates indexes declared on the models (run at startup and by the seed script).
   - SessionLocal()
       Creates a new Session object (used by background jobs that run outside a request).
   - get_database()
       The app's MongoDB database (MONGODB_URL / MONGODB_DB in backend/.env).
   - clear_database()
       Delete every document but keep the collections and indexes.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py
   Used by: app/authentication_dependencies.py, app/main.py, app/reset_admin_password.py,
   app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
   app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
   app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
   app/routers/student_portal_routes.py, app/routers/voice_speech_routes.py,
   app/seed_initial_data.py, app/seed_sample_jobs.py,
   app/services/monitoring/performance_timing.py
   Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/conftest.py,
   tests/test_integrity_detectors.py, tests/test_latency_and_monitoring.py,
   tests/test_live_notifications_and_recruiter.py, tests_e2e/account_browser.py,
   tests_integration/conftest.py, tests_perf/bench_interview_latency.py,
   tests_perf/bench_models.py, tests_perf/bench_prompts.py
```

### 7. Input and output
- **Input:** Connection settings from application_configuration.py.
- **Output:** Session objects used by routers and services to query MongoDB.

### 8. Real project example
When a student submits an answer, interview_routes.py receives `db` from get_db() and saves the answer through it.

### 9. Viva explanation
> This file connects to MongoDB. Every API request gets its own database session through get_db(), which FastAPI injects automatically and closes after the request.

---

## File: `backend/app/database_models.py`

### 1. Purpose
Defines every kind of data HireSense stores (users, profiles, resumes, interviews, questions, answers, jobs, applications, rewards, notifications, logs, monitoring events, English practice, ...). Each class is one MongoDB collection.

### 2. What does it do?
The database schema of the project.

1. Declares about 50 model classes; each class maps to one MongoDB collection (`__tablename__`).
2. Declares fields, primary keys, foreign keys (links by id), unique constraints and indexes.
3. Declares relationships, e.g. InterviewSession.questions and InterviewQuestion.answer.
4. Lists allowed values for status fields (ROLES, JOB_STATUSES, SESSION_STATUSES, ...).

### 3. How does it work?
Classes inherit from `Base` of the project's MongoDB data layer, which works like SQLAlchemy: `mapped_column(...)` describes a field and `relationship(...)` loads related documents on access. Integer ids come from a counters collection so the frontend can keep using numbers in URLs.

```
Router/service imports a model (e.g. InterviewSession)
   |
   v
Creates or queries objects through a Session
   |
   v
Data layer converts objects to/from MongoDB documents
```

### 4. Important functions
```text
   Other helper functions: utcnow, _in
```

**Classes:**
```text
   - TimestampMixin
   - User
   - StudentProfile
   - RecruiterProfile
   - MentorProfile
   - MentorAssignment
   - Resume
   - ResumeSkill
   - InterviewCategory
   - BankQuestion
   - EvaluationRubric
   - InterviewSession
   - InterviewQuestion
   - InterviewAnswer
   - Assessment
   - AssessmentResult
   - EnglishSession
   - EnglishMessage
   - ProgressRecord
   - Badge
   - StudentBadge
   - RewardRule
   - PointTransaction
   - Job
   - JobRequirement
   - JobApplication
   - ApplicationStatusHistory
   - MentorFeedback
   - ImprovementPlan
   - PlanGoal
   - MentorSession
   - Notification
   - AuditLog
   - AIUsageLog
   - PerfMetric
       One timed step of the interview pipeline (services/monitoring/performance_timing.py).
   - IntegrityEvent
       A camera/browser monitoring signal from a monitored interview.
   - IntegrityReview
       Append-only history of reviews of an integrity event.
   - ErrorLog
   - AssessmentAssignment
       A recruiter assigns a specific assessment to a specific applicant.
   - ApplicationMessage
       Recruiter <-> student conversation attached to a job application.
   - Challenge
   - ChallengeCompletion
   - PracticeExercise
       English learning drills: pronunciation (read a sentence aloud) and speaking (answer a
       prompt).
   - PlacementDrive
   - DriveRegistration
   - Announcement
   - PlatformSetting
   - EnglishMistakePattern
       One kind of English mistake a student keeps making, counted from the corrections given
       in their practice sessions (services/english/english_mistake_profile.py).
   - VocabularyItem
       A word or phrase in a student's personal review list
       (services/english/english_vocabulary_trainer.py).
   - VocabularyReview
       One answer in a review ("I knew it" / "not yet"), kept for accuracy trends, daily
       plans and challenges.
```

### 5. Important variables
- Module-level constants: ROLES, USER_STATUSES, JOB_STATUSES, APP_STATUSES, SESSION_STATUSES, INTERVIEW_CATEGORIES,    GOAL_TYPES, INTEGRITY_EVENT_TYPES, INTEGRITY_SEVERITIES, INTEGRITY_REVIEW

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/__init__.py
   Used by: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/main.py, app/reset_admin_password.py,
   app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/job_shared_helpers.py,
   app/routers/jobs/recruiter_job_routes.py, app/routers/jobs/recruiter_screening_routes.py,
   app/routers/jobs/student_job_routes.py, app/routers/live_voice_interview_routes.py,
   app/routers/mentor_portal_routes.py, app/routers/profile_and_notification_routes.py,
   app/routers/skill_assessment_routes.py, app/routers/student_portal_routes.py,
   app/routers/voice_speech_routes.py, app/seed_initial_data.py, app/seed_sample_jobs.py,
   app/services/ai_models/ai_structured_call_base.py,
   app/services/english/english_mistake_profile.py,
   app/services/english/english_vocabulary_trainer.py,
   app/services/monitoring/performance_timing.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/platform_support/student_record_access.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Tested by: eval/run_eval.py, tests/test_account_security.py, tests/test_attention.py,
   tests/test_auth_and_permissions.py, tests/test_deploy.py, tests/test_english_avatar.py,
   tests/test_english_companion.py, tests/test_english_vocab.py, tests/test_features.py,
   tests/test_integrity_detectors.py, tests/test_interview_intelligence.py,
   tests/test_latency_and_monitoring.py, tests/test_live_notifications_and_recruiter.py,
   tests/test_local_ai.py, tests/test_odm.py, tests/test_security_module.py,
   tests/test_workflows.py, tests_e2e/account_browser.py, tests_perf/bench_prompts.py
```

### 7. Input and output
- **Input:** Nothing at runtime; it is imported by routers and services.
- **Output:** Model classes used to create, query and update documents.

### 8. Real project example
When an interview starts, an InterviewSession document is created; each question becomes an InterviewQuestion and each answer an InterviewAnswer with its scores.

### 9. Viva explanation
> This file is our database design. Every class, like User, Resume, InterviewSession or Job, is stored as a MongoDB collection, with ids linking related records such as an answer to its question.

**Note:** Full table-by-table description: documentation/DATABASE_DOCUMENTATION.md.

---

## File: `backend/app/main.py`

### 1. Purpose
The entry point of the backend. It creates the FastAPI application, plugs in every API route file, adds security headers and a global error handler, and prepares the AI models when the server starts.

### 2. What does it do?
Start and configure the whole HireSense API server.

1. Creates the FastAPI `app` object with CORS settings so the React frontend can call it.
2. Adds a middleware that gives every request an ID, logs slow requests and adds security headers.
3. Registers all routers (auth, student, interviews, live interview, English, assessments, jobs, mentor, admin, voice, monitoring).
4. On startup: checks the SECRET_KEY, creates MongoDB indexes, warms up the AI models in a background thread and purges expired integrity events.
5. On shutdown: waits for background jobs (feedback, reports) to finish saving.
6. Exposes health endpoints used by Docker/Render and the frontend.

### 3. How does it work?
uvicorn imports this module and serves `app`. Each router file adds its own URLs to `app`. Unhandled exceptions are caught by `unhandled_error`, saved to the error_logs collection and returned as a polite 500 message. Model warm-up runs in a separate thread so the server is ready immediately.

```
uvicorn starts app.main:app
   |
   v
Startup hook: indexes + model warm-up thread
   |
   v
Request arrives -> middleware adds request ID and headers
   |
   v
Matching router function runs
   |
   v
Response (or logged error) returned to the frontend
```

### 4. Important functions
```text
   - security_headers()
       Middleware: request ID, slow-request log, X-Frame-Options / nosniff headers.
   - unhandled_error()
       Saves any unexpected error to ErrorLog and returns a generic 500 response.
   - warm_up_models()
       Startup hook: secret-key check, indexes, background model warm-up, retention purge.
   - drain_background_jobs()
       Shutdown hook: lets running background jobs finish their database writes.
   - readiness()
       GET /api/health/ready - reports database and AI component status (503 if DB is down).
   - check_secret_key()
       Anyone who knows the SECRET_KEY can forge login cookies, and the placeholder values
       are public (README, .env.example).
   - warn_published_admin_password()
       Loud warning while any admin account still accepts the password older versions
       published in the README.
   - liveness()
       The process is up.
   Other helper functions: health
```

**API endpoints in this file:**
```text
   - GET /api/health
       health() - public
   - GET /api/health/live
       liveness() - public - The process is up.
   - GET /api/health/ready
       readiness() - public - Whether the app can serve requests.
```

### 5. Important variables
- Module-level constants: PLACEHOLDER_SECRETS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
   app/routers/admin/__init__.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/__init__.py,
   app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
   app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
   app/routers/student_portal_routes.py, app/routers/voice_speech_routes.py,
   app/seed_initial_data.py, app/services/ai_models/ai_task_model_router.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/platform_support/background_jobs.py, app/services/voice/speech_to_text.py,
   app/services/voice/text_to_speech.py
   Tested by: eval/run_eval.py, tests/conftest.py, tests/test_health_and_routing.py
```
External packages: fastapi

### 7. Input and output
- **Input:** HTTP requests from the browser (through the Vite proxy in development) and settings from backend/.env.
- **Output:** HTTP responses produced by the routers; health/readiness JSON.

### 8. Real project example
When a student opens the website, the frontend's first call GET /api/auth/me goes through the middleware defined here and is passed to authentication_routes.py.

### 9. Viva explanation
> main.py is the starting point of our FastAPI backend. It creates the app, connects all route files, adds security headers and error logging, and loads the AI models in the background at startup.

**Note:** This file does not contain business logic; it only wires the application together. Run with: uvicorn app.main:app --reload (see start-backend.bat).

---

## File: `backend/app/password_and_token_security.py`

### 1. Purpose
Security helpers for passwords and login tokens: Argon2 password hashing and JWT creation/checking, including password-reset tokens.

### 2. What does it do?
Password hashing and JSON Web Token handling.

1. Hashes passwords with Argon2 (with a random salt) before they are stored.
2. Verifies a typed password against the stored hash.
3. Creates the signed session JWT (user id + role, expiry) and decodes it.
4. Creates password-reset tokens that become invalid once the password changes.

### 3. How does it work?
Passwords are never stored in plain text: only the Argon2 hash is saved in User.password_hash. Tokens are signed with SECRET_KEY using HS256, so a changed token fails verification.

```
User logs in
   |
   v
verify_password() checks hash
   |
   v
create_access_token() makes JWT
   |
   v
authentication_routes.py sets it as an httpOnly cookie
```

### 4. Important functions
```text
   - hash_password()
       Argon2 hash of a password (includes a random salt), stored in `User.password_hash`.
   - verify_password()
       True if the password matches the stored Argon2 hash; False for a wrong password or a
       broken hash.
   - create_access_token()
       Signed session JWT (HS256 with SECRET_KEY) carrying the user id and role, valid for
       ACCESS_TOKEN_MINUTES.
   - decode_access_token()
       Payload of a valid, unexpired session JWT, or None (bad signature, expired,
       malformed).
   - create_reset_token()
       Password-reset JWT: signed with the reset key, tied to the current password hash,
       valid for PASSWORD_RESET_MINUTES.
   - read_reset_token()
       Payload of a valid, unexpired reset token, or None.
   - reset_token_matches()
       True if the token was issued for the user's CURRENT password (so used/old links are
       rejected).
   Other helper functions: _reset_key, _password_fingerprint
```

### 5. Important variables
- Module-level constants: ALGORITHM, COOKIE_NAME

### 6. Connected files
```text
   Uses: app/application_configuration.py
   Used by: app/authentication_dependencies.py, app/main.py, app/reset_admin_password.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/profile_and_notification_routes.py, app/seed_initial_data.py
   Tested by: tests/test_account_security.py, tests_e2e/account_browser.py
```
External packages: argon2, jwt

### 7. Input and output
- **Input:** Plain passwords, user ids/roles, tokens.
- **Output:** Password hashes, True/False checks, signed token strings, decoded token payloads.

### 8. Real project example
During login, authentication_routes.py calls verify_password() and then create_access_token().

### 9. Viva explanation
> We never store real passwords. We store an Argon2 hash and issue a signed JWT after login; the JWT is checked on every request to know who the user is.

---

## File: `backend/app/request_validation_schemas.py`

### 1. Purpose
Describes the exact shape of data the API accepts (request bodies) using Pydantic models, so bad or missing input is rejected before any code runs.

### 2. What does it do?
Input validation for API requests.

1. Defines request models such as StudentRegister, LoginIn, InterviewStart, AnswerIn, TurnIn, JobIn, AssessmentIn, EnglishMessageIn.
2. Sets limits: string lengths, allowed values (Literal), number ranges.
3. Enforces password strength for registration and password change.

### 3. How does it work?
When a route declares `body: InterviewStart`, FastAPI parses the JSON into that class and returns HTTP 422 with details if a field is wrong.

```
Frontend sends JSON
   |
   v
FastAPI validates against the schema
   |
   v
Route receives a clean object (or 422)
```

### 4. Important functions
```text
   Other helper functions: _strong_password
```

**Classes:**
```text
   - StudentRegister
   - RecruiterRegister
   - LoginIn
   - ChangePassword
   - ProjectItem
   - ExperienceItem
   - ResumeAnalysisCorrection
       Student's corrections to the AI-extracted resume details.
   - StudentProfileUpdate
   - RecruiterProfileUpdate
   - MentorProfileUpdate
   - AdminProfileUpdate
   - InterviewStart
   ... and AnswerIn, TTSOptions, TurnIn, MonitoringFeatures, MonitoringConsentIn,
   IntegrityEventIn, IntegrityEventsIn, AttentionIn, ExplanationIn, IntegrityReviewIn,
   ClientMetric, ClientMetricsIn, EnglishStart, EnglishMessageIn, MCQIn, TestCaseIn, CodingIn,
   AssessmentIn, AssessmentGenerate, AssessmentSubmit, JobIn, ApplyIn, ApplicationStatusIn,
   MessageIn, AssignAssessmentIn, CompareIn, FeedbackIn, GoalIn, PlanIn, PlanUpdate,
   MentorSessionIn, MentorSessionUpdate, AdminUserCreate, AdminUserUpdate, AssignmentIn,
   CategoryIn, BankQuestionIn, RubricCriterion, RubricIn, BadgeIn, VocabularyWordIn,
   VocabularyReviewIn, RewardRuleUpdate, SettingUpdate, FlagReview
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: app/routers/admin/admin_content_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
   app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
   app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
   app/routers/student_portal_routes.py
```
External packages: pydantic

### 7. Input and output
- **Input:** JSON bodies sent by the frontend.
- **Output:** Validated Python objects passed to route functions.

### 8. Real project example
When a student starts an interview, InterviewStart checks the job role, category, mode and question count before interview_routes.py creates the session.

### 9. Viva explanation
> These Pydantic schemas validate every request. If the frontend sends a wrong field or a weak password, the API rejects it automatically with a clear error.

---

## File: `backend/app/reset_admin_password.py`

### 1. Purpose
Command-line tool to reset the admin account's password if the one printed by the seed was lost.

### 2. What does it do?
1. Resets (or re-creates) the account named by ADMIN_EMAIL.
2. Uses the password given on the command line or generates a strong one and prints it once.
3. Re-activates the account.

### 3. How does it work?
Run `python -m app.reset_admin_password` or `python -m app.reset_admin_password "NewPass@2026"`.

```
Run the script
   |
   v
Find/create admin
   |
   v
Hash and store new password
   |
   v
Print it
```

### 4. Important functions
```text
   - reset_admin()
       Hashes the new password and saves it on the admin account.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
   app/seed_initial_data.py
```

### 7. Input and output
- **Input:** Optional new password from the command line.
- **Output:** Updated admin account; the new password printed to the console.

### 8. Real project example
If the team forgets the admin password before a demo, this restores access.

### 9. Viva explanation
> A small recovery script that sets a new admin password safely using the same hashing as login.

---

## File: `backend/app/seed_initial_data.py`

### 1. Purpose
Fills a new database with the starting data the platform needs: the admin account, badges, reward rules, challenges, interview categories, rubrics, the question bank and starter assessments.

### 2. What does it do?
One-time (repeatable) database initialisation script.

1. Creates the admin account from ADMIN_EMAIL (generates and prints a password if none is set).
2. Adds badges, reward rules and daily/weekly challenges.
3. Adds interview categories (technical, HR, behavioral, communication, mixed) and the default rubric.
4. Adds the fallback question bank and starter assessments.
5. Skips anything that already exists, so it is safe to run many times.

### 3. How does it work?
Run `python -m app.seed_initial_data`. seed() checks each item by its unique code/name before inserting.

```
Run the script
   |
   v
init_db() creates indexes
   |
   v
Missing admin/badges/categories/questions inserted
   |
   v
Commit
```

### 4. Important functions
```text
   - seed()
       Inserts all missing starting data and commits.
   Other helper functions: _mcq
```

### 5. Important variables
- Module-level constants: PUBLISHED_ADMIN_PASSWORD, BADGES, REWARD_RULES, CHALLENGES, CATEGORIES, BANK, RUBRICS,    STARTER_ASSESSMENTS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/password_and_token_security.py
   Used by: app/main.py, app/reset_admin_password.py, ml/train_question_classifier.py
   Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/conftest.py,
   tests/test_account_security.py, tests/test_english_vocab.py, tests_integration/conftest.py,
   tests_perf/bench_interview_latency.py, tests_perf/bench_models.py, tests_perf/bench_prompts.py
```

### 7. Input and output
- **Input:** Settings (admin email/password) and the constant lists defined in this file.
- **Output:** Documents in MongoDB; the generated admin password printed once to the console.

### 8. Real project example
Before the first demo, start-backend.bat runs this so the question bank exists for interviews when the AI is unavailable.

### 9. Viva explanation
> The seed script prepares a fresh database: admin account, categories, rubrics, badges and a fallback question bank. It can be run again safely because it skips existing data.

**Note:** No demo students or recruiters are created. start-backend.bat, the Dockerfile and CI run this script.

---

## File: `backend/app/seed_sample_jobs.py`

### 1. Purpose
Adds sample job openings and placement drives (fictional companies) so students have something to browse and apply to during a demo.

### 2. What does it do?
1. Publishes sample jobs under the first active recruiter account.
2. Creates sample placement drives under the first admin and notifies eligible students.
3. Skips jobs and drives whose titles already exist.

### 3. How does it work?
Run `python -m app.seed_sample_jobs`. main() looks up the owner accounts and inserts what is missing.

```
Run the script
   |
   v
Find recruiter and admin
   |
   v
Insert missing jobs/drives
   |
   v
Commit
```

### 4. Important functions
```text
   - main()
       Adds the missing sample jobs and drives.
```

### 5. Important variables
- Module-level constants: CS, ALL_TECH, YEARS, JOBS, DRIVES

### 6. Connected files
```text
   Uses: app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/platform_support/audit_and_notification_helpers.py
```

### 7. Input and output
- **Input:** The JOBS and DRIVES lists in this file; existing recruiter/admin accounts.
- **Output:** Job, JobRequirement and PlacementDrive documents.

### 8. Real project example
Used before a presentation so the student 'Jobs & Drives' page and recruiter dashboard show data.

### 9. Viva explanation
> This optional script adds demo job postings and drives so the job-matching features can be shown.

---

# Backend - MongoDB data layer

## File: `backend/app/mongodb_data_layer/__init__.py`

### 1. Purpose
The front door of the project's own MongoDB data layer. It re-exports a small SQLAlchemy-style API (select, update, delete, Session, Base, mapped_column, relationship, func, ...) implemented on top of pymongo.

### 2. What does it do?
Lets the rest of the code write SQLAlchemy-like queries while data is stored in MongoDB.

1. Imports and re-exports the public names of the sibling modules.
2. Documents how data is stored: one collection per model, integer ids from a counters collection.

### 3. How does it work?
The application was first written with SQLAlchemy (SQL). When it moved to MongoDB, this layer was written so routers and services could keep the same query style: `db.scalars(select(User).where(User.email == x))`.

```
Router imports select/Session from here
   |
   v
Builds a query
   |
   v
Session runs it against MongoDB
```

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/database_session.py,
   app/mongodb_data_layer/legacy_query_api.py, app/mongodb_data_layer/model_mapping.py,
   app/mongodb_data_layer/mongo_connection.py, app/mongodb_data_layer/query_expressions.py,
   app/mongodb_data_layer/query_statements.py
   Used by: app/authentication_dependencies.py, app/database_connection.py,
   app/database_models.py, app/main.py, app/reset_admin_password.py,
   app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/job_shared_helpers.py,
   app/routers/jobs/recruiter_job_routes.py, app/routers/jobs/recruiter_screening_routes.py,
   app/routers/jobs/student_job_routes.py, app/routers/live_voice_interview_routes.py,
   app/routers/mentor_portal_routes.py, app/routers/profile_and_notification_routes.py,
   app/routers/skill_assessment_routes.py, app/routers/student_portal_routes.py,
   app/routers/voice_speech_routes.py, app/seed_initial_data.py, app/seed_sample_jobs.py,
   app/services/ai_models/ai_structured_call_base.py,
   app/services/english/ai_english_conversation.py,
   app/services/english/english_mistake_profile.py,
   app/services/english/english_vocabulary_trainer.py,
   app/services/interview/ai_interview_service.py, app/services/monitoring/performance_timing.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/student_record_access.py,
   app/services/resume_and_jobs/ai_career_and_assessment_tasks.py,
   app/services/resume_and_jobs/ai_resume_analyzer.py,
   app/services/resume_and_jobs/semantic_job_matcher.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Tested by: tests/test_account_security.py, tests/test_deploy.py, tests/test_english_vocab.py,
   tests/test_odm.py, tests_e2e/account_browser.py, tests_perf/bench_prompts.py
```

### 7. Input and output
- **Input:** Imports from the modules in this folder.
- **Output:** Names used across the backend: `from ..mongodb_data_layer import select, Session`.

### 8. Real project example
interview_routes.py imports `select` and `func` from here to count a student's interviews in progress.

### 9. Viva explanation
> We built a small data layer that looks like SQLAlchemy but stores data in MongoDB, so our code reads like normal ORM queries while using a NoSQL database.

---

## File: `backend/app/mongodb_data_layer/column_types.py`

### 1. Purpose
Defines field types (String, Text, Integer, Float, Boolean, DateTime, JSON), ForeignKey, unique constraints and indexes used when declaring models, plus value conversion for storage.

### 2. What does it do?
1. Provides column type classes used in database_models.py.
2. Provides ForeignKey, UniqueConstraint and Index declarations (turned into MongoDB indexes).
3. Converts Python values (dates, tuples, JSON) into what MongoDB stores.
4. Defines IntegrityError for unique-constraint violations.

### 3. How does it work?
Each type knows how to convert a value before saving (_to_storage) and how to compare values when a filter has to be evaluated in Python (_cmp_value).

```
Model declares mapped_column(String(...))
   |
   v
Value assigned
   |
   v
Converted for MongoDB on save
```

### 4. Important functions
```text
   Other helper functions: CheckConstraint, _utc, _json_default, _to_storage, _cmp_value
```

**Classes:**
```text
   - IntegrityError
       A unique constraint was violated (raised in place of sqlalchemy.exc.IntegrityError).
   - Mapped
       Annotation marker only (`id: Mapped[int] = mapped_column(...)`).
   - _Type
   - String
   - Text
   - Integer
   - Float
   - Boolean
   - DateTime
   - JSON
   - ForeignKey
   - UniqueConstraint
   - Index
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/query_expressions.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py,
   app/mongodb_data_layer/legacy_query_api.py, app/mongodb_data_layer/model_mapping.py,
   app/mongodb_data_layer/mongo_connection.py, app/mongodb_data_layer/query_expressions.py
```

### 7. Input and output
- **Input:** Field declarations and Python values.
- **Output:** Storable values and index definitions.

### 8. Real project example
User.email is declared as a unique String; inserting a duplicate raises IntegrityError, which registration turns into 'email already registered'.

### 9. Viva explanation
> This module defines the data types and constraints of our models and converts values to the format MongoDB stores.

---

## File: `backend/app/mongodb_data_layer/database_session.py`

### 1. Purpose
The Session class: a unit of work that adds, changes, deletes and queries objects and writes them to MongoDB on commit.

### 2. What does it do?
Runs every database read and write for a request.

1. add / delete objects; flush writes pending changes; commit saves them; rollback discards them.
2. get(Model, id) loads one object; scalars/scalar/execute run select statements.
3. begin_nested() for savepoint-like behaviour; after_commit() runs callbacks (live notifications).
4. Executes update/delete statements and evaluates joins and aggregates.

### 3. How does it work?
Changes are tracked on each object. On flush the Session inserts new documents (assigning integer ids from the counters collection) and updates changed fields. Queries are pushed down to MongoDB where possible.

```
Route calls db.add(obj)
   |
   v
db.commit()
   |
   v
flush(): insert/update documents
   |
   v
after_commit callbacks run
```

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

**Classes:**
```text
   - Session
       Unit of work over one MongoDB database (same role as sqlalchemy.orm.Session, autoflush
       off).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/legacy_query_api.py,
   app/mongodb_data_layer/model_mapping.py, app/mongodb_data_layer/mongo_connection.py,
   app/mongodb_data_layer/query_expressions.py, app/mongodb_data_layer/query_statements.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/model_mapping.py
```
External packages: pymongo

### 7. Input and output
- **Input:** Model objects and select/update/delete statements.
- **Output:** Saved documents and query results.

### 8. Real project example
When an answer is saved, db.commit() writes the InterviewAnswer and the session's flag fields.

### 9. Viva explanation
> The Session works like a transaction manager: we add or change objects and commit, and it writes them to MongoDB.

---

## File: `backend/app/mongodb_data_layer/legacy_query_api.py`

### 1. Purpose
Supports the older `db.query(Model).filter(...)` style used by some tests and scripts, plus helpers for sorting, joins and removing duplicates in Python.

### 2. What does it do?
1. Query class with filter, filter_by, order_by, limit, offset, all, first, count, delete.
2. Helpers to sort results, infer join conditions and de-duplicate rows.

### 3. How does it work?
Query builds a select statement internally and runs it through the Session.

```
db.query(User).filter(...)
   |
   v
Converted to select()
   |
   v
Session executes
```

### 4. Important functions
```text
   Other helper functions: _hashable, _dedupe, _slice, _entity_key, _ordered_models, _mongo_sort,
   _sort, _infer_join, _join_keys
```

**Classes:**
```text
   - Query
       Legacy `db.query(Model).filter(...)` style, as used by some tests and scripts.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/model_mapping.py,
   app/mongodb_data_layer/query_expressions.py, app/mongodb_data_layer/query_statements.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py
```
External packages: pymongo

### 7. Input and output
- **Input:** Legacy-style query calls.
- **Output:** Lists of model objects or counts.

### 8. Real project example
Some tests use db.query(User).filter_by(email=...).first() to check saved data.

### 9. Viva explanation
> This keeps an older query style working, mainly for tests and scripts.

---

## File: `backend/app/mongodb_data_layer/model_mapping.py`

### 1. Purpose
The declarative `Base` class for models, relationships between models, and per-object state (new / loaded / changed).

### 2. What does it do?
1. Base: turns class attributes into columns and gives each model a collection name.
2. Converts objects to MongoDB documents and back (_to_doc, _load_into).
3. relationship: loads related objects on first access (one-to-many and many-to-one).
4. InstrumentedList: keeps child foreign keys in sync when items are appended/removed.

### 3. How does it work?
When code accesses `session.questions`, relationship looks up the related documents by foreign key and caches them on the object.

```
Access interview.questions
   |
   v
relationship queries interview_questions by session_id
   |
   v
List returned
```

### 4. Important functions
```text
   Other helper functions: _state, _collection_name, _to_doc, _load_into, _link,
   set_fallback_session_factory, _session_for, _annotation_text
```

**Classes:**
```text
   - _State
   - Base
   - relationship
       Related objects, loaded on first access.
   - InstrumentedList
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/database_session.py,
   app/mongodb_data_layer/query_expressions.py, app/mongodb_data_layer/query_statements.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py,
   app/mongodb_data_layer/legacy_query_api.py, app/mongodb_data_layer/mongo_connection.py,
   app/mongodb_data_layer/query_statements.py
```

### 7. Input and output
- **Input:** Model class declarations and stored documents.
- **Output:** Python objects with loaded relationships.

### 8. Real project example
`session.questions.append(InterviewQuestion(...))` in interview_routes.py links the new question to the interview automatically.

### 9. Viva explanation
> This module maps Python classes to MongoDB documents and handles relationships, like an interview having many questions.

---

## File: `backend/app/mongodb_data_layer/mongo_connection.py`

### 1. Purpose
Creates the single MongoClient for the process and creates indexes/unique constraints declared on the models.

### 2. What does it do?
1. Opens one MongoDB client per process.
2. Creates indexes from model declarations (safe to run every start).

### 3. How does it work?
database_connection.init_db() calls ensure_indexes() at startup.

```
Server start
   |
   v
connect()
   |
   v
ensure_indexes()
```

### 4. Important functions
```text
   - connect()
       Returns one shared MongoClient (thread-safe, pooled).
   - ensure_indexes()
       Creates every index and unique constraint declared on the models.
   Other helper functions: _model_list
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/model_mapping.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py
```
External packages: pymongo

### 7. Input and output
- **Input:** MongoDB URL; model declarations.
- **Output:** MongoClient and indexes in the database.

### 8. Real project example
On the first start, this creates the unique index on users.email.

### 9. Viva explanation
> This file opens the MongoDB connection and creates the indexes our models need.

---

## File: `backend/app/mongodb_data_layer/query_expressions.py`

### 1. Purpose
Query building blocks: columns, comparisons (==, <, in_, like), AND/OR/NOT, functions such as count and max, and ordering.

### 2. What does it do?
1. Turns Python expressions like `User.role == 'student'` into expression objects.
2. Translates expressions into MongoDB filters when possible (to_mongo).
3. Evaluates expressions in Python when MongoDB cannot (e.g. after joins).
4. Supports aggregate functions (func.count, func.max, func.avg) and ordering (desc, nulls_last).

### 3. How does it work?
Comparing a Column with a value returns a Binary expression instead of True/False. The Session later converts the whole expression tree to a MongoDB query.

```
select(...).where(User.role == 'student')
   |
   v
Expression tree built
   |
   v
to_mongo() -> {'role': 'student'}
```

### 4. Important functions
```text
   Other helper functions: _like_regex, _lit, _apply, and_, or_, not_, _order_parts
```

**Classes:**
```text
   - _CannotPush
   - Expr
   - Literal
   - Column
       A model column.
   - Binary
   - BoolOp
   - Func
   - _FuncFactory
   - Label
   - Ordering
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/column_types.py, app/mongodb_data_layer/query_statements.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/column_types.py,
   app/mongodb_data_layer/database_session.py, app/mongodb_data_layer/legacy_query_api.py,
   app/mongodb_data_layer/model_mapping.py
```

### 7. Input and output
- **Input:** Expressions written in routers/services.
- **Output:** MongoDB filter dictionaries or Python-evaluated results.

### 8. Real project example
`InterviewSession.status == 'in_progress'` becomes a MongoDB filter when starting an interview.

### 9. Viva explanation
> This module lets us write filters like `User.role == 'student'` in Python and converts them into MongoDB queries.

---

## File: `backend/app/mongodb_data_layer/query_statements.py`

### 1. Purpose
The select, update and delete statement builders and the result objects they return.

### 2. What does it do?
1. select(...).where().join().order_by().group_by().limit() builds a query.
2. update(Model).where().values() and delete(Model).where() build bulk changes.
3. ScalarResult / Result give all(), first(), one(), scalar_one_or_none() etc.

### 3. How does it work?
Statements only describe the query; Session.execute()/scalars() runs them.

```
select(Job).where(Job.status == 'published')
   |
   v
db.scalars(stmt)
   |
   v
ScalarResult.all()
```

### 4. Important functions
```text
   Other helper functions: select, update, delete
```

**Classes:**
```text
   - Subquery
   - Select
   - Update
   - Delete
   - Row
   - ScalarResult
   - Result
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/model_mapping.py
   Used by: app/mongodb_data_layer/__init__.py, app/mongodb_data_layer/database_session.py,
   app/mongodb_data_layer/legacy_query_api.py, app/mongodb_data_layer/model_mapping.py,
   app/mongodb_data_layer/query_expressions.py
```

### 7. Input and output
- **Input:** Models and expressions.
- **Output:** Statement objects and result wrappers.

### 8. Real project example
student_job_routes.py uses select(Job) with filters to list published jobs.

### 9. Viva explanation
> This module builds select, update and delete statements in a SQL-like style for our MongoDB layer.

---

# Backend - API route files

## File: `backend/app/routers/__init__.py`

### 1. Purpose
Marks the routers folder as a Python package. It contains no code.

### 2. What does it do?
1. Lets main.py import the route files with `from .routers import ...`.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the routers folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker for the folder that holds all API route files.

---

## File: `backend/app/routers/admin/__init__.py`

### 1. Purpose
Combines the four admin route files into one router mounted under /api/admin.

### 2. What does it do?
1. Imports analytics, user management, content and operations routes.
2. Exposes `router` for main.py.

### 3. How does it work?
Each part has its own APIRouter; this file includes them all into one.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py
   Used by: app/main.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Combines the four admin route files into one router mounted under /api/admin.

### 9. Viva explanation
> This file groups all admin endpoints into a single router.

---

## File: `backend/app/routers/admin/admin_analytics_routes.py`

### 1. Purpose
Admin analytics: platform dashboard, placement report, student overview, AI report review and backup.

### 2. What does it do?
1. Dashboard counts and charts (users, interviews, activity per day, readiness distribution).
2. Placement report as JSON or CSV.
3. Student overview with filters.
4. Recent AI-generated feedback for quality review.
5. Full database backup as a zip of JSON files.

### 3. How does it work?
See the steps above.

```
Admin opens dashboard
   |
   v
Counts aggregated from collections
   |
   v
Charts displayed
```

### 4. Important functions
```text
   - ai_reports()
       Recent AI-generated feedback for quality review.
   - backup()
       Every MongoDB collection as MongoDB Extended JSON (one file per collection) in a zip.
   Other helper functions: _daily_counts, dashboard, _readiness_distribution,
   _popular_activities, placement_report, students_overview
```

**API endpoints in this file:**
```text
   - GET /api/admin/dashboard
       dashboard() - admin
   - GET /api/admin/reports/placements
       placement_report() - admin
   - GET /api/admin/students
       students_overview() - admin
   - GET /api/admin/ai-reports
       ai_reports() - admin - Recent AI-generated feedback for quality review.
   - GET /api/admin/backup
       backup() - admin - Every MongoDB collection as MongoDB Extended JSON (one file per
       collection) in a zip.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/admin/__init__.py
```
External packages: bson, fastapi, starlette

### 7. Input and output
- **Input:** Filters and paging parameters.
- **Output:** Statistics JSON, CSV files, a backup zip.

### 8. Real project example
The placement officer downloads the placement report CSV before a review meeting.

### 9. Viva explanation
> These endpoints give the admin an overview of the platform and downloadable reports.

---

## File: `backend/app/routers/admin/admin_content_routes.py`

### 1. Purpose
Admin configuration of interview content: categories, question bank, evaluation rubrics, badges, reward rules and challenges.

### 2. What does it do?
1. Create/update interview categories.
2. Manage the fallback question bank.
3. Create/update evaluation rubrics (criteria weights must be valid).
4. Manage badges, reward rules and challenges.

### 3. How does it work?
See the steps above.

```
Admin edits rubric
   |
   v
Validated
   |
   v
Saved
   |
   v
Used for scoring new answers
```

### 4. Important functions
```text
   Other helper functions: categories, create_category, update_category, list_questions,
   create_question, update_question, delete_question, rubrics, _validate_rubric, create_rubric,
   update_rubric, badges, create_badge, update_badge, reward_rules, update_reward_rule,
   list_challenges, create_challenge, update_challenge
```

**Classes:**
```text
   - ChallengeIn
```

**API endpoints in this file:**
```text
   - GET /api/admin/categories
       categories() - admin
   - POST /api/admin/categories
       create_category() - admin
   - PUT /api/admin/categories/{category_id}
       update_category() - admin
   - GET /api/admin/questions
       list_questions() - admin
   - POST /api/admin/questions
       create_question() - admin
   - PUT /api/admin/questions/{question_id}
       update_question() - admin
   - DELETE /api/admin/questions/{question_id}
       delete_question() - admin
   - GET /api/admin/rubrics
       rubrics() - admin
   - POST /api/admin/rubrics
       create_rubric() - admin
   - PUT /api/admin/rubrics/{rubric_id}
       update_rubric() - admin
   - GET /api/admin/badges
       badges() - admin
   - POST /api/admin/badges
       create_badge() - admin
   - PUT /api/admin/badges/{badge_id}
       update_badge() - admin
   - GET /api/admin/reward-rules
       reward_rules() - admin
   - PATCH /api/admin/reward-rules/{rule_id}
       update_reward_rule() - admin
   - GET /api/admin/challenges
       list_challenges() - admin
   - POST /api/admin/challenges
       create_challenge() - admin
   - PUT /api/admin/challenges/{challenge_id}
       update_challenge() - admin
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/request_validation_schemas.py,
   app/services/platform_support/audit_and_notification_helpers.py
   Used by: app/routers/admin/__init__.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** Content definitions from the admin pages.
- **Output:** Saved configuration; audit log entries.

### 8. Real project example
If the admin changes rubric weights, new interview answers are scored with the new weights.

### 9. Viva explanation
> This file lets the admin control interview content such as the question bank and scoring rubric.

---

## File: `backend/app/routers/admin/admin_operations_routes.py`

### 1. Purpose
Admin operations: all job postings, flagged activity review, AI usage, error and audit logs, platform settings, placement drives and announcements.

### 2. What does it do?
1. List/close any job.
2. Review flagged interviews/assessments and revoke points if needed.
3. AI usage statistics and error logs.
4. Audit log viewer.
5. Edit platform settings.
6. Create placement drives (eligible students notified) and send announcements.

### 3. How does it work?
See the steps above.

```
Admin reviews flagged interview
   |
   v
Marks outcome
   |
   v
Points revoked if confirmed
```

### 4. Important functions
```text
   Other helper functions: list_jobs, close_job, flagged, view_interview, review_flag, ai_usage,
   errors, audit_logs, settings, update_setting, list_drives, _eligible_students, create_drive,
   update_drive, drive_registrations, list_announcements, send_announcement
```

**Classes:**
```text
   - DriveIn
   - AnnouncementIn
```

**API endpoints in this file:**
```text
   - GET /api/admin/jobs
       list_jobs() - admin
   - POST /api/admin/jobs/{job_id}/close
       close_job() - admin
   - GET /api/admin/flagged
       flagged() - admin
   - GET /api/admin/interviews/{session_id}
       view_interview() - admin
   - POST /api/admin/flagged/{kind}/{item_id}
       review_flag() - admin
   - GET /api/admin/ai-usage
       ai_usage() - admin
   - GET /api/admin/errors
       errors() - admin
   - GET /api/admin/audit-logs
       audit_logs() - admin
   - GET /api/admin/settings
       settings() - admin
   - PUT /api/admin/settings/{key}
       update_setting() - admin
   - GET /api/admin/drives
       list_drives() - admin
   - POST /api/admin/drives
       create_drive() - admin
   - PUT /api/admin/drives/{drive_id}
       update_drive() - admin
   - GET /api/admin/drives/{drive_id}/registrations
       drive_registrations() - admin
   - GET /api/admin/announcements
       list_announcements() - admin
   - POST /api/admin/announcements
       send_announcement() - admin
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/admin/__init__.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** Admin actions and filters.
- **Output:** Lists, settings, notifications, audit entries.

### 8. Real project example
The admin creates a campus drive; eligible students receive a notification.

### 9. Viva explanation
> These are admin tools for running the platform: logs, settings, flagged activity and placement drives.

---

## File: `backend/app/routers/admin/admin_user_management_routes.py`

### 1. Purpose
Admin management of user accounts, mentor-student assignments and recruiter verification.

### 2. What does it do?
1. List, view, create (staff), update and deactivate users.
2. Assign students to mentors and remove assignments.
3. Approve/verify recruiter accounts.

### 3. How does it work?
Deleting a user is a soft delete (deactivation) so historical records stay consistent.

```
Recruiter registers (pending)
   |
   v
Admin verifies
   |
   v
Recruiter can sign in
```

### 4. Important functions
```text
   - delete_user()
       Soft delete: deactivates the account so historical records stay consistent.
   Other helper functions: list_users, get_user, create_user, update_user, list_assignments,
   assign, unassign, verify_recruiter
```

**Classes:**
```text
   - VerifyIn
```

**API endpoints in this file:**
```text
   - GET /api/admin/users
       list_users() - admin
   - GET /api/admin/users/{user_id}
       get_user() - admin
   - POST /api/admin/users
       create_user() - admin
   - PATCH /api/admin/users/{user_id}
       update_user() - admin
   - DELETE /api/admin/users/{user_id}
       delete_user() - admin - Soft delete: deactivates the account so historical records
       stay consistent.
   - GET /api/admin/assignments
       list_assignments() - admin
   - POST /api/admin/assignments
       assign() - admin
   - DELETE /api/admin/assignments/{assignment_id}
       unassign() - admin
   - POST /api/admin/recruiters/{user_id}/verify
       verify_recruiter() - admin
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/password_and_token_security.py, app/request_validation_schemas.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/admin/__init__.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** User data, assignment pairs, verification decisions.
- **Output:** User JSON; audit log entries.

### 8. Real project example
The admin creates mentor accounts and assigns each mentor a group of students.

### 9. Viva explanation
> This file lets the admin manage users, approve recruiters and assign mentors to students.

---

## File: `backend/app/routers/authentication_routes.py`

### 1. Purpose
All account-access endpoints: student and recruiter registration, login, logout, the current user, password reset and change, AI data consent and account deletion.

### 2. What does it do?
Registration and login (Stage 1 of the workflow).

1. Registers students (signed in immediately) and recruiters (may wait for admin approval).
2. Logs users in: checks the Argon2 password hash and sets the JWT in an httpOnly cookie.
3. Blocks brute force: too many wrong passwords for one email locks login for a while (rate_limiter).
4. Returns the signed-in user on page load (GET /api/auth/me) so the session survives a refresh.
5. Handles forgot/reset password with signed one-time tokens sent by email (or logged if email is off).
6. Lets a student delete their own account and data; records consent to hosted-AI processing.

### 3. How does it work?
Each function is a FastAPI route under the prefix /api/auth. Input is validated by schemas such as StudentRegister and LoginIn. Passwords and tokens are handled by password_and_token_security.py, and important actions are written to the audit log.

```
Login form posts email + password
   |
   v
User looked up, password hash verified
   |
   v
Failed attempts counted (lockout)
   |
   v
JWT created and set as httpOnly cookie
   |
   v
User JSON returned
```

### 4. Important functions
```text
   - register_student()
       POST /api/auth/register/student - create a student account and sign in.
   - register_recruiter()
       POST /api/auth/register/recruiter - create a recruiter (pending if approval is
       required).
   - login()
       POST /api/auth/login - verify email/password, apply lockout, set the session cookie.
   - me()
       GET /api/auth/me - current user + AI availability (used by AuthContext.jsx on load).
   - forgot_password()
       POST /api/auth/forgot-password - email a reset link (same reply whether or not the
       account exists).
   - reset_password()
       POST /api/auth/reset-password - set a new password from a valid token.
   - delete_my_account()
       DELETE /api/auth/me - remove a student's own data permanently.
   - logout()
       Clear the session cookie.
   - privacy_info()
       Public: which AI provider processes data on this server, and the consent notice when
       it is hosted.
   - set_ai_consent()
       Give (accept=true) or withdraw (accept=false) consent to the hosted-AI data notice.
   - change_password()
       Change the signed-in user's password after checking the current one.
   Other helper functions: _login_key, _set_cookie, _clear_cookie, _email_taken
```

**Classes:**
```text
   - AIConsentIn
   - ForgotPasswordIn
   - ResetPasswordIn
   - DeleteAccountIn
```

**API endpoints in this file:**
```text
   - POST /api/auth/register/student
       register_student() - public - Create an active student account with an empty profile,
       then sign the student in (sets the cookie). 403 if student registration is closed in
       admin settings, 409 if the email is taken.
   - POST /api/auth/register/recruiter
       register_recruiter() - public - Create a recruiter account.
   - POST /api/auth/login
       login() - public - Check email and password and set the session cookie.
   - POST /api/auth/logout
       logout() - public - Clear the session cookie.
   - GET /api/auth/me
       me() - any signed-in user - Current user's profile plus AI availability.
   - GET /api/auth/privacy
       privacy_info() - public - Public: which AI provider processes data on this server, and
       the consent notice when it is hosted.
   - POST /api/auth/ai-consent
       set_ai_consent() - any signed-in user - Give (accept=true) or withdraw (accept=false)
       consent to the hosted-AI data notice.
   - POST /api/auth/forgot-password
       forgot_password() - public - Start a password reset.
   - POST /api/auth/reset-password
       reset_password() - public - Set a new password from a reset-link token.
   - DELETE /api/auth/me
       delete_my_account() - any signed-in user - Permanently delete a student's own account
       and personal data (resumes and their files, interviews, English practice,
       applications, rewards, notifications).
   - POST /api/auth/change-password
       change_password() - any signed-in user - Change the signed-in user's password after
       checking the current one.
```

### 5. Important variables
- Module-level constants: MAX_RESET_REQUESTS, GENERIC_RESET_REPLY

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/application_configuration.py,
   app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
   app/request_validation_schemas.py, app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/email_sender.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/platform_support/rate_limiter.py
   Used by: app/main.py
   Tested by: tests/test_account_security.py, tests/test_deploy.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** JSON bodies (email, password, name, role details), the session cookie.
- **Output:** User JSON, the hs_session cookie, success/error messages.

### 8. Real project example
A student fills the Register page; the frontend posts to /api/auth/register/student, this file creates the User and StudentProfile and signs them in.

### 9. Viva explanation
> This file handles sign-up, login and passwords. Passwords are hashed with Argon2, login returns a JWT in an httpOnly cookie, and repeated wrong passwords lock the account temporarily.

---

## File: `backend/app/routers/english_practice_routes.py`

### 1. Purpose
Spoken and typed English conversation practice with the AI companion 'Aria', plus vocabulary review, mistake profile, daily plan and English progress.

### 2. What does it do?
1. Start, list, open, end and delete English practice sessions.
2. Send a message and get Aria's reply (plain or streamed with Server-Sent Events).
3. Count verified active practice time and a motivational confidence meter.
4. Evaluate a finished session (grammar, vocabulary, fluency, sentence formation).
5. Vocabulary list with spaced-repetition reviews, recurring-mistake profile, daily plan and progress.

### 3. How does it work?
_send_message() saves the student's message, asks ai.english_reply() for Aria's reply and corrections, records corrections in the mistake profile and vocabulary list, updates conversation memory and awards rewards. end_session() calls ai.english_evaluate().

```
Student starts session
   |
   v
Sends message
   |
   v
Aria replies with corrections
   |
   v
Corrections saved as vocabulary
   |
   v
End -> evaluation scores and rewards
```

### 4. Important functions
```text
   - _send_message()
       Full message round trip shared by the plain and streaming endpoints.
   - compute_active_seconds()
       Verified practice time (ignores idle gaps and one-word spam).
   - end_session()
       Finish a session and get the AI evaluation scores.
   - confidence_meter()
       0-100 motivational estimate of how freely the student is speaking: longer answers,
       fewer corrections, more turns and speaking aloud all raise it.
   - companion()
       The English companion's public configuration and learning modes (for the start
       screen).
   - stats()
       Motivation widgets: English-practice streak (days with >= 1 verified minute) and
       totals.
   - learning_profile()
       The student's recurring-mistake patterns (rule-based, from corrections already given).
   - vocabulary()
       The student's word list (newest first) and box counts. filter: all | due | learning |
       learned | mastered.
   - review_queue()
       The cards due now (oldest first, at most REVIEW_BATCH).
   - daily_plan()
       Today's plan, ticked automatically from what the student did today.
   - send_message_stream()
       Same as POST .../message, but the reply text is sent while the model writes it
       (Server-Sent Events): event: delta {"text": "..."} the reply so far (cumulative; it
       can get shorter if the model starts over, so the...
   Other helper functions: _sse, _aware, _ai_message, session_out, _get, start, dismiss_pattern,
   clear_profile, add_vocabulary, review_card, delete_vocabulary, english_progress,
   list_sessions, get_session, send_message, delete_session
```

**API endpoints in this file:**
```text
   - POST /api/student/english
       start() - student
   - GET /api/student/english/companion
       companion() - student - The English companion's public configuration and learning
       modes (for the start screen).
   - GET /api/student/english/stats
       stats() - student - Motivation widgets: English-practice streak (days with >= 1
       verified minute) and totals.
   - GET /api/student/english/profile
       learning_profile() - student - The student's recurring-mistake patterns (rule-based,
       from corrections already given).
   - POST /api/student/english/profile/{pattern_id}/dismiss
       dismiss_pattern() - student
   - DELETE /api/student/english/profile
       clear_profile() - student
   - GET /api/student/english/vocabulary
       vocabulary() - student - The student's word list (newest first) and box counts.
       filter: all | due | learning | learned | mastered.
   - POST /api/student/english/vocabulary
       add_vocabulary() - student
   - GET /api/student/english/vocabulary/review
       review_queue() - student - The cards due now (oldest first, at most REVIEW_BATCH).
   - POST /api/student/english/vocabulary/{item_id}/review
       review_card() - student
   - DELETE /api/student/english/vocabulary/{item_id}
       delete_vocabulary() - student
   - GET /api/student/english/daily-plan
       daily_plan() - student - Today's plan, ticked automatically from what the student did
       today.
   - GET /api/student/english/progress
       english_progress() - student
   - GET /api/student/english
       list_sessions() - student
   - GET /api/student/english/{session_id}
       get_session() - student
   - POST /api/student/english/{session_id}/message
       send_message() - student
   - POST /api/student/english/{session_id}/message/stream
       send_message_stream() - student - Same as POST .../message, but the reply text is sent
       while the model writes it (Server-Sent Events):
   - POST /api/student/english/{session_id}/end
       end_session() - student
   - DELETE /api/student/english/{session_id}
       delete_session() - student
```

### 5. Important variables
- Module-level constants: MAX_GAP_SECONDS, MIN_WORDS_FOR_ACTIVE, OPENERS

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/services/english/english_companion_memory.py,
   app/services/english/english_mistake_profile.py,
   app/services/english/english_vocabulary_trainer.py,
   app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/background_jobs.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py,
   app/services/voice/streamed_reply_sentence_splitter.py
   Used by: app/main.py
   Tested by: tests/test_english_avatar.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Messages, session settings (topic, style, learning mode), vocabulary reviews.
- **Output:** Session JSON with messages, corrections, memory, scores; plan/progress JSON.

### 8. Real project example
A student practises 'Tell me about yourself' with Aria; grammar corrections become flash cards in the Vocabulary page.

### 9. Viva explanation
> This file powers English practice with an AI companion. It saves the conversation, gives corrections, tracks mistakes and vocabulary, and scores the session at the end.

---

## File: `backend/app/routers/interview_monitoring_routes.py`

### 1. Purpose
Disclosed, opt-in interview integrity monitoring (camera/browser signals), security settings and the performance dashboard API.

### 2. What does it do?
1. Shows the monitoring policy and records the candidate's consent (or withdrawal).
2. Receives integrity events from the browser (face not visible, looking away, paste, tab switch, ...).
3. Receives attention-time totals and builds a neutral attention report.
4. Lets candidates explain events; lets admins/permitted reviewers review them.
5. Admin security settings (detectors, thresholds) and performance timing summary.

### 3. How does it work?
Only events for features the candidate agreed to are stored. Severity and risk summary come from interview_integrity_rules.py. Events never change interview scores; they are signals for a human reviewer.

```
Candidate agrees to monitoring
   |
   v
Browser detects events on-device
   |
   v
Events posted in batches
   |
   v
Reviewer sees neutral summary and decides
```

### 4. Important functions
```text
   - purge_expired()
       Delete integrity events older than the retention period.
   - report_attention()
       Cumulative attention time totals from the browser (see
       services/monitoring/visual_attention_report.py).
   - integrity_overview()
       Per-candidate roll-up of monitored, completed interviews that `viewer` may review
       (same rule as the review pages: for recruiters, only applicants who consented under a
       policy that disclosed recruiter access).
   - client_metrics()
       Timings measured in the browser (e.g. answer submitted → next question audible).
   Other helper functions: _rate_ok, _retention, security_config, _session_config, _own_session,
   _aware, _clock_origin, _elapsed_ms, event_out, _summary, monitoring_policy, give_consent,
   withdraw_consent, _event_rows, report_events, _attention_report, my_events, explain_event,
   _reviewer, _may_review, _parse_date, review_list, review_detail, review_event, _flat,
   get_security_settings, put_security_settings, performance
```

**API endpoints in this file:**
```text
   - GET /api/monitoring/policy
       monitoring_policy() - any signed-in user
   - POST /api/student/interviews/{session_id}/monitoring/consent
       give_consent() - student
   - POST /api/student/interviews/{session_id}/monitoring/withdraw
       withdraw_consent() - student
   - POST /api/student/interviews/{session_id}/integrity-events
       report_events() - student
   - PUT /api/student/interviews/{session_id}/attention
       report_attention() - student - Cumulative attention time totals from the browser (see
       services/monitoring/visual_attention_report.py).
   - GET /api/student/interviews/{session_id}/integrity-events
       my_events() - student
   - PUT /api/student/interviews/{session_id}/integrity-events/{event_id}/explanation
       explain_event() - student
   - GET /api/monitoring/sessions
       review_list() - reviewer (admin / permitted mentor / recruiter)
   - GET /api/monitoring/sessions/{session_id}
       review_detail() - reviewer (admin / permitted mentor / recruiter)
   - PATCH /api/monitoring/events/{event_id}
       review_event() - reviewer (admin / permitted mentor / recruiter)
   - GET /api/admin/security-settings
       get_security_settings() - admin
   - PUT /api/admin/security-settings
       put_security_settings() - admin
   - POST /api/perf/client
       client_metrics() - any signed-in user - Timings measured in the browser (e.g. answer
       submitted → next question audible).
   - GET /api/admin/performance
       performance() - admin
```

### 5. Important variables
- Module-level constants: MAX_EVENTS_PER_SESSION, LATE_EVENTS_GRACE, CLOCK_SLACK_MS, RATE_LIMIT, BAND_ORDER

### 6. Connected files
```text
   Uses: app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/request_validation_schemas.py,
   app/services/monitoring/interview_integrity_rules.py,
   app/services/monitoring/performance_timing.py,
   app/services/monitoring/visual_attention_report.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/rate_limiter.py,
   app/services/platform_support/student_record_access.py
   Used by: app/main.py, app/routers/jobs/recruiter_job_routes.py
   Tested by: tests/test_attention.py, tests/test_latency_and_monitoring.py,
   tests/test_security_module.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** Consent choices, event batches and attention totals from the browser.
- **Output:** Event lists, risk summaries, review history, settings JSON.

### 8. Real project example
If a student looks away for a long time during the interview, an event is recorded and later shown to the admin as 'needs review', not as cheating.

### 9. Viva explanation
> This file handles optional proctoring. The browser analyses the camera locally and sends only event records; reviewers see neutral signals and scores are never changed automatically.

**Note:** No video or images are sent or stored; only short event records.

---

## File: `backend/app/routers/interview_routes.py`

### 1. Purpose
The AI mock interview API: start an interview, get the next adaptive question, submit and score answers, finish the interview and build the report.

### 2. What does it do?
Interview configuration, question generation, answer evaluation, scoring and report (Stages 3-10).

1. Starts an interview with role, category, mode (text/voice), question count, interviewer personality.
2. Chooses each next question: AI-generated from the resume and previous answers, otherwise a resume-based template, otherwise the admin question bank.
3. Adapts difficulty: a high score moves up a level, a low score moves down (ai.next_difficulty).
4. Scores each answer quickly (score_answer) and writes detailed feedback later in a background job.
5. Flags suspicious answers (very fast long answers, identical answers) for admin review, never auto-penalising.
6. On completion: overall score = average of answer scores, AI report + deterministic metrics, progress records, points/badges and mentor alerts.
7. Retry evaluation when the AI was unavailable; abandon an interview.

### 3. How does it work?
_add_next_question() collects the resume analysis, skills and history, asks the AI for a question, then rejects duplicates or bad questions (interview_intelligence_rules.py) and retries. submit_answer() saves the answer, calls _evaluate(full=False) for fast scores, adds the next question and schedules feedback_job() in the background. complete_interview() calls _finalize_scores_and_report() and _post_completion().

```
Student starts interview (role, category, mode)
   |
   v
First question generated (AI or bank)
   |
   v
Student answers -> fast AI score -> next difficulty
   |
   v
Next adaptive question generated
   |
   v
Feedback written in background
   |
   v
Complete -> overall score + report -> rewards and mentor alerts
```

### 4. Important functions
```text
   - start_interview()
       POST /api/student/interviews - create the session and its first question.
   - _add_next_question()
       Generate/validate the next question (AI -> template -> question bank fallback).
   - _next_level()
       Decide the next difficulty from the previous answer's score.
   - submit_answer()
       POST .../{id}/answer - save, fast-score, add next question, queue feedback.
   - _evaluate()
       Score one answer with the AI (fast scores or full evaluation) and store the result.
   - feedback_job()
       Background task: detailed tips + sample answer for a scored answer.
   - _finalize_scores_and_report()
       Overall score = average of scored answers; AI report + metrics.
   - _post_completion()
       Progress records, points, badges, mentor alerts after an interview.
   - complete_interview()
       POST .../{id}/complete - finish, score and report.
   - retry_evaluation()
       POST .../{id}/retry-evaluation - redo missing AI work.
   - list_interviewers()
       Interviewer personalities for the selection screen (behaviour prompts stay on the
       server).
   - is_repeat()
       True if `text` is the same as, or a light rephrasing of, an earlier question.
   Other helper functions: _rubric, _get_session, _bank_question, _norm, list_interviews,
   get_interview, _add_feedback, _feedback_in_background, _check_suspicious, _check_current,
   _save_answer, _lock_turn, _unlock_turn, _start_prefetch, ensure_next_question,
   abandon_interview
```

**API endpoints in this file:**
```text
   - GET /api/interviewers
       list_interviewers() - any signed-in user - Interviewer personalities for the selection
       screen (behaviour prompts stay on the server).
   - POST /api/student/interviews
       start_interview() - student - Create a new interview session (POST
       /api/student/interviews).
   - GET /api/student/interviews
       list_interviews() - student - The student's own interviews, newest first, paginated
       (optionally filtered by status).
   - GET /api/student/interviews/{session_id}
       get_interview() - student - One interview with its questions, answers, scores and
       report.
   - POST /api/student/interviews/{session_id}/answer
       submit_answer() - student - Text-mode answer (POST .../answer).
   - POST /api/student/interviews/{session_id}/next-question
       ensure_next_question() - student - Recovery: if the previous request saved the answer
       but failed before creating the next question, create it now.
   - POST /api/student/interviews/{session_id}/complete
       complete_interview() - student - Finish an interview (POST .../complete): drop the
       unanswered trailing question, compute the overall score and report, then record
       progress, award points/badges and alert mentors when needed.
   - POST /api/student/interviews/{session_id}/retry-evaluation
       retry_evaluation() - student - Re-run whatever AI work is missing: feedback for
       answers that only have scores, full evaluation for unscored answers, then the final
       report. 503 with the reason if the AI is still unavailable.
   - DELETE /api/student/interviews/{session_id}
       abandon_interview() - student - Mark an in-progress interview as abandoned (it stays
       in the history but is never scored).
```

### 5. Important variables
- `DEFAULT_RUBRIC`: Relevance 0.25, Correctness 0.30, Clarity 0.25, Communication 0.20 (used when the admin has no active rubric).
- `_turn_locks`: Which live interviews currently have a turn running (blocks double submissions).
- Module-level constants: DEFAULT_RUBRIC, QUESTION_TYPES, LIVE_QUESTION_ATTEMPTS, TEXT_QUESTION_ATTEMPTS,    FEEDBACK_RETRY_SECONDS, TURN_LOCK_STALE_S

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/services/ai_models/question_type_classifier.py,
   app/services/interview/ai_interview_service.py,
   app/services/interview/interview_intelligence_rules.py,
   app/services/interview/interview_report_metrics.py,
   app/services/interview/interviewer_personalities.py,
   app/services/monitoring/performance_timing.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/background_jobs.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/main.py, app/routers/live_voice_interview_routes.py
   Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/test_latency_and_monitoring.py,
   tests/test_local_ai.py, tests/test_scoring_calibration.py,
   tests_integration/test_real_models.py
```
External packages: fastapi

### 7. Input and output
- **Input:** InterviewStart / AnswerIn JSON from the frontend, the student's resume analysis and profile.
- **Output:** Interview session JSON with questions, answers, scores, feedback and the final report.

### 8. Real project example
A student practising for 'Python Developer' answers 5 questions; each answer gets a score, and the final report lists strengths, weaknesses and an overall score.

### 9. Viva explanation
> This is the core interview API. It creates the session, asks the AI for questions based on the resume and previous answers, scores every answer, adjusts difficulty, and finally builds the report.

**Note:** Scoring formulas live in services/interview/ai_interview_service.py; this file only orchestrates.

---

## File: `backend/app/routers/jobs/__init__.py`

### 1. Purpose
Combines the student job routes and recruiter job routes into two routers for main.py.

### 2. What does it do?
1. Exposes student_router (/api/student) and recruiter_router (/api/recruiter).

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py
   Used by: app/main.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Combines the student job routes and recruiter job routes into two routers for main.py.

### 9. Viva explanation
> Groups the job-related endpoints for students and recruiters.

---

## File: `backend/app/routers/jobs/job_shared_helpers.py`

### 1. Purpose
Helpers shared by student and recruiter job endpoints: job matching, eligibility, payloads, emails and message threads.

### 2. What does it do?
1. semantic_match(): deterministic match score from skills and sentence embeddings.
2. match_with_review(): match score plus an AI explanation (the AI never changes the score).
3. eligibility(): CGPA, branch and graduation-year checks.
4. Builds job/candidate JSON and message threads; emails status updates when SMTP is configured.

### 3. How does it work?
See the steps above.

```
Recruiter opens applicants
   |
   v
semantic_match() per applicant
   |
   v
Optional AI review explains the match
```

### 4. Important functions
```text
   - semantic_match()
       Deterministic semantic match (services/resume_and_jobs/semantic_job_matcher.py).
   - match_with_review()
       Semantic match plus a local-LLM explanation.
   Other helper functions: _email_student, _aware, eligibility, _candidate_payload,
   _assignments_out, _job_payload, message_out, _thread
```

### 5. Important variables
- Module-level constants: STATUS_LABELS, AI_METHODS

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/application_configuration.py,
   app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/interview/ai_interview_service.py, app/services/platform_support/email_sender.py,
   app/services/resume_and_jobs/semantic_job_matcher.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py
```

### 7. Input and output
- **Input:** Job, student profile, resume analysis.
- **Output:** Match results, eligibility issues, payload dictionaries.

### 8. Real project example
When a student applies, the recruiter sees a match score computed here with required/preferred skill coverage.

### 9. Viva explanation
> This file holds shared job logic, mainly the matching between a student's resume and a job.

---

## File: `backend/app/routers/jobs/recruiter_job_routes.py`

### 1. Purpose
Recruiter portal: dashboard, job postings, applicants, AI match, candidate comparison, printable candidate report and candidate search.

### 2. What does it do?
1. Create, edit, publish, close and delete jobs.
2. List applicants sorted by match score.
3. Change application status (shortlist, interview, select, reject) with notifications.
4. AI match explanation; compare 2-4 candidates side by side; candidate report.
5. Search students who share their profile, filtered by skill, branch, CGPA, year and score.

### 3. How does it work?
Recruiters can only access their own jobs and their applicants (_own_job/_own_application).

```
Recruiter posts job
   |
   v
Students apply
   |
   v
Applicants ranked by match
   |
   v
Recruiter shortlists/selects
```

### 4. Important functions
```text
   - compare()
       Side-by-side view of 2-4 applicants to one of this recruiter's jobs (advisory).
   - candidate_report()
       Everything a recruiter may see about one applicant to one of their jobs, for the
       printable report page.
   Other helper functions: _own_job, _own_application, recruiter_dashboard, list_jobs,
   _apply_job_fields, create_job, get_job, update_job, job_action, delete_job, job_applications,
   update_status, ai_match, _match_breakdown, _recent_interviews, _compare_row,
   search_candidates, candidate_detail
```

**API endpoints in this file:**
```text
   - GET /api/recruiter/dashboard
       recruiter_dashboard() - recruiter
   - GET /api/recruiter/jobs
       list_jobs() - recruiter
   - POST /api/recruiter/jobs
       create_job() - recruiter
   - GET /api/recruiter/jobs/{job_id}
       get_job() - recruiter
   - PUT /api/recruiter/jobs/{job_id}
       update_job() - recruiter
   - POST /api/recruiter/jobs/{job_id}/status/{action}
       job_action() - recruiter
   - DELETE /api/recruiter/jobs/{job_id}
       delete_job() - recruiter
   - GET /api/recruiter/jobs/{job_id}/applications
       job_applications() - recruiter
   - PATCH /api/recruiter/applications/{application_id}/status
       update_status() - recruiter
   - POST /api/recruiter/applications/{application_id}/match
       ai_match() - recruiter
   - POST /api/recruiter/jobs/{job_id}/compare
       compare() - recruiter - Side-by-side view of 2-4 applicants to one of this recruiter's
       jobs (advisory).
   - GET /api/recruiter/applications/{application_id}/report
       candidate_report() - recruiter - Everything a recruiter may see about one applicant to
       one of their jobs, for the printable report page.
   - GET /api/recruiter/candidates
       search_candidates() - recruiter
   - GET /api/recruiter/candidates/{student_id}
       candidate_detail() - recruiter
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/routers/interview_monitoring_routes.py,
   app/routers/jobs/job_shared_helpers.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/student_record_access.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/jobs/__init__.py, app/routers/jobs/recruiter_screening_routes.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Job data, status changes, filters.
- **Output:** Job/applicant JSON, comparisons, reports.

### 8. Real project example
A recruiter compares three applicants' interview scores and match results before shortlisting.

### 9. Viva explanation
> This is the recruiter API: post jobs, see applicants ranked by match score, compare them and update their status.

---

## File: `backend/app/routers/jobs/recruiter_screening_routes.py`

### 1. Purpose
Recruiter bulk tools: AI screening of all applicants, assigning assessments, messaging applicants and CSV export.

### 2. What does it do?
1. Screen up to 25 applicants per request with the AI match review.
2. Assign an assessment to an applicant.
3. Read/send messages on an application.
4. Export applicants as CSV.

### 3. How does it work?
See the steps above.

```
Recruiter clicks 'Screen all'
   |
   v
Match + AI review per applicant
   |
   v
Results saved on applications
```

### 4. Important functions
```text
   - screen_all()
       AI resume screening for every active applicant of a job (up to 25 per request).
   Other helper functions: assign_assessment, recruiter_messages, recruiter_send, _csv,
   export_applicants
```

**API endpoints in this file:**
```text
   - POST /api/recruiter/jobs/{job_id}/screen
       screen_all() - recruiter - AI resume screening for every active applicant of a job (up
       to 25 per request).
   - POST /api/recruiter/applications/{application_id}/assessments
       assign_assessment() - recruiter
   - GET /api/recruiter/applications/{application_id}/messages
       recruiter_messages() - recruiter
   - POST /api/recruiter/applications/{application_id}/messages
       recruiter_send() - recruiter
   - GET /api/recruiter/jobs/{job_id}/export
       export_applicants() - recruiter
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/routers/jobs/job_shared_helpers.py,
   app/routers/jobs/recruiter_job_routes.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/jobs/__init__.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Job/application ids, messages.
- **Output:** Screening results, messages, CSV file.

### 8. Real project example
Before shortlisting, a recruiter screens all applicants at once.

### 9. Viva explanation
> These endpoints help recruiters handle many applicants: bulk AI screening, tests and CSV export.

---

## File: `backend/app/routers/jobs/student_job_routes.py`

### 1. Purpose
Student side of placements: browse and apply to jobs, view and withdraw applications, message recruiters.

### 2. What does it do?
1. Browse published jobs with filters (search, location, type, skill, eligible only).
2. View job details with eligibility.
3. Apply (once per job) and withdraw.
4. Read and send messages.

### 3. How does it work?
See the steps above.

```
Student browses jobs
   |
   v
Applies
   |
   v
Recruiter notified
   |
   v
Status updates appear in Applications
```

### 4. Important functions
```text
   Other helper functions: browse_jobs, job_detail, apply, my_applications, withdraw,
   _student_application, student_messages, student_send
```

**API endpoints in this file:**
```text
   - GET /api/student/jobs
       browse_jobs() - student
   - GET /api/student/jobs/{job_id}
       job_detail() - student
   - POST /api/student/jobs/{job_id}/apply
       apply() - student
   - GET /api/student/applications
       my_applications() - student
   - POST /api/student/applications/{application_id}/withdraw
       withdraw() - student
   - GET /api/student/applications/{application_id}/messages
       student_messages() - student
   - POST /api/student/applications/{application_id}/messages
       student_send() - student
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/routers/jobs/job_shared_helpers.py,
   app/services/platform_support/audit_and_notification_helpers.py
   Used by: app/routers/jobs/__init__.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Filters, cover letter, messages.
- **Output:** Job lists, applications, message threads.

### 8. Real project example
A student applies to 'Backend Developer'; the application appears on the recruiter's job page.

### 9. Viva explanation
> These endpoints let students find jobs they are eligible for and apply.

---

## File: `backend/app/routers/live_voice_interview_routes.py`

### 1. Purpose
The live voice interview: one streamed request per conversational turn. The answer is saved and scored, then the next question is generated and spoken sentence by sentence while it is still being written.

### 2. What does it do?
Real-time voice interview turns (Stage 5, voice mode).

1. POST /api/student/interviews/{id}/turn returns Server-Sent Events (stage, scored, sentence, audio, done).
2. Saves and fast-scores the spoken answer (text from speech-to-text).
3. Streams the next question from the AI and splits it into finished sentences (streamed_reply_sentence_splitter.py).
4. Synthesises each sentence to audio with lip-sync timings (text_to_speech.py) on a separate thread.
5. Uses the helpers of interview_routes.py (question choice, scoring, turn locks, prefetch).

### 3. How does it work?
interview_turn() checks the turn lock and starts _turn_work() in a worker thread. _Speaker collects finished sentences and synthesises them in order, so the model writes the next sentence while the previous one becomes audio. Events are pushed to the browser as they happen.

```
Browser sends answer text
   |
   v
Answer saved and scored
   |
   v
AI streams next question
   |
   v
Sentences synthesised to speech
   |
   v
Audio events played by the avatar
```

### 4. Important functions
```text
   - interview_turn()
       Streams one live interview turn as Server-Sent Events.
   - _turn_work()
       Save + score the answer, write the next question, speak it sentence by sentence.
   Other helper functions: _sse
```

**Classes:**
```text
   - _Speaker
       Collects finished sentences (from the streamed reply) and synthesises them on a
       separate thread, in order, so the next sentence is being written by the model while
       the previous one is turned into audio.
```

**API endpoints in this file:**
```text
   - POST /api/student/interviews/{session_id}/turn
       interview_turn() - student - Live interview turn, streamed (see the event list above).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/application_configuration.py,
   app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/request_validation_schemas.py,
   app/routers/interview_routes.py, app/services/ai_models/language_model_client.py,
   app/services/monitoring/performance_timing.py,
   app/services/platform_support/background_jobs.py,
   app/services/voice/streamed_reply_sentence_splitter.py, app/services/voice/text_to_speech.py
   Used by: app/main.py
```
External packages: fastapi

### 7. Input and output
- **Input:** TurnIn JSON (question id, answer text, TTS options) from LiveVoiceInterview.jsx.
- **Output:** An event stream with scores, sentences and audio (base64 WAV + mouth-shape timeline).

### 8. Real project example
In the live interview room, the student speaks; after transcription this endpoint makes the avatar start speaking the next question about a second later.

### 9. Viva explanation
> For voice interviews we stream each turn: the answer is scored, and the next question is spoken sentence by sentence while the AI is still writing it, which makes the interview feel live.

---

## File: `backend/app/routers/mentor_portal_routes.py`

### 1. Purpose
Mentor portal: assigned students, their progress and reports, feedback, improvement plans with goals, mentoring sessions and alerts.

### 2. What does it do?
1. Dashboard and student list (only assigned students unless view_all_students permission).
2. Student detail: interviews, English sessions, resume, progress, remedies.
3. CSV reports for all students or one student.
4. AI recommendations for a student; feedback and private notes.
5. Improvement plans with goals; scheduled mentoring sessions.
6. Inactivity / missed-task alerts (at most once a week per student and type).

### 3. How does it work?
Every student-specific route first calls ensure_mentor_access(). Plan goals track progress automatically through rewards_and_badges.py.

```
Mentor opens dashboard
   |
   v
Sees struggling students
   |
   v
Opens student detail
   |
   v
Adds plan/goal or feedback
```

### 4. Important functions
```text
   - run_alerts()
       Inactivity and missed-task alerts, at most once a week per student and alert type.
   - assign_remedy()
       Turn a suggested remedy into a tracked task in the student's 'Recommended remedies'
       plan.
   - student_report()
       Individual progress report (CSV): summary followed by every attempt with change over
       the previous one.
   Other helper functions: _student_ids, _assigned_ids, _plans_with_progress, _aware,
   last_practice, _recently_alerted, dashboard, students, student_detail, _report_rows, _csv,
   all_students_report, student_interview, student_english, ai_recommendations, add_feedback,
   delete_feedback, _own_plan, create_plan, update_plan, delete_plan, add_goal, update_goal,
   set_goal_status, delete_goal, list_sessions, create_session, update_session, delete_session
```

**API endpoints in this file:**
```text
   - GET /api/mentor/dashboard
       dashboard() - mentor
   - GET /api/mentor/students
       students() - mentor
   - GET /api/mentor/students/{student_id}
       student_detail() - mentor
   - POST /api/mentor/students/{student_id}/remedies/assign
       assign_remedy() - mentor - Turn a suggested remedy into a tracked task in the
       student's 'Recommended remedies' plan.
   - GET /api/mentor/report
       all_students_report() - mentor
   - GET /api/mentor/students/{student_id}/report
       student_report() - mentor - Individual progress report (CSV): summary followed by
       every attempt with change over the previous one.
   - GET /api/mentor/students/{student_id}/interviews/{session_id}
       student_interview() - mentor
   - GET /api/mentor/students/{student_id}/english/{session_id}
       student_english() - mentor
   - POST /api/mentor/students/{student_id}/recommendations
       ai_recommendations() - mentor
   - POST /api/mentor/students/{student_id}/feedback
       add_feedback() - mentor
   - DELETE /api/mentor/feedback/{feedback_id}
       delete_feedback() - mentor
   - POST /api/mentor/students/{student_id}/plans
       create_plan() - mentor
   - PATCH /api/mentor/plans/{plan_id}
       update_plan() - mentor
   - DELETE /api/mentor/plans/{plan_id}
       delete_plan() - mentor
   - POST /api/mentor/plans/{plan_id}/goals
       add_goal() - mentor
   - PUT /api/mentor/goals/{goal_id}
       update_goal() - mentor
   - POST /api/mentor/goals/{goal_id}/status
       set_goal_status() - mentor
   - DELETE /api/mentor/goals/{goal_id}
       delete_goal() - mentor
   - GET /api/mentor/sessions
       list_sessions() - mentor
   - POST /api/mentor/sessions
       create_session() - mentor
   - PATCH /api/mentor/sessions/{session_id}
       update_session() - mentor
   - DELETE /api/mentor/sessions/{session_id}
       delete_session() - mentor
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/main.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Student ids, feedback text, plan/goal/session data.
- **Output:** Student overviews, reports (JSON/CSV), plans.

### 8. Real project example
When a student's interview score drops, the mentor gets an alert and assigns a practice goal.

### 9. Viva explanation
> The mentor portal lets mentors follow their assigned students, give feedback and set improvement goals that are tracked automatically.

---

## File: `backend/app/routers/profile_and_notification_routes.py`

### 1. Purpose
Endpoints every signed-in role uses: view/edit own profile, personal settings, notifications and the live notification stream.

### 2. What does it do?
1. GET/PUT /api/profile - read and update the role-specific profile.
2. GET/PUT /api/settings - speech language, voice and other preferences.
3. List, mark read, mark all read and delete notifications.
4. GET /api/notifications/stream - Server-Sent Events that tell the browser when notifications change.

### 3. How does it work?
The stream sends only a small signal; the browser then re-fetches /api/notifications, so access checks stay in one place. Signals come from live_notification_events.py.

```
Something creates a notification (notify())
   |
   v
After commit a signal is published
   |
   v
Open stream sends 'notification' event
   |
   v
Browser re-fetches the list
```

### 4. Important functions
```text
   - update_profile()
       Validates and saves profile fields for the user's role.
   - notification_stream()
       Keeps an SSE connection open and forwards 'notification'/'sync' signals.
   Other helper functions: get_profile, _prefs, get_preferences, update_preferences,
   list_notifications, mark_read, mark_all_read, delete_notification, _sse
```

**Classes:**
```text
   - PreferencesIn
```

**API endpoints in this file:**
```text
   - GET /api/profile
       get_profile() - any signed-in user
   - PUT /api/profile
       update_profile() - any signed-in user
   - GET /api/settings
       get_preferences() - any signed-in user
   - PUT /api/settings
       update_preferences() - any signed-in user
   - GET /api/notifications
       list_notifications() - any signed-in user
   - POST /api/notifications/{notification_id}/read
       mark_read() - any signed-in user
   - POST /api/notifications/read-all
       mark_all_read() - any signed-in user
   - DELETE /api/notifications/{notification_id}
       delete_notification() - any signed-in user
   - GET /api/notifications/stream
       notification_stream() - public - Server-Sent Events: `ready` once, then `notification`
       (a new one arrived) or `sync` (read/deleted elsewhere) whenever the signed-in user's
       notifications change.
```

### 5. Important variables
- Module-level constants: SPEECH_LANGS

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/application_configuration.py,
   app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
   app/request_validation_schemas.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/live_notification_events.py
   Used by: app/main.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** Profile/settings JSON, notification ids, the session cookie.
- **Output:** Profile JSON, notification lists, an SSE stream.

### 8. Real project example
When a recruiter shortlists a student, the student's bell icon updates instantly through this stream.

### 9. Viva explanation
> This file serves the profile page, user settings and notifications, including a live stream so new notifications appear without refreshing.

---

## File: `backend/app/routers/skill_assessment_routes.py`

### 1. Purpose
Skill tests (aptitude, technical MCQ and coding). Students take them; recruiters and admins create and manage them.

### 2. What does it do?
Coding and problem-solving assessment.

1. Students list available tests, start a timed attempt and submit answers.
2. MCQs are graded instantly on the server.
3. Coding answers are reviewed by the AI (code is not executed); if AI is down they stay 'pending'.
4. Managers create, edit, delete tests, see results and ask the AI to draft MCQs.
5. After grading: progress record, rewards, assignment completion and recruiter notification.

### 3. How does it work?
_grade() marks each MCQ against the stored answer and calls ai.evaluate_code() for coding questions. _finalize() records the result once a score exists.

```
Student starts test
   |
   v
Submits answers
   |
   v
MCQ graded / code reviewed by AI
   |
   v
Result + rewards saved
```

### 4. Important functions
```text
   - submit()
       Grade a submitted attempt.
   - _grade()
       MCQ marking + AI review of coding answers.
   - generate()
       AI-drafted questions for the author to review (nothing saved automatically).
   Other helper functions: _aware, qtype, _visible_to_student, available, my_results,
   result_detail, start, _grade_coding, _finalize, _review, evaluate_pending, _check_owner,
   _validate_job, _apply, list_managed, create, update, delete, results
```

**API endpoints in this file:**
```text
   - GET /api/student/assessments
       available() - student
   - GET /api/student/assessments/results
       my_results() - student
   - GET /api/student/assessments/results/{result_id}
       result_detail() - student
   - POST /api/student/assessments/{assessment_id}/start
       start() - student
   - POST /api/student/assessments/results/{result_id}/submit
       submit() - student
   - POST /api/student/assessments/results/{result_id}/evaluate
       evaluate_pending() - student
   - GET /api/assessments
       list_managed() - recruiter or admin
   - POST /api/assessments
       create() - recruiter or admin
   - PUT /api/assessments/{assessment_id}
       update() - recruiter or admin
   - DELETE /api/assessments/{assessment_id}
       delete() - recruiter or admin
   - GET /api/assessments/{assessment_id}/results
       results() - recruiter or admin
   - POST /api/assessments/generate
       generate() - recruiter or admin - Returns AI-drafted questions for review; nothing is
       saved until the author creates the assessment.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/request_validation_schemas.py, app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/main.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Assessment definitions and student answers.
- **Output:** Results with score, marks and per-question review.

### 8. Real project example
A recruiter assigns a coding test to an applicant; the applicant's result appears in the recruiter view.

### 9. Viva explanation
> This file handles tests. Multiple-choice answers are checked automatically and coding answers are reviewed by the AI; no score is invented if the AI is unavailable.

---

## File: `backend/app/routers/student_portal_routes.py`

### 1. Purpose
Student portal endpoints: dashboard, progress, performance report, history, challenges, placement drives, resume upload and AI analysis, rewards, leaderboard and mentoring.

### 2. What does it do?
Resume upload/analysis (Stage 2) and the student dashboard (Stage 11).

1. Dashboard and progress data (readiness score, trends, recent activity) from student_performance_insights.py.
2. Uploads resumes (PDF/DOCX), extracts text, runs AI resume analysis and keeps a version history.
3. Lets the student correct the AI analysis, copy extracted skills into the profile, set the current resume.
4. AI recommendations and role suggestions; full performance report; practice history.
5. Placement drives (register/unregister), challenges, rewards, leaderboard and mentoring view.
6. Resume view/download for the student and for permitted mentors/recruiters.

### 3. How does it work?
upload_resume() checks size/type, saves the file under uploads/, extracts text with resume_text_extractor.py and calls ai.analyze_resume(); the result (skills, education, projects, completeness score) is stored on the Resume document. Other routes aggregate data with the insights and rewards services.

```
Student uploads resume
   |
   v
Text extracted from PDF/DOCX
   |
   v
AI extracts skills/projects (validated against text)
   |
   v
Analysis stored on Resume
   |
   v
Dashboard and interviews use the analysis
```

### 4. Important functions
```text
   - upload_resume()
       POST /api/student/resumes - save file, extract text, run AI analysis.
   - _run_analysis()
       Calls the AI resume analyser and stores status/result/error on the Resume.
   - correct_analysis()
       PATCH .../analysis - student fixes extracted details; completeness recalculated.
   - dashboard()
       GET /api/student/dashboard - summary numbers, readiness, challenges, upcoming events.
   - performance_report()
       GET /api/student/report - scores, strengths, weaknesses, mistakes to review.
   Other helper functions: progress, recommendations, role_recommendations, history,
   challenges_for, challenges, _drive_eligible, drives, register_drive, unregister_drive,
   list_resumes, _prune_resume_history, reanalyze, apply_skills, make_current, delete_resume,
   view_resume, download_resume, rewards, leaderboard, mentoring, complete_goal_endpoint
```

**API endpoints in this file:**
```text
   - GET /api/student/dashboard
       dashboard() - student
   - GET /api/student/progress
       progress() - student
   - POST /api/student/recommendations
       recommendations() - student
   - POST /api/student/role-recommendations
       role_recommendations() - student
   - GET /api/student/report
       performance_report() - student - Scores, strengths, weaknesses and specific mistakes
       to review.
   - GET /api/student/history
       history() - student
   - GET /api/student/challenges
       challenges() - student
   - GET /api/student/drives
       drives() - student
   - POST /api/student/drives/{drive_id}/register
       register_drive() - student
   - DELETE /api/student/drives/{drive_id}/register
       unregister_drive() - student
   - GET /api/student/resumes
       list_resumes() - student
   - POST /api/student/resumes
       upload_resume() - student
   - POST /api/student/resumes/{resume_id}/analyze
       reanalyze() - student
   - PATCH /api/student/resumes/{resume_id}/analysis
       correct_analysis() - student - Let the student fix details the AI extracted
       incorrectly.
   - POST /api/student/resumes/{resume_id}/apply-skills
       apply_skills() - student
   - POST /api/student/resumes/{resume_id}/make-current
       make_current() - student
   - DELETE /api/student/resumes/{resume_id}
       delete_resume() - student
   - GET /api/resumes/{resume_id}
       view_resume() - any signed-in user
   - GET /api/resumes/{resume_id}/download
       download_resume() - any signed-in user
   - GET /api/student/rewards
       rewards() - student
   - GET /api/student/leaderboard
       leaderboard() - student
   - GET /api/student/mentoring
       mentoring() - student
   - POST /api/student/goals/{goal_id}/complete
       complete_goal_endpoint() - student
```

### 5. Important variables
- Module-level constants: RESUME_HISTORY

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/application_configuration.py,
   app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/request_validation_schemas.py,
   app/services/interview/ai_interview_service.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/platform_support/student_record_access.py,
   app/services/resume_and_jobs/resume_text_extractor.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/main.py
   Tested by: tests/test_account_security.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Uploaded resume files, JSON bodies, the session cookie.
- **Output:** Dashboard/progress/report JSON, resume analysis JSON, file downloads.

### 8. Real project example
Before an interview, the student uploads a resume; later the interview questions mention the projects this analysis found.

### 9. Viva explanation
> This is the student portal API. Its main feature is resume upload: we extract the text, let the AI pull out skills and projects, check them against the resume text, and show the result on the dashboard.

---

## File: `backend/app/routers/voice_speech_routes.py`

### 1. Purpose
Voice support endpoints: text-to-speech for the avatar and speech-to-text for spoken answers.

### 2. What does it do?
1. GET /api/voice/status - whether TTS/STT engines are available.
2. POST /api/voice/speak and /speak/stream - turn text into speech with a mouth-shape timeline.
3. POST /api/voice/warmup - load models while the candidate is on the setup screen.
4. POST .../interviews/{id}/transcribe and .../english/{id}/transcribe - turn recorded audio into text.
5. Rate-limits each user and rejects audio over 12 MB.

### 3. How does it work?
Audio is processed in memory and never stored. The transcribed text is then submitted through the normal interview/English endpoints, so scoring is the same as for typed answers.

```
Student records answer
   |
   v
Audio uploaded to /transcribe
   |
   v
Whisper converts speech to text
   |
   v
Text shown and submitted as the answer
```

### 4. Important functions
```text
   - transcribe_answer()
       Transcribe one recorded answer (or a partial segment / live caption).
   - speak()
       Synthesise speech for the interviewer avatar.
   - speak_stream()
       Same as /voice/speak, but one NDJSON line per sentence as soon as it is synthesised,
       so playback of a long text (greeting, closing remarks) starts after the first sentence
       instead of after the whole text.
   - warmup()
       Called from the interview setup screen: loads the language model (and voice models)
       while the candidate reads the disclosure and tests the camera, so the first question
       isn't delayed by a 30-70 s model load.
   - transcribe_english()
       Spoken English practice: local transcription of one reply (the text is then sent as a
       normal message).
   Other helper functions: _rate_limit, voice_status, _transcribe
```

**Classes:**
```text
   - SpeakIn
```

**API endpoints in this file:**
```text
   - GET /api/voice/status
       voice_status() - any signed-in user
   - POST /api/voice/speak
       speak() - any signed-in user
   - POST /api/voice/speak/stream
       speak_stream() - any signed-in user - Same as /voice/speak, but one NDJSON line per
       sentence as soon as it is synthesised, so playback of a long text (greeting, closing
       remarks) starts after the first sentence instead of after the whole text.
   - POST /api/voice/warmup
       warmup() - any signed-in user - Called from the interview setup screen: loads the
       language model (and voice models) while the candidate reads the disclosure and tests
       the camera, so the first question isn't delayed by a 30-70 s model load.
   - POST /api/student/interviews/{session_id}/transcribe
       transcribe_answer() - student - partial=true: one speech segment while the candidate
       is still talking (shown live and joined at the end, so only the last segment has to be
       transcribed after they stop). live=true: a live caption of the unfinished...
   - POST /api/student/english/{session_id}/transcribe
       transcribe_english() - student - Spoken English practice: local transcription of one
       reply (the text is then sent as a normal message).
```

### 5. Important variables
- Module-level constants: MAX_AUDIO_BYTES

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/authentication_dependencies.py,
   app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/ai_models/language_model_client.py,
   app/services/monitoring/performance_timing.py, app/services/platform_support/rate_limiter.py,
   app/services/voice/speech_to_text.py, app/services/voice/text_to_speech.py
   Used by: app/main.py
   Tested by: tests/test_voice.py
```
External packages: fastapi, pydantic

### 7. Input and output
- **Input:** Text to speak; WAV audio uploads.
- **Output:** Audio (base64 WAV + visemes) or transcript JSON.

### 8. Real project example
In a voice interview, the student's spoken answer is sent here, transcribed by Whisper and shown for review before submitting.

### 9. Viva explanation
> This file connects voice to our system: Kokoro turns questions into speech for the avatar, and Whisper turns the student's spoken answer into text.

---

# Backend - AI model clients

## File: `backend/app/services/ai_models/__init__.py`

### 1. Purpose
Marks the services/ai_models folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the language-model, embedding and classifier modules so they can be imported as app.services.ai_models.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/ai_models folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the language-model, embedding and classifier services.

---

## File: `backend/app/services/ai_models/ai_structured_call_base.py`

### 1. Purpose
Shared plumbing for all AI features: the single gateway `_structured_call` that checks availability and limits, calls the model, validates the JSON and logs usage.

### 2. What does it do?
Safe, validated, logged access to the language model.

1. Refuses cleanly (AIUnavailable) when AI is disabled, Ollama is not running or the model is missing.
2. Enforces a per-user daily AI usage limit.
3. Validates the model's JSON against a Pydantic schema and retries once if invalid.
4. Detects when the model copied the prompt's instructions instead of real content and retries.
5. Logs every attempt to ai_usage_logs (status, latency, tokens - never content).
6. fence(): wraps untrusted text (resume, answer) in tags as a prompt-injection guard.

### 3. How does it work?
See the steps above.

```
Check admin switch + daily limit
   |
   v
Commit pending DB work
   |
   v
Call model
   |
   v
Validate JSON (retry once)
   |
   v
Log usage
   |
   v
Return object
```

### 4. Important functions
```text
   - _structured_call()
       The one function every AI feature uses to call the model.
   - ai_status()
       Whether AI can be used now (shown in the UI, decides AI vs question bank).
   - fence()
       Wrap untrusted text in <tag>...</tag> so the model treats it as data.
   - echoed_placeholders()
       Field paths whose values look like the prompt's template copied back instead of real
       content.
   Other helper functions: _norm, _strings, _log, _strictness, _clamp, _clean_list
```

**Classes:**
```text
   - AIUnavailable
       Raised when a genuine AI result cannot be produced.
```

### 5. Important variables
- Module-level constants: UNTRUSTED_NOTE, ECHO_RETRY_NOTE, STRICTNESS_GUIDE

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/services/ai_models/ai_task_model_router.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/monitoring/performance_timing.py,
   app/services/platform_support/audit_and_notification_helpers.py
   Used by: app/services/english/ai_english_conversation.py,
   app/services/interview/ai_interview_service.py,
   app/services/resume_and_jobs/ai_career_and_assessment_tasks.py,
   app/services/resume_and_jobs/ai_resume_analyzer.py
   Tested by: tests/test_echoed_placeholders.py
```
External packages: pydantic

### 7. Input and output
- **Input:** Feature name, prompts, output schema.
- **Output:** A validated Pydantic object, or AIUnavailable.

### 8. Real project example
score_answer() calls _structured_call(feature='answer_scoring', output_model=QuickScore).

### 9. Viva explanation
> All our AI calls go through one gateway function that checks limits, forces a JSON format, validates it and logs usage, so the AI output is always in a predictable structure.

---

## File: `backend/app/services/ai_models/ai_task_model_router.py`

### 1. Purpose
Decides which model name handles which AI task (fast tier for chat, strong tier for scoring and reports, default otherwise).

### 2. What does it do?
1. Maps each feature name (e.g. 'answer_scoring') to a tier.
2. Returns the configured model for that tier.
3. Describes the routing table for the admin AI page.

### 3. How does it work?
See the steps above.

```
Feature name
   |
   v
Tier
   |
   v
Model from settings
```

### 4. Important functions
```text
   - configured_model()
       The model named in the settings for this feature (not checked for availability).
   - describe()
       Routing table for the admin AI page: tier -> model, and the features in each tier.
   Other helper functions: tier_of, _models
```

### 5. Important variables
- Module-level constants: FAST_TASKS, STRONG_TASKS

### 6. Connected files
```text
   Uses: app/application_configuration.py
   Used by: app/main.py, app/services/ai_models/ai_structured_call_base.py
   Tested by: tests/test_gemini.py, tests/test_health_and_routing.py
```

### 7. Input and output
- **Input:** Feature name.
- **Output:** Model name.

### 8. Real project example
English chat can use a smaller, faster model while answer scoring uses the strong model.

### 9. Viva explanation
> A small router that lets different AI tasks use different models, configured in settings.

---

## File: `backend/app/services/ai_models/gemini_api_client.py`

### 1. Purpose
Client for the Google Gemini API, used when LOCAL_AI_PROVIDER=gemini. Same contract as the Ollama path, so the rest of the app does not know which model answered.

### 2. What does it do?
1. Sends JSON-schema requests to Gemini over HTTPS (streaming supported).
2. Retries on rate limits (429) and server errors; switches to backup models when one is overloaded.
3. Chooses the newest stable Flash model if none is configured.
4. Can transcribe audio with Gemini when Whisper is not installed.

### 3. How does it work?
See the steps above.

```
chat_json() in language_model_client
   |
   v
Gemini selected
   |
   v
Request + retries/backup models
   |
   v
JSON returned
```

### 4. Important functions
```text
   - runtime_status()
       {"provider", "model", "running", "model_ready", "error", "installed"} - cached for a
       few minutes.
   - chat_json()
       Ask Gemini for JSON matching `schema`.
   - candidate_models()
       Models to try in order: the chosen one, then GEMINI_BACKUP_MODELS this key can use.
   - warmup()
       Check the key and resolve the model ahead of time, and open the TLS connection (no
       model to load).
   - transcribe()
       Speech-to-text with Gemini (STT_ENGINE=gemini, for hosts without the Whisper
       packages).
   Other helper functions: _http, _headers, _short, _version, _best_flash, _api_error,
   _thinking_config, _initial_form, _body, _is_json, _mark_busy, _stream_one
```

**Classes:**
```text
   - _Overloaded
       This model is overloaded or slow to start; the caller moves on to the next candidate
       model.
```

### 5. Important variables
- Module-level constants: TRANSCRIBE_SYSTEM

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/ai_models/language_model_client.py
   Used by: app/services/ai_models/language_model_client.py, app/services/voice/speech_to_text.py
   Tested by: tests/conftest.py, tests/test_deploy.py, tests/test_gemini.py,
   tests_perf/bench_prompts.py
```
External packages: httpx

### 7. Input and output
- **Input:** Prompts, JSON schema, API key from .env.
- **Output:** LLMResult or LLMError (same as language_model_client).

### 8. Real project example
On the hosted demo (no GPU) interview questions are generated by Gemini through this file.

### 9. Viva explanation
> An alternative cloud AI provider. If configured, our AI calls go to Google Gemini instead of the local model, with retries and backup models.

---

## File: `backend/app/services/ai_models/language_model_client.py`

### 1. Purpose
Talks to the language model: a local Ollama model (qwen3:4b), or Google Gemini through gemini_api_client.py when LOCAL_AI_PROVIDER=gemini (as in .env.example). If Gemini fails, it falls back to Ollama (AI_FALLBACK_TO_OLLAMA).

### 2. What does it do?
The low-level LLM client every AI feature finally goes through.

1. Checks whether Ollama is running and the model is downloaded (cached briefly).
2. Sends a chat request with a JSON schema so the model must reply with matching JSON.
3. Limits how many generations run at once; interactive requests go before background ones.
4. Applies timeouts, input/output limits and strips the model's hidden 'thinking' text.
5. Warms up (loads) the model at startup so the first question is not slow.

### 3. How does it work?
chat_json() picks the provider, waits for a slot in PriorityGate, posts to Ollama's /api/chat (optionally streaming tokens to on_delta) and returns an LLMResult. Errors become LLMError with a user-safe message.

```
Feature calls _structured_call()
   |
   v
chat_json() waits for a free slot
   |
   v
Request sent to Ollama/Gemini
   |
   v
JSON text returned
```

### 4. Important functions
```text
   - chat_json()
       Ask the model for JSON matching a schema; raises LLMError on failure.
   - runtime_status()
       Is the provider running and the model ready?
   - warmup()
       Load the model into memory ahead of the first request.
   - interactive_hold()
       with interactive_hold(): ... - a candidate is waiting on this work; background
       generations pause.
   Other helper functions: _base_url, _http, _gate, _model_matches, provider, _ollama_status,
   _strip_think, _http_error, _load_options, _options, _switch_model, _chat_ollama
```

**Classes:**
```text
   - LLMError
       The local model could not produce a response.
   - LLMResult
   - PriorityGate
       At most `slots` generations at a time.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/ai_models/gemini_api_client.py
   Used by: app/main.py, app/routers/live_voice_interview_routes.py,
   app/routers/voice_speech_routes.py, app/services/ai_models/ai_structured_call_base.py,
   app/services/ai_models/gemini_api_client.py, app/services/interview/ai_interview_service.py,
   app/services/voice/speech_to_text.py
   Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/conftest.py,
   tests/test_deploy.py, tests/test_echoed_placeholders.py, tests/test_english_companion.py,
   tests/test_english_profile.py, tests/test_english_vocab.py, tests/test_gemini.py,
   tests/test_health_and_routing.py, tests/test_interviewers.py,
   tests/test_latency_and_monitoring.py, tests/test_local_ai.py, tests_integration/conftest.py,
   tests_integration/test_real_features.py, tests_perf/bench_interview_latency.py,
   tests_perf/bench_models.py, tests_perf/bench_prompts.py
```
External packages: httpx

### 7. Input and output
- **Input:** System prompt, user prompt, JSON schema, priority.
- **Output:** LLMResult (text, token counts, timings).

### 8. Real project example
Every interview question and answer score is produced by a chat_json() call from this file.

### 9. Viva explanation
> This is our LLM client. It sends prompts to the local Ollama model (or Gemini) and forces the reply to be JSON in a fixed format, with timeouts and a priority queue.

**Note:** Prompt and response text are never logged because they contain resumes and answers.

---

## File: `backend/app/services/ai_models/question_type_classifier.py`

### 1. Purpose
Runtime part of the project's own machine-learning model: predicts an interview question's type and difficulty with a scikit-learn model trained by backend/ml/train_question_classifier.py.

### 2. What does it do?
1. Loads the saved joblib model once.
2. predict(text) returns predicted type and difficulty.
3. Returns None safely if the model file is missing.

### 3. How does it work?
The prediction is stored in each AI question's meta as a cross-check for admins; it never changes the interview flow.

```
AI writes a question
   |
   v
Classifier predicts type/difficulty
   |
   v
Stored in InterviewQuestion.meta
```

### 4. Important functions
```text
   Other helper functions: _load, status, predict
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py
   Used by: app/routers/interview_routes.py
   Tested by: tests/test_local_ai.py
```
External packages: joblib

### 7. Input and output
- **Input:** Question text.
- **Output:** Predicted type/difficulty (or None).

### 8. Real project example
If the AI labels a question 'easy' but the classifier says 'hard', an admin can spot it.

### 9. Viva explanation
> This is our own trained ML classifier. It double-checks the type and difficulty of AI-generated questions.

---

## File: `backend/app/services/ai_models/sentence_embedding_model.py`

### 1. Purpose
Loads a small local sentence-embedding model (all-MiniLM-L6-v2, Sentence Transformers) that turns text into vectors for meaning comparison.

### 2. What does it do?
1. Loads the model once per process (downloaded once, then offline on CPU).
2. embed(texts) returns unit-length vectors; short texts are cached.
3. Reports status and validates the vectors.

### 3. How does it work?
See the steps above.

```
Text
   |
   v
Embedding model
   |
   v
Vector
   |
   v
Similarity used by matching / off-topic checks
```

### 4. Important functions
```text
   - validate()
       Unit-normalised float array of shape (n, dim), or EmbeddingUnavailable if the output
       is unusable.
   - embed()
       Unit-length embeddings, shape (len(texts), dim).
   Other helper functions: _installed, status, _get_model, warmup, _check, _embed_one
```

**Classes:**
```text
   - EmbeddingUnavailable
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py
   Used by: app/main.py, app/services/ai_models/ai_structured_call_base.py,
   app/services/english/ai_english_conversation.py,
   app/services/interview/ai_interview_service.py,
   app/services/interview/interview_intelligence_rules.py,
   app/services/resume_and_jobs/semantic_job_matcher.py
   Tested by: eval/run_eval.py, tests/conftest.py, tests/test_local_ai.py,
   tests_integration/conftest.py, tests_perf/bench_interview_latency.py,
   tests_perf/bench_models.py, tests_perf/bench_prompts.py
```
External packages: numpy, sentence_transformers

### 7. Input and output
- **Input:** List of texts.
- **Output:** Array of vectors (cosine similarity = dot product).

### 8. Real project example
Used to check whether an answer is about the question at all and to compare resumes with jobs.

### 9. Viva explanation
> This model converts sentences into numbers that capture meaning, so we can measure how similar a resume is to a job or an answer to a question.

---

# Backend - interview services

## File: `backend/app/services/interview/__init__.py`

### 1. Purpose
Marks the services/interview folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the AI interview, scoring and report modules so they can be imported as app.services.interview.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/interview folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the AI interview, scoring and report services.

---

## File: `backend/app/services/interview/ai_interview_service.py`

### 1. Purpose
The AI interview logic: writes the next interview question, scores answers, writes feedback and the final report. It also re-exports the other AI features so callers can use `ai.<name>`.

### 2. What does it do?
AI question generation, answer evaluation, score calculation and report generation (Stages 4, 6-10).

1. next_interview_question(): builds a prompt from role, category, resume facts, previous answers, coverage and difficulty, and gets a JSON question from the model (streaming supported).
2. score_answer(): fast step - the model scores relevance, correctness, completeness, clarity and communication from 0 to 10.
3. apply_answer_rules(): fixed rules cap scores for off-topic, empty, very short, copied or wrong answers.
4. weighted_score(): turns the criteria into a 0-100 score using the rubric weights (completeness blended in at 20% when the rubric does not include it).
5. next_difficulty(): adaptive rule - score >= 75 goes up a level, < 45 goes down (per interviewer).
6. answer_feedback(): slow step - strengths, missing concepts, improvements and a sample answer.
7. interview_report(): summary, strengths, weaknesses, suggestions and closing remarks.

### 3. How does it work?
Each function writes a prompt, calls _structured_call() with a Pydantic schema (NextQuestion, QuickScore, AnswerFeedback, InterviewReport) and then post-processes the result with deterministic rules, so the final numbers do not depend only on the model.

```
Prompt built from resume + history
   |
   v
Model returns JSON
   |
   v
Rules validate/cap scores
   |
   v
Weighted 0-100 score
   |
   v
Next difficulty chosen
```

### 4. Important functions
```text
   - next_interview_question()
       Generate the next adaptive question as JSON.
   - score_answer()
       Fast 0-10 criterion scores + rule caps + 0-100 weighted score.
   - apply_answer_rules()
       Deterministic caps for off-topic/short/non-answers and mostly-wrong answers.
   - weighted_score()
       Rubric-weighted average of the criteria, scaled to 0-100.
   - next_difficulty()
       Move difficulty up/down based on the last score.
   - answer_feedback()
       Detailed tips and sample answer (runs in the background).
   - evaluate_answer()
       Score + feedback in one call (used by Retry evaluation).
   - interview_report()
       Final AI report for the whole interview.
   - strip_greeting()
       The interviewer's greeting is spoken separately; drop any greeting/self-introduction
       the model adds.
   Other helper functions: _transcript, question_is_open, answer_similarity, _feedback_voice
```

**Classes:**
```text
   - NextQuestion
   - QuickScore
   - AnswerFeedback
   - InterviewReport
```

### 5. Important variables
- Module-level constants: DIFFICULTY_GUIDE, RESPONSE_MODES, RECENT_TURNS, ANSWER_CHARS_IN_PROMPT, OFF_TOPIC_SIMILARITY,    SIMILARITY_CHECKED_TYPES, OPEN_QUESTION_TEMPLATES, OPEN_QUESTION_SIMILARITY, CRITERIA,    MISSING_POINT_CAP, WRONG_ANSWER_CAP, EVALUATOR_SYSTEM, SCORE_ANCHORS, COMPLETENESS_SHARE,    MISSING_POINT_PROMPT

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/__init__.py, app/services/ai_models/ai_structured_call_base.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/english/ai_english_conversation.py,
   app/services/interview/interview_intelligence_rules.py,
   app/services/interview/interviewer_personalities.py,
   app/services/interview/score_band_labels.py,
   app/services/resume_and_jobs/ai_career_and_assessment_tasks.py,
   app/services/resume_and_jobs/ai_resume_analyzer.py
   Used by: app/routers/admin/admin_analytics_routes.py,
   app/routers/admin/admin_operations_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_routes.py,
   app/routers/jobs/job_shared_helpers.py, app/routers/mentor_portal_routes.py,
   app/routers/skill_assessment_routes.py, app/routers/student_portal_routes.py,
   app/services/interview/interview_report_metrics.py,
   app/services/voice/streamed_reply_sentence_splitter.py
   Tested by: eval/calibrate_scoring.py, tests/conftest.py, tests/test_ai_tolerance.py,
   tests/test_echoed_placeholders.py, tests/test_english_avatar.py,
   tests/test_english_companion.py, tests/test_features.py, tests/test_interview_engine.py,
   tests/test_interviewers.py, tests/test_latency_and_monitoring.py, tests/test_local_ai.py,
   tests/test_scoring_calibration.py, tests_integration/test_real_features.py,
   tests_integration/test_real_models.py, tests_perf/bench_interview_latency.py,
   tests_perf/bench_models.py, tests_perf/bench_prompts.py
```
External packages: pydantic

### 7. Input and output
- **Input:** Job role, question, answer, rubric, interview history, resume summary.
- **Output:** Question JSON; score dictionaries; feedback; the report.

### 8. Real project example
For the answer 'I don't know', apply_answer_rules caps every criterion at 1/10, so the score is very low regardless of what the model said.

### 9. Viva explanation
> This is the brain of the interview. The AI writes questions and gives 0-10 scores per criterion, then our own rules check the scores and we compute a weighted 0-100 score and the next difficulty.

**Note:** Scores never depend on the interviewer personality; only the question style and difficulty steps do.

---

## File: `backend/app/services/interview/interview_intelligence_rules.py`

### 1. Purpose
Interview logic that does not need the AI: which resume facts a question may use, what the last answer was missing, which topics are covered, duplicate detection, question validation and fallback questions.

### 2. What does it do?
1. candidate_context(): resume facts (projects, internships, skills) allowed in questions.
2. answer_signals(): detects vague 'we did it', unmeasured claims, uncertainty, a request to repeat, etc.
3. coverage() and stage(): what has been asked and what to explore next.
4. is_duplicate(): rejects repeated questions (words, topic and optional embedding similarity).
5. validate_question() and fallback_question(): reject bad questions and provide resume-based templates.

### 3. How does it work?
All rules are plain Python (regular expressions, word sets, similarity), so they are fast and testable.

```
Last answer
   |
   v
answer_signals() finds what is missing
   |
   v
Prompt asks a matching follow-up
   |
   v
Generated question checked by is_duplicate()/validate_question()
```

### 4. Important functions
```text
   - context_block()
       Resume facts for the prompt.
   - derive_topic()
       Which resume item a question is about (project, internship or skill), worked out in
       code so the model does not have to generate it.
   - answer_signals()
       What is missing or notable in the last answer, each with the follow-up that would help
       most.
   - history_block()
       Last `full_last` exchanges in full, earlier ones as one line each (topic, aspect,
       gist).
   - coverage()
       Topics already explored and the most useful ones still open (guidance, not a script).
   - canonical()
       Content stems after removing the request wording: 'Tell me about your hospital
       management project' and 'Describe the project you built for hospital management' both
       become {hospi, manag}.
   - is_duplicate()
       (duplicate?, reason code).
   - fallback_question()
       A resume-grounded question that is not a duplicate.
   Other helper functions: _short, _without_name, candidate_context, _keywords, norm_topic,
   covered_pairs, stage, _norm, lexical_repeat, _jaccard, embedding_similarity, strip_robotic,
   validate_question
```

### 5. Important variables
- Module-level constants: ASPECTS, FOLLOWUP_KINDS, SEMANTIC_DUPLICATE, CONCEPT_SIMILARITY, PROJECT_TEMPLATES,    GENERAL_TEMPLATES

### 6. Connected files
```text
   Uses: app/services/ai_models/sentence_embedding_model.py
   Used by: app/routers/interview_routes.py, app/services/interview/ai_interview_service.py
   Tested by: tests/test_interview_engine.py
```

### 7. Input and output
- **Input:** Resume analysis, interview history, last answer, generated question.
- **Output:** Context blocks, signals, coverage hints, duplicate/validation results, fallback questions.

### 8. Real project example
If a student says 'we improved performance' without numbers, a signal asks the AI for a follow-up about how it was measured.

### 9. Viva explanation
> These are rule-based helpers that make the AI interviewer smarter: they find gaps in the last answer, avoid repeated questions and provide fallback questions from the resume.

---

## File: `backend/app/services/interview/interview_report_metrics.py`

### 1. Purpose
The calculated (non-AI) parts of the interview report: averages per dimension and observable response indicators.

### 2. What does it do?
1. Averages content (technical) and communication scores separately.
2. Counts words, response time, speaking pace and filler words.
3. Groups repeated weaknesses/missing concepts.

### 3. How does it work?
See the steps above.

```
Interview completed
   |
   v
report_metrics(session)
   |
   v
Merged with the AI report
```

### 4. Important functions
```text
   Other helper functions: _near, _avg, report_metrics
```

### 5. Important variables
- Module-level constants: TECHNICAL_TYPES, FILLERS, INDICATOR_LIMITS

### 6. Connected files
```text
   Uses: app/services/interview/ai_interview_service.py,
   app/services/interview/interviewer_personalities.py
   Used by: app/routers/interview_routes.py
   Tested by: tests/test_interviewers.py
```

### 7. Input and output
- **Input:** The completed InterviewSession with answers.
- **Output:** A metrics dictionary merged into the report.

### 8. Real project example
The report shows technical and communication scores separately so weak English does not look like weak knowledge.

### 9. Viva explanation
> These report numbers are calculated directly from stored scores and answer data, not generated by AI.

---

## File: `backend/app/services/interview/interviewer_personalities.py`

### 1. Purpose
Defines the four AI interviewer personalities (Aria, Victor, Marcus, Elena): how each asks questions, follows up, gives hints, changes difficulty, its voice and avatar.

### 2. What does it do?
1. Interviewer class with behaviour settings and a public part sent to the browser.
2. behaviour_prompt(): personality rules added to the question prompt.
3. get(id): returns an interviewer (default Aria).
4. Checks whether HD avatar files exist.

### 3. How does it work?
See the steps above.

```
Student picks interviewer
   |
   v
Personality prompt added to questions
   |
   v
Voice/avatar used in the room
```

### 4. Important functions
```text
   - asset_exists()
       True when a site-relative URL such as "/avatars/hd/aria.glb" is a file in
       frontend/public.
   Other helper functions: _add, get
```

**Classes:**
```text
   - Interviewer
```

### 5. Important variables
- Module-level constants: PUBLIC_DIR, BOUNDARIES, INTERVIEWERS, DEFAULT, IDS

### 6. Connected files
```text
   Used by: app/routers/interview_routes.py, app/services/interview/ai_interview_service.py,
   app/services/interview/interview_report_metrics.py, app/services/voice/text_to_speech.py
   Tested by: tests/test_avatar_assets.py, tests/test_interview_intelligence.py
```

### 7. Input and output
- **Input:** Interviewer id.
- **Output:** Interviewer settings and prompts.

### 8. Real project example
Choosing Victor gives a stricter, faster interview style, but the same scoring rubric.

### 9. Viva explanation
> We have four interviewer personalities that change the interview style, but scoring stays the same for fairness.

**Note:** Personality never changes scores.

---

## File: `backend/app/services/interview/score_band_labels.py`

### 1. Purpose
Turns a 0-100 score into a band label such as 'Strong (75-89)', because AI scores have a few points of noise.

### 2. What does it do?


### 3. How does it work?
See the steps above.

```
Score
   |
   v
band()
   |
   v
Label shown next to the score
```

### 4. Important functions
```text
   - band()
       Return the band (key, label, range) for a score.
```

### 5. Important variables
- Module-level constants: BANDS

### 6. Connected files
```text
   Used by: app/services/interview/ai_interview_service.py
   Tested by: eval/calibrate_scoring.py, tests/test_scoring_calibration.py
```

### 7. Input and output
- **Input:** Score 0-100.
- **Output:** Band dictionary.

### 8. Real project example
A score of 82 is shown as 'Strong (75-89)'.

### 9. Viva explanation
> We show score bands so students do not over-interpret small differences between AI scores.

---

# Backend - resume and job services

## File: `backend/app/services/resume_and_jobs/__init__.py`

### 1. Purpose
Marks the services/resume_and_jobs folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the resume analysis and job matching modules so they can be imported as app.services.resume_and_jobs.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/resume_and_jobs folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the resume analysis and job matching services.

---

## File: `backend/app/services/resume_and_jobs/ai_career_and_assessment_tasks.py`

### 1. Purpose
Smaller AI tasks: explain a job match, give study recommendations, generate MCQ tests, review code and suggest job roles.

### 2. What does it do?
1. match_review(): explains an already computed match (cannot change the score).
2. student_recommendations(): personalised practice recommendations.
3. generate_assessment(): drafts MCQs for authors to review.
4. evaluate_code(): AI review of code against test cases (code is not executed).
5. job_role_recommendations(): roles that fit the student's profile.

### 3. How does it work?
See the steps above.

```
Router collects data
   |
   v
Prompt + schema
   |
   v
_structured_call()
   |
   v
Validated result
```

### 4. Important functions
```text
   - match_review()
       Plain-language review of a match that was already scored by services.matching.
   - evaluate_code()
       AI code review.
   Other helper functions: student_recommendations, generate_assessment, job_role_recommendations
```

**Classes:**
```text
   - MatchReview
   - Recommendation
   - StudentRecommendations
   - MCQ
   - GeneratedAssessment
   - TestCaseVerdict
   - CodeReview
   - RoleSuggestion
   - RoleRecommendations
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/__init__.py, app/services/ai_models/ai_structured_call_base.py
   Used by: app/services/interview/ai_interview_service.py
```
External packages: pydantic

### 7. Input and output
- **Input:** Snapshots of student data, job/candidate data, code.
- **Output:** Validated JSON results.

### 8. Real project example
A student clicks 'Get recommendations' on the progress page and receives suggested practice topics.

### 9. Viva explanation
> These are smaller AI helpers for recommendations, test generation and code review.

---

## File: `backend/app/services/resume_and_jobs/ai_resume_analyzer.py`

### 1. Purpose
AI resume analysis: extracts name, education, skills, projects, experience and certifications, then removes anything not actually present in the resume text and computes a completeness score.

### 2. What does it do?
Resume analysis and skill identification.

1. Defines the extraction schema (ResumeExtraction).
2. analyze_resume(): asks the model to extract the details as JSON.
3. validate_resume_extraction(): drops skills/items the model invented (checked against the text).
4. resume_completeness(): rule-based 0-100 completeness score (RESUME_SCORE_RULES).

### 3. How does it work?
See the steps above.

```
Resume text
   |
   v
AI extraction (JSON)
   |
   v
Evidence check against text
   |
   v
Completeness score
   |
   v
Saved
```

### 4. Important functions
```text
   - validate_resume_extraction()
       Turn raw model output into the stored analysis, dropping anything not supported by the
       resume text.
   - analyze_resume()
       AI resume analysis: extract skills, education, projects, experience and certifications
       that are actually in the resume text, then validate them against the text (removing
       invented items) and compute the completeness...
   Other helper functions: resume_completeness, _soft_skill_evidence
```

**Classes:**
```text
   - ResumeEducation
   - ResumeProject
   - ResumeExperience
   - ResumeSkillItem
   - ResumeExtraction
```

### 5. Important variables
- Module-level constants: RESUME_SCORE_RULES, SOFT_SKILL_EVIDENCE

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/mongodb_data_layer/__init__.py,
   app/services/ai_models/ai_structured_call_base.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/resume_and_jobs/skill_name_normalizer.py
   Used by: app/services/interview/ai_interview_service.py
```
External packages: pydantic

### 7. Input and output
- **Input:** Resume text and target role.
- **Output:** Analysis dictionary stored on the Resume.

### 8. Real project example
If the AI claims 'Kubernetes' but the word is not in the resume, the validation removes it.

### 9. Viva explanation
> The AI extracts skills and projects from the resume, and then we verify every item against the resume text so invented skills are removed.

---

## File: `backend/app/services/resume_and_jobs/resume_text_extractor.py`

### 1. Purpose
Extracts plain text from uploaded PDF and DOCX resumes.

### 2. What does it do?
1. detect_kind(): checks the file really is a PDF or DOCX.
2. extract_text(): returns the text.
3. Raises ResumeParseError for unsupported or unreadable files.

### 3. How does it work?
See the steps above.

```
Upload
   |
   v
detect_kind()
   |
   v
extract_text()
   |
   v
Text sent to AI analysis
```

### 4. Important functions
```text
   Other helper functions: detect_kind, extract_text
```

**Classes:**
```text
   - ResumeParseError
```

### 5. Important variables
- Module-level constants: PDF_TYPES, DOCX_TYPES

### 6. Connected files
```text
   Used by: app/routers/student_portal_routes.py
```
External packages: docx, pypdf

### 7. Input and output
- **Input:** Uploaded file bytes, name and content type.
- **Output:** Resume text.

### 8. Real project example
When a student uploads resume.pdf, its text is extracted here first.

### 9. Viva explanation
> This file reads the text out of PDF or Word resumes so the AI can analyse it.

---

## File: `backend/app/services/resume_and_jobs/semantic_job_matcher.py`

### 1. Purpose
Computes a transparent 0-100 job match score between a student and a job.

### 2. What does it do?
Matching and skill-gap analysis for jobs.

1. Required and preferred skill coverage (matched = 1, partial = 0.5, missing = 0).
2. Meaning similarity between job text and candidate profile (sentence embeddings).
3. Experience check.
4. Weighted average using MATCH_WEIGHT_* settings, then a cap when required skills are missing.
5. Lists matched, partial and missing skills (the skill gap).

### 3. How does it work?
See the steps above.

```
Collect candidate evidence
   |
   v
Check skills
   |
   v
Embedding similarity
   |
   v
Weighted score + gap cap
```

### 4. Important functions
```text
   - compute_match()
       Pure function: job + candidate -> score and breakdown.
   - candidate_profile()
       Collect the student's skills, projects and experience evidence.
   Other helper functions: job_profile, _project_text, _work_text
```

**Classes:**
```text
   - MatchInputError
```

### 5. Important variables
- Module-level constants: PARTIAL_SIM, PROJECT_SIM

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/mongodb_data_layer/__init__.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/resume_and_jobs/skill_name_normalizer.py,
   app/services/student_progress/student_performance_insights.py
   Used by: app/routers/jobs/job_shared_helpers.py
   Tested by: tests/test_local_ai.py, tests_integration/test_real_models.py
```

### 7. Input and output
- **Input:** Job requirements and the student's profile + resume analysis.
- **Output:** Match result with score and skill gaps.

### 8. Real project example
A student missing a required skill cannot get a very high score even with a good profile.

### 9. Viva explanation
> Our job matching is explainable: it combines skill coverage, meaning similarity and experience into a score, and shows exactly which skills are missing.

---

## File: `backend/app/services/resume_and_jobs/skill_name_normalizer.py`

### 1. Purpose
Normalises skill names (e.g. 'js' -> 'javascript') and checks whether a phrase really appears in a text.

### 2. What does it do?
1. ALIASES map common abbreviations.
2. TextIndex gives fast phrase/skill lookups in a document.

### 3. How does it work?
See the steps above.

```
Skill name
   |
   v
normalize_skill()
   |
   v
Compared with resume/job text
```

### 4. Important functions
```text
   - variants()
       The normalised skill plus every alias that maps to it.
   Other helper functions: tokens, normalize_skill
```

**Classes:**
```text
   - TextIndex
       Normalised view of a document for fast phrase lookups.
```

### 5. Important variables
- Module-level constants: ALIASES

### 6. Connected files
```text
   Used by: app/services/resume_and_jobs/ai_resume_analyzer.py,
   app/services/resume_and_jobs/semantic_job_matcher.py
   Tested by: tests/test_local_ai.py
```

### 7. Input and output
- **Input:** Skill names, resume/job text.
- **Output:** Normalised names; True/False evidence checks.

### 8. Real project example
'ReactJS' in a resume matches 'React' in a job requirement.

### 9. Viva explanation
> This helper makes skill comparison fair by treating aliases like JS and JavaScript as the same.

---

# Backend - English practice services

## File: `backend/app/services/english/__init__.py`

### 1. Purpose
Marks the services/english folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the English practice modules so they can be imported as app.services.english.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/english folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the English practice services.

---

## File: `backend/app/services/english/ai_english_conversation.py`

### 1. Purpose
AI logic of English practice with Aria: generates replies with corrections, cleans the reply, avoids repetition, and evaluates a finished conversation.

### 2. What does it do?
1. english_reply(): Aria's next turn plus updated conversation memory.
2. clean_english_reply() / drop_repeated_opener(): keep replies short, speakable and non-repetitive.
3. apply_correction_policy(): how many corrections are shown, depending on the learning mode.
4. english_evaluate(): grammar, vocabulary, fluency and sentence-formation scores (0-10) with suggestions.

### 3. How does it work?
See the steps above.

```
Student message
   |
   v
Prompt with compact memory
   |
   v
Model reply + corrections
   |
   v
Cleanup and policy
```

### 4. Important functions
```text
   - english_system()
       System prompt for one English session: persona + shared rules + practice style +
       learning mode.
   - clean_english_reply()
       Keep the model's output within the contract the UI relies on.
   - repeats_earlier_turn()
       True when `reply` (or its closing question) is a near-copy of one of Aria's earlier
       turns.
   - drop_repeated_opener()
       Real-model eval: replies kept starting 'I love that you mentioned...' / 'That's such a
       cool detail...'.
   - apply_correction_policy()
       Learning-mode rules enforced in code: how many corrections, how often, and whether one
       is spoken.
   - english_reply()
       Aria's next turn plus the updated conversation memory (`out["memory"]`).
   - english_evaluate()
       Score a finished English conversation (grammar, vocabulary, fluency, sentence
       formation, 0-10) from the student's own messages only, with a short summary, strengths
       and suggestions.
   Other helper functions: _norm, _words, _speakable, _spelling_neutral, _similar,
   _semantic_repeat, _mentions_topic, _opener
```

**Classes:**
```text
   - Correction
   - EnglishReply
   - EnglishEvaluation
```

### 5. Important variables
- Module-level constants: ENGLISH_STYLES, AVATAR_REPLY_MODES, ARIA_INTERVIEW_PERSONA, ENGLISH_RULES, STYLE_GUIDE,    ARIA_SYSTEM, CHAT_TEMPERATURE, SEMANTIC_REPEAT

### 6. Connected files
```text
   Uses: app/mongodb_data_layer/__init__.py, app/services/ai_models/ai_structured_call_base.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/english/english_companion_memory.py
   Used by: app/services/interview/ai_interview_service.py
```
External packages: pydantic

### 7. Input and output
- **Input:** Topic, conversation history, learning mode, memory.
- **Output:** Reply text, corrections, memory, scores.

### 8. Real project example
If the student says 'I go to college yesterday', Aria answers naturally and suggests 'I went'.

### 9. Viva explanation
> This file makes Aria a helpful English partner: it generates replies with gentle corrections and scores the conversation at the end.

---

## File: `backend/app/services/english/english_companion_memory.py`

### 1. Purpose
Deterministic settings and memory of the English companion: learning modes, topic-switch detection and what is remembered between turns.

### 2. What does it do?
1. Defines learning modes (free conversation, English learning, confidence).
2. detect_topic_switch(): notices 'can we talk about movies?'.
3. update_memory(): remembers topics, interests and questions already asked (pure function).
4. memory_for_prompt(): compact memory instead of the full transcript.

### 3. How does it work?
See the steps above.

```
Student message
   |
   v
Topic switch?
   |
   v
Memory updated
   |
   v
Compact memory sent to the model
```

### 4. Important functions
```text
   - detect_topic_switch()
       The topic the student explicitly asks to talk about, e.g. 'Actually, I prefer talking
       about movies' -> 'movies'.
   - correction_allowed()
       Whether a correction may be shown on this turn (free/confidence modes space
       corrections out).
   - update_memory()
       New memory after one turn.
   - memory_for_prompt()
       Compact memory block sent to the model instead of the full transcript.
   - public_memory()
       What the student sees: topics and interests (no internal bookkeeping).
   Other helper functions: mode, empty_memory, _clean, _push, closing_question, _pattern
```

**Classes:**
```text
   - Mode
   - CompanionConfig
       Behaviour config of the English companion (compare services/interviewers.Interviewer).
```

### 5. Important variables
- Module-level constants: LEARNING_MODES, DEFAULT_MODE, MODES, COMPANION, COMPANION_PERSONA, MEMORY_LIMITS

### 6. Connected files
```text
   Used by: app/routers/english_practice_routes.py,
   app/services/english/ai_english_conversation.py
   Tested by: tests/test_english_companion.py
```

### 7. Input and output
- **Input:** Student text, current memory, learning mode.
- **Output:** Updated memory, correction permission.

### 8. Real project example
Aria does not ask the same question twice because asked questions are kept in memory.

### 9. Viva explanation
> This keeps a short memory of the English conversation so the AI stays on topic and does not repeat itself.

---

## File: `backend/app/services/english/english_mistake_profile.py`

### 1. Purpose
Finds a student's recurring English mistakes (verb tense, articles, prepositions, ...) from the corrections already given, without extra AI calls.

### 2. What does it do?
1. classify(): rough category of each correction.
2. record_corrections(): counts categories per student.
3. A pattern is 'recurring' only after 3 corrections in 2 different sessions.
4. Student can dismiss a pattern or clear all.

### 3. How does it work?
See the steps above.

```
Correction given
   |
   v
Category counted
   |
   v
Recurring pattern shown
```

### 4. Important functions
```text
   - classify()
       Category of a correction, or None if it is not a single identifiable mistake (rewrite,
       spelling, unclear).
   - record_corrections()
       Count the categories of the corrections just given (called when a message is saved;
       does not commit).
   - focus_lines()
       Names of the top recurring patterns for the prompt (empty until a pattern really is
       recurring).
   Other helper functions: _words, _is_tense_pair, is_recurring, _active, public_profile,
   dismiss, clear
```

### 5. Important variables
- Module-level constants: MIN_COUNT, MIN_SESSIONS, MAX_CHANGED_WORDS, LABELS

### 6. Connected files
```text
   Uses: app/database_models.py, app/mongodb_data_layer/__init__.py
   Used by: app/routers/english_practice_routes.py
   Tested by: tests/test_english_profile.py
```

### 7. Input and output
- **Input:** Corrections (original -> corrected).
- **Output:** Mistake patterns shown on the English page.

### 8. Real project example
After repeated 'a/an/the' corrections, 'Articles' appears as a recurring mistake.

### 9. Viva explanation
> We track recurring mistakes with simple rules, so the student sees which grammar areas to focus on.

---

## File: `backend/app/services/english/english_vocabulary_trainer.py`

### 1. Purpose
Personal word list with spaced repetition (Leitner boxes 1-5), a daily English plan and progress numbers.

### 2. What does it do?
1. Turns Aria's corrections into review cards; students can add their own words.
2. next_state(): knowing a card moves it up a box (longer wait); not knowing sends it to box 1.
3. daily_plan(): today's tasks, ticked from real activity.
4. progress(): accuracy and score trends.

### 3. How does it work?
See the steps above.

```
Correction -> card
   |
   v
Card due
   |
   v
Student reviews
   |
   v
Box updated
```

### 4. Important functions
```text
   - normalise()
       Key for de-duplication: lower case, single spaces, no trailing punctuation.
   - next_state()
       (new box, next due time, became_mastered) after one answer.
   - collect_corrections()
       Add the corrections Aria just gave as cards (called when a message is saved; does not
       commit).
   - review()
       Record one answer.
   - recommended_mode()
       (learning mode, weakest skill) from the last session evaluated before `before` (so the
       plan stays the same all day).
   - daily_plan()
       Today's plan.
   - check_plan()
       Award the once-a-day points when every plan item is done (safe to call repeatedly).
   - progress()
       Numbers for the English progress view: words, review accuracy by week and score trend
       by session.
   Other helper functions: _now, _aware, day_start, _add, add_word, _trim, due_items, item_out,
   counts, reviews_since, _answered_interview_today, plan_source_id, plan_days_completed
```

### 5. Important variables
- Module-level constants: MAX_BOX, INTERVAL_DAYS, MASTERED_INTERVAL_DAYS, LEARNED_BOX, DAILY_REVIEW_TARGET,    REVIEW_BATCH, MAX_ITEMS, PLAN_ACTIVITY, MASTERED_ACTIVITY, MODE_FOR_SKILL, MODE_LABELS,    SKILL_LABELS

### 6. Connected files
```text
   Uses: app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/student_progress/rewards_and_badges.py
   Used by: app/routers/english_practice_routes.py,
   app/services/student_progress/rewards_and_badges.py
   Tested by: tests/test_english_vocab.py
```

### 7. Input and output
- **Input:** Corrections, review answers.
- **Output:** Cards, due lists, plan, progress data.

### 8. Real project example
A card the student knew moves from box 2 to box 3 and returns after 4 days.

### 9. Viva explanation
> This implements spaced repetition: words you know come back less often, words you forget come back tomorrow.

---

# Backend - voice services

## File: `backend/app/services/voice/__init__.py`

### 1. Purpose
Marks the services/voice folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the speech-to-text and text-to-speech modules so they can be imported as app.services.voice.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/voice folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the speech-to-text and text-to-speech services.

---

## File: `backend/app/services/voice/speech_to_text.py`

### 1. Purpose
Speech-to-text with Whisper (faster-whisper by default, Hugging Face transformers as fallback, or Gemini on hosted servers).

### 2. What does it do?
1. Loads the Whisper model once.
2. Decodes WAV audio and measures voiced time.
3. Transcribes the answer, using the question as a spelling hint.
4. Removes Whisper's invented text and repeated loops.

### 3. How does it work?
See the steps above.

```
Audio
   |
   v
decode_wav()
   |
   v
Whisper transcribe
   |
   v
clean_transcript()
```

### 4. Important functions
```text
   - reset()
       Forget the loaded model (benchmarks switch engines; the next call loads again).
   - decode_wav()
       WAV bytes -> (mono float32 samples at 16 kHz, duration seconds).
   - wav_stats()
       (duration, speech seconds) of a PCM WAV using only the standard library (hosts without
       numpy/soundfile).
   - speech_seconds()
       Rough voice-activity measure: total length of frames louder than `threshold_db` dBFS.
   - collapse_loops()
       Whisper sometimes loops, writing the same sentence or phrase again and again.
   - clean_transcript()
       Remove Whisper's invented text.
   - transcribe()
       WAV bytes -> {"text", "duration", "speech_seconds", "engine"}.
   Other helper functions: _hosted, status, _faster_name, _load_faster, _load_transformers,
   _load, warmup, _transcribe_hosted, _key
```

**Classes:**
```text
   - STTUnavailable
   - BadAudio
```

### 5. Important variables
- Module-level constants: TARGET_SR, MIN_SPEECH_SECONDS, HALLUCINATIONS, MAX_WORDS_PER_VOICED_SECOND

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/ai_models/gemini_api_client.py,
   app/services/ai_models/language_model_client.py
   Used by: app/main.py, app/routers/voice_speech_routes.py
   Tested by: tests/test_deploy.py, tests/test_english_avatar.py, tests/test_voice.py,
   tests_integration/test_voice_real.py, tests_perf/bench_interview_latency.py,
   tests_perf/bench_stt.py
```
External packages: faster_whisper, numpy, soundfile, transformers

### 7. Input and output
- **Input:** WAV bytes, optional prompt.
- **Output:** Transcript text, duration and speech seconds.

### 8. Real project example
The student's spoken answer becomes text that is then scored like a typed answer.

### 9. Viva explanation
> This file converts speech to text using the Whisper model running locally.

---

## File: `backend/app/services/voice/streamed_reply_sentence_splitter.py`

### 1. Purpose
Turns the model's streamed JSON reply into complete sentences, in order, so speech can start before the whole reply is written.

### 2. What does it do?
1. Reads string fields from unfinished JSON.
2. Splits finished sentences (handles abbreviations).
3. SpokenStream emits each finished sentence once.

### 3. How does it work?
See the steps above.

```
Token stream
   |
   v
partial_json_string()
   |
   v
split_complete()
   |
   v
Sentence to TTS
```

### 4. Important functions
```text
   - partial_json_string()
       Value of string field `key` in a possibly unfinished JSON object: (text so far,
       finished?).
   - split_complete()
       Split `text` into finished sentences and the unfinished rest.
   - split_first_clause()
       (head, tail) split at the first comma/semicolon after `min_head` characters, if the
       sentence is long; otherwise (sentence, "").
   - final_sentences()
       The sentences SpokenStream would speak for the finished reply (used to finish, or
       correct, a stream).
   - remaining_after()
       Sentences still to speak if what was already spoken matches the start of the final
       reply; None if it does not (the stream must be retracted and the final reply spoken
       from the beginning).
   Other helper functions: _words
```

**Classes:**
```text
   - SpokenStream
       Feed it the model's growing JSON text; it calls `emit(sentence)` once per finished
       spoken sentence: first the preface (feedback / explanation), then the question.
```

### 5. Important variables
- Module-level constants: MIN_WORDS

### 6. Connected files
```text
   Uses: app/services/interview/ai_interview_service.py
   Used by: app/routers/english_practice_routes.py, app/routers/live_voice_interview_routes.py
   Tested by: tests/test_latency_and_monitoring.py, tests_perf/bench_interview_latency.py
```

### 7. Input and output
- **Input:** Growing JSON text from the model.
- **Output:** Finished sentences.

### 8. Real project example
The avatar starts speaking the first sentence of a question while the AI is still writing the rest.

### 9. Viva explanation
> This splitter lets us speak AI replies sentence by sentence as they are generated, reducing waiting time.

---

## File: `backend/app/services/voice/text_to_speech.py`

### 1. Purpose
Text-to-speech with the Kokoro-82M model, plus a mouth-shape (viseme) timeline for avatar lip sync.

### 2. What does it do?
1. Normalises text (pronunciation of technical words).
2. Synthesises sentence-sized pieces to WAV audio.
3. Converts phoneme durations into a viseme timeline.
4. Caches fixed phrases only.

### 3. How does it work?
See the steps above.

```
Question text
   |
   v
Phonemes (espeak)
   |
   v
Kokoro audio
   |
   v
Visemes for the avatar's mouth
```

### 4. Important functions
```text
   - visemes_from_durations()
       Phoneme string + Kokoro durations (with one pad unit at each end) -> [{t, d, v}] in
       seconds.
   - static_phrases()
       Fixed lines that are identical for every candidate (reactions, closings, previews, the
       stress-interview interjection).
   - prewarm_static()
       Synthesise every fixed phrase once (background, after the model loads) so they play
       instantly.
   - split_segments()
       Sentence-sized pieces for streaming speech (short pieces start playing sooner).
   - synthesize()
       -> {"audio_wav_b64", "sample_rate", "duration", "visemes": [{t, d, v}], "voice",
       "text"}. cache=True only for fixed phrases (see static_phrases).
   Other helper functions: status, normalize_text, _load, warmup, _sentences, is_static
```

**Classes:**
```text
   - TTSUnavailable
```

### 5. Important variables
- Module-level constants: SAMPLE_RATE, SAMPLES_PER_UNIT, VOICES, PRONUNCIATIONS, PHONEME_VISEME

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/interview/interviewer_personalities.py
   Used by: app/main.py, app/routers/live_voice_interview_routes.py,
   app/routers/voice_speech_routes.py
   Tested by: tests/test_latency_and_monitoring.py, tests/test_voice.py,
   tests_e2e/english_avatar_browser.py, tests_e2e/partial_transcript_check.py,
   tests_e2e/voice_interview_browser.py, tests_integration/test_voice_real.py,
   tests_perf/bench_interview_latency.py, tests_perf/bench_stt.py
```
External packages: espeakng_loader, huggingface_hub, kokoro, misaki, numpy, phonemizer, soundfile, torch

### 7. Input and output
- **Input:** Text, voice, speed.
- **Output:** Base64 WAV audio + viseme timeline.

### 8. Real project example
The interviewer avatar speaks each question with lips matching the audio.

### 9. Viva explanation
> This file gives our avatar a voice and lip-sync data using a local text-to-speech model.

---

# Backend - monitoring services

## File: `backend/app/services/monitoring/__init__.py`

### 1. Purpose
Marks the services/monitoring folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the integrity monitoring and performance timing modules so they can be imported as app.services.monitoring.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/monitoring folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the integrity monitoring and performance timing services.

---

## File: `backend/app/services/monitoring/interview_integrity_rules.py`

### 1. Purpose
Rules for disclosed interview integrity monitoring: what the candidate is told, which events are allowed, their severity and a neutral risk summary.

### 2. What does it do?
1. Policy text and features the candidate can agree to.
2. event_allowed(): only consented features record.
3. severity(): based on reliability and duration, never an accusation.
4. risk_summary(): neutral band such as 'Low number of potential irregularities'.
5. Admin-configurable SecurityConfig (detectors, thresholds, weights).

### 3. How does it work?
See the steps above.

```
Event received
   |
   v
Allowed?
   |
   v
Severity
   |
   v
Risk summary for reviewer
```

### 4. Important functions
```text
   - load_config()
       Stored JSON -> validated config (an invalid stored row falls back to the defaults).
   - event_allowed()
       Only what the candidate agreed to is recorded.
   - describe()
       One neutral sentence for reports and the timeline.
   - severity()
       (severity, confidence_sufficient).
   - paste_severity()
       A long paste becomes "medium" once it has happened PASTE_LONG_REPEAT times in the same
       interview.
   - session_status()
       Neutral, non-accusatory summary.
   Other helper functions: policy, clean_details, retention_cutoff, _rule_hits, risk_summary
```

**Classes:**
```text
   - DetectorSwitches
   - Thresholds
   - RiskWeights
   - RiskBands
   - SecurityConfig
```

### 5. Important variables
- Module-level constants: POLICY_VERSION, CONFIDENCE_SUFFICIENT, SECURITY_CONFIG_KEY, FEATURES, SESSION_FEATURE,    EVENT_FEATURE, CATEGORIES, ALL_CATEGORIES, SOURCES, DETAIL_INTS, DETAIL_ENUMS, LABELS,    PASTE_LONG_REPEAT, SEVERITY_ORDER, CLEARED, RISK_RULES, BAND_LABELS

### 6. Connected files
```text
   Used by: app/routers/interview_monitoring_routes.py
   Tested by: tests/test_integrity_detectors.py, tests/test_latency_and_monitoring.py,
   tests/test_security_module.py
```
External packages: pydantic

### 7. Input and output
- **Input:** Events, durations, config.
- **Output:** Severity, labels, summaries.

### 8. Real project example
A face missing for 2 seconds is 'info'; a long absence becomes a reviewable event.

### 9. Viva explanation
> These rules make monitoring fair: only agreed features are recorded and results are neutral signals for a human reviewer.

**Note:** Monitoring never changes interview scores.

---

## File: `backend/app/services/monitoring/performance_timing.py`

### 1. Purpose
Times each step of the interview pipeline (AI call, TTS, turn total) so the slowest part is visible to the admin.

### 2. What does it do?
1. record() / timer(): store a step's duration and success.
2. summary(): average, p50, p95, max per step.

### 3. How does it work?
See the steps above.

```
Step runs inside timer()
   |
   v
Duration recorded
   |
   v
Admin performance page
```

### 4. Important functions
```text
   - record()
       Store one measurement.
   - timer()
       with perf.timer("tts.segment"): ... - records the duration, and ok=False if the block
       raises.
   - summary()
       Per metric: count, failures, average, p50, p95, max, plus averaged numeric details
       (e.g. token counts).
   Other helper functions: _clean_meta, _pct
```

### 5. Important variables
- Module-level constants: CLIENT_METRICS, ALLOWED_META, SERVER_METRICS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py
   Used by: app/routers/interview_monitoring_routes.py, app/routers/interview_routes.py,
   app/routers/live_voice_interview_routes.py, app/routers/voice_speech_routes.py,
   app/services/ai_models/ai_structured_call_base.py
```

### 7. Input and output
- **Input:** Step names and durations.
- **Output:** PerfMetric documents and summaries.

### 8. Real project example
The admin can see that question generation takes about 2 seconds on average.

### 9. Viva explanation
> This file measures how long each interview step takes so we can find bottlenecks.

**Note:** Never stores questions, answers or audio.

---

## File: `backend/app/services/monitoring/visual_attention_report.py`

### 1. Purpose
Stores and reports an estimated 'visual attention toward the screen' percentage measured in the browser.

### 2. What does it do?
1. merge(): accepts plausible time totals from the browser.
2. pct(): toward / (toward + away).
3. report(): attention section with limitations.

### 3. How does it work?
See the steps above.

```
Browser measures
   |
   v
Totals sent
   |
   v
merge() validates
   |
   v
report()
```

### 4. Important functions
```text
   - merge()
       Return (updated attention record, "") or (None, reason) if the snapshot is not
       acceptable.
   - report()
       The attention section of the monitoring report, or None if attention tracking was not
       used/recorded.
   Other helper functions: _sum_epochs, pct
```

### 5. Important variables
- Module-level constants: BUCKET_MS, MIN_VALID_MS, MAX_EPOCHS, MAX_BUCKETS, CLOCK_SLACK_MS, REASONS, TOTALS, LABEL,    LIMITATIONS

### 6. Connected files
```text
   Used by: app/routers/interview_monitoring_routes.py
```

### 7. Input and output
- **Input:** Time totals from the browser.
- **Output:** Attention record and report.

### 8. Real project example
The integrity report shows 'Estimated attention 92%' with an explanation of its limits.

### 9. Viva explanation
> We estimate attention from time looking toward the screen, measured locally in the browser.

---

# Backend - student progress services

## File: `backend/app/services/student_progress/__init__.py`

### 1. Purpose
Marks the services/student_progress folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the progress insights and rewards modules so they can be imported as app.services.student_progress.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/student_progress folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the progress insights and rewards services.

---

## File: `backend/app/services/student_progress/rewards_and_badges.py`

### 1. Purpose
Points, badges, streaks, challenges and mentor-goal progress, with anti-gaming rules.

### 2. What does it do?
1. award_points(): each activity rewarded once, with daily caps.
2. Badges and streaks.
3. Challenge progress per day/week.
4. Mentor goal progress.
5. Revoking points for flagged activity.

### 3. How does it work?
See the steps above.

```
Activity completed
   |
   v
after_activity()
   |
   v
Points/badges/goals updated
```

### 4. Important functions
```text
   - streaks()
       Return (current_streak, longest_streak) in days of verified activity.
   - streak_lengths()
       (current, longest) run of consecutive days; the current run may end today or
       yesterday.
   - evaluate_challenges()
       Award each active challenge at most once per period when its target is reached.
   - after_activity()
       Run every automatic reward/goal check after a verified activity.
   Other helper functions: _today_start, award_points, rule_requirements, activity_dates,
   badge_stats, english_vocab_stats, evaluate_badges, total_points, revoke_for_source,
   _goal_progress, goal_progress, refresh_goals, complete_goal, period_bounds, challenge_progress
```

### 5. Important variables
- Module-level constants: CHALLENGE_METRICS

### 6. Connected files
```text
   Uses: app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/english/english_vocabulary_trainer.py,
   app/services/platform_support/audit_and_notification_helpers.py
   Used by: app/routers/admin/admin_operations_routes.py, app/routers/english_practice_routes.py,
   app/routers/interview_routes.py, app/routers/mentor_portal_routes.py,
   app/routers/skill_assessment_routes.py, app/routers/student_portal_routes.py,
   app/services/english/english_vocabulary_trainer.py,
   app/services/student_progress/student_performance_insights.py
   Tested by: tests/test_english_vocab.py, tests/test_features.py
```

### 7. Input and output
- **Input:** Completed activities.
- **Output:** Points transactions, badges, goal updates.

### 8. Real project example
Completing a mock interview with real answers earns points and may unlock 'First Interview'.

### 9. Viva explanation
> This gamification module awards points and badges, with rules that prevent gaming the system.

---

## File: `backend/app/services/student_progress/student_performance_insights.py`

### 1. Purpose
Read-only summaries of a student's performance shared by all portals: readiness score, trends, remedies, history and weekly progress.

### 2. What does it do?
Skill-gap analysis and dashboard data.

1. student_summary(): averages and trends from interviews, assessments and English sessions.
2. readiness_score(): weighted score (interviews 30%, assessments 20%, English 20%, resume 20%, profile 10%).
3. remedies(): rule-based weakness -> suggested practice.
4. weekly_progress(), attempt_comparison(), progress_series(), practice_history().

### 3. How does it work?
See the steps above.

```
Dashboard request
   |
   v
Results aggregated
   |
   v
Readiness + trends computed
   |
   v
JSON to frontend
```

### 4. Important functions
```text
   - trend_label()
       'improving' | 'struggling' | 'stable' | 'no_data' based on chronological scores.
   - readiness_score()
       Transparent weighted score.
   - remedies()
       Deterministic weakness -> remedy suggestions (not AI).
   - weekly_progress()
       Activities and average score per ISO week for the last N weeks.
   - attempt_comparison()
       Each completed interview with the change versus the previous attempt in the same
       category.
   Other helper functions: _avg, current_resume, student_summary, profile_completeness,
   practice_history, progress_series, record_progress
```

### 5. Important variables
- Module-level constants: READINESS_WEIGHTS

### 6. Connected files
```text
   Uses: app/api_response_serializers.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/student_progress/rewards_and_badges.py
   Used by: app/routers/admin/admin_analytics_routes.py,
   app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/english_practice_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/job_shared_helpers.py,
   app/routers/jobs/recruiter_job_routes.py, app/routers/jobs/recruiter_screening_routes.py,
   app/routers/mentor_portal_routes.py, app/routers/skill_assessment_routes.py,
   app/routers/student_portal_routes.py, app/services/resume_and_jobs/semantic_job_matcher.py
```

### 7. Input and output
- **Input:** Student id and stored results.
- **Output:** Summary dictionaries for dashboards and reports.

### 8. Real project example
The student dashboard's readiness card and 'weak areas' list come from this file.

### 9. Viva explanation
> This file calculates placement readiness and strengths/weaknesses from all practice results, using transparent weights.

---

# Backend - platform support services

## File: `backend/app/services/__init__.py`

### 1. Purpose
Marks the services folder (business logic used by the routers) as a Python package. No code.

### 2. What does it do?
1. Lets routers import services, e.g. `from ..services.interview import ai_interview_service`.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services folder (business logic used by the routers) as a Python package. No code.

### 9. Viva explanation
> Package marker for the business-logic layer, which is split into sub-folders by area.

---

## File: `backend/app/services/platform_support/__init__.py`

### 1. Purpose
Marks the services/platform_support folder as a Python package. It contains no code.

### 2. What does it do?
1. Groups the shared platform helper modules so they can be imported as app.services.platform_support.<module>.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks the services/platform_support folder as a Python package. It contains no code.

### 9. Viva explanation
> An empty package marker; the folder groups the shared platform helper services.

---

## File: `backend/app/services/platform_support/audit_and_notification_helpers.py`

### 1. Purpose
Small shared helpers: audit log entries, in-app notifications, pagination, platform settings and skill normalisation.

### 2. What does it do?
1. Used by almost every router for logging, notifications and paging.

### 3. How does it work?
See the steps above.

```
Router action
   |
   v
audit()/notify()
   |
   v
Commit
   |
   v
Live notification signal
```

### 4. Important functions
```text
   - audit()
       Save an audit log entry.
   - notify()
       Create an in-app notification (live stream signalled after commit).
   - paginate()
       Return one page of results plus page info.
   - get_setting()
       Read a platform setting.
   - signal_notifications()
       After the next commit, tell the user's open notification streams to re-fetch
       (services/platform_support/live_notification_events.py).
   Other helper functions: normalize_skills
```

### 5. Important variables
- Module-level constants: DEFAULT_SETTINGS, SETTING_OPTIONS

### 6. Connected files
```text
   Uses: app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/services/platform_support/live_notification_events.py
   Used by: app/routers/admin/admin_analytics_routes.py,
   app/routers/admin/admin_content_routes.py, app/routers/admin/admin_operations_routes.py,
   app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
   app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/interview_routes.py, app/routers/jobs/recruiter_job_routes.py,
   app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
   app/routers/mentor_portal_routes.py, app/routers/profile_and_notification_routes.py,
   app/routers/skill_assessment_routes.py, app/routers/student_portal_routes.py,
   app/seed_sample_jobs.py, app/services/ai_models/ai_structured_call_base.py,
   app/services/resume_and_jobs/ai_resume_analyzer.py,
   app/services/student_progress/rewards_and_badges.py,
   app/services/student_progress/student_performance_insights.py
   Tested by: tests/test_live_notifications_and_recruiter.py
```

### 7. Input and output
- **Input:** Database session and values.
- **Output:** AuditLog/Notification documents, pages.

### 8. Real project example
When a recruiter changes an application status, notify() tells the student.

### 9. Viva explanation
> Common helper functions used across the backend for audit logging, notifications and paging.

---

## File: `backend/app/services/platform_support/background_jobs.py`

### 1. Purpose
Runs background jobs (feedback, question prefetch, emails) in tracked threads and lets them finish on shutdown.

### 2. What does it do?
1. spawn(): start a tracked daemon thread.
2. drain(): wait for running jobs at shutdown.

### 3. How does it work?
See the steps above.

```
spawn()
   |
   v
Job runs
   |
   v
drain() at shutdown
```

### 4. Important functions
```text
   - spawn()
       Start `target(*args)` in a tracked daemon thread.
   - drain()
       Signal shutdown and wait up to `timeout` seconds for the running jobs.
   - started()
       Called at startup (a test client starts and stops the app many times in one process).
   Other helper functions: stopping, running
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: app/main.py, app/routers/english_practice_routes.py, app/routers/interview_routes.py,
   app/routers/live_voice_interview_routes.py, app/services/platform_support/email_sender.py
   Tested by: tests/conftest.py, tests/test_deploy.py
```

### 7. Input and output
- **Input:** Functions to run.
- **Output:** Running threads.

### 8. Real project example
Detailed answer feedback is written in a background job after the next question is shown.

### 9. Viva explanation
> This file runs slow tasks in the background so students do not have to wait.

---

## File: `backend/app/services/platform_support/email_sender.py`

### 1. Purpose
Sends plain-text emails over SMTP when configured; otherwise logs them.

### 2. What does it do?
1. enabled(): is SMTP set?
2. send(): queue an email on a background thread.

### 3. How does it work?
See the steps above.

```
send()
   |
   v
Background thread
   |
   v
SMTP
```

### 4. Important functions
```text
   - send()
       Queue a plain-text email.
   Other helper functions: enabled, _deliver
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/platform_support/background_jobs.py
   Used by: app/routers/authentication_routes.py, app/routers/jobs/job_shared_helpers.py
```

### 7. Input and output
- **Input:** Recipient, subject, body.
- **Output:** Email sent or logged.

### 8. Real project example
Password-reset links are emailed through this file.

### 9. Viva explanation
> Optional email sending for password resets and status updates.

---

## File: `backend/app/services/platform_support/hosted_ai_consent.py`

### 1. Purpose
Asks students to agree once before their data is sent to a hosted AI (Gemini). Not needed with the local model.

### 2. What does it do?
1. required(), info(), has(user)
2. check(user): returns HTTP 428 if consent is required but missing.

### 3. How does it work?
See the steps above.

```
AI feature called
   |
   v
check()
   |
   v
Continue or 428
```

### 4. Important functions
```text
   - check()
       428 Precondition Required when a student must agree to the AI data notice before this
       action.
   Other helper functions: required, info, has
```

### 5. Important variables
- Module-level constants: NOTICE, REQUIRED_MESSAGE

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_models.py
   Used by: app/routers/authentication_routes.py, app/routers/english_practice_routes.py,
   app/routers/interview_routes.py, app/routers/student_portal_routes.py
   Tested by: tests/test_deploy.py
```
External packages: fastapi

### 7. Input and output
- **Input:** User.
- **Output:** Consent status / 428 error.

### 8. Real project example
With Gemini enabled, a student must accept the AI data notice before uploading a resume.

### 9. Viva explanation
> A privacy safeguard: if a cloud AI is used, the student must give consent first.

---

## File: `backend/app/services/platform_support/live_notification_events.py`

### 1. Purpose
Delivers 'something changed' signals to open browser tabs over Server-Sent Events.

### 2. What does it do?
1. publish(user_id, event)
2. subscribe(user_id): queue for one stream (max 5 per user).

### 3. How does it work?
See the steps above.

```
notify() commit
   |
   v
publish()
   |
   v
SSE stream
```

### 4. Important functions
```text
   - publish()
       Send `event` to every open stream of `user_id`.
   - subscribe()
       Register a queue for `user_id` on the running event loop; always unregistered on exit.
   Other helper functions: _put, stream_count
```

**Classes:**
```text
   - TooManyStreams
```

### 5. Important variables
- Module-level constants: MAX_STREAMS_PER_USER, QUEUE_SIZE

### 6. Connected files
```text
   Used by: app/routers/profile_and_notification_routes.py,
   app/services/platform_support/audit_and_notification_helpers.py
   Tested by: tests/test_live_notifications_and_recruiter.py
```

### 7. Input and output
- **Input:** User id and event.
- **Output:** Events in subscriber queues.

### 8. Real project example
The notification bell updates without refreshing the page.

### 9. Viva explanation
> This enables live notifications by pushing small signals to the browser.

**Note:** Works within one server process only.

---

## File: `backend/app/services/platform_support/rate_limiter.py`

### 1. Purpose
Sliding-window counters used for login lockout, password-reset limits and voice/monitoring rate limits (memory or Redis).

### 2. What does it do?
1. hit(), add(), count(), clear().
2. Uses Redis when REDIS_URL is set, otherwise memory.

### 3. How does it work?
See the steps above.

```
Request
   |
   v
hit(key)
   |
   v
Allowed or blocked
```

### 4. Important functions
```text
   - set_redis_client()
       Use this client (tests pass a fakeredis instance); None goes back to REDIS_URL /
       memory.
   - backend()
       The backend to use right now (Redis when configured and reachable, else memory).
   - count()
       Events recorded for `key` within the last `window` seconds.
   - add()
       Record one event; returns the count including it.
   - hit()
       Record one event if fewer than `limit` happened in the window.
   - reset()
       Forget every counter (tests).
   Other helper functions: _connect, _run, clear, status
```

**Classes:**
```text
   - MemoryBackend
   - RedisBackend
```

### 5. Important variables
- Module-level constants: KEY_PREFIX

### 6. Connected files
```text
   Uses: app/application_configuration.py
   Used by: app/routers/authentication_routes.py, app/routers/interview_monitoring_routes.py,
   app/routers/voice_speech_routes.py
   Tested by: tests/conftest.py, tests/test_account_security.py, tests/test_deploy.py,
   tests/test_security_module.py, tests/test_voice.py
```
External packages: redis

### 7. Input and output
- **Input:** Key and limits.
- **Output:** Allowed or not.

### 8. Real project example
After several wrong passwords, login for that email is blocked for a while.

### 9. Viva explanation
> This rate limiter protects login and heavy endpoints from abuse.

---

## File: `backend/app/services/platform_support/student_record_access.py`

### 1. Purpose
Decides who may view a student's detailed records (the student, admins, assigned mentors, recruiters with an application from that student).

### 2. What does it do?
1. recruiter_has_applicant()
2. can_view_student_detail()
3. ensure_can_view_student(): 403 otherwise.

### 3. How does it work?
See the steps above.

```
Request
   |
   v
Access check
   |
   v
Data or 403
```

### 4. Important functions
```text
   Other helper functions: recruiter_has_applicant, can_view_student_detail,
   ensure_can_view_student
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/authentication_dependencies.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py
   Used by: app/routers/interview_monitoring_routes.py, app/routers/jobs/recruiter_job_routes.py,
   app/routers/student_portal_routes.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Viewer and student id.
- **Output:** True/False or 403.

### 8. Real project example
A recruiter can open a resume only if that student applied to one of their jobs.

### 9. Viva explanation
> This enforces privacy rules about who can see a student's resume and results.

---

# Backend - machine learning (question classifier)

## File: `backend/ml/__init__.py`

### 1. Purpose
Marks backend/ml as a Python package so the training script can be run with `python -m ml.train_question_classifier`. It contains no code.

### 2. What does it do?


### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Marks backend/ml as a Python package so the training script can be run with `python -m ml.train_question_classifier`. It contains no code.

### 9. Viva explanation
> Marks backend/ml as a Python package so the training script can be run with `python -m ml.train_question_classifier`. It contains no code.

---

## File: `backend/ml/train_question_classifier.py`

### 1. Purpose
Trains the project's own machine-learning model that predicts an interview question's type (technical, HR, behavioral, ...) and difficulty, and saves it for the backend.

### 2. What does it do?
1. Loads the hand-labelled CSV dataset from ml/data/.
2. Builds TF-IDF text features.
3. Trains scikit-learn classifiers for type and difficulty.
4. Evaluates accuracy and writes ml/models/metrics.json.
5. Saves the trained model as ml/models/question_classifier.joblib.

### 3. How does it work?
Run offline from backend/: python -m ml.train_question_classifier. The web app only loads the saved file (services/ai_models/question_type_classifier.py); it never trains during a request.

```
Load CSV
   |
   v
TF-IDF features
   |
   v
Train classifiers
   |
   v
Evaluate
   |
   v
Save joblib + metrics
```

### 4. Important functions
```text
   Other helper functions: load_data, make_model, rule_type, rule_difficulty, report, evaluate,
   main
```

### 5. Important variables
- Module-level constants: HERE, SEED, TYPE_RULES

### 6. Connected files
```text
   Uses: app/seed_initial_data.py
```
External packages: joblib, numpy, sklearn

### 7. Input and output
- **Input:** ml/data/interview_questions_dev.csv.
- **Output:** question_classifier.joblib and metrics.json.

### 8. Real project example
After adding more labelled questions, the team re-runs this script to improve the classifier.

### 9. Viva explanation
> This script trains our custom ML model with scikit-learn. The trained model is saved and later used by the backend to double-check the type and difficulty of AI-generated questions.

---

# Backend - evaluation scripts (real AI model)

## File: `backend/eval/calibrate_scoring.py`

### 1. Purpose
Score calibration check for interview answers, using the REAL configured model.

### 2. What does it do?
1. Evaluation script using the real configured AI model.
2. Run manually to measure AI behaviour/scoring quality; not part of the normal test run.

### 3. How does it work?
Scores the fixed answers in eval/calibration_set.json (poor / fair / good / excellent, hand-labelled) with the same function the live interview uses (ai.score_answer + the default rubric) and reports: * spearman - rank correlation between the hand label and the 0-100 score (1.0 = perfect ordering) * mean_by_label - average score per label, and the gap between neighbouring labels (spread) * in_band - share of answers whose score falls in the band a fair interviewer would give * perfect_100 - answers that got 100 (nothing in this set deserves 100) .\venv\Scripts\python.exe eval\calibrate_scoring.py --out eval\results\calibration_after.json .\venv\Scripts\python.exe eval\calibrate_scoring.py --...

### 4. Important functions
```text
   Other helper functions: spearman, main
```

### 5. Important variables
- Module-level constants: HERE, BACKEND

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py,
   app/routers/interview_routes.py, app/seed_initial_data.py,
   app/services/ai_models/language_model_client.py,
   app/services/interview/ai_interview_service.py, app/services/interview/score_band_labels.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Score calibration check for interview answers, using the REAL configured model.

### 9. Viva explanation
> Score calibration check for interview answers, using the REAL configured model.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/eval/run_eval.py`

### 1. Purpose
Behaviour evaluation of the interviewers and the English companion with the REAL local models.

### 2. What does it do?
1. Evaluation script using the real configured AI model.
2. Run manually to measure AI behaviour/scoring quality; not part of the normal test run.

### 3. How does it work?
Drives the real HTTP API (FastAPI TestClient, in-memory database) through the fixed scenarios in eval/scenarios.json, so the same script measures any version of the backend: .\venv\Scripts\python.exe eval\run_eval.py --out eval\results\after.json .\venv\Scripts\python.exe eval\run_eval.py --backend-dir <copy of an older backend> --out before.json Metrics (all computed automatically; transcripts are saved for manual review): * duplicate_pairs - question pairs in one interview whose meaning similarity (MiniLM cosine, an independent judge that is NOT the app's own duplicate filter) is >= 0.75 * resume_grounded - share of questions that mention something from the candidate's resume or role * fol...

### 4. Important functions
```text
   Other helper functions: setup, embedder, register, add_resume, grounding_terms, mentions,
   usage_since, run_interview, closing_question, run_english, lat, main
```

### 5. Important variables
- Module-level constants: HERE, BANNED, VAGUE_KINDS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/main.py, app/routers/interview_routes.py, app/seed_initial_data.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py
```
External packages: fastapi

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Behaviour evaluation of the interviewers and the English companion with the REAL local models.

### 9. Viva explanation
> Behaviour evaluation of the interviewers and the English companion with the REAL local models.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

# Backend - automated tests (mocked AI)

## File: `backend/tests/conftest.py`

### 1. Purpose
Shared pytest setup: forces a safe test environment (no real AI model, no Gemini, no email, a separate 'hiresense_test' MongoDB database emptied before every test, throwaway upload folder) and provides fixtures such as the API test client, the database session and fake AI responses.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   - join_app_threads()
       Wait for the app's background threads (first-question prefetch, streamed turns,
       background feedback), so a thread still running from one step (or test) cannot write
       into the next one's data.
   - db_session_factory()
       An emptied MongoDB test database with the standard seed (admin account, badges,
       question bank, ...).
   - new_client()
       Factory for additional independent clients (separate cookie jars) sharing the same DB.
   - fake_embed()
       MOCK embedding: bag of hashed words + character trigrams, unit length.
   - fake_embeddings()
       MOCKED embedding model for semantic-matching tests.
   - fake_ai()
       MOCKED local LLM: deterministic stand-in used to test the AI-dependent workflows end
       to end.
   Other helper functions: _isolated_uploads, _join_app_threads, _prefetch_runs_inline,
   _reset_ai_caches, client, db, make_client, register_student, login, admin_login
```

### 5. Important variables
- Module-level constants: APP_THREADS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/main.py,
   app/seed_initial_data.py, app/services/ai_models/gemini_api_client.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/interview/ai_interview_service.py,
   app/services/platform_support/background_jobs.py,
   app/services/platform_support/rate_limiter.py
```
External packages: fastapi, numpy, pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Shared pytest setup: forces a safe test environment (no real AI model, no Gemini, no email, a separate 'hiresense_test' MongoDB database emptied before every test, throwaway upload folder) and provides fixtures such as the API test client, the database session and fake AI responses.

### 9. Viva explanation
> This is a test file. Shared pytest setup: forces a safe test environment (no real AI model, no Gemini, no email, a separate 'hiresense_test' MongoDB database emptied before every test, throwaway upload folder) and provides fixtures such as the API test client, the database session and fake AI responses.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_account_security.py`

### 1. Purpose
Password reset, self-service account deletion, upload storage and the admin password policy.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 10 test(s), e.g.: forgot password does not reveal accounts; reset password flow is single use; reset rejects weak password and garbage token; reset token cannot be used as a session; reset requests are rate limited; student can delete own account and files; only students can self delete; uploads go to temp dir not backend uploads; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: docx_bytes, upload, capture_mail, token_from,
   test_forgot_password_does_not_reveal_accounts, test_reset_password_flow_is_single_use,
   test_reset_rejects_weak_password_and_garbage_token,
   test_reset_token_cannot_be_used_as_a_session, test_reset_requests_are_rate_limited,
   test_student_can_delete_own_account_and_files, test_only_students_can_self_delete,
   test_uploads_go_to_temp_dir_not_backend_uploads, test_resume_history_is_capped,
   test_seed_generates_random_admin_password_when_unset
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
   app/routers/authentication_routes.py, app/routers/student_portal_routes.py,
   app/seed_initial_data.py, app/services/platform_support/rate_limiter.py
```
External packages: docx

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Password reset, self-service account deletion, upload storage and the admin password policy.

### 9. Viva explanation
> This is a test file. Password reset, self-service account deletion, upload storage and the admin password policy.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_ai_tolerance.py`

### 1. Purpose
Model-output tolerance: a display-only label the model invents must not discard a whole analysis.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 1 test(s), e.g.: unknown skill category is mapped not rejected.
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_unknown_skill_category_is_mapped_not_rejected
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/services/interview/ai_interview_service.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Model-output tolerance: a display-only label the model invents must not discard a whole analysis.

### 9. Viva explanation
> This is a test file. Model-output tolerance: a display-only label the model invents must not discard a whole analysis.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_attention.py`

### 1. Purpose
Estimated visual attention: server storage rules, the report, and who can read it.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 13 test(s), e.g.: percentage is toward over valid time and unobserved time is separate; half and half and too little data; no percentage without enough valid data and never zero for a dead camera; a running total can grow but not shrink and resends are idempotent; totals cannot exceed the interview clock; malformed snapshots are rejected; only the owner with attention consent can send; a reload re consent keeps the totals and they stay out of the config; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
The percentage is measured in the browser (frontend/src/monitoring/attentionMeter.js, unit-tested there). These tests prove what the server accepts, how it combines monitor runs and that unobserved time is never counted as attention.

### 4. Important functions
```text
   - spread()
       Fill consecutive 10-second buckets with the time, the way the browser does.
   Other helper functions: snap, put, started, report,
   test_percentage_is_toward_over_valid_time_and_unobserved_time_is_separate,
   test_half_and_half_and_too_little_data,
   test_no_percentage_without_enough_valid_data_and_never_zero_for_a_dead_camera,
   test_a_running_total_can_grow_but_not_shrink_and_resends_are_idempotent,
   test_totals_cannot_exceed_the_interview_clock, test_malformed_snapshots_are_rejected,
   test_only_the_owner_with_attention_consent_can_send,
   test_a_reload_re_consent_keeps_the_totals_and_they_stay_out_of_the_config,
   test_report_counts_deviation_events_and_tracking_failures,
   test_no_measurements_means_unavailable_not_a_fake_zero, test_updates_are_rate_limited,
   test_recruiter_and_other_roles_see_it_only_where_they_may_review,
   test_attention_summary_is_purged_with_the_events
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/database_models.py, app/routers/interview_monitoring_routes.py
```
External packages: pytest, test_latency_and_monitoring, test_security_module

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Estimated visual attention: server storage rules, the report, and who can read it.

### 9. Viva explanation
> This is a test file. Estimated visual attention: server storage rules, the report, and who can read it.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_auth_and_permissions.py`

### 1. Purpose
Tests registration, login and the current-user endpoint, password rules, wrong-password lockout, password hashing, role-based access, recruiter approval, and that mentors and students can only see the data they are allowed to see.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 9 test(s), e.g.: register login me; password rules and duplicates; wrong password and lockout; passwords are hashed; role based access; recruiter requires approval; admin cannot demote self; mentor only sees assigned students; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_register_login_me, test_password_rules_and_duplicates,
   test_wrong_password_and_lockout, test_passwords_are_hashed, test_role_based_access,
   test_recruiter_requires_approval, test_admin_cannot_demote_self,
   test_mentor_only_sees_assigned_students, test_student_cannot_access_other_students_data
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/database_models.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Tests registration, login and the current-user endpoint, password rules, wrong-password lockout, password hashing, role-based access, recruiter approval, and that mentors and students can only see the data they are allowed to see.

### 9. Viva explanation
> This is a test file. Tests registration, login and the current-user endpoint, password rules, wrong-password lockout, password hashing, role-based access, recruiter approval, and that mentors and students can only see the data they are allowed to see.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_avatar_assets.py`

### 1. Purpose
The browser is only told about a high-detail avatar model when the file really exists (no wasted 404).

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 4 test(s), e.g.: missing hd model is not advertised; existing hd model is advertised; asset exists rejects unsafe urls; public does not mutate the persona.
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_missing_hd_model_is_not_advertised,
   test_existing_hd_model_is_advertised, test_asset_exists_rejects_unsafe_urls,
   test_public_does_not_mutate_the_persona
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/services/interview/interviewer_personalities.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: The browser is only told about a high-detail avatar model when the file really exists (no wasted 404).

### 9. Viva explanation
> This is a test file. The browser is only told about a high-detail avatar model when the file really exists (no wasted 404).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_deploy.py`

### 1. Purpose
Deployment features: shared rate limiter (memory / Redis), cross-site cookies, hosted-AI consent, Gemini speech recognition and the graceful-shutdown drain. Uses only the standard library and the slim cloud requirements, so it also runs in a requirements-cloud.txt environment (the Redis tests need `fakeredis`, otherwise they are skipped).

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 17 test(s), e.g.: memory limiter; redis limiter and shared state; login lockout uses redis when configured; redis outage falls back to memory; no redis url means memory; cookie is lax by default; cross site cookie is samesite none and secure; privacy info local; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: pcm_wav, _exercise, test_memory_limiter,
   test_redis_limiter_and_shared_state, test_login_lockout_uses_redis_when_configured,
   limiter_max, test_redis_outage_falls_back_to_memory, test_no_redis_url_means_memory,
   test_cookie_is_lax_by_default, test_cross_site_cookie_is_samesite_none_and_secure, hosted_ai,
   test_privacy_info_local, test_consent_required_before_ai_features_with_gemini,
   test_consent_at_registration_is_recorded, test_consent_not_needed_locally,
   test_wav_stats_without_numpy, test_gemini_stt_engine, test_gemini_stt_errors_are_readable,
   test_gemini_transcribe_request, test_drain_waits_for_background_jobs,
   test_drain_gives_up_after_the_deadline
```

**Classes:**
```text
   - _BrokenRedis
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/routers/authentication_routes.py,
   app/services/ai_models/gemini_api_client.py, app/services/ai_models/language_model_client.py,
   app/services/platform_support/background_jobs.py,
   app/services/platform_support/hosted_ai_consent.py,
   app/services/platform_support/rate_limiter.py, app/services/voice/speech_to_text.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Deployment features: shared rate limiter (memory / Redis), cross-site cookies, hosted-AI consent, Gemini speech recognition and the graceful-shutdown drain. Uses only the standard library and the slim cloud requirements, so it also runs in a requirements-cloud.txt environment (the Redis tests need `fakeredis`, otherwise they are skipped).

### 9. Viva explanation
> This is a test file. Deployment features: shared rate limiter (memory / Redis), cross-site cookies, hosted-AI consent, Gemini speech recognition and the graceful-shutdown drain. Uses only the standard library and the slim cloud requirements, so it also runs in a requirements-cloud.txt environment (the Redis tests need `

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_echoed_placeholders.py`

### 1. Purpose
The model copying the prompt's instructions back as content (seen 2026-11-05 on the interview report with the Ollama fallback) is treated as invalid output: retried once, then reported as unavailable.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 7 test(s), e.g.: exact bad payload is detected; genuine report with one count phrase is not flagged; conversation reply repeating the students words is not flagged; identical list items are flagged; report retries once after an echo and uses the real answer; report echoed twice is unavailable not shown; report prompt has no copyable count phrases.
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_exact_bad_payload_is_detected,
   test_genuine_report_with_one_count_phrase_is_not_flagged,
   test_conversation_reply_repeating_the_students_words_is_not_flagged,
   test_identical_list_items_are_flagged, ai_on, _fake,
   test_report_retries_once_after_an_echo_and_uses_the_real_answer,
   test_report_echoed_twice_is_unavailable_not_shown,
   test_report_prompt_has_no_copyable_count_phrases
```

### 5. Important variables
- Module-level constants: ECHOED_REPORT, GOOD_REPORT, QA

### 6. Connected files
```text
   Uses: app/services/ai_models/ai_structured_call_base.py,
   app/services/ai_models/language_model_client.py,
   app/services/interview/ai_interview_service.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: The model copying the prompt's instructions back as content (seen 2026-11-05 on the interview report with the Ollama fallback) is treated as invalid output: retried once, then reported as unavailable.

### 9. Viva explanation
> This is a test file. The model copying the prompt's instructions back as content (seen 2026-11-05 on the interview report with the Ollama fallback) is treated as invalid output: retried once, then reported as unavailable.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_english_avatar.py`

### 1. Purpose
Spoken-English avatar practice ("Aria"): persona output contract, live widgets, local transcription.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 11 test(s), e.g.: opening uses aria persona and style; reply contract is enforced; aria does not repeat her previous turn; repeat detection; whisper hallucinations are removed; spoken text has no emoji; empty model reply is an error not a silent turn; confidence meter rewards longer cleaner spoken answers; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
The LLM and STT are MOCKED here.

### 4. Important functions
```text
   - test_aria_does_not_repeat_her_previous_turn()
       Regression (real session): the model returned the identical reply to three different
       answers.
   Other helper functions: aria, start, test_opening_uses_aria_persona_and_style,
   test_reply_contract_is_enforced, test_repeat_detection,
   test_whisper_hallucinations_are_removed, test_spoken_text_has_no_emoji,
   test_empty_model_reply_is_an_error_not_a_silent_turn,
   test_confidence_meter_rewards_longer_cleaner_spoken_answers,
   test_live_active_time_matches_final_verified_time, test_english_stats_streak,
   test_english_transcribe_local
```

### 5. Important variables
- Module-level constants: REPEATED

### 6. Connected files
```text
   Uses: app/database_models.py, app/routers/english_practice_routes.py,
   app/services/interview/ai_interview_service.py, app/services/voice/speech_to_text.py
```
External packages: test_local_ai, test_voice

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Spoken-English avatar practice ("Aria"): persona output contract, live widgets, local transcription.

### 9. Viva explanation
> This is a test file. Spoken-English avatar practice ("Aria"): persona output contract, live widgets, local transcription.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_english_companion.py`

### 1. Purpose
English conversation companion: learning modes, topic following, conversation memory, no repeated questions.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 17 test(s), e.g.: topic switch is detected; no false topic switch; memory tracks topics details and skips sensitive items; modes differ in behaviour config; start stores mode and memory and uses companion persona; interview style is isolated from free talk; topic switch is followed and enforced; paraphrased question is rejected by meaning; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
The LLM is MOCKED (prompts are inspected); real-model behaviour is measured by eval/run_eval.py.

### 4. Important functions
```text
   - llm()
       MOCKED local LLM (accepts any extra keyword arguments the client may pass).
   - test_bad_corrections_from_the_real_model_are_dropped()
       Regressions from the real-model eval: a British spelling 'corrected', and a long
       rewrite of 'one match'.
   Other helper functions: turn, start, say, test_topic_switch_is_detected,
   test_no_false_topic_switch, test_memory_tracks_topics_details_and_skips_sensitive_items,
   test_modes_differ_in_behaviour_config,
   test_start_stores_mode_and_memory_and_uses_companion_persona,
   test_interview_style_is_isolated_from_free_talk, test_topic_switch_is_followed_and_enforced,
   test_paraphrased_question_is_rejected_by_meaning,
   test_free_conversation_spaces_out_corrections,
   test_learning_mode_speaks_a_gentle_correction_and_continues,
   test_repeated_reply_opener_is_dropped, test_companion_config_endpoint,
   test_old_sessions_without_memory_still_work, parse_sse,
   test_streamed_reply_sends_growing_text_then_the_saved_session,
   test_streamed_reply_reports_model_failure_without_saving,
   test_streamed_reply_is_private_to_the_owner
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/database_models.py, app/services/ai_models/language_model_client.py,
   app/services/english/english_companion_memory.py,
   app/services/interview/ai_interview_service.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: English conversation companion: learning modes, topic following, conversation memory, no repeated questions.

### 9. Viva explanation
> This is a test file. English conversation companion: learning modes, topic following, conversation memory, no repeated questions.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_english_profile.py`

### 1. Purpose
Recurring-mistake profile for the English companion. The language model is mocked.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 6 test(s), e.g.: classify known patterns; classify does not guess; a pattern becomes recurring only after enough corrections in enough sessions; the note is not sent in other learning modes; student can dismiss and clear and cannot touch anothers; deleting a session keeps the learning profile.
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_classify_known_patterns, test_classify_does_not_guess, llm,
   new_session, say,
   test_a_pattern_becomes_recurring_only_after_enough_corrections_in_enough_sessions,
   test_the_note_is_not_sent_in_other_learning_modes,
   test_student_can_dismiss_and_clear_and_cannot_touch_anothers,
   test_deleting_a_session_keeps_the_learning_profile
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/services/ai_models/language_model_client.py,
   app/services/english/english_mistake_profile.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Recurring-mistake profile for the English companion. The language model is mocked.

### 9. Viva explanation
> This is a test file. Recurring-mistake profile for the English companion. The language model is mocked.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_english_vocab.py`

### 1. Purpose
English vocabulary review (Leitner boxes), daily plan, progress and English milestone rewards. The language model is mocked.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 20 test(s), e.g.: knowing a card moves it up one box with a longer gap; not knowing sends any card back to box one for tomorrow; knowing a box five card masters it; out of range boxes are clamped; normalise ignores case spacing and end punctuation; corrections become review cards once; punctuation only corrections are not cards; review moves boxes and logs answers; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   - backdate()
       Verified time counts the gap before each student message, so move the session and
       Aria's opener back.
   Other helper functions: test_knowing_a_card_moves_it_up_one_box_with_a_longer_gap,
   test_not_knowing_sends_any_card_back_to_box_one_for_tomorrow,
   test_knowing_a_box_five_card_masters_it, test_out_of_range_boxes_are_clamped,
   test_normalise_ignores_case_spacing_and_end_punctuation, llm, start, say,
   test_corrections_become_review_cards_once, test_punctuation_only_corrections_are_not_cards,
   test_review_moves_boxes_and_logs_answers, test_mastering_a_card_awards_points_once,
   test_another_students_cards_are_invisible, test_students_can_add_and_delete_their_own_words,
   test_vocabulary_filters, test_daily_plan_without_any_data_has_conversation_and_interview,
   test_daily_plan_recommends_the_mode_for_the_weakest_skill_of_an_earlier_session,
   test_daily_plan_ticks_itself_and_awards_points_once,
   test_conversation_in_another_mode_does_not_tick_the_plan,
   test_progress_has_score_trend_and_weekly_reviews, test_word_badges_are_awarded,
   test_weekly_review_challenge_counts_reviews,
   test_seed_adds_english_rewards_and_stays_repeatable
```

### 5. Important variables
- Module-level constants: NOW, FIX

### 6. Connected files
```text
   Uses: app/database_models.py, app/mongodb_data_layer/__init__.py, app/seed_initial_data.py,
   app/services/ai_models/language_model_client.py,
   app/services/english/english_vocabulary_trainer.py,
   app/services/student_progress/rewards_and_badges.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: English vocabulary review (Leitner boxes), daily plan, progress and English milestone rewards. The language model is mocked.

### 9. Viva explanation
> This is a test file. English vocabulary review (Leitner boxes), daily plan, progress and English milestone rewards. The language model is mocked.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_features.py`

### 1. Purpose
Tests for the extended feature set: English learning, coding tests, readiness, challenges, recruiter communication/assignments, mentor tools and admin management.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 9 test(s), e.g.: speaking drills are not available to students; challenge completes once per period; coding assessment pending then ai review; readiness report history and role recs; settings preferences and consent; recruiter messages assignment on hold export; mentor dashboard cards remedies and reports; admin announcements drives challenges verification; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   - test_speaking_drills_are_not_available_to_students()
       The pronunciation/speaking drill feature was removed from the student portal
       (2026-10-11).
   Other helper functions: _recruiter, test_challenge_completes_once_per_period,
   test_coding_assessment_pending_then_ai_review, test_readiness_report_history_and_role_recs,
   test_settings_preferences_and_consent, test_recruiter_messages_assignment_on_hold_export,
   test_mentor_dashboard_cards_remedies_and_reports,
   test_admin_announcements_drives_challenges_verification,
   test_interview_difficulty_and_sample_answers
```

### 5. Important variables
- Module-level constants: CODING_TEST

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_models.py,
   app/services/interview/ai_interview_service.py,
   app/services/student_progress/rewards_and_badges.py
```
External packages: bson

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Tests for the extended feature set: English learning, coding tests, readiness, challenges, recruiter communication/assignments, mentor tools and admin management.

### 9. Viva explanation
> This is a test file. Tests for the extended feature set: English learning, coding tests, readiness, challenges, recruiter communication/assignments, mentor tools and admin management.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_gemini.py`

### 1. Purpose
Gemini provider (services/ai_models/gemini_api_client.py) and the Ollama fallback in local_llm. No real API is called: the HTTP client is replaced by a fake that replays Server-Sent Events.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 15 test(s), e.g.: streams json and skips thought parts; retries rate limit and server errors; unsupported thinking option is downgraded; timeout is not retried and starts cooldown; cut off answer is an error; falls back to ollama when gemini fails; no fallback after text was streamed; status picks newest flash when configured model is missing; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: sse, text_chunk, gemini, test_streams_json_and_skips_thought_parts,
   test_retries_rate_limit_and_server_errors, test_unsupported_thinking_option_is_downgraded,
   test_timeout_is_not_retried_and_starts_cooldown, test_cut_off_answer_is_an_error,
   test_falls_back_to_ollama_when_gemini_fails, test_no_fallback_after_text_was_streamed,
   test_status_picks_newest_flash_when_configured_model_is_missing,
   test_missing_key_reports_setup_hint, test_routing_uses_gemini_tier_models, _with_backup,
   test_overloaded_model_switches_to_backup_without_waiting, test_slow_model_switches_to_backup,
   test_backup_not_offered_to_key_is_skipped, test_cut_off_json_retries_on_backup_model,
   test_streamed_reply_is_never_restarted_on_bad_json
```

**Classes:**
```text
   - FakeResponse
   - FakeHttp
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/ai_models/ai_task_model_router.py,
   app/services/ai_models/gemini_api_client.py, app/services/ai_models/language_model_client.py
```
External packages: httpx, pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Gemini provider (services/ai_models/gemini_api_client.py) and the Ollama fallback in local_llm. No real API is called: the HTTP client is replaced by a fake that replays Server-Sent Events.

### 9. Viva explanation
> This is a test file. Gemini provider (services/ai_models/gemini_api_client.py) and the Ollama fallback in local_llm. No real API is called: the HTTP client is replaced by a fake that replays Server-Sent Events.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_health_and_routing.py`

### 1. Purpose
Health endpoints, request IDs and per-task model routing. No real model is used.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 6 test(s), e.g.: liveness needs nothing; readiness reports components and never fails for missing ai; request id is returned and unsafe ids are replaced; placeholder secret key is refused only when served securely; router defaults to the main model and follows tier settings; a routed model that is not downloaded falls back to the main model.
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_liveness_needs_nothing,
   test_readiness_reports_components_and_never_fails_for_missing_ai,
   test_request_id_is_returned_and_unsafe_ids_are_replaced,
   test_placeholder_secret_key_is_refused_only_when_served_securely,
   test_router_defaults_to_the_main_model_and_follows_tier_settings,
   test_a_routed_model_that_is_not_downloaded_falls_back_to_the_main_model
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/main.py,
   app/services/ai_models/ai_task_model_router.py,
   app/services/ai_models/language_model_client.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Health endpoints, request IDs and per-task model routing. No real model is used.

### 9. Viva explanation
> This is a test file. Health endpoints, request IDs and per-task model routing. No real model is used.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_integrity_detectors.py`

### 1. Purpose
Integrity detectors added on top of the camera monitoring: paste, full screen / second display, phone or notes.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 9 test(s), e.g.: new detectors are never high severity; paste is informational and long pastes escalate only when repeated; phone needs duration and confidence for medium; policy discloses new features and marks them optional; new events are stored only with their own consent; new events get server side severity; repeated long pastes escalate across batches; object detection is switched off without camera; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: _events, _send, test_new_detectors_are_never_high_severity,
   test_paste_is_informational_and_long_pastes_escalate_only_when_repeated,
   test_phone_needs_duration_and_confidence_for_medium,
   test_policy_discloses_new_features_and_marks_them_optional,
   test_new_events_are_stored_only_with_their_own_consent,
   test_new_events_get_server_side_severity, test_repeated_long_pastes_escalate_across_batches,
   test_object_detection_is_switched_off_without_camera, test_unknown_event_type_is_rejected
```

### 5. Important variables
- Module-level constants: ALL

### 6. Connected files
```text
   Uses: app/database_connection.py, app/database_models.py,
   app/services/monitoring/interview_integrity_rules.py
```
External packages: test_latency_and_monitoring

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Integrity detectors added on top of the camera monitoring: paste, full screen / second display, phone or notes.

### 9. Viva explanation
> This is a test file. Integrity detectors added on top of the camera monitoring: paste, full screen / second display, phone or notes.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_interview_engine.py`

### 1. Purpose
Deterministic interview intelligence (no model): context, answer signals, coverage, duplicates, fallbacks.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 13 test(s), e.g.: context includes project details but not soft skills; answer signals; strong answer has no vagueness signals; paraphrases are duplicates without embeddings; different followups on the same project are allowed; semantic and concept checks; coverage tracks aspects and suggests open ones; output checks; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: test_context_includes_project_details_but_not_soft_skills,
   test_answer_signals, test_strong_answer_has_no_vagueness_signals,
   test_paraphrases_are_duplicates_without_embeddings,
   test_different_followups_on_the_same_project_are_allowed, test_semantic_and_concept_checks,
   test_coverage_tracks_aspects_and_suggests_open_ones, test_output_checks,
   test_fallback_is_grounded_and_never_repeats,
   test_topic_is_derived_from_the_resume_not_generated, test_greeting_with_comma_is_removed,
   test_candidate_name_is_not_given_to_the_question_writer, test_history_block_compacts_old_turns
```

### 5. Important variables
- Module-level constants: ANALYSIS, DUPLICATES, DIFFERENT

### 6. Connected files
```text
   Uses: app/services/interview/ai_interview_service.py,
   app/services/interview/interview_intelligence_rules.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Deterministic interview intelligence (no model): context, answer signals, coverage, duplicates, fallbacks.

### 9. Viva explanation
> This is a test file. Deterministic interview intelligence (no model): context, answer signals, coverage, duplicates, fallbacks.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_interview_intelligence.py`

### 1. Purpose
Interview intelligence wired into the interview API: resume-grounded prompts, answer signals, coverage, duplicate rejection with retries, fallbacks and per-personality behaviour. The LLM is MOCKED (prompts are inspected); real-model behaviour is measured by eval/run_eval.py.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 9 test(s), e.g.: prompt uses full resume facts and stage; vague answer signal reaches the prompt and metadata is stored; paraphrased duplicate is rejected and regenerated; repeated failures use a resume grounded fallback not a loop; clarifying followup on same aspect is allowed; repeat request allows asking again; stock praise is removed from the spoken question; each personality adds its own behaviour rules; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: q, student, start, answer, q_prompts,
   test_prompt_uses_full_resume_facts_and_stage,
   test_vague_answer_signal_reaches_the_prompt_and_metadata_is_stored,
   test_paraphrased_duplicate_is_rejected_and_regenerated,
   test_repeated_failures_use_a_resume_grounded_fallback_not_a_loop,
   test_clarifying_followup_on_same_aspect_is_allowed, test_repeat_request_allows_asking_again,
   test_stock_praise_is_removed_from_the_spoken_question,
   test_each_personality_adds_its_own_behaviour_rules,
   test_personality_configs_are_distinct_and_public_part_hides_prompts
```

### 5. Important variables
- Module-level constants: ANALYSIS

### 6. Connected files
```text
   Uses: app/database_models.py, app/services/interview/interviewer_personalities.py
```
External packages: pytest, test_local_ai

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Interview intelligence wired into the interview API: resume-grounded prompts, answer signals, coverage, duplicate rejection with retries, fallbacks and per-personality behaviour. The LLM is MOCKED (prompts are inspected); real-model behaviour is measured by eval/run_eval.py.

### 9. Viva explanation
> This is a test file. Interview intelligence wired into the interview API: resume-grounded prompts, answer signals, coverage, duplicate rejection with retries, fallbacks and per-personality behaviour. The LLM is MOCKED (prompts are inspected); real-model behaviour is measured by eval/run_eval.py.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_interviewers.py`

### 1. Purpose
Interviewer personalities: selection list, per-personality behaviour, fair scoring and the report.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 10 test(s), e.g.: interviewer list is public but prompts stay private; default is aria and unknown interviewer rejected; each personality gets its own instructions; greeting is not repeated in the question; followup and hint policies differ; scores do not depend on the interviewer; difficulty steps depend on interviewer; report has dimensions indicators and closing remarks; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
The LLM is MOCKED (prompts are inspected); real-model checks are in tests_integration and tests_e2e.

### 4. Important functions
```text
   - test_greeting_is_not_repeated_in_the_question()
       Regression (real model): Aria's first question started 'Hi Priya!
   - test_revision_topics_are_deduplicated()
       Regression (real run): near-identical missing concepts were listed separately.
   Other helper functions: start, answer,
   test_interviewer_list_is_public_but_prompts_stay_private,
   test_default_is_aria_and_unknown_interviewer_rejected,
   test_each_personality_gets_its_own_instructions, test_followup_and_hint_policies_differ,
   test_scores_do_not_depend_on_the_interviewer, test_difficulty_steps_depend_on_interviewer,
   test_report_has_dimensions_indicators_and_closing_remarks,
   test_report_numbers_survive_ai_outage
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/services/ai_models/language_model_client.py,
   app/services/interview/ai_interview_service.py,
   app/services/interview/interview_report_metrics.py
```
External packages: pytest, test_local_ai

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Interviewer personalities: selection list, per-personality behaviour, fair scoring and the report.

### 9. Viva explanation
> This is a test file. Interviewer personalities: selection list, per-personality behaviour, fair scoring and the report.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_latency_and_monitoring.py`

### 1. Purpose
Streamed interview turns, response modes, performance metrics and camera-monitoring integrity events.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 18 test(s), e.g.: partial json string handles unfinished values and escapes; split complete never cuts words or abbreviations; spoken stream emits preface then question and skips greeting; ollama url avoids slow localhost lookup; question starting like a greeting is still spoken; long first sentence split at a natural pause only; live interview prefetches first question and streams turns; turn lock blocks concurrent turns; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
All model calls are MOCKED (no Ollama/Kokoro): these tests prove the pipeline logic, ordering, access control and privacy rules. Real latency is measured by tests_perf/bench_interview_latency.py and tests_e2e/.

### 4. Important functions
```text
   - test_ollama_url_avoids_slow_localhost_lookup()
       Windows: 'localhost' tried IPv6 first and cost ~2.1 s per connection to Ollama
       (measured).
   - test_question_starting_like_a_greeting_is_still_spoken()
       Regression (browser run): "Hi Priya, how did you ...?" matched the greeting filter and
       was never spoken.
   - streaming_ai()
       Fake model that streams its question JSON through on_delta like Ollama does, plus fake
       TTS.
   Other helper functions: _join_background_threads, parse_sse,
   test_partial_json_string_handles_unfinished_values_and_escapes,
   test_split_complete_never_cuts_words_or_abbreviations,
   test_spoken_stream_emits_preface_then_question_and_skips_greeting,
   test_long_first_sentence_split_at_a_natural_pause_only, _start, _wait_question,
   test_live_interview_prefetches_first_question_and_streams_turns,
   test_turn_lock_blocks_concurrent_turns, test_repeated_question_is_retracted_and_replaced,
   test_text_mode_start_is_unchanged, test_perf_metrics_whitelisted_and_admin_only, _consent,
   test_policy_discloses_processing_retention_and_access,
   test_events_only_for_consented_features_with_server_side_severity,
   test_attention_signal_never_above_low_and_no_score_change,
   test_camera_required_setting_blocks_start_without_camera,
   test_withdraw_stops_recording_events, test_reviewer_access_is_least_privilege_and_audited,
   test_expired_events_are_purged
```

### 5. Important variables
- Module-level constants: FEATURES

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/routers/interview_monitoring_routes.py, app/routers/interview_routes.py,
   app/services/ai_models/language_model_client.py,
   app/services/interview/ai_interview_service.py,
   app/services/monitoring/interview_integrity_rules.py,
   app/services/voice/streamed_reply_sentence_splitter.py, app/services/voice/text_to_speech.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Streamed interview turns, response modes, performance metrics and camera-monitoring integrity events.

### 9. Viva explanation
> This is a test file. Streamed interview turns, response modes, performance metrics and camera-monitoring integrity events.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_live_notifications_and_recruiter.py`

### 1. Purpose
Live notification stream (SSE) and the recruiter comparison / candidate report endpoints.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 11 test(s), e.g.: notify signals only after commit; failing after commit hook does not break commit; stream requires login; stream delivers new notification and heartbeats; mark read signals other tabs; stream limit per user; publish reaches only that user; compare two to four applicants with breakdown; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: _recruiter, _job, short_streams, _events,
   test_notify_signals_only_after_commit, test_failing_after_commit_hook_does_not_break_commit,
   test_stream_requires_login, test_stream_delivers_new_notification_and_heartbeats,
   test_mark_read_signals_other_tabs, test_stream_limit_per_user,
   test_publish_reaches_only_that_user, _two_applicants,
   test_compare_two_to_four_applicants_with_breakdown,
   test_compare_and_report_respect_recruiter_ownership, test_candidate_report_contents_and_audit,
   test_integrity_overview_only_when_shared
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/services/platform_support/audit_and_notification_helpers.py,
   app/services/platform_support/live_notification_events.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Live notification stream (SSE) and the recruiter comparison / candidate report endpoints.

### 9. Viva explanation
> This is a test file. Live notification stream (SSE) and the recruiter comparison / candidate report endpoints.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_local_ai.py`

### 1. Purpose
Tests for the local-AI features.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 48 test(s), e.g.: resume valid analysis removes invented items; resume validation rejects sentences and duplicate internships; evaluation never leaves student without improvements; resume prompt fences untrusted text; resume empty file rejected; resume without text rejected; resume corrupted file rejected without internals; resume unsupported type rejected; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
ALL tests in this file use MOCKED model output (a fake `local_llm.chat_json` and a fake embedding function). They prove the plumbing, validation, scoring rules, persistence and access control work. They do NOT prove the quality of the real model's answers - see tests_integration/ for checks against the real local models.

### 4. Important functions
```text
   - resume_json()
       MOCK model output.
   - mock_llm()
       MOCKED local LLM.
   - feedback_json()
       MOCK detailed feedback (generated in the background after the answer is scored).
   - test_background_generation_gives_way_to_interactive()
       A background request (detailed feedback) is cancelled when a candidate-facing request
       is waiting.
   - test_interactive_hold_keeps_background_generation_out()
       While a turn is speaking/transcribing (CPU-heavy), background generations neither
       start nor continue.
   - test_off_topic_answer_is_capped_even_if_model_is_generous()
       Regression for a real case: a model gave 100/100 to an answer about indexes for a
       different question.
   Other helper functions: docx_bytes, upload, question_json, question_prompts, eval_json,
   test_resume_valid_analysis_removes_invented_items,
   test_resume_validation_rejects_sentences_and_duplicate_internships,
   test_evaluation_never_leaves_student_without_improvements,
   test_resume_prompt_fences_untrusted_text, test_resume_empty_file_rejected,
   test_resume_without_text_rejected, test_resume_corrupted_file_rejected_without_internals,
   test_resume_unsupported_type_rejected,
   test_resume_invalid_model_output_is_not_saved_as_success,
   test_resume_invalid_then_valid_output_retries, test_resume_model_not_downloaded,
   test_resume_ollama_not_running, test_student_can_correct_analysis_and_score_updates, _start,
   test_interview_questions_are_personalised, test_answer_evaluation_stored_with_details,
   test_short_answer_is_capped_by_rules, test_adaptive_difficulty_goes_down_with_explanation,
   test_adaptive_difficulty_goes_up_after_strong_answer, test_repeated_question_is_replaced,
   test_transient_ai_failure_affects_only_one_question, test_next_question_recovery,
   test_ollama_runner_crash_is_retried_once, test_priority_gate_serves_interactive_first,
   test_is_repeat_detects_rephrasing, test_model_says_answer_misses_question,
   test_answer_rules_unit, test_missing_interview_session,
   test_cannot_answer_other_students_interview_or_skip, test_interview_subject_validation, cand,
   match, test_match_strong, test_match_partial_uses_related_skill, test_match_weak,
   test_missing_required_skills_cap_score, test_skill_found_in_project_text_counts,
   test_match_empty_profile, test_match_empty_job_description,
   test_match_invalid_embedding_output_falls_back, test_match_embedding_unavailable_falls_back,
   test_eligibility_issue_blocks_strong_fit, test_skill_aliases, test_status_without_api_key,
   test_apply_uses_semantic_match_when_embeddings_available, test_ai_usage_log_records_success,
   test_resume_isolation_between_students, test_question_classifier_prediction
```

**Classes:**
```text
   - _Ctx
```

### 5. Important variables
- Module-level constants: RESUME_TEXT, JOB

### 6. Connected files
```text
   Uses: app/database_models.py, app/routers/interview_routes.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/question_type_classifier.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/interview/ai_interview_service.py,
   app/services/resume_and_jobs/semantic_job_matcher.py,
   app/services/resume_and_jobs/skill_name_normalizer.py
```
External packages: docx, httpx, numpy, pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Tests for the local-AI features.

### 9. Viva explanation
> This is a test file. Tests for the local-AI features.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_odm.py`

### 1. Purpose
The MongoDB data layer (app/mongodb_data_layer.py): SQL semantics the routers rely on.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 14 test(s), e.g.: ids defaults and roundtrip; only changed fields are written; in place json changes are saved; unique constraint raises and flush is undone; null values do not collide in unique constraints; begin nested skips only the failing row; relationships one to one one to many and orphans; delete cascades and sets null; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   - test_null_values_do_not_collide_in_unique_constraints()
       uq_integrity_client_event covers a nullable column: like SQL, several NULLs are
       allowed.
   Other helper functions: _user, test_ids_defaults_and_roundtrip,
   test_only_changed_fields_are_written, test_in_place_json_changes_are_saved,
   test_unique_constraint_raises_and_flush_is_undone,
   test_begin_nested_skips_only_the_failing_row,
   test_relationships_one_to_one_one_to_many_and_orphans, test_delete_cascades_and_sets_null,
   test_set_null_on_delete, test_where_semantics_joins_groups_and_ordering,
   test_bulk_update_refreshes_loaded_objects, test_rollback_reloads_and_unique_partial_insert,
   test_onupdate_timestamp, test_unique_student_badge
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/database_models.py, app/mongodb_data_layer/__init__.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: The MongoDB data layer (app/mongodb_data_layer.py): SQL semantics the routers rely on.

### 9. Viva explanation
> This is a test file. The MongoDB data layer (app/mongodb_data_layer.py): SQL semantics the routers rely on.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_scoring_calibration.py`

### 1. Purpose
Scoring post-processing added after the 2026-11-04 calibration run (eval/calibrate_scoring.py).

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 7 test(s), e.g.: completeness counts when rubric leaves it out; rubric with completeness is used as is; uniform scores unchanged; open question skips similarity cap; open question still trusts the model; score bands; prompt has anchors.
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   - test_open_question_skips_similarity_cap()
       Strong project answers to an open question measured 0.13-0.17 similarity with the real
       MiniLM model.
   Other helper functions: _ev, test_completeness_counts_when_rubric_leaves_it_out,
   test_rubric_with_completeness_is_used_as_is, test_uniform_scores_unchanged,
   test_open_question_still_trusts_the_model, test_score_bands, test_prompt_has_anchors
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/routers/interview_routes.py, app/services/interview/ai_interview_service.py,
   app/services/interview/score_band_labels.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Scoring post-processing added after the 2026-11-04 calibration run (eval/calibrate_scoring.py).

### 9. Viva explanation
> This is a test file. Scoring post-processing added after the 2026-11-04 calibration run (eval/calibrate_scoring.py).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_security_module.py`

### 1. Purpose
Interview security module (2026-10-23): event engine (validation, idempotency, time window, rate limit), session reconnects, admin security settings, recruiter access, review history and the risk summary.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 15 test(s), e.g.: own interview events carry taxonomy details and wall clock; cannot post to or read another candidates interview; duplicate events are stored once; malformed events are rejected; too many events in one request rejected; expired interview and future timestamps; rate limit; reconsent records reconnect and keeps the interview clock; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
Detector outputs are SIMULATED here (events posted as the browser would send them). These tests prove the server's rules; they say nothing about how well the on-device computer vision works - see README for the camera checks.

### 4. Important functions
```text
   Other helper functions: _start, _events, _finish, _recruiter,
   test_own_interview_events_carry_taxonomy_details_and_wall_clock,
   test_cannot_post_to_or_read_another_candidates_interview,
   test_duplicate_events_are_stored_once, test_malformed_events_are_rejected,
   test_too_many_events_in_one_request_rejected, test_expired_interview_and_future_timestamps,
   test_rate_limit, test_reconsent_records_reconnect_and_keeps_the_interview_clock,
   test_session_events_need_some_consent_but_not_a_specific_feature,
   test_security_settings_admin_only_validated_audited_and_applied,
   test_monitoring_can_be_switched_off_by_policy, _applied_student,
   test_recruiter_sees_only_completed_interviews_of_own_applicants,
   test_recruiter_access_requires_disclosure_at_consent, test_reviewer_filters, _ev,
   test_risk_summary_aggregates_caps_and_excludes_uncertain_or_cleared
```

### 5. Important variables
- Module-level constants: ALL

### 6. Connected files
```text
   Uses: app/database_models.py, app/routers/interview_monitoring_routes.py,
   app/services/monitoring/interview_integrity_rules.py,
   app/services/platform_support/rate_limiter.py
```
External packages: pytest, test_latency_and_monitoring

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Interview security module (2026-10-23): event engine (validation, idempotency, time window, rate limit), session reconnects, admin security settings, recruiter access, review history and the risk summary.

### 9. Viva explanation
> This is a test file. Interview security module (2026-10-23): event engine (validation, idempotency, time window, rate limit), session reconnects, admin security settings, recruiter access, review history and the risk summary.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_voice.py`

### 1. Purpose
Voice-interview API tests. TTS/STT engines are MOCKED here (real engines: tests_integration/test_voice_real.py).

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 12 test(s), e.g.: voice endpoints require login; speak reports disabled engine honestly; speak returns audio and visemes; viseme timeline from durations; pronunciation normalisation; transcribe mocked then submit through existing answer api; live captions have their own rate limit; transcribe rejects wrong question other student and recruiter; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: wav_bytes, start_interview, send, test_voice_endpoints_require_login,
   test_speak_reports_disabled_engine_honestly, test_speak_returns_audio_and_visemes,
   test_viseme_timeline_from_durations, test_pronunciation_normalisation,
   test_transcribe_mocked_then_submit_through_existing_answer_api,
   test_live_captions_have_their_own_rate_limit,
   test_transcribe_rejects_wrong_question_other_student_and_recruiter,
   test_transcribe_when_stt_disabled_suggests_typing, test_transcribe_finished_interview_refused,
   test_bad_and_silent_audio, test_speech_activity_measure
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/routers/voice_speech_routes.py,
   app/services/platform_support/rate_limiter.py, app/services/voice/speech_to_text.py,
   app/services/voice/text_to_speech.py
```
External packages: numpy, pytest, soundfile, test_local_ai

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Voice-interview API tests. TTS/STT engines are MOCKED here (real engines: tests_integration/test_voice_real.py).

### 9. Viva explanation
> This is a test file. Voice-interview API tests. TTS/STT engines are MOCKED here (real engines: tests_integration/test_voice_real.py).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests/test_workflows.py`

### 1. Purpose
End-to-end API workflow tests: AI unavailability is reported (never faked), non-resume files are rejected, a full interview with rewards and mentor goals, short or pasted answers earn no points / are flagged, verified English practice time, the recruiter job-application cycle, eligibility, assessment grading, and admin settings / rubric validation.

### 2. What does it do?
1. Automated test (pytest, mocked AI - no real model needed).
2. Contains 10 test(s), e.g.: ai unavailable is reported not faked; rejects non resume files; full interview flow with rewards and mentor goal; short answers earn no points; pasted duplicate answers are flagged; english active time is verified; recruiter job application cycle; ineligible student cannot apply; ....
3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: _docx_bytes, _make_recruiter,
   test_ai_unavailable_is_reported_not_faked, test_rejects_non_resume_files,
   test_full_interview_flow_with_rewards_and_mentor_goal, test_short_answers_earn_no_points,
   test_pasted_duplicate_answers_are_flagged, test_english_active_time_is_verified,
   test_recruiter_job_application_cycle, test_ineligible_student_cannot_apply,
   test_assessment_grading_and_answer_secrecy, test_admin_settings_and_rubric_validation
```

### 5. Important variables
- Module-level constants: RESUME

### 6. Connected files
```text
   Uses: app/database_models.py
```
External packages: docx

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: End-to-end API workflow tests: AI unavailability is reported (never faked), non-resume files are rejected, a full interview with rewards and mentor goals, short or pasted answers earn no points / are flagged, verified English practice time, the recruiter job-application cycle, eligibility, assessment grading, and admin settings / rubric validation.

### 9. Viva explanation
> This is a test file. End-to-end API workflow tests: AI unavailability is reported (never faked), non-resume files are rejected, a full interview with rewards and mentor goals, short or pasted answers earn no points / are flagged, verified English practice time, the recruiter job-application cycle, eligibility, assessmen

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

# Backend - browser end-to-end tests

## File: `backend/tests_e2e/account_browser.py`

### 1. Purpose
Real-browser check of the account features and the merged student pages.

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Covers: forgot password -> reset link -> new password works (old one doesn't), the merged "My Progress" and "Jobs & Drives" pages (old URLs redirect to the right tab), and "Delete my account". Email is off in development, so the reset token is created here the same way the server does (same secret, same database). Run from backend with the backend + frontend running: .\venv\Scripts\python.exe tests_e2e\account_browser.py

### 4. Important functions
```text
   Other helper functions: ok, reset_token
```

### 5. Important variables
- Module-level constants: OUT, BASE, EMAIL

### 6. Connected files
```text
   Uses: app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
   app/password_and_token_security.py
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Real-browser check of the account features and the merged student pages.

### 9. Viva explanation
> This is a test file. Real-browser check of the account features and the merged student pages.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/attention_browser.py`

### 1. Purpose
Visual-attention percentage, end to end in a real browser (headless Chromium, fake camera + fake microphone).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
REAL: the app and backend, MediaPipe face analysis in the browser, the attention meter, the live card, the upload of cumulative totals, the stored report. SIMULATED: the person - the fake camera plays the app's own synthetic 3D interviewer (not a real person) facing the camera, with the head turned 45 degrees, and an empty room. This is NOT a test with a human face, glasses, real lighting or a real webcam. Fake camera timeline (seconds after the camera opens, loops): 0-25 facing | 25-40 head turned | 40-60 facing | 60-70 nobody in view | 70-90 facing. Checks, independent of the meter: while polling the page every 0.5 s the test counts for itself what the monitor saw (dev hook window.__hsMoni...

### 4. Important functions
```text
   Other helper functions: say, ok, api, render_heads, make_video, setup_and_start, report
```

### 5. Important variables
- Module-level constants: HERE, OUT, MIC, BASE, STUDENT, TIMELINE, LOGIN, FETCH

### 6. Connected files
```text
Standalone.
```
External packages: PIL, numpy, playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Visual-attention percentage, end to end in a real browser (headless Chromium, fake camera + fake microphone).

### 9. Viva explanation
> This is a test file. Visual-attention percentage, end to end in a real browser (headless Chromium, fake camera + fake microphone).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/avatar_snapshot.py`

### 1. Purpose
Browser check: the realistic 3D interviewer loads, has its viseme blendshapes, and renders.

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Saves tests_e2e/output/avatar_idle.png (and avatar_speaking_*.png if --speak). Run from backend: .\venv\Scripts\python.exe tests_e2e\avatar_snapshot.py [--speak]

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
- Module-level constants: OUT, BASE, CREDS

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Browser check: the realistic 3D interviewer loads, has its viseme blendshapes, and renders.

### 9. Viva explanation
> This is a test file. Browser check: the realistic 3D interviewer loads, has its viseme blendshapes, and renders.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/camera_preview_browser.py`

### 1. Purpose
Browser check: the optional camera preview starts only on click and is released on "Hide".

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Uses Chromium's fake camera. Run from the backend folder: .\venv\Scripts\python.exe tests_e2e\camera_preview_browser.py

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
- Module-level constants: OUT, BASE, CREDS

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Browser check: the optional camera preview starts only on click and is released on "Hide".

### 9. Viva explanation
> This is a test file. Browser check: the optional camera preview starts only on click and is released on "Hide".

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/ci_smoke_browser.py`

### 1. Purpose
Fast browser smoke test, run by CI on every push (no GPU, no AI models, no demo accounts needed).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Registers a fresh student, opens the main student pages and checks that each renders without an uncaught page error, then runs one live (voice-room) interview turn by typing: setup screen with the fake camera, the room's control bar, settings and transcript panels, a typed answer, and the next question from the question bank. Needs the backend (any AI settings; CI runs it with AI_ENABLED=false) and the frontend (dev server or `vite preview`). From the backend folder: python tests_e2e/ci_smoke_browser.py # HS_E2E_BASE=http://127.0.0.1:4173 for vite preview

### 4. Important functions
```text
   Other helper functions: ok, api, settle
```

### 5. Important variables
- Module-level constants: OUT, BASE, EMAIL, PASSWORD, FETCH, INIT, PAGES

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Fast browser smoke test, run by CI on every push (no GPU, no AI models, no demo accounts needed).

### 9. Viva explanation
> This is a test file. Fast browser smoke test, run by CI on every push (no GPU, no AI models, no demo accounts needed).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/consent_browser.py`

### 1. Purpose
Real-browser check of the hosted-AI consent flow (cloud profile, LOCAL_AI_PROVIDER=gemini).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Needs a backend started with LOCAL_AI_PROVIDER=gemini (a Gemini key is not needed: the AI is reported offline and interviews use the question bank) and the frontend pointing at it. Example (two terminals, from backend): set LOCAL_AI_PROVIDER=gemini& set GEMINI_API_KEY=& set MONGODB_DB=hiresense_e2e_consent .\venv\Scripts\python.exe -m uvicorn app.main:app --port 8023 (frontend) set HS_API=http://127.0.0.1:8023& npx vite --port 5193 set HS_E2E_BASE=http://localhost:5193& .\venv\Scripts\python.exe tests_e2e\consent_browser.py Checks: the register checkbox and /privacy say Google; without consent the interview page shows the notice and the API refuses to start (428); "I agree" removes it; the S...

### 4. Important functions
```text
   Other helper functions: ok
```

### 5. Important variables
- Module-level constants: OUT, BASE, EMAIL, START

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Real-browser check of the hosted-AI consent flow (cloud profile, LOCAL_AI_PROVIDER=gemini).

### 9. Viva explanation
> This is a test file. Real-browser check of the hosted-AI consent flow (cloud profile, LOCAL_AI_PROVIDER=gemini).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/english_avatar_browser.py`

### 1. Purpose
Real-browser end-to-end test of spoken-English practice with Aria (Chromium via Playwright).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Pass 1 - "local" voice: Kokoro TTS (phoneme lip sync) + fake microphone -> local Whisper -> Aria (local LLM). Pass 2 - "browser" voice: /api/voice/status is answered as "TTS and STT off", so the page uses the browser's speechSynthesis (approximate lip sync) and typed replies. Both passes then end the session and check the score report and that the avatar, audio and mic are released. Run (backend + frontend + Ollama running), from the backend folder: .\venv\Scripts\python.exe tests_e2e\english_avatar_browser.py Uses the seeded demo student unless HS_E2E_EMAIL / HS_E2E_PASSWORD are set. Screenshots go to tests_e2e/output/.

### 4. Important functions
```text
   - make_student_audio()
       The fake microphone plays this: ~3 s of silence (hesitation), a short spoken reply,
       then silence.
   Other helper functions: say, run_pass
```

### 5. Important variables
- Module-level constants: HERE, OUT, MIC, BASE, INIT, SAMPLE

### 6. Connected files
```text
   Uses: app/services/voice/text_to_speech.py
```
External packages: numpy, playwright, soundfile

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Real-browser end-to-end test of spoken-English practice with Aria (Chromium via Playwright).

### 9. Viva explanation
> This is a test file. Real-browser end-to-end test of spoken-English practice with Aria (Chromium via Playwright).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/face_video_check.py`

### 1. Purpose
Camera-analysis check with a face in view (Chromium fake camera fed with a generated video).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Chromium's default fake camera shows a test pattern without a face, so the main E2E only exercises "face not visible". This script builds a looping fake-camera video from the app's own synthetic 3D interviewer (Rocketbox model, not a real person; taken from an earlier E2E screenshot) and checks, on the setup screen and in the room: * 0-12 s one face, centred -> "face is visible", no warning * 12-24 s two faces -> "More than one face" guidance, warning after the grace period, event stored * 24-36 s one face at the edge -> "move ... center" guidance Needs backend + frontend running (no AI calls beyond the first question). From the backend folder: .\venv\Scripts\python.exe tests_e2e\face_video_...

### 4. Important functions
```text
   Other helper functions: rgba_to_i420, make_video, ok
```

### 5. Important variables
- Module-level constants: HERE, SRC, BASE, SEGMENT_S, COMPOSE

### 6. Connected files
```text
Standalone.
```
External packages: numpy, playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Camera-analysis check with a face in view (Chromium fake camera fed with a generated video).

### 9. Viva explanation
> This is a test file. Camera-analysis check with a face in view (Chromium fake camera fed with a generated video).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/interviewers_browser.py`

### 1. Purpose
Real-browser end-to-end test of the multi-interviewer experience (Chromium via Playwright).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
1. Selection screen: 4 interviewer cards with live 3D previews, filters, a voice preview that is lip-synced. 2. Full VOICE interview with Victor: his own 3D model and voice, greeting -> speaking -> listening -> reaction -> thinking states, mouth moving only with audio, true pause/resume, fake-microphone answer transcribed by local Whisper, a real follow-up from the local LLM, report with skill breakdown + Victor's spoken closing remarks, and microphone/audio released at the end. 3. Stress interview with Marcus: the answer is stopped at the (shortened, test-only) time limit and stored as interrupted. Run (backend + frontend + Ollama running), from the backend folder: .\venv\Scripts\python.exe...

### 4. Important functions
```text
   Other helper functions: say, main
```

### 5. Important variables
- Module-level constants: HERE, OUT, MIC, BASE, INIT, SAMPLE

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Real-browser end-to-end test of the multi-interviewer experience (Chromium via Playwright).

### 9. Viva explanation
> This is a test file. Real-browser end-to-end test of the multi-interviewer experience (Chromium via Playwright).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/latency_monitoring_browser.py`

### 1. Purpose
Real-browser end-to-end test: fast streamed interview + disclosed camera monitoring (Chromium via Playwright).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
Uses the REAL local models (Ollama, Kokoro, Whisper). Chromium's fake devices provide the camera (a synthetic test pattern - it contains NO face, which exercises the "face not visible" path) and the microphone (a WAV of a spoken answer, made by voice_interview_browser.py). Checks and measures: * setup: disclosure shown, nothing opened before the student presses the test button, separate opt-ins * first question: Start pressed -> first interviewer audio (greeting streamed while the question is prefetched) * answer: Submit -> first audio of the next question, and that sentence audio is ordered / never overlaps * live partial transcript, end-of-speech, subtitles following playback * monitoring:...

### 4. Important functions
```text
   - audio_overlaps()
       True if any interviewer audio buffer was scheduled to start before the previous one
       finished.
   Other helper functions: say, ok, wait_status, api, login
```

### 5. Important variables
- Module-level constants: HERE, OUT, MIC, BASE, INIT, STATUS

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Real-browser end-to-end test: fast streamed interview + disclosed camera monitoring (Chromium via Playwright).

### 9. Viva explanation
> This is a test file. Real-browser end-to-end test: fast streamed interview + disclosed camera monitoring (Chromium via Playwright).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/partial_transcript_check.py`

### 1. Purpose
Live partial transcript check (real Whisper + Kokoro + Ollama, Chromium fake microphone).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
The fake microphone plays an answer with natural pauses between sentences (Kokoro's own ~1.2 s plus 0.4 s; ~1.6 s of detected quiet): hand a finished piece to Whisper while the candidate keeps talking (segment pause 0.6 s), shorter than the Fast mode end-of-answer pause (1.0 s). Checks that "Heard so far" text appears DURING recording, that the final transcript keeps all sentences in order, and how long the transcript takes after the candidate stops. Run (servers running), from the backend folder: .\venv\Scripts\python.exe tests_e2e\partial_transcript_check.py

### 4. Important functions
```text
   Other helper functions: ok
```

### 5. Important variables
- Module-level constants: HERE, OUT, WAV, BASE, SENTENCES, STATUS

### 6. Connected files
```text
   Uses: app/services/voice/text_to_speech.py
```
External packages: numpy, playwright, soundfile

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Live partial transcript check (real Whisper + Kokoro + Ollama, Chromium fake microphone).

### 9. Viva explanation
> This is a test file. Live partial transcript check (real Whisper + Kokoro + Ollama, Chromium fake microphone).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/security_module_browser.py`

### 1. Purpose
Interview security module, end to end in a real browser (headless Chromium, fake camera + fake microphone).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
What is REAL here: the app, the backend, MediaPipe face analysis in the browser, the AI interviewer (Ollama + TTS), the event pipeline and database. What is SIMULATED: the person. The fake camera plays a video built from the app's own synthetic 3D interviewer (Rocketbox model, not a real person) rendered facing the camera and with the head turned 45 degrees, an empty room, and two faces; the fake microphone plays output/candidate_answer.wav. Timeline of the fake camera (seconds after the camera opens, loops): 0-22 facing the screen | 22-34 head turned 45 deg | 34-40 facing | 40-50 nobody | 50-56 facing 56-66 two faces | 66-90 facing Then: a tab switch (another tab in front for ~6 s), 8 s off...

### 4. Important functions
```text
   Other helper functions: say, ok, api, render_heads, make_video, text, setup_and_start
```

### 5. Important variables
- Module-level constants: HERE, OUT, MIC, BASE, STUDENT, RECRUITER, TIMELINE, LOGIN, FETCH

### 6. Connected files
```text
Standalone.
```
External packages: PIL, numpy, playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Interview security module, end to end in a real browser (headless Chromium, fake camera + fake microphone).

### 9. Viva explanation
> This is a test file. Interview security module, end to end in a real browser (headless Chromium, fake camera + fake microphone).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/typed_monitoring_browser.py`

### 1. Purpose
Typed interview monitoring, end to end in a real browser (headless Chromium, Chromium's built-in fake camera).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
The fake camera shows a test pattern (no face), so this checks the wiring, not face detection: the setup screen with the notice, consent, the status bar, the self-view, tab-switch/offline events reaching the database, and that the camera is released when the interview finishes. Face detection itself is covered by security_module_browser.py. Needs backend + frontend running and the demo accounts. From the backend folder: .\venv\Scripts\python.exe tests_e2e\typed_monitoring_browser.py Leaves one abandoned or completed demo typed interview.

### 4. Important functions
```text
   Other helper functions: ok, api
```

### 5. Important variables
- Module-level constants: BASE, STUDENT, LOGIN, FETCH

### 6. Connected files
```text
Standalone.
```
External packages: playwright

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Typed interview monitoring, end to end in a real browser (headless Chromium, Chromium's built-in fake camera).

### 9. Viva explanation
> This is a test file. Typed interview monitoring, end to end in a real browser (headless Chromium, Chromium's built-in fake camera).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_e2e/voice_interview_browser.py`

### 1. Purpose
Real-browser end-to-end test of the live voice interview (Chromium via Playwright).

### 2. What does it do?
1. Browser end-to-end check (Playwright + Chromium against a running app).
2. Run manually with the backend and frontend running: python tests_e2e/<file>.py.

### 3. How does it work?
The microphone is Chromium's fake capture device fed with a WAV of a spoken answer, so the whole pipeline runs: mic -> AudioWorklet recorder -> WAV upload -> local Whisper -> review -> existing answer API -> local LLM -> next question -> local TTS -> avatar lip sync. Run (backend + frontend + Ollama running), from the backend folder: .\venv\Scripts\python.exe -m pip install playwright .\venv\Scripts\python.exe -m playwright install chromium .\venv\Scripts\python.exe tests_e2e\voice_interview_browser.py Uses the seeded demo student unless HS_E2E_EMAIL / HS_E2E_PASSWORD are set. Screenshots go to tests_e2e/output/.

### 4. Important functions
```text
   - make_candidate_audio()
       The fake microphone plays this WAV: a spoken answer made with a different local voice,
       plus pauses.
   - wait_status()
       Poll the status badge until it matches `pattern`, sampling the avatar meanwhile.
   Other helper functions: say, mouth_stats
```

### 5. Important variables
- Module-level constants: HERE, OUT, MIC, BASE, MIC, INIT, SAMPLE

### 6. Connected files
```text
   Uses: app/services/voice/text_to_speech.py
```
External packages: numpy, playwright, soundfile

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Real-browser end-to-end test of the live voice interview (Chromium via Playwright).

### 9. Viva explanation
> This is a test file. Real-browser end-to-end test of the live voice interview (Chromium via Playwright).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

# Backend - integration tests (real AI models)

## File: `backend/tests_integration/conftest.py`

### 1. Purpose
Integration tests against the REAL local models (Ollama + Sentence Transformers).

### 2. What does it do?
1. Integration test against the REAL local AI models.
2. Run from backend/: pytest tests_integration -s (needs Ollama and the voice models).

### 3. How does it work?
Run from the backend folder (Ollama must be running and the model pulled): .\venv\Scripts\python.exe -m pytest tests_integration -s -v Tests skip themselves (with the reason) when a model is not available. They are slow: a few minutes on CPU.

### 4. Important functions
```text
   Other helper functions: db, llm_ready, embeddings_ready
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/seed_initial_data.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Integration tests against the REAL local models (Ollama + Sentence Transformers).

### 9. Viva explanation
> This is a test file. Integration tests against the REAL local models (Ollama + Sentence Transformers).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_integration/test_real_features.py`

### 1. Purpose
REAL-model checks for the features README section 9 listed as "not yet verified with the real model": English conversation + evaluation, AI MCQ generation, code review, student/mentor recommendations and job-role suggestions. Uses whatever provider backend/.env configures (Gemini with Ollama fallback, or Ollama only).

### 2. What does it do?
1. Integration test against the REAL local AI models.
2. Contains 5 test(s), e.g.: real english conversation and evaluation; real mcq generation; real code review separates correct and buggy; real student recommendations; real job role suggestions.
3. Run from backend/: pytest tests_integration -s (needs Ollama and the voice models).

### 3. How does it work?
Each test prints the model that answered and the time it took (run with -s). Smoke tests of quality, not benchmarks.

### 4. Important functions
```text
   - answered_by()
       Records which model answered each language-model call (from the result's timings).
   - test_real_student_recommendations()
       Used by both the student page (POST /students/recommendations) and the mentor page
       (POST /mentors/students/{id}/recommendations) - same function, same prompt.
   Other helper functions: _timed, test_real_english_conversation_and_evaluation,
   test_real_mcq_generation, test_real_code_review_separates_correct_and_buggy,
   test_real_job_role_suggestions
```

### 5. Important variables
- Module-level constants: SNAPSHOT

### 6. Connected files
```text
   Uses: app/services/ai_models/language_model_client.py,
   app/services/interview/ai_interview_service.py
```
External packages: pytest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: REAL-model checks for the features README section 9 listed as "not yet verified with the real model": English conversation + evaluation, AI MCQ generation, code review, student/mentor recommendations and job-role suggestions. Uses whatever provider backend/.env configures (Gemini with Ollama fallback, or Ollama only).

### 9. Viva explanation
> This is a test file. REAL-model checks for the features README section 9 listed as "not yet verified with the real model": English conversation + evaluation, AI MCQ generation, code review, student/mentor recommendations and job-role suggestions. Uses whatever provider backend/.env configures (Gemini with Ollama fallbac

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_integration/test_real_models.py`

### 1. Purpose
REAL local-model checks (not mocked). These measure behaviour of the actual models on a few fixed examples.

### 2. What does it do?
1. Integration test against the REAL local AI models.
2. Contains 5 test(s), e.g.: real embeddings rank candidates; real resume analysis; real question is personalised; real evaluation separates good and bad answers; real struggling followup is simpler.
3. Run from backend/: pytest tests_integration -s (needs Ollama and the voice models).

### 3. How does it work?
Passing means the pipeline works end to end with the real model on these examples - it is a smoke test of quality, not a benchmark. Timings are printed with -s.

### 4. Important functions
```text
   Other helper functions: _timed, test_real_embeddings_rank_candidates,
   test_real_resume_analysis, test_real_question_is_personalised,
   test_real_evaluation_separates_good_and_bad_answers, test_real_struggling_followup_is_simpler
```

### 5. Important variables
- Module-level constants: RESUME_TEXT, JOB

### 6. Connected files
```text
   Uses: app/routers/interview_routes.py, app/services/interview/ai_interview_service.py,
   app/services/resume_and_jobs/semantic_job_matcher.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: REAL local-model checks (not mocked). These measure behaviour of the actual models on a few fixed examples.

### 9. Viva explanation
> This is a test file. REAL local-model checks (not mocked). These measure behaviour of the actual models on a few fixed examples.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_integration/test_voice_real.py`

### 1. Purpose
REAL local voice engines (Kokoro TTS + Whisper STT). Not mocked. Run: pytest tests_integration -s -k voice

### 2. What does it do?
1. Integration test against the REAL local AI models.
2. Contains 4 test(s), e.g.: voice tts audio and viseme timeline; voice mouth is closed in pauses; voice round trip tts to stt; voice silence is not transcribed.
3. Run from backend/: pytest tests_integration -s (needs Ollama and the voice models).

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
   Other helper functions: engines, _wav16k, test_voice_tts_audio_and_viseme_timeline,
   test_voice_mouth_is_closed_in_pauses, test_voice_round_trip_tts_to_stt,
   test_voice_silence_is_not_transcribed
```

### 5. Important variables
- Module-level constants: QUESTION

### 6. Connected files
```text
   Uses: app/services/voice/speech_to_text.py, app/services/voice/text_to_speech.py
```
External packages: numpy, pytest, soundfile

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: REAL local voice engines (Kokoro TTS + Whisper STT). Not mocked. Run: pytest tests_integration -s -k voice

### 9. Viva explanation
> This is a test file. REAL local voice engines (Kokoro TTS + Whisper STT). Not mocked. Run: pytest tests_integration -s -k voice

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

# Backend - performance benchmarks

## File: `backend/tests_perf/bench_interview_latency.py`

### 1. Purpose
Latency benchmark for the interview pipeline with the REAL local models (Ollama, Kokoro, Whisper).

### 2. What does it do?
1. Performance benchmark with the real models.
2. Run manually; results are written to tests_perf/results/.

### 3. How does it work?
Measures each stage separately so the bottleneck is visible instead of guessed: * LLM cold load, question generation, answer scoring (with Ollama's own load / prompt / generation split) * text-to-speech: whole question vs. first sentence only (what the streaming path waits for) * speech-to-text of a recorded answer * the full "answer -> next question" server path (score + question), as the old endpoint did it Run from the backend folder (Ollama running, model pulled): .\venv\Scripts\python.exe tests_perf\bench_interview_latency.py [--runs 5] [--out results.json] Uses an in-memory database; no candidate data is written anywhere. Prints p50 / p95 / mean per stage.

### 4. Important functions
```text
   Other helper functions: pct, summary, timed, main
```

### 5. Important variables
- Module-level constants: HERE, WAV, RESUME, ANSWERS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/seed_initial_data.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/interview/ai_interview_service.py, app/services/voice/speech_to_text.py,
   app/services/voice/streamed_reply_sentence_splitter.py, app/services/voice/text_to_speech.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Latency benchmark for the interview pipeline with the REAL local models (Ollama, Kokoro, Whisper).

### 9. Viva explanation
> This is a test file. Latency benchmark for the interview pipeline with the REAL local models (Ollama, Kokoro, Whisper).

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_perf/bench_models.py`

### 1. Purpose
Compare local models on the two workloads that matter most, using the app's real prompts and validation.

### 2. What does it do?
1. Performance benchmark with the real models.
2. Run manually; results are written to tests_perf/results/.

### 3. How does it work?
1. English chat turns (the conversational path: english_reply) -> latency + whether a grammar slip is corrected 2. Answer scoring (score_answer) on six labelled answers -> does the score separate good from bad? Run from the backend folder, Ollama running, every listed model already pulled: .\venv\Scripts\python.exe tests_perf\bench_models.py --models qwen3:4b qwen3:1.7b --runs 3 --out results.json Each model is unloaded first, so the first call of each model is a cold start (reported separately). Uses an in-memory database. Only timings and numeric scores are printed; model output text is not stored.

### 4. Important functions
```text
   Other helper functions: pct, stats, unload_all, ps_info, main
```

### 5. Important variables
- Module-level constants: RUBRIC, QUESTION, ANSWERS, CHAT

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/seed_initial_data.py,
   app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/interview/ai_interview_service.py
```
External packages: httpx

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Compare local models on the two workloads that matter most, using the app's real prompts and validation.

### 9. Viva explanation
> This is a test file. Compare local models on the two workloads that matter most, using the app's real prompts and validation.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_perf/bench_prompts.py`

### 1. Purpose
Latency + quality benchmark of the analysis prompts (resume analysis, answer scoring, answer feedback, final interview report) with the REAL configured provider (Gemini, falling back to Ollama), using the app's own functions.

### 2. What does it do?
1. Performance benchmark with the real models.
2. Run manually; results are written to tests_perf/results/.

### 3. How does it work?
.\venv\Scripts\python.exe tests_perf\bench_prompts.py --runs 2 --out tests_perf\results\prompts_after.json Uses the throwaway MongoDB database "hiresense_bench" (cleared first). Fictional inputs only. Prints timings, token counts, which provider answered and simple quality checks; model text is not stored.

### 4. Important functions
```text
   Other helper functions: stats, main
```

### 5. Important variables
- Module-level constants: RESUME, QUESTION, ANSWERS, RUBRIC, QA

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
   app/mongodb_data_layer/__init__.py, app/seed_initial_data.py,
   app/services/ai_models/gemini_api_client.py, app/services/ai_models/language_model_client.py,
   app/services/ai_models/sentence_embedding_model.py,
   app/services/interview/ai_interview_service.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Latency + quality benchmark of the analysis prompts (resume analysis, answer scoring, answer feedback, final interview report) with the REAL configured provider (Gemini, falling back to Ollama), using the app's own functions.

### 9. Viva explanation
> This is a test file. Latency + quality benchmark of the analysis prompts (resume analysis, answer scoring, answer feedback, final interview report) with the REAL configured provider (Gemini, falling back to Ollama), using the app's own functions.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

## File: `backend/tests_perf/bench_stt.py`

### 1. Purpose
Speech-to-text latency on this computer: how long after the candidate stops talking until the text is ready.

### 2. What does it do?
1. Performance benchmark with the real models.
2. Run manually; results are written to tests_perf/results/.

### 3. How does it work?
Makes spoken answers with the app's own TTS voice (Kokoro), then times the configured STT engine on them, and checks the words come back (word error rate against the script). Run: python tests_perf/bench_stt.py [engine ...] Engines: whatever STT_ENGINE/STT_MODEL say, unless names are given (e.g. "transformers:openai/whisper-base.en", "faster:base.en", "faster:small.en"). Clips are cached in tests_perf/results/stt_clips/.

### 4. Important functions
```text
   Other helper functions: words, wer, clips, main
```

### 5. Important variables
- Module-level constants: SCRIPTS, CLIPS

### 6. Connected files
```text
   Uses: app/application_configuration.py, app/services/voice/speech_to_text.py,
   app/services/voice/text_to_speech.py
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Used during development and before a release to prove the feature still works: Speech-to-text latency on this computer: how long after the candidate stops talking until the text is ready.

### 9. Viva explanation
> This is a test file. Speech-to-text latency on this computer: how long after the candidate stops talking until the text is ready.

**Note:** Test/tool file: it checks or measures the application and is not used by the running app.

---

# Frontend - entry, routing, API client, styles

## File: `frontend/index.html`

### 1. Purpose
The single HTML page that the browser loads. React draws the app inside it.

### 2. What does it do?
1. Sets the page title, icon and mobile viewport.
2. Loads the Geist font from Google Fonts.
3. Contains the empty <div id="root"> and loads /src/main.jsx.

### 3. How does it work?
Vite serves this file and injects the compiled JavaScript. Everything visible is created by React.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** A page with an empty root element for React.

### 8. Real project example
Opening http://localhost:5173 returns this page.

### 9. Viva explanation
> HireSense is a single-page application: index.html is loaded once and React renders all pages inside the root div.

---

## File: `frontend/postcss.config.js`

### 1. Purpose
Tells PostCSS to run Tailwind CSS and Autoprefixer when CSS is built.

### 2. What does it do?
1. Enables the tailwindcss plugin.
2. Enables autoprefixer (adds browser-specific CSS prefixes).

### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Processed CSS for the browser.

### 8. Real project example
Used automatically by Vite every time the app is started or built.

### 9. Viva explanation
> postcss.config.js plugs Tailwind and Autoprefixer into the CSS build.

---

## File: `frontend/src/App.jsx`

### 1. Purpose
Defines every page URL (route) of the frontend and makes sure each role only opens its own pages.

### 2. What does it do?
Routing table and role-based route guard.

1. Shows a loading spinner while the login session is being checked.
2. Shows only the public pages (login, register, forgot/reset password, privacy) when nobody is logged in.
3. For a logged-in user, maps URLs such as /student/interviews or /recruiter/jobs to page components.
4. Uses RequireRole so a student cannot open recruiter/mentor/admin pages (they are sent to their own home).
5. Redirects old URLs of merged pages to the new tabbed pages.
6. Loads most pages lazily (React.lazy) so the first download is small.

### 3. How does it work?
It reads the user from useAuth(). If there is no user, a small route list is used. Otherwise all routes are placed inside the AppShellLayout (sidebar + header). Each protected route is wrapped in RequireRole which compares user.role with the role required by the page.

```
AuthContext finishes /auth/me check
   |
   v
No user -> public routes only
   |
   v
User -> routes inside AppShellLayout
   |
   v
RequireRole checks the role
   |
   v
Matching page component is rendered
```

### 4. Important functions
```text
   - App()
       Main component: chooses the signed-out or signed-in route list.
   - RequireRole()
       Guard component: renders the page only if the user has the required role, else
       redirects to the user's home page.
   Other helper functions: Profile, Notifications, NotFound, Settings, ProgressHub,
   Opportunities, StudentDashboard, Resume, Interviews, InterviewSession, VoiceInterview,
   English, EnglishSession, Vocabulary, StudentAssessments, Rewards, Applications, Mentoring,
   RecruiterDashboard, RecruiterJobs, RecruiterJobDetail, Candidates, CandidateDetail,
   CompareCandidates, CandidateReport, MentorDashboard, MentorStudents, MentorStudentDetail,
   MentorSessions, AdminDashboard, AdminUsers, AdminAssignments, AdminJobs, InterviewConfig,
   AdminRewards, Monitoring, AuditLogs, Reports, AdminSettings, AssessmentManager,
   IntegrityReviewPage
```

### 5. Important variables
- `HOME`: Home URL of each role: /student, /recruiter, /mentor, /admin.

### 6. Connected files
```text
   Uses: AuthContext.jsx, components/AppShellLayout.jsx, components/SharedUiComponents.jsx,
   pages/AccountSettings.jsx, pages/ForgotPassword.jsx, pages/Login.jsx, pages/NotFound.jsx,
   pages/Notifications.jsx, pages/Privacy.jsx, pages/ProfileEditor.jsx, pages/Register.jsx,
   pages/ResetPassword.jsx, pages/admin/AdminDashboard.jsx, pages/admin/AdminJobPostings.jsx,
   pages/admin/AdminMonitoring.jsx, pages/admin/AdminRewardRules.jsx, pages/admin/AuditLogs.jsx,
   pages/admin/InterviewConfig.jsx, pages/admin/MentorAssignments.jsx,
   pages/admin/PlacementReports.jsx, pages/admin/PlatformSettings.jsx,
   pages/admin/UserManagement.jsx, pages/mentor/MentorDashboard.jsx,
   pages/mentor/MentorSessions.jsx, pages/mentor/MentorStudentDetail.jsx,
   pages/mentor/MentorStudentList.jsx, pages/recruiter/CandidateDetail.jsx,
   pages/recruiter/CandidateReport.jsx, pages/recruiter/CandidateSearch.jsx,
   pages/recruiter/CompareCandidates.jsx, pages/recruiter/RecruiterDashboard.jsx,
   pages/recruiter/RecruiterJobApplicants.jsx, pages/recruiter/RecruiterJobPostings.jsx,
   pages/shared/AssessmentManager.jsx, pages/shared/IntegrityReview.jsx,
   pages/student/EnglishPracticeHome.jsx, pages/student/EnglishSession.jsx,
   pages/student/InterviewSession.jsx, pages/student/JobApplications.jsx,
   pages/student/JobsAndDrives.jsx, pages/student/LiveVoiceInterview.jsx,
   pages/student/MockInterviewHome.jsx, pages/student/ProgressHub.jsx,
   pages/student/ResumeUploadAndAnalysis.jsx, pages/student/StudentAssessments.jsx,
   pages/student/StudentDashboard.jsx, pages/student/StudentMentoring.jsx,
   pages/student/StudentRewards.jsx, pages/student/VocabularyTrainer.jsx
   Used by: main.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** The current user and loading flag from AuthContext, and the browser URL.
- **Output:** The page component that matches the URL.

### 8. Real project example
When a student clicks 'Mock interviews', the URL becomes /student/interviews and App.jsx shows MockInterviewHome.jsx.

### 9. Viva explanation
> App.jsx is the routing table. It uses React Router, lazy-loads pages, and has a RequireRole guard so each of the four roles - student, recruiter, mentor, admin - only sees its own portal.

**Note:** This is only a user-interface guard. The real security check is done again by the backend on every API call.

---

## File: `frontend/src/AuthContext.jsx`

### 1. Purpose
Keeps track of the logged-in user for the whole frontend.

### 2. What does it do?
React context for authentication (login, logout, current user).

1. On page load calls GET /auth/me to restore the session from the cookie.
2. Stores the user object and the AI availability info.
3. Provides login() (POST /auth/login) and logout() (POST /auth/logout).
4. Clears the user when any API call reports 401 (session expired).

### 3. How does it work?
AuthProvider holds user, ai and loading in React state and shares them with useAuth(). Pages call useAuth() to read the user or to log in/out.

```
App starts
   |
   v
AuthProvider calls /auth/me
   |
   v
User saved in state (or null)
   |
   v
App.jsx shows the right portal
```

### 4. Important functions
```text
   - AuthProvider()
       Context provider that loads /auth/me and exposes user, ai, loading, login, logout,
       refresh, setUser.
   - useAuth()
       Hook that pages use to read the authentication context.
```

### 5. Important variables
- `user`: The logged-in user (id, name, email, role) or null.
- `ai`: Whether AI features are available.
- `loading`: True until the first /auth/me check finishes.

### 6. Connected files
```text
   Uses: apiClient.js
   Used by: App.jsx, components/AppShellLayout.jsx, components/HostedAiConsentGate.jsx,
   components/useSpeechAndPreferences.jsx, main.jsx, pages/AccountSettings.jsx, pages/Login.jsx,
   pages/Privacy.jsx, pages/ProfileEditor.jsx, pages/Register.jsx,
   pages/admin/PlatformSettings.jsx, pages/admin/UserManagement.jsx,
   pages/shared/AssessmentManager.jsx, pages/shared/IntegrityReview.jsx,
   pages/student/EnglishPracticeHome.jsx, pages/student/MockInterviewHome.jsx,
   pages/student/StudentDashboard.jsx
```
External packages: react

### 7. Input and output
- **Input:** Responses of /auth/me, /auth/login and /auth/logout.
- **Output:** The shared authentication state used by App.jsx and every page.

### 8. Real project example
When a student types their email and password on the login page, login() calls /auth/login and then refreshes the user.

### 9. Viva explanation
> AuthContext uses the React Context API to share the logged-in user across all components. Login is cookie-based, so the frontend only calls /auth/me to know who is logged in.

---

## File: `frontend/src/apiClient.js`

### 1. Purpose
One small helper used by every page to talk to the backend API.

### 2. What does it do?
HTTP client (wrapper around fetch) for all /api calls.

1. Builds the full URL (/api + path, plus query parameters).
2. Sends JSON or file uploads (FormData) with the login cookie included.
3. Turns the backend's error message into a readable ApiError.
4. Fires a global 'hs:unauthorized' event when the session has expired (HTTP 401).
5. Offers short helpers get/post/put/patch/del and a download() helper for files.

### 3. How does it work?
api() calls the browser fetch() with credentials: 'include', so the httpOnly session cookie set by the backend is sent automatically; no token is stored in JavaScript. The response text is parsed as JSON. If the status is not OK, an ApiError with the status and message is thrown. API_BASE allows the API to be on a different domain.

```
Page calls get('/student/dashboard')
   |
   v
api() builds /api/student/dashboard
   |
   v
fetch() sends request with cookie
   |
   v
Backend replies with JSON
   |
   v
Data returned to the page (or ApiError thrown)
```

### 4. Important functions
```text
   - api()
       Core request function: builds URL, sends request, parses response, throws ApiError on
       failure.
   - get()
       GET request with optional query parameters.
   - post()
       POST request with a JSON or FormData body.
   - put()
       PUT request.
   - patch()
       PATCH request.
   - del()
       DELETE request.
   - download()
       Downloads a file (e.g. resume or CSV) and saves it in the browser.
   - apiUrl()
       Adds VITE_API_URL in front of an /api path when the API is hosted elsewhere.
   - formatDetail()
       Turns FastAPI validation errors into a readable message.
   Other helper functions: ApiError
```

### 5. Important variables
- `API_BASE`: Optional backend address from VITE_API_URL (empty = same site).

### 6. Connected files
```text
   Used by: AuthContext.jsx, components/AppShellLayout.jsx, components/EnglishDailyPlan.jsx,
   components/EnglishMistakeProfile.jsx, components/EnglishProgress.jsx,
   components/HostedAiConsentGate.jsx, live/notificationStream.js,
   monitoring/InterviewMonitorBar.jsx, monitoring/eventReporter.js, monitoring/mediaSession.js,
   monitoring/useTypedMonitoring.js, pages/AccountSettings.jsx, pages/ForgotPassword.jsx,
   pages/Notifications.jsx, pages/ProfileEditor.jsx, pages/Register.jsx, pages/ResetPassword.jsx,
   pages/admin/AdminDashboard.jsx, pages/admin/AdminJobPostings.jsx,
   pages/admin/AdminMonitoring.jsx, pages/admin/AdminRewardRules.jsx, pages/admin/AuditLogs.jsx,
   pages/admin/InterviewConfig.jsx, pages/admin/MentorAssignments.jsx,
   pages/admin/PlacementReports.jsx, pages/admin/PlatformSettings.jsx,
   pages/admin/SecuritySettings.jsx, pages/admin/UserManagement.jsx,
   pages/mentor/MentorDashboard.jsx, pages/mentor/MentorSessions.jsx,
   pages/mentor/MentorStudentDetail.jsx, pages/mentor/MentorStudentList.jsx,
   pages/recruiter/CandidateDetail.jsx, pages/recruiter/CandidateReport.jsx,
   pages/recruiter/CandidateSearch.jsx, pages/recruiter/CompareCandidates.jsx,
   pages/recruiter/RecruiterDashboard.jsx, pages/recruiter/RecruiterJobApplicants.jsx,
   pages/recruiter/RecruiterJobPostings.jsx, pages/shared/AssessmentManager.jsx,
   pages/shared/IntegrityReview.jsx, pages/student/EnglishAvatarSession.jsx,
   pages/student/EnglishPracticeHome.jsx, pages/student/EnglishSession.jsx,
   pages/student/InterviewSession.jsx, pages/student/InterviewSetup.jsx,
   pages/student/InterviewerFeedback.jsx, pages/student/InterviewerPicker.jsx,
   pages/student/JobApplications.jsx, pages/student/LiveVoiceInterview.jsx,
   pages/student/MockInterviewHome.jsx, pages/student/PerformanceReport.jsx,
   pages/student/PlacementDrives.jsx, pages/student/PracticeHistory.jsx,
   pages/student/ProgressOverview.jsx, pages/student/ResumeUploadAndAnalysis.jsx,
   pages/student/StudentAssessments.jsx, pages/student/StudentDashboard.jsx,
   pages/student/StudentJobOpenings.jsx, pages/student/StudentMentoring.jsx,
   pages/student/StudentRewards.jsx, pages/student/VocabularyTrainer.jsx, voice/turnStream.js,
   voice/useInterviewers.js
   Tested by: monitoring/interviewSecurity.test.js
```

### 7. Input and output
- **Input:** A path such as '/student/dashboard', an optional body and query parameters.
- **Output:** The parsed JSON response, or an ApiError.

### 8. Real project example
When the student dashboard opens it calls get('/student/dashboard'); this file sends the request and returns the data.

### 9. Viva explanation
> apiClient.js is our API service layer. Every page uses its get/post/put/patch/del helpers, which wrap fetch, send the session cookie and convert backend errors into readable messages.

---

## File: `frontend/src/index.css`

### 1. Purpose
Global stylesheet: the colour theme and shared CSS classes of the whole app.

### 2. What does it do?
1. Loads Tailwind CSS (base, components, utilities).
2. Defines the 'dark premium' theme colours as CSS variables (used by tailwind.config.js).
3. Defines shared classes such as .card, .input, .label, .th/.td for tables, .skeleton loaders.
4. Contains print styles so reports can be saved as PDF in a light layout.

### 3. How does it work?
Colours are RGB variables in :root; Tailwind classes like bg-slate-50 read these variables, so changing the variables re-themes the whole application.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: main.jsx
```

### 7. Input and output
- **Input:** Imported once by main.jsx.
- **Output:** Styles applied to every page.

### 8. Real project example
The recruiter's printable candidate report uses the print rules in this file when 'Save as PDF' is used.

### 9. Viva explanation
> index.css holds the global theme. All colours are CSS variables so the whole UI can be re-themed from one place.

---

## File: `frontend/src/main.jsx`

### 1. Purpose
The starting point of the React application. It puts the whole app on the web page.

### 2. What does it do?
Mount <App/> inside the router, login context and toast provider.

1. Finds the <div id="root"> element in index.html.
2. Wraps the app in BrowserRouter so page URLs work.
3. Wraps it in AuthProvider so every page knows who is logged in.
4. Wraps it in ToastProvider so any page can show small pop-up messages.
5. Loads the global stylesheet index.css.

### 3. How does it work?
When the browser loads /src/main.jsx, ReactDOM.createRoot renders the component tree once. All other pages are reached from App.jsx inside this tree.

```
Browser opens index.html
   |
   v
main.jsx runs
   |
   v
Providers are created (router, auth, toasts)
   |
   v
App.jsx decides which page to show
```

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: App.jsx, AuthContext.jsx, components/SharedUiComponents.jsx, index.css
```
External packages: react, react-dom, react-router-dom

### 7. Input and output
- **Input:** The HTML page (index.html) with an empty root element.
- **Output:** The running React application drawn in the browser.

### 8. Real project example
Every time a student opens HireSense in the browser, this file runs first.

### 9. Viva explanation
> main.jsx is the React entry point. It mounts the App component and wraps it with the router, the authentication context and the toast notification provider.

---

## File: `frontend/tailwind.config.js`

### 1. Purpose
Configuration of Tailwind CSS: which files to scan and the custom theme colours and fonts.

### 2. What does it do?
1. Tells Tailwind to scan index.html and src/**/*.js(x) for class names.
2. Maps colour names (slate, brand, emerald, ...) to the CSS variables in index.css.
3. Sets the Geist font family.

### 3. How does it work?
The helper v(name) creates a colour scale whose values are rgb(var(--name-N)), so colours come from index.css.

### 4. Important functions
```text
   - v()
       Theme: "dark premium".
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```
External packages: tailwindcss

### 7. Input and output
- **Input:** Not applicable.
- **Output:** The Tailwind theme used when the CSS is built.

### 8. Real project example
The class bg-brand-500 on a button gets its colour through this configuration.

### 9. Viva explanation
> tailwind.config.js defines our design tokens - colours and fonts - for the Tailwind utility CSS framework.

---

## File: `frontend/vite.config.js`

### 1. Purpose
Configuration of Vite, the tool that runs the development server and builds the frontend.

### 2. What does it do?
1. Enables the React plugin.
2. Splits big libraries (react, three.js, recharts) into separate cached chunks.
3. Runs the dev server on port 5173.
4. Forwards /api requests to the FastAPI backend (http://127.0.0.1:8000).

### 3. How does it work?
The proxy makes the browser think the API is on the same site, so the login cookie works in development.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
Standalone.
```
External packages: @vitejs/plugin-react, vite

### 7. Input and output
- **Input:** Environment variable HS_API (optional, another backend for tests).
- **Output:** Dev server behaviour and production build output (dist/).

### 8. Real project example
During development `npm run dev` uses this file so frontend calls to /api reach the backend.

### 9. Viva explanation
> vite.config.js configures the Vite build tool: React plugin, code splitting and a proxy from /api to the backend.

---

# Frontend - shared components

## File: `frontend/src/components/AppShellLayout.jsx`

### 1. Purpose
The common frame around every signed-in page: sidebar menu, top header, notification bell and sign-out.

### 2. What does it do?
Application shell (navigation + notifications) for all four portals.

1. Shows a different sidebar menu for student, recruiter, mentor and admin (NAV table).
2. Adds 'Integrity review' to the menu only for mentors with the review_integrity permission.
3. Shows the notification bell: loads GET /notifications, marks read with POST /notifications/{id}/read and /notifications/read-all.
4. Receives live notification signals through live/notificationStream.js.
5. Shows profile, account settings and sign-out links; renders the current page in <Outlet/>.

### 3. How does it work?
Layout reads the user from useAuth(), builds the menu from NAV[user.role] and wraps the routed page in a Suspense block (pages are lazy-loaded). NotificationBell subscribes to the live stream and reloads the list when a signal arrives.

```
User logs in
   |
   v
Layout builds the menu for the user's role
   |
   v
Bell loads notifications and listens for live signals
   |
   v
Clicking a menu item changes the routed page
```

### 4. Important functions
```text
   - Layout()
       The page frame: sidebar (desktop + mobile drawer), header and page outlet.
   - NotificationBell()
       Bell icon with unread count and a dropdown of the latest notifications.
   Other helper functions: initials, navItemClass
```

### 5. Important variables
- `NAV`: Menu items for each role (link, label, icon, section headings).

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/Logo.jsx, components/SharedUiComponents.jsx,
   live/notificationStream.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Logged-in user (role, permissions), notification API responses, live stream signals.
- **Output:** Rendered navigation and the current page.

### 8. Real project example
A recruiter sees 'Job postings', 'Candidates', 'Assessments' and 'Security reports' in the sidebar; a student sees 'Mock interviews', 'Resume analysis' etc.

### 9. Viva explanation
> AppShellLayout is the shared layout of all portals. The menu is role-based, and the notification bell updates live using Server-Sent Events.

---

## File: `frontend/src/components/ConversationMemory.jsx`

### 1. Purpose
Shows what Aria (the English practice partner) remembers in the current English conversation.

### 2. What does it do?
1. Lists earlier topics, the student's interests and important details Aria noted.
2. Shows which grammar points are being practised.
3. Shows the current learning mode label.

### 3. How does it work?
It receives the memory object returned by the backend and renders it in a Card; renders nothing if there is no memory.

### 4. Important functions
```text
   - ConversationMemory()
       What Aria remembers from this conversation (topics, interests, details), so the
       student can see it.
```

### 5. Important variables
- `LEARNING_MODE_LABEL`: Readable names of the three learning modes.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx
   Used by: pages/student/EnglishAvatarSession.jsx, pages/student/EnglishSession.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Props: memory (from the English session API) and learningMode.
- **Output:** A 'What Aria remembers' card.

### 8. Real project example
During an English chat about cricket, the panel shows 'cricket' as a topic and details the student shared.

### 9. Viva explanation
> ConversationMemory makes the AI's memory transparent: the student can see exactly what Aria remembers.

---

## File: `frontend/src/components/DashboardCharts.jsx`

### 1. Purpose
Ready-made chart components (built on Recharts) used by the dashboards, progress pages and reports.

### 2. What does it do?
1. ProgressChart: line chart of a student's scores over time.
2. SimpleBar and MultiBar: bar charts.
3. SkillRadar: radar (spider) chart of skill scores.
4. TimelineChart: multi-line chart of scores by session.
5. Shows an empty state when there is no data.

### 3. How does it work?
Each function receives data arrays and wraps Recharts components with the app's colours, axis and tooltip styles.

### 4. Important functions
```text
   - ProgressChart()
       Line chart of progress records (interview, English, assessment scores) by date.
   - SimpleBar()
       Single-series bar chart.
   - MultiBar()
       Bar chart with several series per item.
   - SkillRadar()
       Radar chart of scores 0-10.
   - TimelineChart()
       Lines for several keys across sessions.
```

### 5. Important variables
- `COLORS`: Colour list used for chart series.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx
   Used by: components/EnglishProgress.jsx, pages/admin/AdminDashboard.jsx,
   pages/admin/AdminMonitoring.jsx, pages/mentor/MentorDashboard.jsx,
   pages/recruiter/RecruiterDashboard.jsx, pages/student/EnglishSession.jsx,
   pages/student/PerformanceReport.jsx, pages/student/ProgressOverview.jsx,
   pages/student/StudentDashboard.jsx
```
External packages: recharts

### 7. Input and output
- **Input:** Data arrays and options (keys, height, max) from the calling page.
- **Output:** SVG charts in the page.

### 8. Real project example
The student progress page shows how interview scores improved over weeks with ProgressChart.

### 9. Viva explanation
> DashboardCharts wraps the Recharts library so every portal draws charts in the same style with very little code.

---

## File: `frontend/src/components/EnglishDailyPlan.jsx`

### 1. Purpose
Shows 'Today's English plan' - small daily tasks that tick themselves when the student does them.

### 2. What does it do?
1. Loads GET /student/english/daily-plan.
2. Shows a progress bar and each task with a done/not-done icon.
3. Links each task to the page where it can be done.
4. Has a compact version for the student dashboard.

### 3. How does it work?
Uses useApi to load the plan and planSummary() from english/vocabularyReview.js to count done tasks.

### 4. Important functions
```text
   - DailyPlan()
       Card with the daily plan items and progress.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, english/vocabularyReview.js
   Used by: pages/student/EnglishPracticeHome.jsx, pages/student/StudentDashboard.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Props: compact, className. Data from /student/english/daily-plan.
- **Output:** Rendered plan card.

### 8. Real project example
A student sees 'Review 10 words' and 'Have one conversation' and gets points after finishing both.

### 9. Viva explanation
> The daily plan is checked by the backend from real activity, so students cannot tick tasks by hand.

---

## File: `frontend/src/components/EnglishMistakeProfile.jsx`

### 1. Purpose
Shows the student's recurring English mistakes (for example verb tense or articles).

### 2. What does it do?
1. Loads GET /student/english/profile.
2. Lists each pattern with an example and whether it is recurring.
3. 'This is wrong' dismisses one pattern (POST /student/english/profile/{id}/dismiss).
4. 'Clear all' deletes the profile (DELETE /student/english/profile).

### 3. How does it work?
Uses useApi for loading and a small run() helper that calls the API and replaces the data with the reply.

### 4. Important functions
```text
   - MistakeProfile()
       Card listing the mistake patterns with dismiss/clear actions.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: pages/student/EnglishPracticeHome.jsx
```
External packages: react

### 7. Input and output
- **Input:** Data from /student/english/profile.
- **Output:** Rendered card (nothing if there are no patterns).

### 8. Real project example
After several chats the student sees 'Articles (a / an / the) - recurring'.

### 9. Viva explanation
> This component shows a rule-based mistake profile and lets the student correct it, so the system stays honest.

**Note:** The categories come from simple rules on the backend, so they are approximate; the student can dismiss them.

---

## File: `frontend/src/components/EnglishProgress.jsx`

### 1. Purpose
Shows English learning progress: words learned, review accuracy and skill scores over time.

### 2. What does it do?
1. Loads GET /student/english/progress.
2. Shows stat cards (words, learned, accuracy, plan days).
3. Draws skill scores by session (TimelineChart) and weekly review accuracy (SimpleBar).

### 3. How does it work?
Data is loaded with useApi and shaped with trendRows() from english/vocabularyReview.js before charting.

### 4. Important functions
```text
   - EnglishProgress()
       The progress view with stat cards and two charts.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx,
   english/vocabularyReview.js
   Used by: pages/student/EnglishPracticeHome.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Data from /student/english/progress.
- **Output:** Stat cards and charts.

### 8. Real project example
On the English page the student sees grammar and fluency scores improving across sessions.

### 9. Viva explanation
> EnglishProgress turns stored practice data into charts so the student can track improvement.

---

## File: `frontend/src/components/HostedAiConsentGate.jsx`

### 1. Purpose
Asks a student to agree to the AI data notice when the server uses the hosted Google Gemini AI.

### 2. What does it do?
1. Loads GET /auth/privacy once (cached) to know if consent is required.
2. Shows a notice with an 'I agree' button only to students who have not agreed yet.
3. Saves consent with POST /auth/ai-consent and updates the user.

### 3. How does it work?
usePrivacyInfo() caches the privacy info in a module variable. AIConsentGate returns nothing when consent is not needed or already given.

### 4. Important functions
```text
   - usePrivacyInfo()
       Hook that loads and caches /auth/privacy.
   - AIConsentGate()
       The consent card shown before AI features.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx
   Used by: pages/AccountSettings.jsx, pages/Privacy.jsx, pages/Register.jsx,
   pages/student/EnglishPracticeHome.jsx, pages/student/MockInterviewHome.jsx,
   pages/student/ResumeUploadAndAnalysis.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Logged-in user; /auth/privacy response.
- **Output:** Consent card, or nothing.

### 8. Real project example
Before uploading a resume on a Gemini-hosted server, the student first clicks 'I agree'.

### 9. Viva explanation
> This component implements informed consent: students must agree before their data is sent to a hosted AI service.

**Note:** With the local Ollama AI nothing leaves the server, so no consent is asked.

---

## File: `frontend/src/components/InterviewerStage.jsx`

### 1. Purpose
Shows a live 3D interviewer as a decorative hero element on the sign-in page and student dashboard.

### 2. What does it do?
1. Checks that the browser supports WebGL.
2. Waits until the browser is idle, then lazy-loads Avatar3D in 'lite' mode.
3. Falls back to a plain backdrop if 3D is not possible.

### 3. How does it work?
PEOPLE maps each interviewer id (aria, victor, marcus, elena) to a .glb model. The component plays only the idle/listening animation; no audio or recording.

### 4. Important functions
```text
   - InterviewerStage()
       Container that renders the 3D avatar with a caption.
   - webglOk()
       Returns true if WebGL is available.
   Other helper functions: Avatar3D
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/Avatar3D.jsx
   Used by: pages/AuthShell.jsx, pages/student/StudentDashboard.jsx
```
External packages: react

### 7. Input and output
- **Input:** Props: who, mode, className, caption, children.
- **Output:** A 3D animated interviewer or a static backdrop.

### 8. Real project example
The login page shows Aria standing and 'listening' next to the sign-in form.

### 9. Viva explanation
> InterviewerStage reuses our 3D avatar in a light mode as a visual element, loading it only when the page is idle.

---

## File: `frontend/src/components/Logo.jsx`

### 1. Purpose
Draws the HireSense logo (an 'H' mark) and the product name.

### 2. What does it do?
1. LogoMark draws the SVG icon with a gradient.
2. Logo shows the icon plus the 'HireSense' text.

### 3. How does it work?
useId() gives each logo a unique gradient id so several logos on one page do not break each other.

### 4. Important functions
```text
   Other helper functions: LogoMark, Logo
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: components/AppShellLayout.jsx, pages/AuthShell.jsx,
   pages/recruiter/CandidateReport.jsx
```
External packages: react

### 7. Input and output
- **Input:** Not applicable.
- **Output:** SVG logo.

### 8. Real project example
Shown at the top of the sidebar and on the login page.

### 9. Viva explanation
> A small presentational component for the brand logo.

---

## File: `frontend/src/components/PlacementReadinessCard.jsx`

### 1. Purpose
Shows the student's placement-readiness score: overall score, level and per-area bars.

### 2. What does it do?
1. Shows the level as a coloured pill (Placement ready / Almost ready / Needs preparation).
2. Shows bars for interviews, assessments, English, resume and profile.

### 3. How does it work?
It only displays the readiness object; the score is calculated on the backend (student_performance_insights.py).

### 4. Important functions
```text
   - ReadinessCard()
       Card with the readiness score and area bars.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx
   Used by: pages/student/PerformanceReport.jsx, pages/student/StudentDashboard.jsx
```

### 7. Input and output
- **Input:** Prop: readiness (from the dashboard or report API).
- **Output:** Rendered card.

### 8. Real project example
On the dashboard a student sees 'Almost ready - 68' with a weak English bar.

### 9. Viva explanation
> The readiness card visualises a transparent weighted score computed by the backend.

---

## File: `frontend/src/components/SharedUiComponents.jsx`

### 1. Purpose
The shared user-interface kit: buttons, cards, tables, pop-ups, toasts, a data-loading hook and date helpers used by every page.

### 2. What does it do?
Reusable UI building blocks so all pages look and behave the same.

1. useApi(): loads data from the API and tracks loading / error / data state.
2. ToastProvider + useToast(): small pop-up success/error messages.
3. Visual components: Button, Card, StatCard, Pill, StatusPill, Spinner, ErrorBox, Notice, EmptyState, PageHeader.
4. Form and layout helpers: Field, Modal, ConfirmButton, Table, Pagination, Tabs, ScoreBar, TagInput.
5. Date helpers: fmtDate, fmtDateTime, toLocalInput, fromLocalInput.

### 3. How does it work?
Each component is a small React function that takes props and returns Tailwind-styled JSX. useApi keeps the loader function in a ref and re-runs it when its dependency list changes; reload() can be called after an update.

```
Page imports a component or hook
   |
   v
Passes props / a loader
   |
   v
Component renders consistent UI
   |
   v
User actions call the page's callbacks
```

### 4. Important functions
```text
   - useApi()
       Hook: runs an async loader (usually get('/...')) and returns {data, setData, error,
       loading, reload}.
   - ToastProvider()
       Context provider that shows toast messages in the bottom-right corner (auto-hide after
       4-7 s).
   - useToast()
       Hook returning the function used to show a toast.
   - Button()
       Styled button with variants (primary, secondary, danger, ghost, success) and a loading
       spinner.
   - Card()
       Panel with an optional title and action buttons.
   - Table()
       Data table with an empty message; rows can be clickable.
   - Modal()
       Pop-up dialog with a title, body and footer buttons.
   - ConfirmButton()
       Button that asks 'Are you sure?' in a modal before running onConfirm.
   - ScoreBar()
       Horizontal bar that shows a score out of 100 (or another maximum).
   - TagInput()
       Input where the user types a skill and presses Enter to add it as a tag.
   Other helper functions: StatCard, Pill, StatusPill, Spinner, ErrorBox, Notice, EmptyState,
   PageHeader, Field, Pagination, Tabs, fmtDate, fmtDateTime, toLocalInput, fromLocalInput
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: App.jsx, components/AppShellLayout.jsx, components/ConversationMemory.jsx,
   components/DashboardCharts.jsx, components/EnglishDailyPlan.jsx,
   components/EnglishMistakeProfile.jsx, components/EnglishProgress.jsx,
   components/HostedAiConsentGate.jsx, components/PlacementReadinessCard.jsx, main.jsx,
   monitoring/InterviewMonitorBar.jsx, pages/AccountSettings.jsx, pages/ForgotPassword.jsx,
   pages/Login.jsx, pages/NotFound.jsx, pages/Notifications.jsx, pages/ProfileEditor.jsx,
   pages/Register.jsx, pages/ResetPassword.jsx, pages/admin/AdminDashboard.jsx,
   pages/admin/AdminJobPostings.jsx, pages/admin/AdminMonitoring.jsx,
   pages/admin/AdminRewardRules.jsx, pages/admin/AuditLogs.jsx, pages/admin/InterviewConfig.jsx,
   pages/admin/MentorAssignments.jsx, pages/admin/PlacementReports.jsx,
   pages/admin/PlatformSettings.jsx, pages/admin/SecuritySettings.jsx,
   pages/admin/UserManagement.jsx, pages/mentor/MentorDashboard.jsx,
   pages/mentor/MentorSessions.jsx, pages/mentor/MentorStudentDetail.jsx,
   pages/mentor/MentorStudentList.jsx, pages/recruiter/CandidateDetail.jsx,
   pages/recruiter/CandidateReport.jsx, pages/recruiter/CandidateSearch.jsx,
   pages/recruiter/CompareCandidates.jsx, pages/recruiter/IntegrityOverview.jsx,
   pages/recruiter/RecruiterDashboard.jsx, pages/recruiter/RecruiterJobApplicants.jsx,
   pages/recruiter/RecruiterJobPostings.jsx, pages/shared/AssessmentManager.jsx,
   pages/shared/IntegrityReview.jsx, pages/student/EnglishAvatarSession.jsx,
   pages/student/EnglishPracticeHome.jsx, pages/student/EnglishSession.jsx,
   pages/student/InterviewSession.jsx, pages/student/InterviewSetup.jsx,
   pages/student/InterviewerFeedback.jsx, pages/student/InterviewerPicker.jsx,
   pages/student/JobApplications.jsx, pages/student/LiveVoiceInterview.jsx,
   pages/student/MockInterviewHome.jsx, pages/student/PerformanceReport.jsx,
   pages/student/PlacementDrives.jsx, pages/student/PracticeHistory.jsx,
   pages/student/ProgressOverview.jsx, pages/student/ResumeUploadAndAnalysis.jsx,
   pages/student/StudentAssessments.jsx, pages/student/StudentDashboard.jsx,
   pages/student/StudentJobOpenings.jsx, pages/student/StudentMentoring.jsx,
   pages/student/StudentRewards.jsx, pages/student/VocabularyTrainer.jsx, voice/AnswerDock.jsx,
   voice/ControlBar.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Props from pages (titles, rows, values, callbacks) and loader functions for useApi.
- **Output:** Rendered UI elements; useApi returns loaded data.

### 8. Real project example
The student dashboard uses useApi(() => get('/student/dashboard')) and shows the numbers in StatCard components.

### 9. Viva explanation
> SharedUiComponents.jsx is our component library. Keeping buttons, cards, tables and the useApi hook in one place keeps the design consistent and avoids repeating code in every page.

---

## File: `frontend/src/components/UrlTabs.jsx`

### 1. Purpose
Tabs whose selected tab is kept in the page URL (?tab=...), so tabs can be linked and the back button works.

### 2. What does it do?
1. Reads ?tab= from the URL.
2. Shows the tab buttons and the active tab's content.
3. Updates the URL when a tab is clicked.

### 3. How does it work?
Uses React Router's useSearchParams. The first tab is the default and has no ?tab parameter.

### 4. Important functions
```text
   - UrlTabs()
       Renders tab buttons and the selected tab panel.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: pages/student/JobsAndDrives.jsx, pages/student/ProgressHub.jsx
```
External packages: react-router-dom

### 7. Input and output
- **Input:** Props: tabs [{id, label, element}], label.
- **Output:** Tab bar and active panel.

### 8. Real project example
'My progress' uses it for Overview / Full report / Practice history.

### 9. Viva explanation
> UrlTabs stores the selected tab in the URL so each tab is bookmarkable.

---

## File: `frontend/src/components/browserCodeRunner.js`

### 1. Purpose
Lets a student test their JavaScript coding answer against sample test cases inside the browser.

### 2. What does it do?
1. Creates a Web Worker from a small script.
2. Runs the student's function on each test case and compares the output.
3. Stops the worker after a timeout (to catch infinite loops).

### 3. How does it work?
The code runs in a separate worker thread with no access to the page. Results come back by postMessage.

### 4. Important functions
```text
   - runJavaScript()
       Runs code + function name + test cases in a worker and resolves with results or an
       error.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: pages/student/StudentAssessments.jsx
```

### 7. Input and output
- **Input:** Student code, function name, test cases, timeout.
- **Output:** A promise with pass/fail per test case.

### 8. Real project example
In a coding assessment the student clicks 'Run tests' and sees which sample cases pass.

### 9. Viva explanation
> browserCodeRunner safely executes student code in a Web Worker sandbox with a timeout.

**Note:** This is only for self-checking. The official grade comes from the backend's AI code review.

---

## File: `frontend/src/components/scoreBandLabel.js`

### 1. Purpose
Turns a 0-100 interview score into a band label such as 'Strong (75-89)'.

### 2. What does it do?
1. Defines five bands: Outstanding, Strong, Competent, Developing, Needs work.
2. Clamps the score to 0-100 and returns the matching band.

### 3. How does it work?
Same table as the backend file score_band_labels.py, so both sides show the same labels.

### 4. Important functions
```text
   - scoreBand()
       Returns {key, label, min, max, text} for a score, or null.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: pages/student/InterviewSession.jsx, pages/student/LiveVoiceInterview.jsx
   Tested by: components/scoreBandLabel.test.js
```

### 7. Input and output
- **Input:** A score number.
- **Output:** A band object.

### 8. Real project example
An answer scored 82 is shown as 'Strong (75-89)'.

### 9. Viva explanation
> AI scores have some noise, so we show a band instead of treating 82 and 84 as different.

---

## File: `frontend/src/components/scoreBandLabel.test.js`

### 1. Purpose
Unit tests for scoreBandLabel.js.

### 2. What does it do?
1. Checks that scores map to the same bands as the backend.
2. Checks missing and out-of-range scores.

### 3. How does it work?
Runs with Vitest (npm test).

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/scoreBandLabel.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run automatically in CI and with `npm test`.

### 9. Viva explanation
> This test keeps the frontend score bands identical to the backend ones.

---

## File: `frontend/src/components/useSpeechAndPreferences.jsx`

### 1. Purpose
Browser speech helpers for the English practice pages: speech-to-text, text-to-speech, subtitles and voice preferences.

### 2. What does it do?
1. usePrefs(): reads speech language, subtitles and speech rate from the user's preferences.
2. useSpeechToText(): uses the browser Web Speech API to turn the microphone into text.
3. useSpeaker(): reads text aloud with browser speechSynthesis and tracks the current word for subtitles.
4. Subtitles: caption bar that highlights the word being spoken.
5. speak()/stopSpeaking(): simple fire-and-forget speech.

### 3. How does it work?
These are React hooks around the browser's SpeechRecognition and speechSynthesis APIs.

### 4. Important functions
```text
   - usePrefs()
       Returns the user's speech language, subtitle and rate preferences.
   - useSpeechToText()
       Starts/stops browser speech recognition and returns the transcript.
   - useSpeaker()
       Speaks text and exposes subtitle state.
   - Subtitles()
       Shows highlighted subtitles while speaking.
   - speak()
       Back-compat helpers for places that only need fire-and-forget speech.
   Other helper functions: stopSpeaking
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx
   Used by: pages/AccountSettings.jsx, pages/student/EnglishAvatarSession.jsx,
   pages/student/EnglishSession.jsx, pages/student/InterviewSession.jsx,
   pages/student/InterviewerPicker.jsx, pages/student/LiveVoiceInterview.jsx
```
External packages: react

### 7. Input and output
- **Input:** User preferences; microphone audio; text to speak.
- **Output:** Transcripts, spoken audio and subtitle UI.

### 8. Real project example
In a text English session the student presses the mic button and their speech appears as text.

### 9. Viva explanation
> This file wraps the browser's speech APIs as React hooks. It is used for English practice; the interview uses our own local speech recognition.

**Note:** In Chrome/Edge the Web Speech API sends audio to Google/Microsoft. The live AI interview does NOT use it; it uses voice/recorder.js and the backend Whisper model.

---

# Frontend - authentication and common pages

## File: `frontend/src/pages/AccountSettings.jsx`

### 1. Purpose
Account settings for every role.

### 2. What does it do?
1. Speech language, voice and subtitle preferences (GET/PUT /settings).
2. Hosted-AI consent on/off (POST /auth/ai-consent).
3. Change password (POST /auth/change-password).
4. Students can permanently delete their account (DELETE /auth/me).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /settings, PUT /settings, POST /auth/ai-consent, POST /auth/change-password, DELETE /auth/me.

### 4. Important functions
```text
   - Settings()
       Page component.
   - AIConsentSetting()
       Consent toggle.
   - DeleteAccount()
       Account deletion section.
   - Toggle()
       Switch UI.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/HostedAiConsentGate.jsx,
   components/SharedUiComponents.jsx, components/useSpeechAndPreferences.jsx
   Used by: App.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** User preferences and form input.
- **Output:** Saved settings.

### 8. Real project example
A student switches speech language to en-IN and turns on subtitles before English practice.

### 9. Viva explanation
> AccountSettings lets users control preferences, privacy consent, password and account deletion.

---

## File: `frontend/src/pages/AuthShell.jsx`

### 1. Purpose
The two-column layout shared by the login, register, forgot-password and reset-password pages.

### 2. What does it do?
1. Left: a dark product panel with a headline, a live 3D interviewer (InterviewerStage) and a sample report preview.
2. Right: the form passed in as children.

### 3. How does it work?
A layout component; ReportPreview is a static mock-up of a report card for decoration.

### 4. Important functions
```text
   - AuthShell()
       The layout wrapper.
   - ReportPreview()
       Decorative example report card.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/InterviewerStage.jsx, components/Logo.jsx
   Used by: pages/ForgotPassword.jsx, pages/Login.jsx, pages/Register.jsx,
   pages/ResetPassword.jsx
```

### 7. Input and output
- **Input:** Props: title, subtitle, children (the form).
- **Output:** The page layout.

### 8. Real project example
Every signed-out page looks the same because they all use AuthShell.

### 9. Viva explanation
> AuthShell is a shared layout component for the authentication pages.

---

## File: `frontend/src/pages/ForgotPassword.jsx`

### 1. Purpose
Page to request a password-reset link by email.

### 2. What does it do?
1. Takes the account email.
2. Calls POST /auth/forgot-password.
3. Always shows the same neutral message.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: POST /auth/forgot-password.

### 4. Important functions
```text
   - ForgotPassword()
       Form component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/AuthShell.jsx
   Used by: App.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** Email address.
- **Output:** Confirmation message.

### 8. Real project example
A student who forgot their password asks for a reset link.

### 9. Viva explanation
> The reply is always the same so nobody can find out which emails have accounts.

---

## File: `frontend/src/pages/Login.jsx`

### 1. Purpose
The sign-in page for all four roles.

### 2. What does it do?
1. Shows email and password fields inside AuthShell.
2. Calls login() from AuthContext (POST /auth/login sets the session cookie).
3. Shows an error message if sign-in fails.
4. After login, App.jsx sends the user to their portal home.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: POST /auth/login (through AuthContext.login).

```
User enters email + password
   |
   v
login() calls POST /auth/login
   |
   v
Backend sets cookie
   |
   v
/auth/me loads user
   |
   v
Redirect to portal
```

### 4. Important functions
```text
   - Login()
       Login form component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, components/SharedUiComponents.jsx, pages/AuthShell.jsx
   Used by: App.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** Email and password typed by the user.
- **Output:** A signed-in session or an error message.

### 8. Real project example
A student enters their college email and password and lands on /student.

### 9. Viva explanation
> The login page uses the AuthContext login function; the backend sets an httpOnly cookie, so no token is kept in JavaScript.

---

## File: `frontend/src/pages/NotFound.jsx`

### 1. Purpose
The 404 page for unknown URLs inside the signed-in app.

### 2. What does it do?
1. Shows a 'page not found' message with a link home.

### 3. How does it work?
A tiny component rendered by the catch-all route in App.jsx.

### 4. Important functions
```text
   Other helper functions: NotFound
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: react-router-dom

### 7. Input and output
- **Input:** Unknown URL.
- **Output:** 404 message.

### 8. Real project example
Typing a wrong URL like /student/xyz shows this page.

### 9. Viva explanation
> A simple fallback route.

---

## File: `frontend/src/pages/Notifications.jsx`

### 1. Purpose
The full notifications list for any role.

### 2. What does it do?
1. Loads GET /notifications with paging.
2. Marks one as read (POST /notifications/{id}/read) or all (POST /notifications/read-all).
3. Deletes a notification (DELETE /notifications/{id}).
4. Shows whether the live connection is active and reloads on live signals.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /notifications, POST /notifications/{id}/read, POST /notifications/read-all, DELETE /notifications/{id}.

### 4. Important functions
```text
   - Notifications()
       Page component.
   - LiveStatus()
       Shows live connection status.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, live/notificationStream.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Notification list from the API and live stream signals.
- **Output:** Notification list UI.

### 8. Real project example
A student opens all notifications to see 'You have been shortlisted'.

### 9. Viva explanation
> This page lists notifications and stays up to date through Server-Sent Events.

---

## File: `frontend/src/pages/Privacy.jsx`

### 1. Purpose
Public privacy notice page (/privacy).

### 2. What does it do?
1. Loads GET /auth/privacy (through usePrivacyInfo) to know which AI provider this server uses.
2. Explains what data is processed and where.
3. Shows the AI consent card for students when needed.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /auth/privacy.

### 4. Important functions
```text
   Other helper functions: Privacy
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, components/HostedAiConsentGate.jsx
   Used by: App.jsx
```
External packages: react-router-dom

### 7. Input and output
- **Input:** Server privacy info.
- **Output:** Privacy text.

### 8. Real project example
Before registering, a student reads whether their resume will be processed locally or by Google Gemini.

### 9. Viva explanation
> The privacy page is generated from the server's real configuration, so it is always accurate.

---

## File: `frontend/src/pages/ProfileEditor.jsx`

### 1. Purpose
Profile editor for each role.

### 2. What does it do?
1. Students: education, CGPA, skills, projects, experience, target role, links.
2. Recruiters: company details.
3. Mentors: department, expertise.
4. Saves with PUT /profile.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: PUT /profile (profile data comes from the logged-in user).

### 4. Important functions
```text
   - Profile()
       Page component.
   - StudentFields()
       Student form fields.
   - RecruiterFields()
       Recruiter form fields.
   - MentorFields()
       Mentor form fields.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Form fields.
- **Output:** Updated profile.

### 8. Real project example
A student adds 'React' and 'Python' as skills, which are then used in interviews and job matching.

### 9. Viva explanation
> The profile page shows different fields per role; a student's skills and target role feed the AI interview and job matching.

---

## File: `frontend/src/pages/Register.jsx`

### 1. Purpose
Self-registration page for students and recruiters.

### 2. What does it do?
1. Lets the user choose student or recruiter.
2. Collects name, email, password and role-specific details.
3. Calls POST /auth/register/{role}.
4. Shows the hosted-AI consent notice when the server uses Gemini.
5. Recruiters may stay 'pending' until an admin approves them.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: POST /auth/register/student, POST /auth/register/recruiter.

### 4. Important functions
```text
   - Register()
       Registration form component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/HostedAiConsentGate.jsx,
   components/SharedUiComponents.jsx, pages/AuthShell.jsx
   Used by: App.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** Form fields typed by the user.
- **Output:** A new account (and sign-in for students).

### 8. Real project example
A new student creates an account before their first mock interview.

### 9. Viva explanation
> Register.jsx sends the form to the backend registration endpoint; the backend validates password strength and duplicate emails.

---

## File: `frontend/src/pages/ResetPassword.jsx`

### 1. Purpose
Page that sets a new password from the emailed reset link.

### 2. What does it do?
1. Reads the token from the URL (?token=...).
2. Asks for the new password twice.
3. Calls POST /auth/reset-password.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: POST /auth/reset-password.

### 4. Important functions
```text
   - ResetPassword()
       Form component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/AuthShell.jsx
   Used by: App.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** Token from the URL and the new password.
- **Output:** Password changed message.

### 8. Real project example
The student clicks the link in the email and sets a new password.

### 9. Viva explanation
> The reset token is tied to the current password, so an old link stops working after use.

---

# Frontend - student pages

## File: `frontend/src/pages/student/EnglishAvatarSession.jsx`

### 1. Purpose
Face-to-face spoken English practice with the Aria avatar, hands-free.

### 2. What does it do?
1. Aria speaks with lip sync and subtitles (POST /voice/speak, SpeechPlayer).
2. The mic opens automatically; the student speaks.
3. Speech is transcribed by the server's Whisper (POST /student/english/{id}/transcribe) or by the browser.
4. Sends the text as a message (POST /student/english/{id}/message) and shows corrections on screen.
5. Ends (POST .../end) or deletes (DELETE /student/english/{id}) the session; shows streak stats (GET /student/english/stats).

### 3. How does it work?
Uses useReducer with englishTransition, a SpeechPlayer and MicRecorder in refs, and Avatar3D (lazy-loaded). Falls back to browser speech recognition or typing when local speech is not available.

### 4. Important functions
```text
   - EnglishAvatarSession()
       Page component.
   - Conversation()
       Transcript panel.
   - SubtitleLine()
       Subtitles.
   - Avatar3D()
       three.js is large: load the 3D avatar only when this page is opened.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/ConversationMemory.jsx, components/SharedUiComponents.jsx,
   components/useSpeechAndPreferences.jsx, voice/Avatar3D.jsx, voice/SvgAvatar2D.jsx,
   voice/englishMachine.js, voice/recorder.js, voice/speechPlayer.js
   Used by: pages/student/EnglishSession.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Props: initial session, onEnded; microphone audio.
- **Output:** Spoken conversation UI.

### 8. Real project example
A student speaks about their weekend; Aria replies by voice and shows 'I go -> I went' on screen.

### 9. Viva explanation
> This page uses the englishMachine state machine, local speech recognition and TTS for a natural spoken conversation.

---

## File: `frontend/src/pages/student/EnglishPracticeHome.jsx`

### 1. Purpose
Home page of English conversation practice.

### 2. What does it do?
1. Starts a new conversation (POST /student/english) with topic, style, learning mode and text/voice.
2. Shows the companion's modes (GET /student/english/companion).
3. Shows today's plan, word-list summary, mistake profile and progress.
4. Lists past sessions (GET /student/english).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: POST /student/english, GET /student/english, GET /student/english/companion, GET /student/english/vocabulary/review.

### 4. Important functions
```text
   - English()
       Page component.
   Other helper functions: chip
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/EnglishDailyPlan.jsx,
   components/EnglishMistakeProfile.jsx, components/EnglishProgress.jsx,
   components/HostedAiConsentGate.jsx, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Student choices; ?mode= from the daily plan.
- **Output:** A new English session.

### 8. Real project example
A student chooses 'Job interview practice' in voice mode to rehearse self-introduction.

### 9. Viva explanation
> This page configures English practice with Aria, the AI conversation partner.

---

## File: `frontend/src/pages/student/EnglishSession.jsx`

### 1. Purpose
One English conversation: text chat, ending and final scores.

### 2. What does it do?
1. Loads the session (GET /student/english/{id}).
2. For voice sessions in progress, renders EnglishAvatarSession.
3. Text chat: streams Aria's reply (POST /api/student/english/{id}/message/stream via streamPost).
4. Ends the session (POST /student/english/{id}/end) and shows grammar, vocabulary, fluency scores and feedback.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/english/{id}, POST /student/english/{id}/message/stream, POST /student/english/{id}/end.

### 4. Important functions
```text
   - EnglishSession()
       Page component.
   - EnglishChat()
       Text chat panel.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/ConversationMemory.jsx, components/DashboardCharts.jsx,
   components/SharedUiComponents.jsx, components/useSpeechAndPreferences.jsx,
   pages/student/EnglishAvatarSession.jsx, voice/turnStream.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Session id and typed messages.
- **Output:** Chat UI and evaluation.

### 8. Real project example
A student chats about their hobbies and gets a grammar correction on screen.

### 9. Viva explanation
> EnglishSession shows the chat and the AI evaluation of the student's English.

---

## File: `frontend/src/pages/student/InterviewSession.jsx`

### 1. Purpose
Text-mode interview page and the results/report view for any finished interview.

### 2. What does it do?
1. Loads the session (GET /student/interviews/{id}).
2. Runs the setup screen (consent + device check) and typed monitoring.
3. Submits typed answers (POST /student/interviews/{id}/answer) and shows the score.
4. Finishes (POST .../complete), retries scoring (POST .../retry-evaluation) or abandons (DELETE /student/interviews/{id}).
5. Shows the full InterviewReport: overall score, band, per-question scores, feedback, sample answers, strengths and weaknesses.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET/DELETE /student/interviews/{id}, POST .../answer, POST .../complete, POST .../retry-evaluation.

```
Load session
   |
   v
Show question
   |
   v
Student types answer
   |
   v
POST .../answer -> score + next question
   |
   v
POST .../complete -> report
```

### 4. Important functions
```text
   - InterviewSession()
       Page component.
   - InterviewReport()
       Full report view (exported, reused elsewhere).
   - AnswerDetails()
       Feedback, strengths and missing points for one answer.
   - SampleAnswer()
       Shows the model answer.
   - QuestionRow()
       One question with its score.
   - Indicators()
       Observable answer indicators.
   Other helper functions: scoreTone, scoreText, BulletList
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, components/scoreBandLabel.js,
   components/useSpeechAndPreferences.jsx, monitoring/InterviewMonitorBar.jsx,
   monitoring/useTypedMonitoring.js, pages/student/InterviewSetup.jsx,
   pages/student/InterviewerFeedback.jsx, voice/useInterviewers.js
   Used by: App.jsx, pages/admin/AdminMonitoring.jsx, pages/mentor/MentorStudentDetail.jsx,
   pages/recruiter/CandidateDetail.jsx, pages/student/LiveVoiceInterview.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Interview id from the URL; typed answers.
- **Output:** Questions, scores and the final report.

### 8. Real project example
A student types an answer about database indexing, gets 72 (Competent), then the next harder question appears.

### 9. Viva explanation
> This page runs the text interview and also shows the AI report; the report component is reused by the voice interview and mentors.

---

## File: `frontend/src/pages/student/InterviewSetup.jsx`

### 1. Purpose
Steps before an interview: explanation and monitoring consent, device checks, then start.

### 2. What does it do?
1. Loads the monitoring policy (GET /monitoring/policy).
2. Shows each monitoring feature with a separate opt-in.
3. Tests camera, microphone and network (mediaSession.js) and face framing (faceMonitor.js, frameAnalysis.js).
4. Saves consent (POST /student/interviews/{id}/monitoring/consent).
5. Warms up the AI/voice models (POST /voice/warmup).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /monitoring/policy, POST /student/interviews/{id}/monitoring/consent, POST /voice/warmup.

### 4. Important functions
```text
   - InterviewSetup()
       Setup component.
   - Term()
       One monitoring feature row.
   - Check()
       One device check row.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, monitoring/faceMonitor.js,
   monitoring/frameAnalysis.js, monitoring/mediaSession.js, monitoring/objectMonitor.js
   Used by: pages/student/InterviewSession.jsx, pages/student/LiveVoiceInterview.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Props: session, persona, voice, camera, onStart, typed.
- **Output:** Consented features and a start signal.

### 8. Real project example
Before a voice interview, the student ticks 'camera' and 'face presence', tests the mic and presses Start.

### 9. Viva explanation
> InterviewSetup implements informed, per-feature consent and device checks before the interview.

---

## File: `frontend/src/pages/student/InterviewerFeedback.jsx`

### 1. Purpose
End-of-interview closing remarks spoken by the interviewer.

### 2. What does it do?
1. Reads the AI-written closing_remarks from the report.
2. Plays them with the local voice (POST /voice/speak) and lip sync on the 3D avatar.
3. Nothing plays automatically; the student presses play.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /voice/status, POST /voice/speak.

### 4. Important functions
```text
   - InterviewerFeedback()
       Feedback component.
   Other helper functions: Avatar3D
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, voice/Avatar3D.jsx,
   voice/speechPlayer.js, voice/useInterviewers.js
   Used by: pages/student/InterviewSession.jsx, pages/student/LiveVoiceInterview.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Props: session, persona.
- **Output:** Spoken feedback with an animated avatar.

### 8. Real project example
After finishing, Elena reads out a short summary of the student's strengths.

### 9. Viva explanation
> This component gives a human-like ending to the interview using TTS and the 3D avatar.

---

## File: `frontend/src/pages/student/InterviewerPicker.jsx`

### 1. Purpose
Interviewer selection cards with a live 3D preview and a voice sample.

### 2. What does it do?
1. Shows one card per interviewer personality with level and style.
2. Filters by interview type.
3. Plays a voice preview (POST /voice/speak) that the avatar lip-syncs.
4. Renders the 3D preview only while the card is visible (LazyAvatar).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: POST /voice/speak.

### 4. Important functions
```text
   - InterviewerPicker()
       Selection component.
   - LazyAvatar()
       3D preview rendered only when on screen.
   Other helper functions: Avatar3D
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, components/useSpeechAndPreferences.jsx,
   voice/Avatar3D.jsx, voice/speechPlayer.js, voice/useInterviewers.js
   Used by: pages/student/MockInterviewHome.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Props: interviewers, value, onSelect, voiceStatus.
- **Output:** The selected interviewer id.

### 8. Real project example
The student listens to Marcus's sample before choosing a stress interview.

### 9. Viva explanation
> Each personality changes interview style, but scoring is the same for all.

---

## File: `frontend/src/pages/student/JobApplications.jsx`

### 1. Purpose
The student's job applications.

### 2. What does it do?
1. Lists applications and their status (GET /student/applications).
2. Withdraws an application (POST /student/applications/{id}/withdraw).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/applications, POST /student/applications/{id}/withdraw.

### 4. Important functions
```text
   - Applications()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/filterChipStyle.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Applications.
- **Output:** Status list.

### 8. Real project example
A student sees 'Shortlisted' for one application.

### 9. Viva explanation
> Students track recruitment status here.

---

## File: `frontend/src/pages/student/JobsAndDrives.jsx`

### 1. Purpose
'Jobs & drives' area with two URL tabs.

### 2. What does it do?
1. Shows StudentJobOpenings and PlacementDrives as tabs.

### 3. How does it work?
Only arranges child pages in UrlTabs.

### 4. Important functions
```text
   - Opportunities()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/UrlTabs.jsx, pages/student/PlacementDrives.jsx,
   pages/student/StudentJobOpenings.jsx
   Used by: App.jsx
```

### 7. Input and output
- **Input:** URL ?tab=.
- **Output:** Tabbed page.

### 8. Real project example
A student switches to the 'Drives' tab to register for a campus drive.

### 9. Viva explanation
> Combines job openings and campus drives in one menu item.

---

## File: `frontend/src/pages/student/LiveVoiceInterview.jsx`

### 1. Purpose
The live voice interview room with an animated interviewer (route /student/interviews/:id/live).

### 2. What does it do?
1. Runs InterviewSetup first (consent, camera/microphone check, policy).
2. The interviewer speaks each question with lip sync (SpeechPlayer, Avatar3D or SvgAvatar2D).
3. The student answers by microphone (MicRecorder -> POST /student/interviews/{id}/transcribe, local Whisper) or by typing.
4. Sends the answer with streamTurn (POST .../turn, Server-Sent Events): score first, then the next question streamed sentence by sentence.
5. Runs consented monitoring (InterviewMonitor) and lets the student withdraw it.
6. Finishes with POST .../complete and shows InterviewerFeedback and InterviewReport.

### 3. How does it work?
The screen state lives in a useReducer with transition() from voice/interviewMachine.js. Refs hold the SpeechPlayer, MicRecorder, InterviewMonitor and settings. Each answer goes through streamTurn; event handlers play audio sentences as they arrive and update the score. Room settings and notes are stored in browser storage.

```
Setup: consent + device check
   |
   v
Interviewer speaks question
   |
   v
Student answers (mic -> transcribe)
   |
   v
POST .../turn streams score + next question
   |
   v
Repeat until last question
   |
   v
POST .../complete -> feedback + report
```

### 4. Important functions
```text
   - VoiceInterview()
       Page component that coordinates the whole voice interview.
   - Avatar3D()
       three.js is large: load the 3D interviewer only when this page is opened.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, components/scoreBandLabel.js,
   components/useSpeechAndPreferences.jsx, monitoring/InterviewMonitorBar.jsx,
   monitoring/eventReporter.js, monitoring/interviewMonitor.js, monitoring/mediaSession.js,
   pages/student/InterviewSession.jsx, pages/student/InterviewSetup.jsx,
   pages/student/InterviewerFeedback.jsx, voice/AnswerDock.jsx, voice/Avatar3D.jsx,
   voice/ControlBar.jsx, voice/RoomParts.jsx, voice/RoomSettingsPanel.jsx,
   voice/RoomSidePanels.jsx, voice/SvgAvatar2D.jsx, voice/avatarStates.js,
   voice/interviewMachine.js, voice/recorder.js, voice/roomUtils.js, voice/speechPlayer.js,
   voice/turnStream.js, voice/useInterviewers.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Interview id, microphone audio, typed text, camera frames (analysed locally).
- **Output:** Spoken questions, live captions, scores and the final report.

### 8. Real project example
A student speaks an answer about their hospital project; within a few seconds Aria reacts and asks a follow-up about their personal contribution.

### 9. Viva explanation
> This is the main interview screen. A useReducer state machine (interviewMachine.js) controls the flow, speech is streamed for low delay, and monitoring is consent-based.

**Note:** Timing-sensitive code: change with care and re-run the voice end-to-end tests in backend/tests_e2e.

---

## File: `frontend/src/pages/student/MockInterviewHome.jsx`

### 1. Purpose
Start page and history of mock interviews.

### 2. What does it do?
1. Step 1: choose an interviewer personality (InterviewerPicker).
2. Step 2: choose job role, category, text or voice mode, number of questions and response mode.
3. Creates the interview with POST /student/interviews.
4. Opens the text interview or the live voice room (/live).
5. Lists past interviews (GET /student/interviews).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/interviews, GET /voice/status, POST /student/interviews.

```
Pick interviewer
   |
   v
Set role, category, mode, count
   |
   v
POST /student/interviews
   |
   v
Go to InterviewSession or LiveVoiceInterview
```

### 4. Important functions
```text
   - Interviews()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/HostedAiConsentGate.jsx,
   components/SharedUiComponents.jsx, pages/student/InterviewerPicker.jsx,
   voice/useInterviewers.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Student's choices.
- **Output:** A new interview session and navigation to it.

### 8. Real project example
A student picks Victor, role 'Java Developer', 'technical', voice mode and 5 questions, then starts.

### 9. Viva explanation
> This is the interview configuration step: the backend creates a session and generates the first AI question.

---

## File: `frontend/src/pages/student/PerformanceReport.jsx`

### 1. Purpose
Full performance report of the student.

### 2. What does it do?
1. Loads GET /student/report.
2. Shows readiness, area scores, a weekly activity chart and every attempt with change vs. the previous attempt.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/report.

### 4. Important functions
```text
   - PerformanceReport()
       Page component.
   - AttemptsTable()
       All attempts.
   - WeeklyChart()
       Weekly activity chart.
   - AreaScores()
       Scores per area.
   Other helper functions: Bullets
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/PlacementReadinessCard.jsx,
   components/SharedUiComponents.jsx
   Used by: pages/student/ProgressHub.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Report data.
- **Output:** Report UI.

### 8. Real project example
Before placements a student reviews all past attempts and their weak areas.

### 9. Viva explanation
> The performance report shows strengths, weaknesses and improvement over time.

---

## File: `frontend/src/pages/student/PlacementDrives.jsx`

### 1. Purpose
Campus placement drives for students.

### 2. What does it do?
1. Lists drives (GET /student/drives).
2. Registers (POST /student/drives/{id}/register) or cancels (DELETE ...).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/drives, POST/DELETE /student/drives/{id}/register.

### 4. Important functions
```text
   - StudentDrives()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: pages/student/JobsAndDrives.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Drive list.
- **Output:** Registration status.

### 8. Real project example
A student registers for an upcoming campus drive.

### 9. Viva explanation
> Drive registration for campus recruitment.

---

## File: `frontend/src/pages/student/PracticeHistory.jsx`

### 1. Purpose
All practice activities in one filterable list.

### 2. What does it do?
1. Loads GET /student/history with a type filter.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/history.

### 4. Important functions
```text
   Other helper functions: PracticeHistory
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/filterChipStyle.js
   Used by: pages/student/ProgressHub.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** Filter.
- **Output:** History list.

### 8. Real project example
The student filters to see only English sessions.

### 9. Viva explanation
> One list of interviews, English sessions and assessments.

---

## File: `frontend/src/pages/student/ProgressHub.jsx`

### 1. Purpose
'My progress' area with three URL tabs.

### 2. What does it do?
1. Combines ProgressOverview, PerformanceReport and PracticeHistory with UrlTabs.

### 3. How does it work?
Only arranges child pages in UrlTabs.

### 4. Important functions
```text
   - ProgressHub()
       One "My Progress" area instead of three separate menu items (Progress, Performance
       Report, Practice History).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/UrlTabs.jsx, pages/student/PerformanceReport.jsx,
   pages/student/PracticeHistory.jsx, pages/student/ProgressOverview.jsx
   Used by: App.jsx
```

### 7. Input and output
- **Input:** URL ?tab=.
- **Output:** Tabbed page.

### 8. Real project example
The student opens 'My progress' and switches to 'Full report'.

### 9. Viva explanation
> ProgressHub merges three progress pages into one menu item.

---

## File: `frontend/src/pages/student/ProgressOverview.jsx`

### 1. Purpose
Progress overview with charts and AI recommendations.

### 2. What does it do?
1. Loads GET /student/progress.
2. Shows summary charts.
3. RecommendationsCard asks the AI for study recommendations (endpoint passed as prop).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/progress (recommendations endpoint such as POST /student/recommendations).

### 4. Important functions
```text
   - Progress()
       Page component.
   - SummaryCharts()
       Charts (reused).
   - RecommendationsCard()
       AI recommendations (reused).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx
   Used by: pages/mentor/MentorStudentDetail.jsx, pages/student/ProgressHub.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Progress data.
- **Output:** Charts and recommendations.

### 8. Real project example
A student sees interview scores rising and gets the recommendation 'practise system design'.

### 9. Viva explanation
> ProgressOverview visualises progress; its components are reused in the mentor view.

---

## File: `frontend/src/pages/student/ResumeUploadAndAnalysis.jsx`

### 1. Purpose
Resume upload and AI resume analysis page.

### 2. What does it do?
1. Uploads a PDF/DOCX resume (POST /student/resumes, multipart form).
2. Lists resume versions (GET /student/resumes) and sets the current one (POST .../make-current).
3. Runs or retries the AI analysis (POST /student/resumes/{id}/analyze) and shows skills, education, projects, experience and a completeness score.
4. Lets the student correct the extracted result (PATCH /student/resumes/{id}/analysis).
5. Copies extracted skills to the profile (POST .../apply-skills), downloads (GET /resumes/{id}/download) or deletes a resume.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: the /student/resumes endpoints and GET /resumes/{id}/download.

```
Student selects a file
   |
   v
POST /student/resumes
   |
   v
Backend extracts text + AI analysis
   |
   v
Analysis shown
   |
   v
Student may correct or apply skills
```

### 4. Important functions
```text
   - Resume()
       Page component.
   - ResumeAnalysisView()
       Shows the analysis (also reused by mentor and recruiter pages).
   - CorrectAnalysisModal()
       Form to fix extracted details.
   - AnalysingNotice()
       Shown while analysis runs.
   Other helper functions: splitList, Section, Muted, Entry
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/HostedAiConsentGate.jsx, components/SharedUiComponents.jsx
   Used by: App.jsx, pages/mentor/MentorStudentDetail.jsx, pages/recruiter/CandidateDetail.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Uploaded file and analysis data.
- **Output:** Resume analysis view.

### 8. Real project example
A student uploads their resume; the AI extracts 'Python, React, MongoDB' and two projects, which the interview then asks about.

### 9. Viva explanation
> This page implements resume upload and analysis; the AI output is validated by the backend and the student can correct it.

---

## File: `frontend/src/pages/student/StudentAssessments.jsx`

### 1. Purpose
Student assessments: take timed tests and see results.

### 2. What does it do?
1. Lists available tests (GET /student/assessments) and results (GET /student/assessments/results).
2. Starts an attempt (POST /student/assessments/{id}/start) and submits (POST .../results/{id}/submit).
3. Coding questions can be self-checked in the browser (browserCodeRunner.js).
4. Shows result details (GET .../results/{id}) and requests AI review of pending code answers (POST .../results/{id}/evaluate).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/assessments, GET /student/assessments/results, GET .../results/{id}, POST .../{id}/start, POST .../results/{id}/submit, POST .../results/{id}/evaluate.

### 4. Important functions
```text
   - StudentAssessments()
       Page component.
   - TakeAssessment()
       Timed attempt.
   - CodingQuestion()
       Code editor with self-check.
   - ReviewList()
       Answer review.
   - ResultHeader()
       Score summary.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, components/browserCodeRunner.js,
   pages/shared/filterChipStyle.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Student answers.
- **Output:** Scores and reviews.

### 8. Real project example
A student takes a 20-minute aptitude test and sees 14/20 instantly.

### 9. Viva explanation
> MCQs are graded on the server instantly; code is reviewed by AI, never executed on the server.

---

## File: `frontend/src/pages/student/StudentDashboard.jsx`

### 1. Purpose
The student's home page.

### 2. What does it do?
1. Loads GET /student/dashboard: summary stats, readiness score, challenges, progress, upcoming events, weak areas, achievements, applications and interviews.
2. Shows the placement readiness card, the English daily plan and a 3D interviewer hero.
3. On request, asks the AI for suitable job roles (POST /student/role-recommendations).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/dashboard, POST /student/role-recommendations.

```
Page opens
   |
   v
GET /student/dashboard
   |
   v
Stats, readiness and charts shown
   |
   v
Optional: AI role suggestions
```

### 4. Important functions
```text
   - StudentDashboard()
       Page component.
   - RoleRecommendations()
       Card that requests and shows AI job-role suggestions.
   - greeting()
       Good morning/afternoon/evening text.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/DashboardCharts.jsx,
   components/EnglishDailyPlan.jsx, components/InterviewerStage.jsx,
   components/PlacementReadinessCard.jsx, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Dashboard data from the backend.
- **Output:** The dashboard screen.

### 8. Real project example
After a mock interview the student returns to the dashboard and sees their readiness score go up.

### 9. Viva explanation
> The student dashboard is the student's performance overview, combining readiness, progress charts and AI role suggestions.

---

## File: `frontend/src/pages/student/StudentJobOpenings.jsx`

### 1. Purpose
Job openings for students.

### 2. What does it do?
1. Searches and filters jobs (GET /student/jobs).
2. Shows details and eligibility (GET /student/jobs/{id}).
3. Applies (POST /student/jobs/{id}/apply).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/jobs, GET /student/jobs/{id}, POST /student/jobs/{id}/apply.

### 4. Important functions
```text
   - Jobs()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: pages/student/JobsAndDrives.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Filters and apply action.
- **Output:** Job list and application.

### 8. Real project example
A student filters 'internship' jobs and applies to one they are eligible for.

### 9. Viva explanation
> Students see eligibility before applying.

---

## File: `frontend/src/pages/student/StudentMentoring.jsx`

### 1. Purpose
The student's view of mentoring.

### 2. What does it do?
1. Loads GET /student/mentoring: mentor, feedback, plans, goals, sessions.
2. Marks a goal complete (POST /student/goals/{id}/complete).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/mentoring, POST /student/goals/{id}/complete.

### 4. Important functions
```text
   - Mentoring()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Mentoring data.
- **Output:** Mentoring UI.

### 8. Real project example
The student sees the mentor's goal 'Complete 3 HR interviews' and its progress.

### 9. Viva explanation
> Connects students with mentor guidance.

---

## File: `frontend/src/pages/student/StudentRewards.jsx`

### 1. Purpose
Points, badges, streaks, challenges and leaderboard.

### 2. What does it do?
1. Loads GET /student/rewards, GET /student/challenges and GET /student/leaderboard.
2. Read-only: the backend awards points.

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: GET /student/rewards, GET /student/challenges, GET /student/leaderboard.

### 4. Important functions
```text
   - Rewards()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Rewards data.
- **Output:** Rewards UI.

### 8. Real project example
A student sees the 'First Interview' badge and a 5-day streak.

### 9. Viva explanation
> Gamification to motivate regular practice.

---

## File: `frontend/src/pages/student/VocabularyTrainer.jsx`

### 1. Purpose
English word list and spaced-repetition review.

### 2. What does it do?
1. Lists words (GET /student/english/vocabulary) with filters.
2. Adds a word (POST /student/english/vocabulary) or deletes one (DELETE .../vocabulary/{id}).
3. Review session: GET .../vocabulary/review, flip a card, answer 'I knew it'/'Not yet' (POST .../vocabulary/{id}/review).

### 3. How does it work?
A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with useState and sends changes with post/put/patch/del, then shows results with the shared UI components. API calls used: the /student/english/vocabulary endpoints.

### 4. Important functions
```text
   - Vocabulary()
       Page component.
   - Review()
       Review session panel.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, english/vocabularyReview.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Cards from the API; student answers.
- **Output:** Word list and review UI.

### 8. Real project example
Words Aria corrected (e.g. 'informations' -> 'information') appear here for review.

### 9. Viva explanation
> The server applies Leitner-box spaced repetition; this page only shows cards and sends answers.

---

# Frontend - recruiter pages

## File: `frontend/src/pages/recruiter/CandidateDetail.jsx`

### 1. Purpose
One candidate's profile and resume analysis as seen by a recruiter.

### 2. What does it do?
1. Loads GET /recruiter/candidates/{id}.
2. Shows profile, resume analysis and interview overview.
3. Downloads the resume (GET /resumes/{id}/download).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/candidates/{id}, GET /resumes/{id}/download.

### 4. Important functions
```text
   Other helper functions: CandidateDetail
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/IntegrityReview.jsx,
   pages/student/InterviewSession.jsx, pages/student/ResumeUploadAndAnalysis.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Student id from URL.
- **Output:** Candidate view.

### 8. Real project example
A recruiter opens a candidate to check their projects before shortlisting.

### 9. Viva explanation
> Shows only what recruiters are allowed to see.

---

## File: `frontend/src/pages/recruiter/CandidateReport.jsx`

### 1. Purpose
Printable report about one applicant.

### 2. What does it do?
1. Loads GET /recruiter/applications/{id}/report.
2. Shows profile, match, interviews, assessments and integrity overview.
3. 'Save as PDF' uses the browser print dialog.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/applications/{id}/report.

### 4. Important functions
```text
   - CandidateReport()
       Page component.
   - Section()
       Report section.
   - KV()
       Label/value row.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/Logo.jsx, components/SharedUiComponents.jsx,
   pages/recruiter/IntegrityOverview.jsx, pages/recruiter/RecruiterJobApplicants.jsx
   Used by: App.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Application id from the URL.
- **Output:** Printable report.

### 8. Real project example
A recruiter prints the candidate report for the hiring panel.

### 9. Viva explanation
> The report is printed with CSS print styles, no PDF library needed.

---

## File: `frontend/src/pages/recruiter/CandidateSearch.jsx`

### 1. Purpose
Search students for recruiters.

### 2. What does it do?
1. Filters by skill, branch, CGPA, graduation year and interview score (GET /recruiter/candidates).
2. Optionally ranks against one of the recruiter's jobs (GET /recruiter/jobs).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/candidates, GET /recruiter/jobs.

### 4. Important functions
```text
   - Candidates()
       Page component.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Filter values.
- **Output:** Candidate table.

### 8. Real project example
A recruiter searches for CS students with Python and CGPA above 7.

### 9. Viva explanation
> Recruiters can discover students who share their profile with recruiters.

---

## File: `frontend/src/pages/recruiter/CompareCandidates.jsx`

### 1. Purpose
Side-by-side comparison of 2-4 applicants to one job.

### 2. What does it do?
1. Reads applicant ids from the URL (?ids=12,15).
2. Calls POST /recruiter/jobs/{id}/compare.
3. Shows match, scores and integrity rows; marks a single clear leader.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: POST /recruiter/jobs/{id}/compare.

### 4. Important functions
```text
   - CompareCandidates()
       Page component.
   - parseIds()
       Reads up to 4 valid ids from the URL.
   - leaderIndex()
       Finds a single clear leader in a row.
   Other helper functions: Row
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/recruiter/IntegrityOverview.jsx,
   pages/recruiter/RecruiterJobApplicants.jsx
   Used by: App.jsx
   Tested by: pages/recruiter/CompareCandidates.test.js
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Job id and applicant ids from the URL.
- **Output:** Comparison table (printable).

### 8. Real project example
A recruiter compares the final three applicants before selection.

### 9. Viva explanation
> Comparison is advisory; integrity information is shown separately from performance.

---

## File: `frontend/src/pages/recruiter/CompareCandidates.test.js`

### 1. Purpose
Unit tests for the helpers of CompareCandidates.jsx.

### 2. What does it do?
1. parseIds accepts up to four distinct positive ids.
2. leaderIndex marks only a single clear leader.

### 3. How does it work?
Vitest tests.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: pages/recruiter/CompareCandidates.jsx
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests the comparison helpers.

---

## File: `frontend/src/pages/recruiter/IntegrityOverview.jsx`

### 1. Purpose
Small summary of one candidate's interview-integrity counts, shown separately from performance.

### 2. What does it do?
1. Shows counts of monitored interviews and reviewed/unreviewed signals.

### 3. How does it work?
Presentational component used by CompareCandidates and CandidateReport.

### 4. Important functions
```text
   Other helper functions: IntegrityOverview
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx
   Used by: pages/recruiter/CandidateReport.jsx, pages/recruiter/CompareCandidates.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Prop: integrity overview data.
- **Output:** Summary card.

### 8. Real project example
In the candidate report a recruiter sees '2 monitored interviews, no significant events'.

### 9. Viva explanation
> Integrity data is shown apart from scores so it does not bias performance evaluation.

---

## File: `frontend/src/pages/recruiter/RecruiterDashboard.jsx`

### 1. Purpose
Recruiter home page.

### 2. What does it do?
1. Loads GET /recruiter/dashboard.
2. Shows job and applicant counts and charts.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/dashboard.

### 4. Important functions
```text
   Other helper functions: RecruiterDashboard
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Dashboard data.
- **Output:** Stats and charts.

### 8. Real project example
A recruiter sees 40 applicants across 3 jobs.

### 9. Viva explanation
> Gives recruiters a quick overview of hiring activity.

---

## File: `frontend/src/pages/recruiter/RecruiterJobApplicants.jsx`

### 1. Purpose
Applicants for one job, with match scores and status changes.

### 2. What does it do?
1. Loads applicants sorted by match (GET /recruiter/jobs/{id}/applications).
2. Shows the rule/semantic match breakdown.
3. Requests an AI match explanation (POST /recruiter/applications/{id}/match).
4. Changes status: shortlist, schedule interview, select, reject (PATCH /recruiter/applications/{id}/status) - the student is notified.
5. Selects 2-4 applicants to compare.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/jobs/{id}/applications, POST /recruiter/applications/{id}/match, PATCH /recruiter/applications/{id}/status.

### 4. Important functions
```text
   - RecruiterJobDetail()
       Page component.
   - MatchPanel()
       Match breakdown panel (also used in the candidate report).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/filterChipStyle.js
   Used by: App.jsx, pages/recruiter/CandidateReport.jsx, pages/recruiter/CompareCandidates.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Job id from the URL.
- **Output:** Applicant table and status updates.

### 8. Real project example
A recruiter sorts applicants by match score and shortlists the top five.

### 9. Viva explanation
> The AI explains the match but never changes the computed score.

---

## File: `frontend/src/pages/recruiter/RecruiterJobPostings.jsx`

### 1. Purpose
Recruiter's job postings: create, edit, publish, close, delete.

### 2. What does it do?
1. Lists jobs (GET /recruiter/jobs).
2. Creates (POST /recruiter/jobs) and edits (PUT /recruiter/jobs/{id}) with JobForm.
3. Publishes/closes (POST /recruiter/jobs/{id}/status/publish|close).
4. Deletes (DELETE /recruiter/jobs/{id}).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/jobs, POST /recruiter/jobs, PUT /recruiter/jobs/{id}, POST /recruiter/jobs/{id}/status/{action}, DELETE /recruiter/jobs/{id}.

### 4. Important functions
```text
   - RecruiterJobs()
       Page component.
   - JobForm()
       Create/edit form.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/filterChipStyle.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Job form input.
- **Output:** Job list.

### 8. Real project example
A recruiter posts a 'Backend Developer' job with required skills and minimum CGPA.

### 9. Viva explanation
> Required and preferred skills entered here are used later for semantic job matching.

---

# Frontend - mentor pages

## File: `frontend/src/pages/mentor/MentorDashboard.jsx`

### 1. Purpose
Mentor home page.

### 2. What does it do?
1. Loads GET /mentor/dashboard.
2. Shows assigned students, who is struggling and upcoming sessions.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /mentor/dashboard.

### 4. Important functions
```text
   Other helper functions: MentorDashboard
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Dashboard data.
- **Output:** Stats, charts and lists.

### 8. Real project example
A mentor sees that two students' scores dropped this week.

### 9. Viva explanation
> The mentor dashboard highlights students who need help.

---

## File: `frontend/src/pages/mentor/MentorSessions.jsx`

### 1. Purpose
The mentor's follow-up sessions.

### 2. What does it do?
1. Lists sessions (GET /mentor/sessions).
2. Schedules (POST /mentor/sessions), edits (PATCH) and deletes (DELETE /mentor/sessions/{id}).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /mentor/sessions, GET /mentor/students, POST /mentor/sessions, PATCH /mentor/sessions/{id}, DELETE /mentor/sessions/{id}.

### 4. Important functions
```text
   Other helper functions: MentorSessions
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/filterChipStyle.js
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Form input.
- **Output:** Session list.

### 8. Real project example
A mentor schedules a 30-minute call with a struggling student.

### 9. Viva explanation
> Mentors track one-to-one follow-up sessions here.

---

## File: `frontend/src/pages/mentor/MentorStudentDetail.jsx`

### 1. Purpose
Everything a mentor needs about one student, in tabs.

### 2. What does it do?
1. Overview with progress and AI recommendations (GET /mentor/students/{id}, POST /mentor/students/{id}/recommendations).
2. Interview and English session details (GET /mentor/students/{id}/interviews/{sid}, /english/{sid}).
3. Resume analysis view.
4. Improvement plans and goals (POST /mentor/students/{id}/plans, PATCH/DELETE /mentor/plans/{id}, POST /mentor/plans/{id}/goals, goal status/delete).
5. Feedback and notes (POST /mentor/students/{id}/feedback, DELETE /mentor/feedback/{id}) and follow-up sessions.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: the /mentor/students/{id}, /mentor/plans, /mentor/goals, /mentor/feedback and /mentor/sessions endpoints.

### 4. Important functions
```text
   - MentorStudentDetail()
       Page component.
   - GoalFields()
       Goal form fields.
   - goalBody()
       Builds the goal request body.
   Other helper functions: blankGoal
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, pages/student/InterviewSession.jsx,
   pages/student/ProgressOverview.jsx, pages/student/ResumeUploadAndAnalysis.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Student id from the URL.
- **Output:** Tabbed student view and saved mentor actions.

### 8. Real project example
A mentor creates a plan 'Improve HR answers' with a goal of 3 HR mock interviews.

### 9. Viva explanation
> This page lets mentors turn analytics into concrete improvement plans.

---

## File: `frontend/src/pages/mentor/MentorStudentList.jsx`

### 1. Purpose
List of the mentor's students with search.

### 2. What does it do?
1. Loads GET /mentor/students with a search query.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /mentor/students.

### 4. Important functions
```text
   Other helper functions: MentorStudents
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: react, react-router-dom

### 7. Input and output
- **Input:** Search text.
- **Output:** Student table.

### 8. Real project example
A mentor searches for a student by name.

### 9. Viva explanation
> Mentors only see assigned students unless given the view-all permission.

---

# Frontend - admin pages

## File: `frontend/src/pages/admin/AdminDashboard.jsx`

### 1. Purpose
Admin analytics home page.

### 2. What does it do?
1. Loads GET /admin/dashboard.
2. Shows platform counts (users, interviews, jobs...) and charts.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/dashboard.

### 4. Important functions
```text
   Other helper functions: AdminDashboard
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react-router-dom

### 7. Input and output
- **Input:** Dashboard data.
- **Output:** Stat cards and charts.

### 8. Real project example
The placement officer checks how many interviews were done this month.

### 9. Viva explanation
> The admin dashboard summarises platform-wide activity using charts.

---

## File: `frontend/src/pages/admin/AdminJobPostings.jsx`

### 1. Purpose
Admin view of all job postings from all recruiters.

### 2. What does it do?
1. Lists jobs (GET /admin/jobs).
2. Closes a job (POST /admin/jobs/{id}/close).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/jobs, POST /admin/jobs/{id}/close.

### 4. Important functions
```text
   Other helper functions: AdminJobs
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Job list.
- **Output:** Job table.

### 8. Real project example
The admin closes an outdated posting.

### 9. Viva explanation
> Gives the placement cell oversight of all recruiter jobs.

---

## File: `frontend/src/pages/admin/AdminMonitoring.jsx`

### 1. Purpose
Admin monitoring centre in tabs.

### 2. What does it do?
1. Flagged interviews/assessments: review and revoke points (GET /admin/flagged, POST /admin/flagged/{kind}/{id}, GET /admin/interviews/{id}).
2. Interview integrity review (IntegrityReview) and security settings (SecuritySettings).
3. AI usage and speed (GET /admin/ai-usage, GET /admin/performance).
4. Application errors (GET /admin/errors).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/flagged, POST /admin/flagged/{kind}/{id}, GET /admin/interviews/{id}, GET /admin/ai-usage, GET /admin/performance, GET /admin/errors.

### 4. Important functions
```text
   - Monitoring()
       Tabbed page.
   - Flagged()
       Flagged items tab.
   - AIUsage()
       AI usage tab.
   - Performance()
       Pipeline timing tab.
   - AiSpeed()
       AI speed by task card.
   - Errors()
       Error log tab.
   Other helper functions: ms
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx,
   pages/admin/SecuritySettings.jsx, pages/shared/IntegrityReview.jsx,
   pages/student/InterviewSession.jsx
   Used by: App.jsx
```
External packages: react

### 7. Input and output
- **Input:** API data.
- **Output:** Tabbed monitoring UI.

### 8. Real project example
The admin checks average AI response time for answer scoring.

### 9. Viva explanation
> AdminMonitoring combines cheating review, AI usage, performance and error logs in one place.

---

## File: `frontend/src/pages/admin/AdminRewardRules.jsx`

### 1. Purpose
Manage badges and reward rules.

### 2. What does it do?
1. Lists and edits badges (GET/POST /admin/badges, PUT /admin/badges/{id}).
2. Edits reward rules: points, daily caps, minimum quality (GET /admin/reward-rules, PATCH /admin/reward-rules/{id}).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/badges, POST /admin/badges, PUT /admin/badges/{id}, GET /admin/reward-rules, PATCH /admin/reward-rules/{id}.

### 4. Important functions
```text
   Other helper functions: AdminRewards
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Admin input.
- **Output:** Saved rules.

### 8. Real project example
The admin increases points for completing a mock interview.

### 9. Viva explanation
> Gamification rules are configurable by the admin, not hard-coded.

---

## File: `frontend/src/pages/admin/AuditLogs.jsx`

### 1. Purpose
Read-only audit log of admin and security actions.

### 2. What does it do?
1. Loads GET /admin/audit-logs with an action filter.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/audit-logs.

### 4. Important functions
```text
   Other helper functions: AuditLogs
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Filter.
- **Output:** Audit table.

### 8. Real project example
The admin checks who changed a user's role.

### 9. Viva explanation
> Audit logs provide accountability for sensitive actions.

---

## File: `frontend/src/pages/admin/InterviewConfig.jsx`

### 1. Purpose
Interview setup for admins: question bank, interview categories and evaluation rubrics.

### 2. What does it do?
1. Manages categories (GET/POST /admin/categories, PUT /admin/categories/{id}).
2. Manages the question bank (GET/POST /admin/questions, PUT/DELETE /admin/questions/{id}).
3. Manages scoring rubrics (GET/POST /admin/rubrics, PUT /admin/rubrics/{id}).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: /admin/categories, /admin/questions, /admin/rubrics endpoints.

### 4. Important functions
```text
   - InterviewConfig()
       Tabbed page.
   - Categories()
       Category tab.
   - QuestionBank()
       Question bank tab.
   - Rubrics()
       Rubrics tab.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Admin input.
- **Output:** Saved configuration.

### 8. Real project example
The admin adds HR questions to the bank, used as a fallback when the AI cannot generate a question.

### 9. Viva explanation
> InterviewConfig controls the rubric used by the AI scorer and the fallback question bank.

---

## File: `frontend/src/pages/admin/MentorAssignments.jsx`

### 1. Purpose
Assign students to mentors.

### 2. What does it do?
1. Lists assignments (GET /admin/assignments).
2. Loads mentors and students (GET /admin/users).
3. Creates (POST /admin/assignments) and removes (DELETE /admin/assignments/{id}) assignments.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/assignments, GET /admin/users, POST /admin/assignments, DELETE /admin/assignments/{id}.

### 4. Important functions
```text
   Other helper functions: AdminAssignments
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: react

### 7. Input and output
- **Input:** Selected mentor and student.
- **Output:** Assignment table.

### 8. Real project example
The admin assigns five final-year students to a faculty mentor.

### 9. Viva explanation
> Mentors only see students assigned here, which enforces privacy.

---

## File: `frontend/src/pages/admin/PlacementReports.jsx`

### 1. Purpose
Placement report table with CSV export.

### 2. What does it do?
1. Loads GET /admin/reports/placements.
2. Downloads CSV with ?format=csv.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/reports/placements.

### 4. Important functions
```text
   Other helper functions: Reports
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Report data.
- **Output:** Table and CSV file.

### 8. Real project example
The placement officer exports the report for the college management.

### 9. Viva explanation
> Reports summarise student placement readiness and outcomes.

---

## File: `frontend/src/pages/admin/PlatformSettings.jsx`

### 1. Purpose
Editor for platform settings (key/value).

### 2. What does it do?
1. Loads GET /admin/settings.
2. Saves one setting with PUT /admin/settings/{key}.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/settings, PUT /admin/settings/{key}.

### 4. Important functions
```text
   - AdminSettings()
       Page component.
   - SettingRow()
       One editable setting.
   - humanize()
       Turns a key into readable text.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: react

### 7. Input and output
- **Input:** Settings list.
- **Output:** Saved values.

### 8. Real project example
The admin turns off 'ai_features_enabled' during maintenance.

### 9. Viva explanation
> Platform behaviour like max interview questions is changed here without code changes.

---

## File: `frontend/src/pages/admin/SecuritySettings.jsx`

### 1. Purpose
Admin settings for interview monitoring.

### 2. What does it do?
1. Which detectors are offered, thresholds, reminder and pause rules, severity caps, risk weights, recruiter access.
2. Loads/saves GET/PUT /admin/security-settings.
3. Global switches via PUT /admin/settings/{key}.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/security-settings, PUT /admin/security-settings, PUT /admin/settings/{key}.

### 4. Important functions
```text
   - SecuritySettings()
       Page component.
   - Num()
       Number input.
   - Switch()
       On/off switch.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx
   Used by: pages/admin/AdminMonitoring.jsx
```
External packages: react

### 7. Input and output
- **Input:** Admin input.
- **Output:** Saved security config.

### 8. Real project example
The admin raises the 'looking away' threshold from 5 to 8 seconds.

### 9. Viva explanation
> SecuritySettings makes the proctoring rules configurable and every change is audit-logged.

**Note:** The values are starting points, not validated cheating thresholds.

---

## File: `frontend/src/pages/admin/UserManagement.jsx`

### 1. Purpose
User management for admins.

### 2. What does it do?
1. Lists and filters users (GET /admin/users).
2. Creates staff accounts such as mentors (POST /admin/users).
3. Changes role/status, approves recruiters (PATCH /admin/users/{id}).
4. Deactivates users (DELETE /admin/users/{id}).

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /admin/users, GET /admin/users/{id}, POST /admin/users, PATCH /admin/users/{id}, DELETE /admin/users/{id}.

### 4. Important functions
```text
   Other helper functions: AdminUsers
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react, react-router-dom

### 7. Input and output
- **Input:** Filters and forms.
- **Output:** User table and changes.

### 8. Real project example
The admin approves a new recruiter account that is pending.

### 9. Viva explanation
> UserManagement gives admins control of all accounts; deletion is a soft deactivate on the backend.

---

# Frontend - pages shared by several roles

## File: `frontend/src/pages/shared/AssessmentManager.jsx`

### 1. Purpose
Create, edit, AI-draft and view results of assessments (used by recruiters and admins).

### 2. What does it do?
1. Lists assessments (GET /assessments).
2. Create/update/delete (POST /assessments, PUT/DELETE /assessments/{id}).
3. Lets AI draft MCQ questions (POST /assessments/generate) for review before saving.
4. Shows results of an assessment (GET /assessments/{id}/results).
5. Recruiters can link an assessment to one of their jobs.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /assessments, POST /assessments, PUT /assessments/{id}, DELETE /assessments/{id}, POST /assessments/generate, GET /assessments/{id}/results, GET /recruiter/jobs or /admin/jobs.

### 4. Important functions
```text
   - AssessmentManager()
       Page component.
   - AssessmentForm()
       Create/edit form with question editor.
   Other helper functions: blankQ
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx
   Used by: App.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Form input and API data.
- **Output:** Saved assessments and result tables.

### 8. Real project example
A recruiter asks AI to draft 10 Python MCQs, edits them and publishes a test for job applicants.

### 9. Viva explanation
> AssessmentManager is shared by two roles; AI only drafts questions, a human reviews them before saving.

---

## File: `frontend/src/pages/shared/IntegrityReview.jsx`

### 1. Purpose
Review page for interview-security events, for admins, permitted mentors and recruiters.

### 2. What does it do?
1. Lists monitored interviews with filters (GET /monitoring/sessions).
2. Shows one session's events, risk summary, attention report and timeline (GET /monitoring/sessions/{id}).
3. Reviewer marks an event (no concern, concern noted, false positive...) with PATCH /monitoring/events/{id}.

### 3. How does it work?
A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and modal state with useState, sends changes with post/put/patch/del and shows the result with the shared components from SharedUiComponents.jsx. API calls used: GET /monitoring/sessions, GET /monitoring/sessions/{id}, PATCH /monitoring/events/{id}.

### 4. Important functions
```text
   - IntegrityReviewPage()
       Page with the session list.
   - IntegrityReview()
       Session list component (also embedded in other pages).
   - SessionDetail()
       One session's details.
   - RiskPanel()
       Risk summary.
   - Timeline()
       Event timeline.
   - EventRow()
       One event with review buttons.
   Other helper functions: fmt, clock, pretty
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx,
   monitoring/AttentionPanels.jsx
   Used by: App.jsx, pages/admin/AdminMonitoring.jsx, pages/recruiter/CandidateDetail.jsx
```
External packages: react

### 7. Input and output
- **Input:** Monitoring data from the API.
- **Output:** Review UI and saved review decisions.

### 8. Real project example
An admin opens a flagged interview, watches the event timeline and marks a 'looking away' event as no concern.

### 9. Viva explanation
> IntegrityReview presents monitoring signals for human judgement; it never applies automatic penalties.

---

## File: `frontend/src/pages/shared/filterChipStyle.js`

### 1. Purpose
One shared CSS class helper for the filter 'chips' on list pages.

### 2. What does it do?


### 3. How does it work?
Returns a class string; used so all status/type filters look the same.

### 4. Important functions
```text
   - chipClass()
       Returns Tailwind classes for an active or inactive filter chip.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: pages/mentor/MentorSessions.jsx, pages/recruiter/RecruiterJobApplicants.jsx,
   pages/recruiter/RecruiterJobPostings.jsx, pages/student/JobApplications.jsx,
   pages/student/PracticeHistory.jsx, pages/student/StudentAssessments.jsx
```

### 7. Input and output
- **Input:** Whether the chip is active.
- **Output:** Class name string.

### 8. Real project example
The 'Shortlisted' filter on the applicants page uses chipClass.

### 9. Viva explanation
> A tiny style helper reused by several list pages.

---

# Frontend - live voice interview and avatar

## File: `frontend/src/voice/AnswerDock.jsx`

### 1. Purpose
The answer area under the interviewer: microphone level, live caption, typed answer and transcript review.

### 2. What does it do?
1. Shows the mic level and partial transcript while speaking.
2. Lets the student type instead of speak.
3. Shows the transcript for review before sending.

### 3. How does it work?
Receives state and dispatch from LiveVoiceInterview.jsx and renders according to the state.

### 4. Important functions
```text
   Other helper functions: AnswerDock
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx, voice/interviewMachine.js
   Used by: pages/student/LiveVoiceInterview.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Props: state, dispatch, input mode, mic level, partial text.
- **Output:** Answer UI.

### 8. Real project example
The student sees their spoken answer as text and can edit it before submitting.

### 9. Viva explanation
> AnswerDock shows the student's answer as it is captured and lets them correct it.

---

## File: `frontend/src/voice/Avatar3D.jsx`

### 1. Purpose
Renders the realistic 3D interviewer with three.js, including lip sync, blinking, gaze and head motion.

### 2. What does it do?
1. Loads the interviewer's .glb 3D model (an optional HD model first, else the normal model).
2. Maps the model's blendshapes with faceRig.js.
3. Every frame: applies visemes (mouth shapes) from the speech player and expressions from avatarStates.js.
4. Adds natural motion (blinks, gaze, head movement) from motion.js.
5. Reports failure if WebGL is missing so the page can use a fallback.

### 3. How does it work?
A useEffect creates a WebGLRenderer, scene, camera and lights, loads the model with GLTFLoader and starts an animation loop. It reads the latest props through refs so it does not re-render React every frame.

```
Load .glb model
   |
   v
Build face rig
   |
   v
Animation loop reads visemes + mode
   |
   v
Compose face and body motion
   |
   v
Render frame
```

### 4. Important functions
```text
   - Avatar3D()
       The 3D avatar component (props: getVisemes, mode, interviewer, modelUrl, hdModelUrl,
       quality, lite...).
   Other helper functions: skinMaterial, upgradeMaterials, smooth, findBone
```

### 5. Important variables
- `AVATAR_URL`: Default interviewer model path.

### 6. Connected files
```text
   Uses: voice/avatarStates.js, voice/faceRig.js, voice/motion.js
   Used by: components/InterviewerStage.jsx, pages/student/EnglishAvatarSession.jsx,
   pages/student/InterviewerFeedback.jsx, pages/student/InterviewerPicker.jsx,
   pages/student/LiveVoiceInterview.jsx
```
External packages: react, three

### 7. Input and output
- **Input:** Props: getVisemes callback, mode, interviewer id, model URLs, quality.
- **Output:** A WebGL canvas with the animated interviewer.

### 8. Real project example
In the live interview, Marcus's lips move in sync with the generated speech while he asks a question.

### 9. Viva explanation
> Avatar3D uses three.js to render a 3D interviewer whose mouth is driven by phoneme timings from our text-to-speech engine.

---

## File: `frontend/src/voice/ControlBar.jsx`

### 1. Purpose
The round-button toolbar of the live interview (mic, repeat, pause, voice, self-view, settings, end).

### 2. What does it do?
1. Shows buttons enabled or disabled according to the interview state.
2. Calls the page's callbacks when pressed.

### 3. How does it work?
Uses interviewMachine state values to decide which buttons are active.

### 4. Important functions
```text
   Other helper functions: ControlBar
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: components/SharedUiComponents.jsx, voice/RoomParts.jsx, voice/interviewMachine.js
   Used by: pages/student/LiveVoiceInterview.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Props: interview state and callback functions.
- **Output:** Toolbar UI.

### 8. Real project example
The microphone button is disabled while the interviewer is speaking.

### 9. Viva explanation
> ControlBar is the main control panel of the voice room, driven by the state machine.

---

## File: `frontend/src/voice/RoomParts.jsx`

### 1. Purpose
Small presentational pieces of the live interview room.

### 2. What does it do?
1. SubtitleLine: subtitles with the current word highlighted.
2. RoundButton, Panel, Stat, Toggle: basic room UI pieces.

### 3. How does it work?
Simple React components with props only.

### 4. Important functions
```text
   - SubtitleLine()
       Subtitles: exactly what is being said (greeting included); the word being spoken is
       highlighted.
   Other helper functions: RoundButton, Panel, Stat, Toggle
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: pages/student/LiveVoiceInterview.jsx, voice/ControlBar.jsx,
   voice/RoomSettingsPanel.jsx, voice/RoomSidePanels.jsx
```

### 7. Input and output
- **Input:** Props.
- **Output:** UI elements.

### 8. Real project example
The captions under the avatar use SubtitleLine.

### 9. Viva explanation
> RoomParts keeps small UI pieces of the voice room in one file.

---

## File: `frontend/src/voice/RoomSettingsPanel.jsx`

### 1. Purpose
Settings panel of the live interview room.

### 2. What does it do?
1. Voice on/off and speed.
2. Captions and subtitle size.
3. Auto microphone, end-of-speech pause and auto-send.
4. 3D graphics quality.

### 3. How does it work?
Calls setSetting/setAvatarQuality passed in by the page.

### 4. Important functions
```text
   Other helper functions: RoomSettingsPanel
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/RoomParts.jsx, voice/avatarStates.js
   Used by: pages/student/LiveVoiceInterview.jsx
```

### 7. Input and output
- **Input:** Props: settings and setter functions.
- **Output:** Settings UI.

### 8. Real project example
A student with a slow laptop switches the avatar to 'performance' quality.

### 9. Viva explanation
> RoomSettingsPanel lets candidates adjust voice, captions and graphics to their needs.

---

## File: `frontend/src/voice/RoomSidePanels.jsx`

### 1. Purpose
Right-hand panels of the live interview room: progress, running transcript and private notes.

### 2. What does it do?
1. Shows question number, total and elapsed time.
2. Shows the transcript of the conversation.
3. Private notes area.

### 3. How does it work?
Presentational component fed by LiveVoiceInterview.jsx.

### 4. Important functions
```text
   Other helper functions: RoomSidePanels
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/RoomParts.jsx, voice/roomUtils.js
   Used by: pages/student/LiveVoiceInterview.jsx
```
External packages: react-router-dom

### 7. Input and output
- **Input:** Props: session, question number, timer, etc.
- **Output:** Side panels UI.

### 8. Real project example
The student sees 'Question 3 of 6' and the earlier questions.

### 9. Viva explanation
> RoomSidePanels gives context during the interview: progress and transcript.

---

## File: `frontend/src/voice/SvgAvatar2D.jsx`

### 1. Purpose
A simpler 2D illustrated interviewer ('Aria') drawn in SVG, used when 3D is not available.

### 2. What does it do?
1. Draws the face in SVG.
2. Animates mouth shapes from getMouth() (lip sync).
3. Animates blinking, eye contact, head motion and expressions from mode.

### 3. How does it work?
Updates SVG attributes directly in an animation frame loop (no React re-render per frame), using visemes.js geometry.

### 4. Important functions
```text
   - Avatar()
       The SVG avatar component.
   Other helper functions: face, smooth
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/visemes.js
   Used by: pages/student/EnglishAvatarSession.jsx, pages/student/LiveVoiceInterview.jsx
```
External packages: react

### 7. Input and output
- **Input:** Props: getMouth, mode, palette.
- **Output:** Animated SVG avatar.

### 8. Real project example
On a computer without WebGL, the voice interview shows this 2D Aria instead of the 3D model.

### 9. Viva explanation
> SvgAvatar2D is the lightweight fallback avatar with the same lip-sync data as the 3D one.

---

## File: `frontend/src/voice/avatarStates.js`

### 1. Purpose
Defines the avatar's animation states and each interviewer's facial expression profile.

### 2. What does it do?
1. avatarStateFor() picks exactly one avatar state from the conversation state.
2. PROFILES give each interviewer (Aria, Victor, Marcus, Elena) a different face for each state.
3. Stores and reads the chosen graphics quality in localStorage.

### 3. How does it work?
Pure data and functions; the 3D renderer blends smoothly between expressions. The mouth is NOT part of the state - it follows the audio.

### 4. Important functions
```text
   - avatarStateFor()
       Single avatar state for the current status.
   - expressionFor()
       Expression of an interviewer in a state.
   - profileFor()
       Full profile of an interviewer.
   - storedQuality()
       Saved graphics quality.
   - saveQuality()
       Save graphics quality.
```

### 5. Important variables
- `A`: Avatar state names.
- `PROFILES`: Expression profiles per interviewer.
- `AVATAR_QUALITY`: Quality presets.

### 6. Connected files
```text
   Used by: pages/student/LiveVoiceInterview.jsx, voice/Avatar3D.jsx, voice/RoomSettingsPanel.jsx
   Tested by: voice/interviewers.test.js
```

### 7. Input and output
- **Input:** Interview status and flags.
- **Output:** State name and expression weights.

### 8. Real project example
When the student is answering, Aria shows an attentive 'listening' face; Victor looks stricter.

### 9. Viva explanation
> avatarStates separates animation logic from rendering so each interviewer's personality is visible and testable.

---

## File: `frontend/src/voice/englishMachine.js`

### 1. Purpose
State machine of the hands-free spoken English practice with Aria.

### 2. What does it do?
1. Defines the conversation loop: Aria speaks -> mic opens -> student talks -> transcribe -> Aria thinks -> Aria speaks.
2. Ignores disallowed events (no recording while Aria speaks, no double sends).
3. Maps states to avatar expressions and labels the confidence meter.

### 3. How does it work?
englishTransition(state, event) is a pure function used by EnglishAvatarSession.jsx with useReducer. Unlike the interview there is no review step.

### 4. Important functions
```text
   - englishTransition()
       Next conversation state for an event.
   - englishAvatarMode()
       Avatar mood for a state.
   - confidenceLabel()
       Text label for the confidence score.
```

### 5. Important variables
- `E`: State names.
- `initialEnglishState`: Starting state.
- `GENERIC_STARTERS`: Fallback conversation starters.

### 6. Connected files
```text
   Used by: pages/student/EnglishAvatarSession.jsx
   Tested by: voice/englishMachine.test.js
```

### 7. Input and output
- **Input:** State and events.
- **Output:** Next state.

### 8. Real project example
When the student stops talking, the machine moves to 'transcribing' and the reply is sent automatically.

### 9. Viva explanation
> englishMachine keeps the spoken English conversation flowing hands-free using a pure state machine.

---

## File: `frontend/src/voice/englishMachine.test.js`

### 1. Purpose
Unit tests for the spoken-English conversation state machine.

### 2. What does it do?
1. Hands-free loop order.
2. No recording while Aria speaks; double sends ignored.
3. Pause/resume and clean ending.

### 3. How does it work?
Vitest tests on englishTransition.

### 4. Important functions
```text
   Other helper functions: run
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/englishMachine.js, voice/recorder.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests that the English practice loop cannot get stuck.

---

## File: `frontend/src/voice/faceRig.js`

### 1. Purpose
Adapter that maps any avatar model's face shapes onto one common vocabulary (ARKit names + visemes).

### 2. What does it do?
1. canonicalName() normalises different blendshape spellings.
2. buildRig() finds which shapes a model has.
3. composeFace() combines lip sync, expressions, blinks and gaze into final weights between 0 and 1.
4. Spells visemes with ARKit mouth shapes when a model has no viseme shapes.

### 3. How does it work?
Pure functions without three.js, so they are unit-tested.

### 4. Important functions
```text
   - buildRig()
       Builds a rig description from a model's morph target names.
   - composeFace()
       Final face weights for one frame.
   - canonicalName()
       Normalised channel name.
   Other helper functions: clamp01
```

### 5. Important variables
- `VISEMES`: The 15 viseme ids.
- `ARKIT`: ARKit blendshape names.
- `VISEME_ARKIT`: Viseme to ARKit mix.

### 6. Connected files
```text
   Used by: voice/Avatar3D.jsx
   Tested by: voice/faceRig.test.js
```

### 7. Input and output
- **Input:** Morph target names; face state.
- **Output:** Weights per morph target.

### 8. Real project example
Lets both the Rocketbox models and a MetaHuman model use the same lip-sync code.

### 9. Viva explanation
> faceRig makes the avatar renderer model-independent by translating face shape names.

---

## File: `frontend/src/voice/faceRig.test.js`

### 1. Purpose
Unit tests for faceRig.js.

### 2. What does it do?
1. Name mapping across model formats.
2. Rig detection for Rocketbox and ARKit models.
3. Face composition rules and weight limits.

### 3. How does it work?
Vitest tests.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/faceRig.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests ensure lip sync works for every supported avatar model.

---

## File: `frontend/src/voice/interviewMachine.js`

### 1. Purpose
The state machine of the live voice interview: it decides which step the interview is in and which actions are allowed.

### 2. What does it do?
Pure state logic for the voice interview room.

1. Lists all states (initializing, interviewer speaking, listening, recording, transcribing, reviewing, evaluating, finished...).
2. transition(state, event) returns the next state and ignores events that are not allowed.
3. Prevents double submissions and recording while the interviewer is speaking.
4. avatarMode() maps the interview state to the avatar's animation mode.

### 3. How does it work?
It is a pure function (no React, no audio), so it can be unit-tested. LiveVoiceInterview.jsx keeps the state with useReducer and dispatches events.

```
Interviewer speaks the question
   |
   v
Microphone opens (listening/recording)
   |
   v
Answer is transcribed
   |
   v
Student reviews/sends the answer
   |
   v
Backend scores it; next question
```

### 4. Important functions
```text
   - transition()
       Returns the new state for an event, or the same state if the event is not allowed.
   - canTransition()
       Checks whether an event type is allowed in the current state.
   - avatarMode()
       Animation mode for the avatar in each state.
```

### 5. Important variables
- `S`: Names of all interview states.
- `initialState`: Starting state.
- `STATUS_LABEL`: Readable label for each state.

### 6. Connected files
```text
   Used by: pages/student/LiveVoiceInterview.jsx, voice/AnswerDock.jsx, voice/ControlBar.jsx
   Tested by: voice/interviewers.test.js, voice/voice.test.js
```

### 7. Input and output
- **Input:** Current state and an event (e.g. SPEECH_ENDED, RECORD_STOP, SUBMITTED).
- **Output:** Next state.

### 8. Real project example
If the student clicks 'Send' twice, the second click is ignored because the state is already 'evaluating'.

### 9. Viva explanation
> The voice interview is controlled by a finite state machine, which removes race conditions like recording while the AI is speaking.

---

## File: `frontend/src/voice/interviewers.test.js`

### 1. Purpose
Unit tests for avatar states, personality expressions and interviewer voices.

### 2. What does it do?
1. One avatar state per conversation state.
2. Each personality looks different.
3. Stress-interview interruption and voice selection.

### 3. How does it work?
Vitest tests.

### 4. Important functions
```text
   Other helper functions: run
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/avatarStates.js, voice/interviewMachine.js, voice/speechPlayer.js,
   voice/useInterviewers.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests confirm that each interviewer persona behaves as designed.

---

## File: `frontend/src/voice/motion.js`

### 1. Purpose
Procedural 'aliveness' for the interviewer: natural gaze, blinks, head motion and micro-expressions.

### 2. What does it do?
1. Gaze: holds eye contact with small movements, looks away briefly while speaking or thinking.
2. Blinker: random blink intervals, double and half blinks.
3. HeadMotion: smooth non-repeating noise plus nods.
4. Micro: short small expressions tied to the conversation.

### 3. How does it work?
Pure classes using a seeded random generator (rng) so tests are repeatable.

### 4. Important functions
```text
   - Gaze()
       Eye direction controller.
   - Blinker()
       Blink controller.
   - HeadMotion()
       Head movement controller.
   - Micro()
       Micro-expression controller.
   - rng()
       Deterministic random number generator.
   - noise1()
       Smooth 1-D noise.
   Other helper functions: smooth
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: voice/Avatar3D.jsx
   Tested by: voice/motion.test.js
```

### 7. Input and output
- **Input:** Time step and conversation mode.
- **Output:** Gaze, blink, head and expression values.

### 8. Real project example
Aria blinks at irregular intervals and glances away while thinking, so she looks less robotic.

### 9. Viva explanation
> motion.js adds realistic random behaviour so the avatar does not look like a looping animation.

---

## File: `frontend/src/voice/motion.test.js`

### 1. Purpose
Unit tests for motion.js.

### 2. What does it do?
1. Blinks vary and never stare too long.
2. Gaze holds eye contact and looks away while talking.
3. Head motion is smooth and non-repeating.

### 3. How does it work?
Vitest tests with a seeded random generator.

### 4. Important functions
```text
   Other helper functions: run
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/motion.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests check the avatar's natural motion is realistic and deterministic.

---

## File: `frontend/src/voice/recorder.js`

### 1. Purpose
Records the student's spoken answer from the microphone and prepares it for transcription.

### 2. What does it do?
1. Opens the microphone only while recording and fully releases it afterwards.
2. Downsamples audio to 16 kHz mono and encodes WAV pieces.
3. Detects end of speech (silence) with a simple voice-activity check (vadStep).
4. Hands out pieces for live captions and the final tail for transcription; reports the mic level.

### 3. How does it work?
MicRecorder uses an AudioWorklet to collect samples in memory; helper functions are pure and tested.

### 4. Important functions
```text
   - MicRecorder()
       Microphone recorder class (start, stop, cancel, release).
   - encodeWav()
       Builds a WAV file from samples.
   - downsample()
       Converts to 16 kHz.
   - vadStep()
       One step of the silence/end-of-speech detector.
   - rms()
       Loudness of a chunk.
   Other helper functions: PcmCapture
```

### 5. Important variables
- `VAD_THRESHOLD`: Loudness level counted as speech.

### 6. Connected files
```text
   Used by: pages/student/EnglishAvatarSession.jsx, pages/student/LiveVoiceInterview.jsx
   Tested by: voice/englishMachine.test.js, voice/streaming.test.js, voice/voice.test.js
```

### 7. Input and output
- **Input:** Microphone audio.
- **Output:** WAV audio pieces and level/end-of-speech signals.

### 8. Real project example
When the student stops talking for 3.5 seconds, the recorder ends the answer automatically.

### 9. Viva explanation
> recorder.js captures audio, encodes WAV and detects silence so answers end naturally.

**Note:** Audio stays in memory and goes only to this app's backend for local Whisper transcription.

---

## File: `frontend/src/voice/roomUtils.js`

### 1. Purpose
Small helpers and default settings for the live interview room.

### 2. What does it do?
1. Default room settings and loading saved settings.
2. Fallback interviewer if the list cannot load.
3. Helpers: split sentences, make a turn id, format a clock, storage wrappers, find the current question.

### 3. How does it work?
Plain functions and constants imported by LiveVoiceInterview.jsx and RoomSidePanels.jsx.

### 4. Important functions
```text
   Other helper functions: savedSettings, splitSentences, turnId, fmtClock, store,
   currentQuestion
```

### 5. Important variables
- `DEFAULT_SETTINGS`: Voice, captions, auto-mic, auto-send defaults.
- `INTERJECTION`: Stress-interview interruption line.

### 6. Connected files
```text
   Used by: pages/student/LiveVoiceInterview.jsx, voice/RoomSidePanels.jsx
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
The room's timer uses fmtClock to show 03:25.

### 9. Viva explanation
> roomUtils holds shared constants and helper functions for the voice interview page.

---

## File: `frontend/src/voice/speechPlayer.js`

### 1. Purpose
Plays the interviewer's voice and tells the avatar which mouth shape to show.

### 2. What does it do?
1. Plays audio from the local Kokoro text-to-speech engine with its phoneme timeline.
2. Falls back to the browser's speechSynthesis voice (approximate lip sync) if needed.
3. Plays streamed sentences in order with SpeechQueue (startQueue, queueAdd, queueFill...).
4. Supports pause, resume, stop and gives getMouth()/getVisemes() to the avatar.

### 3. How does it work?
Audio is played with the Web Audio API; mouth shapes are looked up on the same AudioContext clock and scaled by the volume, so lips close when sound stops.

### 4. Important functions
```text
   - SpeechPlayer()
       Class managing playback, the queue and lip-sync state.
   - pickBrowserVoice()
       Chooses a browser voice by language and gender.
   Other helper functions: b64ToArrayBuffer
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/speechQueue.js, voice/visemes.js
   Used by: pages/student/EnglishAvatarSession.jsx, pages/student/InterviewerFeedback.jsx,
   pages/student/InterviewerPicker.jsx, pages/student/LiveVoiceInterview.jsx
   Tested by: voice/interviewers.test.js
```

### 7. Input and output
- **Input:** Base64 WAV audio + visemes from /voice/speak or the interview turn stream; or plain text for the browser voice.
- **Output:** Audio playback and current mouth shape.

### 8. Real project example
While the next question is still being generated, the first sentence already plays through SpeechPlayer.

### 9. Viva explanation
> SpeechPlayer synchronises audio and lip movement using the audio clock, and supports streamed sentence playback.

---

## File: `frontend/src/voice/speechQueue.js`

### 1. Purpose
Keeps streamed speech in the correct order without overlaps (pure logic, no audio).

### 2. What does it do?
1. Stores numbered sentences in lanes (e.g. greeting, then question).
2. Waits for sentence n before playing n+1.
3. Falls back to the browser voice from a failed sentence onwards.
4. Can retract unplayed sentences.

### 3. How does it work?
SpeechQueue is a small class; speechPlayer.js calls it to decide what to play next.

### 4. Important functions
```text
   - SpeechQueue()
       Ordered multi-lane speech queue.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: voice/speechPlayer.js
   Tested by: voice/streaming.test.js
```

### 7. Input and output
- **Input:** Sentence text and later its audio.
- **Output:** Next item to play.

### 8. Real project example
The greeting finishes before the question starts, even if the question audio arrived first.

### 9. Viva explanation
> speechQueue guarantees ordered, non-overlapping streaming speech and is unit-tested.

---

## File: `frontend/src/voice/streaming.test.js`

### 1. Purpose
Unit tests for streamed speech and the SSE parser.

### 2. What does it do?
1. SpeechQueue ordering and fallbacks.
2. SSE parsing across split chunks.
3. End-of-speech detection.

### 3. How does it work?
Vitest tests.

### 4. Important functions
```text
   Other helper functions: res
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/recorder.js, voice/speechQueue.js, voice/turnStream.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests prove streamed speech plays in order and the stream parser is robust.

---

## File: `frontend/src/voice/turnStream.js`

### 1. Purpose
Client for the streamed live-interview turn: POST /student/interviews/{id}/turn with Server-Sent Events.

### 2. What does it do?
1. Sends the answer as JSON with the login cookie.
2. Reads the streamed response and splits it into events.
3. Calls handlers such as scored, sentence, audio, question, done.

### 3. How does it work?
Uses fetch with a readable stream instead of EventSource so it can POST a body. createSseParser() parses chunks.

### 4. Important functions
```text
   - streamTurn()
       Streams one interview turn.
   - streamPost()
       Generic SSE-over-POST helper (also used for English replies).
   - createSseParser()
       Pure parser for SSE text chunks.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js
   Used by: pages/student/EnglishSession.jsx, pages/student/LiveVoiceInterview.jsx
   Tested by: voice/streaming.test.js
```

### 7. Input and output
- **Input:** Session id, answer body, event handlers.
- **Output:** Handler calls as events arrive.

### 8. Real project example
After the student answers, the score arrives first and then the next question sentence by sentence.

### 9. Viva explanation
> turnStream lets the frontend receive the AI's reply while it is still being generated, which cuts waiting time.

---

## File: `frontend/src/voice/useInterviewers.js`

### 1. Purpose
Loads the interviewer personalities from the server and helps build their voice settings.

### 2. What does it do?
1. useInterviewers() loads GET /interviewers once and caches it.
2. findInterviewer() picks one by id.
3. speakBody() builds the /voice/speak request with the persona's voice and speed.
4. browserVoiceOpts() gives fallback voice options.

### 3. How does it work?
A small React hook with a module-level cache.

### 4. Important functions
```text
   - useInterviewers()
       Hook returning the interviewer list.
   - findInterviewer()
       Find by id.
   - speakBody()
       TTS request body.
   - browserVoiceOpts()
       Options for SpeechPlayer.playBrowser (browser-voice fallback).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js
   Used by: pages/student/InterviewSession.jsx, pages/student/InterviewerFeedback.jsx,
   pages/student/InterviewerPicker.jsx, pages/student/LiveVoiceInterview.jsx,
   pages/student/MockInterviewHome.jsx
   Tested by: voice/interviewers.test.js
```
External packages: react

### 7. Input and output
- **Input:** /interviewers response; persona; user speed.
- **Output:** Interviewer data and voice options.

### 8. Real project example
The interviewer picker shows Aria, Victor, Marcus and Elena from this list.

### 9. Viva explanation
> Personalities are defined on the server; this hook brings them to the frontend.

---

## File: `frontend/src/voice/visemes.js`

### 1. Purpose
Lip-sync maths: mouth-shape parameters, timeline lookup and SVG mouth geometry.

### 2. What does it do?
1. Defines mouth SHAPES for each viseme.
2. Finds the active viseme segment at a time (segmentAt, mouthAt, visemeWeightsAt).
3. approximateVisemes() estimates shapes from letters when no phoneme timing exists.
4. mouthGeometry() draws the SVG mouth.

### 3. How does it work?
Pure functions so they can be tested without a browser.

### 4. Important functions
```text
   - mouthAt()
       Mouth shape at time t from a viseme timeline.
   - visemeWeightsAt()
       Viseme weights at time t (3D).
   - approximateVisemes()
       Approximate shapes for a word (browser voice fallback).
   - segmentAt()
       Index of the segment active at time t (binary search), or -1.
   - amplitudeFactor()
       Map an audio RMS level to a 0..1 openness factor so the mouth closes when the audio is
       quiet.
   - mouthGeometry()
       SVG geometry for the mouth centred at (cx, cy).
   Other helper functions: lerpShape, f
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: voice/SvgAvatar2D.jsx, voice/speechPlayer.js
   Tested by: voice/voice.test.js
```

### 7. Input and output
- **Input:** Viseme timeline and time.
- **Output:** Mouth parameters.

### 8. Real project example
When the backend returns Kokoro's viseme timeline, these functions decide the mouth shape every frame.

### 9. Viva explanation
> visemes.js converts the speech timeline into mouth shapes for lip sync.

---

## File: `frontend/src/voice/voice.test.js`

### 1. Purpose
Unit tests for the voice interview state machine, lip-sync maths and audio helpers.

### 2. What does it do?
1. Happy path and blocked actions of interviewMachine.
2. Lip-sync segment lookup and mouth shapes.
3. WAV encoding and silence detection.

### 3. How does it work?
Vitest tests on pure functions.

### 4. Important functions
```text
   Other helper functions: run
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: voice/interviewMachine.js, voice/recorder.js, voice/visemes.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> These tests protect the voice interview logic from regressions.

---

# Frontend - interview monitoring (camera, microphone, browser)

## File: `frontend/src/monitoring/AttentionPanels.jsx`

### 1. Purpose
Displays the estimated visual attention - live during the interview and as a report afterwards.

### 2. What does it do?
1. AttentionCard: live rolling attention figure and tracking status.
2. AttentionReport: whole-interview value, coverage, a timeline and the limits of the estimate.

### 3. How does it work?
Formats the values computed by attentionMeter.js / the backend; always labels them 'estimated' and never shows stale values as current.

### 4. Important functions
```text
   - AttentionCard()
       Live attention card.
   - AttentionReport()
       Stored attention report.
   - trackingLabel()
       Human-readable tracking status.
   - Timeline()
       One column per 10 s: height = attention in that bucket; a grey column = no usable
       observation.
   Other helper functions: mmss, Stat
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: monitoring/InterviewMonitorBar.jsx, pages/shared/IntegrityReview.jsx
```
External packages: lucide-react

### 7. Input and output
- **Input:** Monitoring status or stored attention data.
- **Output:** Attention UI.

### 8. Real project example
A reviewer opening an interview sees 'Estimated attention 86%, coverage 92%'.

### 9. Viva explanation
> AttentionPanels presents attention as an estimate with coverage and limits, not as a verdict.

---

## File: `frontend/src/monitoring/InterviewMonitorBar.jsx`

### 1. Purpose
Shows the candidate the live status of camera, microphone, face tracking, connection and monitoring, and lets them review events afterwards.

### 2. What does it do?
1. MonitorBar: status pills and the current neutral warning during the interview.
2. Lets the candidate stop monitoring.
3. MonitoringSummary: after the interview, loads GET /student/interviews/{id}/integrity-events.
4. Lets the candidate add an explanation with PUT .../integrity-events/{eventId}/explanation.

### 3. How does it work?
Pure display of state passed in from the interview page, plus a small summary component that loads its own data.

### 4. Important functions
```text
   - MonitorBar()
       Live status bar during the interview.
   - MonitoringSummary()
       Event list with explanation boxes after the interview.
   Other helper functions: fmt
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, components/SharedUiComponents.jsx, monitoring/AttentionPanels.jsx
   Used by: pages/student/InterviewSession.jsx, pages/student/LiveVoiceInterview.jsx
```
External packages: lucide-react, react

### 7. Input and output
- **Input:** Props: features, status, camera/mic state, warning; sessionId for the summary.
- **Output:** Status bar and event summary UI.

### 8. Real project example
During a voice interview the candidate always sees 'Camera on' and 'Face tracking active'.

### 9. Viva explanation
> This component makes monitoring transparent: the candidate always sees what is running and can explain events.

---

## File: `frontend/src/monitoring/attentionMeter.js`

### 1. Purpose
Estimates the percentage of time the candidate looked toward the interview screen.

### 2. What does it do?
1. Adds time between samples to toward, away or unobserved totals.
2. Treats missing frames and no face as unobserved (never as looking away).
3. Ignores brief glances shorter than confirmMs.
4. Gives a rolling live value and a full-interview snapshot with 10-second buckets.

### 3. How does it work?
attention % = time toward / (toward + away). It uses elapsed time, not frame counts, so the frame rate does not matter. Pure class, no timers or DOM.

### 4. Important functions
```text
   - AttentionMeter()
       Time-based attention calculator (add, setPaused, finish, rolling, snapshot).
   - classifyFrame()
       Maps a frame's face/light state to toward, away or unobserved.
   Other helper functions: newEpoch
```

### 5. Important variables
- `STATE`: Possible frame states.

### 6. Connected files
```text
   Used by: monitoring/interviewMonitor.js
   Tested by: monitoring/attentionMeter.test.js
```

### 7. Input and output
- **Input:** Timestamped frame states.
- **Output:** Attention percentage, coverage and buckets.

### 8. Real project example
24 s toward + 6 s away gives 80% estimated attention in the report.

### 9. Viva explanation
> The attention meter is time-based and treats missing data as unobserved, so poor cameras do not unfairly lower the value.

---

## File: `frontend/src/monitoring/attentionMeter.test.js`

### 1. Purpose
Unit tests for attentionMeter.js.

### 2. What does it do?
1. Percentage comes from elapsed time, not frame count.
2. Missing data is unobserved, never attention or looking away.
3. Old values are not shown as current; enough valid time is needed before a number appears.

### 3. How does it work?
Vitest tests feed synthetic timed samples into AttentionMeter.

### 4. Important functions
```text
   - feed()
       samples every `step` ms from `from` (inclusive) to `to` (exclusive), all in `state`
   Other helper functions: meter
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: monitoring/attentionMeter.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> These tests prove the attention formula is fair and frame-rate independent.

---

## File: `frontend/src/monitoring/audioMonitor.js`

### 1. Purpose
Approximately detects a possible additional voice during the candidate's answer, and tracks connection outages.

### 2. What does it do?
1. Uses only microphone loudness levels from the already-open answer recording.
2. Compares voiced audio with whether the single visible face's mouth is moving.
3. Reports nothing when it cannot attribute the voice (no face / several faces).
4. ConnectionTracker records network down/up episodes.

### 3. How does it work?
SpeechAttribution.audio() and .face() collect samples; end() decides if sustained voice without mouth movement happened.

### 4. Important functions
```text
   - SpeechAttribution()
       Audio-visual check for a voice that may not be the candidate's.
   - ConnectionTracker()
       Tracks offline periods.
```

### 5. Important variables
- `AUDIO_DEFAULTS`: Thresholds for the audio check.

### 6. Connected files
```text
   Used by: monitoring/interviewMonitor.js
   Tested by: monitoring/interviewSecurity.test.js
```

### 7. Input and output
- **Input:** Audio levels and face mouth-openness samples.
- **Output:** Possible-additional-voice or connection events.

### 8. Real project example
If someone whispers answers while the candidate's mouth is closed, a low-severity event may be recorded.

### 9. Viva explanation
> audioMonitor is a cautious audio-visual check; it never uses voice identity and is only a hint for a human reviewer.

**Note:** Nothing is recorded or sent for this check except the event; accent, emotion or speech style are never analysed.

---

## File: `frontend/src/monitoring/browserGuards.test.js`

### 1. Purpose
Unit tests for pasteGuard.js, screenGuard.js and objectMonitor.js.

### 2. What does it do?
1. Short pastes ignored and paste text never recorded.
2. Fullscreen exits timed, second display reported once.
3. Only confident, persistent phones/books are reported.

### 3. How does it work?
Vitest tests with fake browser objects and synthetic detections.

### 4. Important functions
```text
   Other helper functions: det
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: monitoring/objectMonitor.js, monitoring/pasteGuard.js, monitoring/screenGuard.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> These tests check the browser-level integrity guards without a real browser.

---

## File: `frontend/src/monitoring/eventReporter.js`

### 1. Purpose
Sends monitoring events to the backend in small, retry-safe batches.

### 2. What does it do?
1. Gives each event a unique client id so re-sending never duplicates it.
2. Sends batches with POST /student/interviews/{id}/integrity-events.
3. Sends attention totals with PUT /student/interviews/{id}/attention.
4. Keeps unsent events in sessionStorage so a reload does not lose them.
5. reportMetric() sends browser timing metrics to POST /perf/client.

### 3. How does it work?
EventReporter queues events, flushes on an interval (8 s) and on page exit (keepalive), and reports connection problems.

### 4. Important functions
```text
   - EventReporter()
       Batching sender (add, flush, sendAttention, flushOnExit, close).
   - reportMetric()
       Sends one client performance metric.
   - eventId()
       Creates a unique event id.
   Other helper functions: storeKey
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js
   Used by: monitoring/interviewMonitor.js, pages/student/LiveVoiceInterview.jsx
   Tested by: monitoring/interviewSecurity.test.js
```

### 7. Input and output
- **Input:** Event objects from the detectors.
- **Output:** API requests to the backend.

### 8. Real project example
After a 'face absent' event happens, it is sent in the next batch a few seconds later.

### 9. Viva explanation
> eventReporter makes event delivery reliable with client ids, batching and sessionStorage backup.

**Note:** Only short event records leave the browser - never video, images, audio or face measurements.

---

## File: `frontend/src/monitoring/faceMonitor.js`

### 1. Purpose
Analyses the camera picture on the device with MediaPipe Face Landmarker a few times per second.

### 2. What does it do?
1. Loads the MediaPipe WebAssembly runtime and face model served by this app.
2. Reads frames from the camera <video> element.
3. Passes face results (and a tiny brightness sample) to a callback.
4. faceAnalysisAvailable() checks whether face analysis can run in this browser.

### 3. How does it work?
FaceMonitor.start(video) creates the landmarker and runs detection on a timer (default 4 fps); stop() ends it.

### 4. Important functions
```text
   - FaceMonitor()
       Class that runs face analysis on a video element.
   - faceAnalysisAvailable()
       Returns whether the face model can be loaded.
   Other helper functions: loadLandmarker
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: monitoring/frameAnalysis.js
   Used by: monitoring/interviewMonitor.js, pages/student/InterviewSetup.jsx
```
External packages: @mediapipe/tasks-vision

### 7. Input and output
- **Input:** Camera video element.
- **Output:** Per-frame face results for frameAnalysis.js / interviewMonitor.js.

### 8. Real project example
On the interview setup screen it checks that the candidate's face is visible before starting.

### 9. Viva explanation
> faceMonitor uses Google's MediaPipe face landmark model locally in the browser for privacy.

**Note:** Frames never leave the browser and no third-party server is contacted.

---

## File: `frontend/src/monitoring/frameAnalysis.js`

### 1. Purpose
Pure maths functions that turn MediaPipe face results into simple measurements: number of faces, head angle, eye direction, brightness.

### 2. What does it do?
1. Measures picture brightness (to detect a covered camera or low light).
2. Calculates head yaw/pitch and approximate eye gaze.
3. Counts faces and checks if the face is partly outside the frame.
4. Calibration: learns the candidate's own neutral position for 5 seconds.
5. observe() turns one frame into an observation (face absent, multiple faces, looking away...).

### 3. How does it work?
Only geometry is used. Nothing identifies a person and no emotions are computed. Being pure functions, they are unit-tested.

### 4. Important functions
```text
   - analyzeFaces()
       Summarises all faces in one MediaPipe result.
   - observe()
       Converts faces + light into one observation.
   - brightness()
       Mean and spread of pixel brightness.
   - headAngles()
       Yaw/pitch from the face transformation matrix.
   - setupGuidance()
       Advice for the setup screen (move closer, more light...).
   - Calibration()
       Class that computes the neutral baseline.
   - yawFromLandmarks()
       Rough yaw from landmarks when no matrix is available: nose position between the outer
       eye corners.
   - gazeFromBlendshapes()
       Horizontal / vertical eye direction from ARKit-style eye blendshapes (-1..1,
       approximate).
   - mouthOpen()
       Mouth opening (0-1) from the jawOpen blendshape; used only to tell whether the visible
       person is speaking.
   - observeMeta()
       Facts that go with the conditions above (kept per episode by SignalTracker: max faces,
       gaze cause, edge).
   Other helper functions: median
```

### 5. Important variables
- `ATTENTION_LIMITS`: Head/eye angle limits for 'looking toward the screen'.
- `LIGHT`: Brightness limits for obstructed / low light.

### 6. Connected files
```text
   Used by: monitoring/faceMonitor.js, monitoring/interviewMonitor.js,
   pages/student/InterviewSetup.jsx
   Tested by: monitoring/frameAnalysisAndSignals.test.js, monitoring/interviewSecurity.test.js
```

### 7. Input and output
- **Input:** MediaPipe face results and a small pixel buffer.
- **Output:** Observation objects.

### 8. Real project example
If the candidate turns their head far to the side, observe() reports 'attention away'.

### 9. Viva explanation
> frameAnalysis contains the deterministic geometry used for attention estimation, kept pure so it can be tested.

---

## File: `frontend/src/monitoring/frameAnalysisAndSignals.test.js`

### 1. Purpose
Unit tests for frameAnalysis.js and signalTracker.js.

### 2. What does it do?
1. Brief face dropouts are ignored; warnings only after the grace period.
2. Hysteresis keeps one episode despite flicker.
3. Only consented signals are tracked.
4. Brightness, face counting and head/gaze maths.

### 3. How does it work?
Vitest tests using synthetic MediaPipe-shaped results.

### 4. Important functions
```text
   Other helper functions: run, series
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: monitoring/frameAnalysis.js, monitoring/signalTracker.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> These tests verify the false-positive protections of camera monitoring.

---

## File: `frontend/src/monitoring/interviewMonitor.js`

### 1. Purpose
Runs all the interview monitoring checks the candidate agreed to, for one interview, and stops them at the end.

### 2. What does it do?
Coordinator of camera, face, attention, object, paste, screen, focus and audio checks.

1. Starts only the detectors the candidate ticked on the setup screen (consented features).
2. Analyses camera frames with FaceMonitor and ObjectMonitor and turns them into events with SignalTracker.
3. Tracks attention time with AttentionMeter and focus/fullscreen/paste with the guards.
4. Sends every event through ONE EventReporter (batched, retry-safe).
5. Shows candidate reminders through one rate-limited warning function and can request a pause.
6. Stops everything and flushes pending events on stop().

### 3. How does it work?
InterviewMonitor is a class created with the session id, consented features, the admin policy and an optional calibration baseline. start(video) begins frame analysis; callbacks (onStatus, onWarning, onPauseRequest) update the interview page.

```
Candidate gives consent on setup screen
   |
   v
InterviewMonitor.start(video)
   |
   v
Detectors analyse frames on the device
   |
   v
Persistent conditions become events
   |
   v
EventReporter sends events to the server
   |
   v
stop() ends monitoring
```

### 4. Important functions
```text
   - InterviewMonitor()
       Class that wires all detectors together for one interview (start, recalibrate, paused,
       resumed, cameraLost, micLost, stop).
```

### 5. Important variables
- `FOCUS_WARNING`: Message shown when the candidate leaves the interview window.

### 6. Connected files
```text
   Uses: monitoring/attentionMeter.js, monitoring/audioMonitor.js, monitoring/eventReporter.js,
   monitoring/faceMonitor.js, monitoring/frameAnalysis.js, monitoring/objectMonitor.js,
   monitoring/pasteGuard.js, monitoring/screenGuard.js, monitoring/signalTracker.js
   Used by: monitoring/useTypedMonitoring.js, pages/student/LiveVoiceInterview.jsx
   Tested by: monitoring/interviewSecurity.test.js
```

### 7. Input and output
- **Input:** Session id, consented features, policy (GET /monitoring/policy), camera video element, microphone levels.
- **Output:** Integrity events and attention totals sent to the backend; status and warnings for the UI.

### 8. Real project example
During a live voice interview, if a second face stays visible for several seconds a 'multiple faces' event is recorded for a reviewer.

### 9. Viva explanation
> interviewMonitor.js is the controller of our consent-based proctoring. Analysis happens in the browser with MediaPipe, and only small event records are sent to the backend.

**Note:** Only short event records leave the browser - never video, images, audio or face measurements. Signals are approximate and are only reviewed by humans; they never change interview scores.

---

## File: `frontend/src/monitoring/interviewSecurity.test.js`

### 1. Purpose
Scenario tests for the whole interview security module.

### 2. What does it do?
1. Calibration and eye-gaze scenarios (side camera, brief glance, long deviation).
2. Face presence, partial face and multiple faces.
3. Audio attribution, connection outages, the event reporter and rate-limited reminders.

### 3. How does it work?
Detector inputs are simulated; the tests prove the decision logic, not MediaPipe's accuracy.

### 4. Important functions
```text
   - box()
       --- synthetic MediaPipe results
       ------------------------------------------------------------------------------------
   - play()
       Feed frames at `step` ms through analysis + tracker like InterviewMonitor does;
       returns all outputs.
   Other helper functions: yawMatrix, blend, result, n
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, monitoring/audioMonitor.js, monitoring/eventReporter.js,
   monitoring/frameAnalysis.js, monitoring/interviewMonitor.js, monitoring/signalTracker.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> These tests simulate realistic cheating and non-cheating situations to check the monitoring decisions.

---

## File: `frontend/src/monitoring/mediaSession.js`

### 1. Purpose
Handles the camera for the interview and the pre-interview device checks.

### 2. What does it do?
1. CameraSession opens one camera stream only when the candidate asks, and watches for disconnects.
2. testMicrophone() measures microphone level for a short test.
3. checkNetwork() calls /api/health to check the connection.
4. browserSupport() checks required browser features.
5. cameraErrorMessage() gives friendly error messages.

### 3. How does it work?
Uses navigator.mediaDevices.getUserMedia; stop() releases all camera tracks.

### 4. Important functions
```text
   - CameraSession()
       Opens/stops the camera stream.
   - testMicrophone()
       Short microphone level test.
   - checkNetwork()
       Health check of the backend.
   - browserSupport()
       Feature support check.
   Other helper functions: cameraErrorMessage
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js
   Used by: monitoring/useTypedMonitoring.js, pages/student/InterviewSetup.jsx,
   pages/student/LiveVoiceInterview.jsx
```

### 7. Input and output
- **Input:** Browser media permissions.
- **Output:** A camera stream and device check results.

### 8. Real project example
On the setup screen the candidate clicks 'Test microphone' and sees the level meter move.

### 9. Viva explanation
> mediaSession manages camera access carefully: opened only on request and always fully released.

---

## File: `frontend/src/monitoring/objectMonitor.js`

### 1. Purpose
Detects a phone or book/notes in the camera view on the device (MediaPipe Object Detector, EfficientDet-Lite0).

### 2. What does it do?
1. Runs object detection about once per second.
2. Keeps only confident 'cell phone' and 'book' detections.
3. ObjectTracker requires the object to be seen in most frames for several seconds before warning or recording.
4. Can run detection in a Web Worker or on the page.

### 3. How does it work?
observeObjects() filters detections by score; ObjectTracker turns repeated detections into events.

### 4. Important functions
```text
   - ObjectMonitor()
       Runs the object detector on the camera video.
   - ObjectTracker()
       Debounces detections into events.
   - observeObjects()
       Filters detection results to phone/notes.
   - preloadObjectDetector()
       Loads the model early.
   - workerDetector()
       Each detection takes ~70-85 ms (measured in the browser E2E).
   - loadDetector()
       -> {detect(video, t): Promise<ObjectDetectorResult>}
   Other helper functions: pageDetector
```

### 5. Important variables
- `OBJECT_CLASSES`: COCO labels we care about.
- `OBJECT_MIN_SCORE`: Minimum confidence per object.

### 6. Connected files
```text
   Uses: monitoring/signalTracker.js
   Used by: monitoring/interviewMonitor.js, pages/student/InterviewSetup.jsx
   Tested by: monitoring/browserGuards.test.js
```
External packages: @mediapipe/tasks-vision

### 7. Input and output
- **Input:** Camera video frames.
- **Output:** phone_in_view / notes_in_view events.

### 8. Real project example
A phone held in front of the camera for several seconds creates a 'phone in view' event.

### 9. Viva explanation
> objectMonitor uses a small object detection model in the browser and debounces results to avoid false alarms.

**Note:** Detection is approximate; the server caps the severity and a reviewer decides what it means.

---

## File: `frontend/src/monitoring/pasteGuard.js`

### 1. Purpose
Notices when text is pasted into an answer box, without recording the pasted text.

### 2. What does it do?
1. Ignores short pastes (under 40 characters).
2. Records 'paste_detected' or, from 200 characters, 'paste_long'.
3. Warns the candidate only for long pastes.

### 3. How does it work?
PasteGuard.attach() listens for paste events on answer fields; pasteEvent() builds the event.

### 4. Important functions
```text
   - PasteGuard()
       Attaches/detaches the paste listener.
   - pasteEvent()
       Creates an event for one paste or returns null.
   - isAnswerField()
       Checks whether the paste happened in an answer field.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: monitoring/interviewMonitor.js
   Tested by: monitoring/browserGuards.test.js
```

### 7. Input and output
- **Input:** Browser paste events.
- **Output:** Paste events for the reporter.

### 8. Real project example
Pasting a full paragraph into a typed interview answer creates a 'paste_long' event.

### 9. Viva explanation
> pasteGuard records only that a paste happened and its length category, never the text itself.

---

## File: `frontend/src/monitoring/screenGuard.js`

### 1. Purpose
Tracks leaving fullscreen and notes a second connected display during the interview.

### 2. What does it do?
1. Requests fullscreen at the start.
2. Records time spent outside fullscreen (ignoring sub-second flickers).
3. Notes once if the browser reports an extended (second) screen.

### 3. How does it work?
FullscreenTracker measures episodes; ScreenGuard listens to fullscreenchange and uses screen.isExtended when available.

### 4. Important functions
```text
   - ScreenGuard()
       Manages fullscreen and display checks.
   - FullscreenTracker()
       Pure episode tracker.
   - secondDisplayEvent()
       Event for a second display, if detectable.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Used by: monitoring/interviewMonitor.js
   Tested by: monitoring/browserGuards.test.js
```

### 7. Input and output
- **Input:** Browser fullscreen and screen information.
- **Output:** Fullscreen-exit and second-display events.

### 8. Real project example
If the candidate exits fullscreen for 20 seconds, that duration is recorded.

### 9. Viva explanation
> screenGuard is a browser-level integrity signal; it does not know what was on the other screen.

---

## File: `frontend/src/monitoring/signalTracker.js`

### 1. Purpose
Turns per-frame observations into calm warnings and recorded integrity events, avoiding false alarms.

### 2. What does it do?
1. Waits for a grace period before warning the student.
2. Records an event only if the condition lasted a minimum time.
3. Ignores short detector dropouts (hysteresis).
4. Gives each event a confidence = share of frames that showed it.
5. RepeatTracker detects repeated looking away; FocusTracker records time away from the window.

### 3. How does it work?
SignalTracker.update(time, observation) keeps an episode per condition; flush() closes open episodes at the end.

### 4. Important functions
```text
   - SignalTracker()
       Main episode tracker for camera conditions.
   - RepeatTracker()
       Counts repeated deviations in a time window.
   - FocusTracker()
       Measures time the candidate spent outside the interview window.
   - thresholdsFrom()
       Merges admin-configured thresholds with defaults.
```

### 5. Important variables
- `DEFAULT_THRESHOLDS`: Default warn/record/end times.
- `WARNINGS`: Neutral reminder messages.

### 6. Connected files
```text
   Used by: monitoring/interviewMonitor.js, monitoring/objectMonitor.js
   Tested by: monitoring/frameAnalysisAndSignals.test.js, monitoring/interviewSecurity.test.js
```

### 7. Input and output
- **Input:** Observations with timestamps; thresholds from the admin policy.
- **Output:** Warnings and event objects.

### 8. Real project example
A face missing for 1 second is ignored, but missing for 10 seconds becomes one 'face_absent' event.

### 9. Viva explanation
> signalTracker applies grace periods and minimum durations so innocent movements do not create alerts.

---

## File: `frontend/src/monitoring/useTypedMonitoring.js`

### 1. Purpose
React hook that runs consent-based monitoring on the typed (text) interview page.

### 2. What does it do?
1. Waits until the setup screen calls begin with the consented features.
2. Starts the camera and an InterviewMonitor.
3. Keeps status, warnings and camera state for the page.
4. Stops monitoring, and on withdrawal calls POST /student/interviews/{id}/monitoring/withdraw.

### 3. How does it work?
Uses refs for the camera, monitor and policy, and React state for UI values; reuses the same detectors as the voice room.

### 4. Important functions
```text
   - useTypedMonitoring()
       Hook returning monitoring state and begin/stop controls.
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: apiClient.js, monitoring/interviewMonitor.js, monitoring/mediaSession.js
   Used by: pages/student/InterviewSession.jsx
```
External packages: react

### 7. Input and output
- **Input:** Interview session id; setup choices.
- **Output:** Monitoring state for InterviewSession.jsx.

### 8. Real project example
When a student chooses a typed interview with camera monitoring, this hook runs the checks.

### 9. Viva explanation
> useTypedMonitoring reuses the monitoring engine for text interviews through a React hook.

---

# Frontend - English learning helpers

## File: `frontend/src/english/vocabularyReview.js`

### 1. Purpose
Pure helpers for the English word list, the review session and the daily plan display.

### 2. What does it do?
1. Labels Leitner boxes and due dates.
2. Runs a review session on screen (start, flip, answer, progress).
3. Summarises the daily plan and shapes score trends for charts.

### 3. How does it work?
No React and no API calls; the server owns the spaced-repetition rules, this file only manages the on-screen session.

### 4. Important functions
```text
   - startReview()
       Creates a review session from cards.
   - answer()
       Records 'knew it'/'not yet' locally.
   - planSummary()
       Counts done items of the daily plan.
   - trendRows()
       Converts skill scores to 0-100 rows for charts.
   - dueText()
       'Due now' / 'Due in 4 days' text.
   Other helper functions: boxLabel, currentCard, isFinished, flip, reviewProgress
```

### 5. Important variables
- `BOX_LABELS`: Names of the 5 Leitner boxes.

### 6. Connected files
```text
   Used by: components/EnglishDailyPlan.jsx, components/EnglishProgress.jsx,
   pages/student/VocabularyTrainer.jsx
   Tested by: english/vocabularyReview.test.js
```

### 7. Input and output
- **Input:** Cards and plan data from the API.
- **Output:** Session state and formatted values.

### 8. Real project example
On the vocabulary page the student flips each card and answers; a 'not yet' card is shown again at the end.

### 9. Viva explanation
> This file holds the pure logic of the vocabulary trainer so it can be unit-tested.

---

## File: `frontend/src/english/vocabularyReview.test.js`

### 1. Purpose
Unit tests for vocabularyReview.js.

### 2. What does it do?
1. Review session flow and repeats.
2. Formatting of boxes, due dates, plan summary and trends.

### 3. How does it work?
Vitest tests.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: english/vocabularyReview.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests the vocabulary review logic.

---

# Frontend - live notifications

## File: `frontend/src/live/notificationStream.js`

### 1. Purpose
Keeps one live connection per browser tab to receive 'new notification' signals from the server.

### 2. What does it do?
1. Opens GET /api/notifications/stream (Server-Sent Events) with the login cookie.
2. Tells subscribers to re-fetch notifications when a signal arrives.
3. Reconnects with exponential backoff (1-60 s) and polls every 30 s while disconnected.
4. Shares one connection between the header bell and the Notifications page.

### 3. How does it work?
NotificationStream wraps EventSource; subscribeNotifications() adds a listener and returns an unsubscribe function.

### 4. Important functions
```text
   - subscribeNotifications()
       Subscribe to change signals.
   - onNotificationStatus()
       Subscribe to connection status.
   - backoffDelay()
       Reconnect delay with jitter.
   - NotificationStream()
       The shared stream class.
```

### 5. Important variables
- `BACKOFF_MIN_MS`: 1 s
- `BACKOFF_MAX_MS`: 60 s
- `POLL_MS`: 30 s polling fallback

### 6. Connected files
```text
   Uses: apiClient.js
   Used by: components/AppShellLayout.jsx, pages/Notifications.jsx
   Tested by: live/notificationStream.test.js
```

### 7. Input and output
- **Input:** Server signals.
- **Output:** Callbacks to subscribed components.

### 8. Real project example
When a recruiter shortlists a student, the student's bell updates within a second.

### 9. Viva explanation
> notificationStream implements real-time notifications with Server-Sent Events plus a polling fallback.

**Note:** Signals carry no content; components re-fetch /notifications so normal access checks apply.

---

## File: `frontend/src/live/notificationStream.test.js`

### 1. Purpose
Unit tests for notificationStream.js.

### 2. What does it do?
1. Backoff doubling and cap.
2. Connect, relay, reconnect and polling fallback.
3. One shared connection.

### 3. How does it work?
Vitest tests with fake timers and a fake EventSource.

### 4. Important functions
```text
   Other helper functions: FakeES, fakeTimers, setup
```

### 5. Important variables
No important module-level variables.

### 6. Connected files
```text
   Uses: live/notificationStream.js
```
External packages: vitest

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Run with `npm test`.

### 9. Viva explanation
> Tests prove live notifications recover from network errors.

---

# Tooling - avatar conversion scripts

## File: `frontend/avatar-src/compress_avatars.py`

### 1. Purpose
Shrinks the interviewer .glb files for faster web loading.

### 2. What does it do?
1. Unpacks a GLB with gltf-transform.
2. Re-encodes textures as WebP with Pillow.
3. Compresses geometry and blendshapes with meshopt and repacks the GLB.

### 3. How does it work?
Run: python frontend/avatar-src/compress_avatars.py IN.glb OUT.glb [...]. Needs Node (npx) and Pillow. Avatar3D.jsx sets a MeshoptDecoder to read the result.

### 4. Important functions
```text
   Other helper functions: npx, compress
```

### 5. Important variables
- Module-level constants: CLI

### 6. Connected files
```text
Standalone.
```
External packages: PIL

### 7. Input and output
- **Input:** Original GLB files.
- **Output:** Compressed GLB files (bones and morph names unchanged).

### 8. Real project example
Reduced the avatar downloads from about 16.5 MB to 5.4 MB.

### 9. Viva explanation
> This script compresses 3D models with WebP textures and meshopt geometry so the interview page loads faster.

**Note:** Developer tool; run on the original exports, not on already-compressed files.

---

## File: `frontend/avatar-src/convert_metahuman.py`

### 1. Purpose
Optional Blender script that bakes a MetaHuman's facial rig into plain blendshapes so it can be used as a high-detail web avatar.

### 2. What does it do?
1. Lists the controls and meshes of an imported MetaHuman (--list).
2. For each ARKit expression (and optional visemes) sets face controls from metahuman_bake_map.json and stores the deformed mesh as a shape key.
3. Exports a GLB that the web app drives through blendshapes only.

### 3. How does it work?
Runs in Blender 4.5+ on a .blend with the MetaHuman imported by the Character DNA add-on; uses depsgraph evaluation and the glTF exporter.

### 4. Important functions
```text
   - face_board()
       The face-board armature (its pose bones are the GUI controls RigLogic reads).
   - face_meshes()
       Meshes of the head that RigLogic deforms (head, teeth, eyes, lashes, eye shell,
       saliva...) at the chosen LOD.
   - evaluate()
       Let RigLogic (driven by frame/depsgraph updates) apply the current face-board pose.
   - apply_target()
       spec: {"CTRL_L_eye_blink": [x, y], ...} or {"pose": "<action name>"}; values are face-
       board locations.
   Other helper functions: opt, lod_of, reset, capture, main
```

### 5. Important variables
- Module-level constants: HERE, MAP, LOD, TEX, LIST, OUT

### 6. Connected files
```text
Standalone.
```
External packages: bpy

### 7. Input and output
- **Input:** .blend file, bake map JSON, options --lod and --tex.
- **Output:** An HD .glb avatar (e.g. public/avatars/hd/aria.glb).

### 8. Real project example
Used if the team wants a more realistic optional HD interviewer model.

### 9. Viva explanation
> Browsers cannot run MetaHuman's RigLogic, so this script bakes the needed facial poses into blendshapes.

**Note:** The add-on's control names were not verified against a real export (see METAHUMAN_GUIDE.md). Developer tool only.

---

## File: `frontend/avatar-src/convert_rocketbox.py`

### 1. Purpose
One-time build script that converts a Microsoft Rocketbox avatar (FBX, MIT licence) into a web-ready .glb file for the 3D interviewer.

### 2. What does it do?
1. Imports the '_facial' FBX (rigged body + facial blendshapes) into Blender.
2. Keeps only the blendshapes the app animates (15 visemes + about 25 ARKit expressions).
3. Relinks, downsizes and converts textures to JPEG/PNG (browsers cannot read TGA).
4. Exports a GLB with skin and morph targets, no animations.

### 3. How does it work?
Runs inside Blender: blender -b --factory-startup --python convert_rocketbox.py -- <avatar_folder> <output.glb>.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
- Module-level constants: TEX, TMP, KEEP_PREFIX, KEEP_ARKIT

### 6. Connected files
```text
Standalone.
```
External packages: bpy

### 7. Input and output
- **Input:** A Rocketbox avatar folder (Export/*_facial.fbx and Textures/*.tga).
- **Output:** A .glb model saved to frontend/public/avatars/.

### 8. Real project example
The Aria, Victor, Marcus and Elena models in public/avatars were produced with this script.

### 9. Viva explanation
> This Blender script prepares open-licence 3D characters for the browser by keeping only the facial shapes we need for lip sync.

**Note:** A developer tool, not part of the running application.

---

# Tooling - team report generator

## File: `docs/team_report/build.py`

### 1. Purpose
Builds docs/HireSense_Team_Work_Distribution.pdf from content.py.

### 2. What does it do?


### 3. How does it work?
Run from the repository root with the backend venv (needs playwright + pypdf): backend\venv\Scripts\python docs\team_report\build.py Two passes: render, find the page of every section heading, then render again with page numbers in the contents. The cover is rendered separately (no header/footer) and merged in front; body pages are numbered from 1.

### 4. Important functions
```text
   - fmt()
       Escape, then show file paths in a monospace style.
   - simple_arch_svg()
       Three-layer architecture: browser -> backend -> data and AI.
   - flow_svg()
       Numbered boxes in a snake layout with arrows: left-to-right, then right-to-left on the
       next row.
   Other helper functions: ul, cover, toc, arch_svg, body, page, render, find_pages, main
```

### 5. Important variables
- Module-level constants: HERE, OUT_PDF, SHOTS, CSS, COVER_CSS, SECTIONS, HEADER, FOOTER

### 6. Connected files
```text
Standalone.
```
External packages: content, playwright, pypdf

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Builds docs/HireSense_Team_Work_Distribution.pdf from content.py.

### 9. Viva explanation
> Builds docs/HireSense_Team_Work_Distribution.pdf from content.py.

---

## File: `docs/team_report/content.py`

### 1. Purpose
Content of the HireSense team work-distribution report (facts taken from the repository and its docs).

### 2. What does it do?


### 3. How does it work?
See the steps above.

### 4. Important functions
```text
No functions (data / configuration / markup file).
```

### 5. Important variables
- Module-level constants: PROJECT, SUBTITLE, DATE, TEAM, DESCRIPTION, TECH_TABLE, MEMBERS, TIMELINE, COLLABORATION,    SIMPLE_ARCH_TEXT, STUDENT_FLOW, STUDENT_FLOW_TEXT, RECRUITER_FLOW, ADMIN_FLOW,    OTHER_FLOW_TEXT, ARCHITECTURE, CONCLUSION

### 6. Connected files
```text
Standalone.
```

### 7. Input and output
- **Input:** Not applicable.
- **Output:** Not applicable.

### 8. Real project example
Content of the HireSense team work-distribution report (facts taken from the repository and its docs).

### 9. Viva explanation
> Content of the HireSense team work-distribution report (facts taken from the repository and its docs).

---

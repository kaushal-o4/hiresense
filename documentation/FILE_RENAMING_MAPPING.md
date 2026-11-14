# HireSense AI: File Renaming Mapping

This document lists every file that was renamed or moved during the restructuring (branch
`restructure-and-document`, 2026-11-14), why, and what was updated so the application keeps working.

## Summary

| | Count |
|---|---|
| Backend Python modules renamed | 71 (+ the `odm` package folder renamed to `mongodb_data_layer`) |
| ...of which also moved into a new group folder | 36 (`app/services/*` was split into 8 sub-folders) |
| New package marker files (`__init__.py`) for the new service folders | 8 |
| Frontend files renamed (same folder) | 55 |
| Files whose import statements were rewritten | 106 Python files, 234 import paths in JavaScript/JSX files |
| Other files whose references were updated | 60 (README, `docs/`, `start-backend.bat`, `backend/Dockerfile`, `.github/workflows/tests.yml`, `.env.example` files, requirements comments, code comments) |

Verification after the renaming: all 77 backend application modules import, the backend test suite passes
(369 passed, 2 skipped, the same as before), the frontend unit tests pass (141 of 141) and the production build
succeeds. FastAPI's OpenAPI schema still lists the same 203 endpoints.

## How references were updated

- **Python imports** were rewritten from the syntax tree, not with plain text search. Relative imports stay
  relative and are recalculated from the new location. When code used a module object, the import keeps the old
  short name as an alias so the rest of the file did not have to change, for example:

  ```python
  # before
  from ..services import ai, interviewers
  # after
  from ..services.interview import ai_interview_service as ai, interviewer_personalities as interviewers
  ```
- **Dotted module strings** were rewritten, for example test patches like
  `"app.services.local_llm.chat_json"`, and commands such as `python -m app.seed` (now `python -m app.seed_initial_data`).
- **JavaScript/JSX imports**, `import()` calls (lazy routes in `App.jsx`) and `vi.mock()` paths were resolved to
  the real file and rewritten relative to the new name.
- **File paths in documentation and comments** (`services/ai.py`, `pages/student/Dashboard.jsx`, ...) were
  replaced with the new paths. Ambiguous bare names such as `common.py` were fixed by hand.
- **Path-sensitive code:** `services/interview/interviewer_personalities.py` finds `frontend/public/avatars`
  relative to its own location. Because it moved one folder deeper, `parents[3]` became `parents[4]`. This was the
  only code (not import) change needed.

## Files and names that were deliberately kept

| File | Why the name was kept |
|---|---|
| `backend/app/main.py` | Standard FastAPI/uvicorn entry point. `app.main:app` is used by `start-backend.bat`, `backend/Dockerfile`, `render.yaml`, CI and the README; it already says what it is. |
| all `__init__.py` | Required by Python to mark packages. |
| `backend/app/routers/`, `backend/app/services/`, `routers/admin/`, `routers/jobs/` folder names | Already descriptive (FastAPI "routers" convention). |
| `frontend/index.html`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/src/index.css` | Vite/React conventions (`index.html` loads `/src/main.jsx`). |
| `package.json`, `package-lock.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `vercel.json`, `nginx.conf.template`, `Dockerfile`, `docker-compose.yml`, `render.yaml`, `requirements*.txt`, `pytest.ini`, `.env.example` | Names required by the tools that read them. |
| React components that already had a clear name (`Login.jsx`, `Register.jsx`, `InterviewSession.jsx`, `InterviewSetup.jsx`, `Avatar3D.jsx`, `CompareCandidates.jsx`, ...) | Already describe their content. React components keep PascalCase, which is the React convention. |
| Most `frontend/src/voice/*` and `frontend/src/monitoring/*` modules (`speechPlayer.js`, `faceMonitor.js`, `attentionMeter.js`, ...) | Already descriptive. |
| Test files `backend/tests/test_*.py` | Already named after the feature they test. pytest discovers files by the `test_` prefix. |
| `backend/ml/`, `backend/eval/`, `backend/tests_e2e/`, `backend/tests_integration/`, `backend/tests_perf/` | Already descriptive. |

Naming conventions used:
- Python files use lowercase with underscores (`snake_case`).
- React component files use PascalCase (`StudentDashboard.jsx`).
- Other JavaScript modules use camelCase (`apiClient.js`).
- Original file extensions were kept.

## Backend: renamed and moved files

| # | Old filename | New filename | Purpose | Reason for renaming |
|---|---|---|---|---|
| 1 | `backend/app/odm/__init__.py` | `backend/app/mongodb_data_layer/__init__.py` | Lets the rest of the code write SQLAlchemy-like queries while data is stored in MongoDB. | descriptive name |
| 2 | `backend/app/config.py` | `backend/app/application_configuration.py` | Single source of truth for application settings. | `config.py` was a generic/ambiguous name |
| 3 | `backend/app/database.py` | `backend/app/database_connection.py` | Database connection and per-request session handling. | `database.py` was a generic/ambiguous name |
| 4 | `backend/app/deps.py` | `backend/app/authentication_dependencies.py` | Authentication (who are you?) and authorisation (are you allowed?) for every protected endpoint. | `deps.py` was a generic/ambiguous name |
| 5 | `backend/app/models.py` | `backend/app/database_models.py` | The database schema of the project. | `models.py` was a generic/ambiguous name |
| 6 | `backend/app/schemas.py` | `backend/app/request_validation_schemas.py` | Input validation for API requests. | `schemas.py` was a generic/ambiguous name |
| 7 | `backend/app/security.py` | `backend/app/password_and_token_security.py` | Password hashing and JSON Web Token handling. | `security.py` was a generic/ambiguous name |
| 8 | `backend/app/serializers.py` | `backend/app/api_response_serializers.py` | Output formatting (database object -> JSON). | `serializers.py` was a generic/ambiguous name |
| 9 | `backend/app/seed.py` | `backend/app/seed_initial_data.py` | One-time (repeatable) database initialisation script. | `seed.py` was a generic/ambiguous name |
| 10 | `backend/app/seed_jobs.py` | `backend/app/seed_sample_jobs.py` | Adds sample job openings and placement drives (fictional companies) so students have something to browse and apply to during a demo. | name now states the responsibility |
| 11 | `backend/app/reset_admin.py` | `backend/app/reset_admin_password.py` | Command-line tool to reset the admin account's password if the one printed by the seed was lost. | name now states the responsibility |
| 12 | `backend/app/odm/coltypes.py` | `backend/app/mongodb_data_layer/column_types.py` | Defines field types (String, Text, Integer, Float, Boolean, DateTime, JSON), ForeignKey, unique constraints and indexes used when declaring... | name now states the responsibility |
| 13 | `backend/app/odm/connection.py` | `backend/app/mongodb_data_layer/mongo_connection.py` | Creates the single MongoClient for the process and creates indexes/unique constraints declared on the models. | name now states the responsibility |
| 14 | `backend/app/odm/expressions.py` | `backend/app/mongodb_data_layer/query_expressions.py` | Query building blocks: columns, comparisons (==, <, in_, like), AND/OR/NOT, functions such as count and max, and ordering. | name now states the responsibility |
| 15 | `backend/app/odm/mapping.py` | `backend/app/mongodb_data_layer/model_mapping.py` | The declarative `Base` class for models, relationships between models, and per-object state (new / loaded / changed). | name now states the responsibility |
| 16 | `backend/app/odm/query.py` | `backend/app/mongodb_data_layer/legacy_query_api.py` | Supports the older `db.query(Model).filter(...)` style used by some tests and scripts, plus helpers for sorting, joins and removing duplicates in... | name now states the responsibility |
| 17 | `backend/app/odm/session.py` | `backend/app/mongodb_data_layer/database_session.py` | Runs every database read and write for a request. | name now states the responsibility |
| 18 | `backend/app/odm/statements.py` | `backend/app/mongodb_data_layer/query_statements.py` | The select, update and delete statement builders and the result objects they return. | name now states the responsibility |
| 19 | `backend/app/routers/auth.py` | `backend/app/routers/authentication_routes.py` | Registration and login (Stage 1 of the workflow). | `auth.py` was a generic/ambiguous name |
| 20 | `backend/app/routers/common.py` | `backend/app/routers/profile_and_notification_routes.py` | Endpoints every signed-in role uses: view/edit own profile, personal settings, notifications and the live notification stream. | `common.py` was a generic/ambiguous name |
| 21 | `backend/app/routers/english.py` | `backend/app/routers/english_practice_routes.py` | Spoken and typed English conversation practice with the AI companion 'Aria', plus vocabulary review, mistake profile, daily plan and English... | name now states the responsibility |
| 22 | `backend/app/routers/interviews.py` | `backend/app/routers/interview_routes.py` | Interview configuration, question generation, answer evaluation, scoring and report (Stages 3-10). | name now states the responsibility |
| 23 | `backend/app/routers/interview_live.py` | `backend/app/routers/live_voice_interview_routes.py` | Real-time voice interview turns (Stage 5, voice mode). | name now states the responsibility |
| 24 | `backend/app/routers/assessments.py` | `backend/app/routers/skill_assessment_routes.py` | Coding and problem-solving assessment. | name now states the responsibility |
| 25 | `backend/app/routers/mentors.py` | `backend/app/routers/mentor_portal_routes.py` | Mentor portal: assigned students, their progress and reports, feedback, improvement plans with goals, mentoring sessions and alerts. | name now states the responsibility |
| 26 | `backend/app/routers/monitoring.py` | `backend/app/routers/interview_monitoring_routes.py` | Disclosed, opt-in interview integrity monitoring (camera/browser signals), security settings and the performance dashboard API. | name now states the responsibility |
| 27 | `backend/app/routers/students.py` | `backend/app/routers/student_portal_routes.py` | Resume upload/analysis (Stage 2) and the student dashboard (Stage 11). | name now states the responsibility |
| 28 | `backend/app/routers/voice.py` | `backend/app/routers/voice_speech_routes.py` | Voice support endpoints: text-to-speech for the avatar and speech-to-text for spoken answers. | name now states the responsibility |
| 29 | `backend/app/routers/admin/analytics.py` | `backend/app/routers/admin/admin_analytics_routes.py` | Admin analytics: platform dashboard, placement report, student overview, AI report review and backup. | name now states the responsibility |
| 30 | `backend/app/routers/admin/content.py` | `backend/app/routers/admin/admin_content_routes.py` | Admin configuration of interview content: categories, question bank, evaluation rubrics, badges, reward rules and challenges. | name now states the responsibility |
| 31 | `backend/app/routers/admin/operations.py` | `backend/app/routers/admin/admin_operations_routes.py` | Admin operations: all job postings, flagged activity review, AI usage, error and audit logs, platform settings, placement drives and announcements. | name now states the responsibility |
| 32 | `backend/app/routers/admin/people.py` | `backend/app/routers/admin/admin_user_management_routes.py` | Admin management of user accounts, mentor-student assignments and recruiter verification. | name now states the responsibility |
| 33 | `backend/app/routers/jobs/common.py` | `backend/app/routers/jobs/job_shared_helpers.py` | Helpers shared by student and recruiter job endpoints: job matching, eligibility, payloads, emails and message threads. | `common.py` was a generic/ambiguous name |
| 34 | `backend/app/routers/jobs/recruiter.py` | `backend/app/routers/jobs/recruiter_job_routes.py` | Recruiter portal: dashboard, job postings, applicants, AI match, candidate comparison, printable candidate report and candidate search. | name now states the responsibility |
| 35 | `backend/app/routers/jobs/screening.py` | `backend/app/routers/jobs/recruiter_screening_routes.py` | Recruiter bulk tools: AI screening of all applicants, assigning assessments, messaging applicants and CSV export. | name now states the responsibility |
| 36 | `backend/app/routers/jobs/student.py` | `backend/app/routers/jobs/student_job_routes.py` | Student side of placements: browse and apply to jobs, view and withdraw applications, message recruiters. | name now states the responsibility |
| 37 | `backend/app/services/local_llm.py` | `backend/app/services/ai_models/language_model_client.py` | The low-level LLM client every AI feature finally goes through. | name now states the responsibility; moved into the `ai_models/` group folder |
| 38 | `backend/app/services/gemini_llm.py` | `backend/app/services/ai_models/gemini_api_client.py` | Client for the Google Gemini API, used when LOCAL_AI_PROVIDER=gemini. Same contract as the Ollama path, so the rest of the app does not know which... | name now states the responsibility; moved into the `ai_models/` group folder |
| 39 | `backend/app/services/model_router.py` | `backend/app/services/ai_models/ai_task_model_router.py` | Decides which model name handles which AI task (fast tier for chat, strong tier for scoring and reports, default otherwise). | name now states the responsibility; moved into the `ai_models/` group folder |
| 40 | `backend/app/services/ai_base.py` | `backend/app/services/ai_models/ai_structured_call_base.py` | Safe, validated, logged access to the language model. | name now states the responsibility; moved into the `ai_models/` group folder |
| 41 | `backend/app/services/embeddings.py` | `backend/app/services/ai_models/sentence_embedding_model.py` | Loads a small local sentence-embedding model (all-MiniLM-L6-v2, Sentence Transformers) that turns text into vectors for meaning comparison. | name now states the responsibility; moved into the `ai_models/` group folder |
| 42 | `backend/app/services/question_classifier.py` | `backend/app/services/ai_models/question_type_classifier.py` | Runtime part of the project's own machine-learning model: predicts an interview question's type and difficulty with a scikit-learn model trained... | name now states the responsibility; moved into the `ai_models/` group folder |
| 43 | `backend/app/services/ai.py` | `backend/app/services/interview/ai_interview_service.py` | AI question generation, answer evaluation, score calculation and report generation (Stages 4, 6-10). | `ai.py` was a generic/ambiguous name; moved into the `interview/` group folder |
| 44 | `backend/app/services/interview_engine.py` | `backend/app/services/interview/interview_intelligence_rules.py` | Interview logic that does not need the AI: which resume facts a question may use, what the last answer was missing, which topics are covered,... | name now states the responsibility; moved into the `interview/` group folder |
| 45 | `backend/app/services/interviewers.py` | `backend/app/services/interview/interviewer_personalities.py` | Defines the four AI interviewer personalities (Aria, Victor, Marcus, Elena): how each asks questions, follows up, gives hints, changes difficulty,... | name now states the responsibility; moved into the `interview/` group folder |
| 46 | `backend/app/services/report_metrics.py` | `backend/app/services/interview/interview_report_metrics.py` | The calculated (non-AI) parts of the interview report: averages per dimension and observable response indicators. | name now states the responsibility; moved into the `interview/` group folder |
| 47 | `backend/app/services/scoring_bands.py` | `backend/app/services/interview/score_band_labels.py` | Turns a 0-100 score into a band label such as 'Strong (75-89)', because AI scores have a few points of noise. | name now states the responsibility; moved into the `interview/` group folder |
| 48 | `backend/app/services/ai_resume.py` | `backend/app/services/resume_and_jobs/ai_resume_analyzer.py` | Resume analysis and skill identification. | name now states the responsibility; moved into the `resume_and_jobs/` group folder |
| 49 | `backend/app/services/resume_parser.py` | `backend/app/services/resume_and_jobs/resume_text_extractor.py` | Extracts plain text from uploaded PDF and DOCX resumes. | name now states the responsibility; moved into the `resume_and_jobs/` group folder |
| 50 | `backend/app/services/matching.py` | `backend/app/services/resume_and_jobs/semantic_job_matcher.py` | Matching and skill-gap analysis for jobs. | `matching.py` was a generic/ambiguous name; moved into the `resume_and_jobs/` group folder |
| 51 | `backend/app/services/skills.py` | `backend/app/services/resume_and_jobs/skill_name_normalizer.py` | Normalises skill names (e.g. 'js' -> 'javascript') and checks whether a phrase really appears in a text. | `skills.py` was a generic/ambiguous name; moved into the `resume_and_jobs/` group folder |
| 52 | `backend/app/services/ai_tasks.py` | `backend/app/services/resume_and_jobs/ai_career_and_assessment_tasks.py` | Smaller AI tasks: explain a job match, give study recommendations, generate MCQ tests, review code and suggest job roles. | name now states the responsibility; moved into the `resume_and_jobs/` group folder |
| 53 | `backend/app/services/ai_english.py` | `backend/app/services/english/ai_english_conversation.py` | AI logic of English practice with Aria: generates replies with corrections, cleans the reply, avoids repetition, and evaluates a finished... | name now states the responsibility; moved into the `english/` group folder |
| 54 | `backend/app/services/english_companion.py` | `backend/app/services/english/english_companion_memory.py` | Deterministic settings and memory of the English companion: learning modes, topic-switch detection and what is remembered between turns. | name now states the responsibility; moved into the `english/` group folder |
| 55 | `backend/app/services/english_profile.py` | `backend/app/services/english/english_mistake_profile.py` | Finds a student's recurring English mistakes (verb tense, articles, prepositions, ...) from the corrections already given, without extra AI calls. | name now states the responsibility; moved into the `english/` group folder |
| 56 | `backend/app/services/english_vocab.py` | `backend/app/services/english/english_vocabulary_trainer.py` | Personal word list with spaced repetition (Leitner boxes 1-5), a daily English plan and progress numbers. | name now states the responsibility; moved into the `english/` group folder |
| 57 | `backend/app/services/tts.py` | `backend/app/services/voice/text_to_speech.py` | Text-to-speech with the Kokoro-82M model, plus a mouth-shape (viseme) timeline for avatar lip sync. | `tts.py` was a generic/ambiguous name; moved into the `voice/` group folder |
| 58 | `backend/app/services/stt.py` | `backend/app/services/voice/speech_to_text.py` | Speech-to-text with Whisper (faster-whisper by default, Hugging Face transformers as fallback, or Gemini on hosted servers). | `stt.py` was a generic/ambiguous name; moved into the `voice/` group folder |
| 59 | `backend/app/services/speech_stream.py` | `backend/app/services/voice/streamed_reply_sentence_splitter.py` | Turns the model's streamed JSON reply into complete sentences, in order, so speech can start before the whole reply is written. | name now states the responsibility; moved into the `voice/` group folder |
| 60 | `backend/app/services/attention.py` | `backend/app/services/monitoring/visual_attention_report.py` | Stores and reports an estimated 'visual attention toward the screen' percentage measured in the browser. | name now states the responsibility; moved into the `monitoring/` group folder |
| 61 | `backend/app/services/integrity.py` | `backend/app/services/monitoring/interview_integrity_rules.py` | Rules for disclosed interview integrity monitoring: what the candidate is told, which events are allowed, their severity and a neutral risk summary. | name now states the responsibility; moved into the `monitoring/` group folder |
| 62 | `backend/app/services/perf.py` | `backend/app/services/monitoring/performance_timing.py` | Times each step of the interview pipeline (AI call, TTS, turn total) so the slowest part is visible to the admin. | `perf.py` was a generic/ambiguous name; moved into the `monitoring/` group folder |
| 63 | `backend/app/services/access.py` | `backend/app/services/platform_support/student_record_access.py` | Decides who may view a student's detailed records (the student, admins, assigned mentors, recruiters with an application from that student). | `access.py` was a generic/ambiguous name; moved into the `platform_support/` group folder |
| 64 | `backend/app/services/background.py` | `backend/app/services/platform_support/background_jobs.py` | Runs background jobs (feedback, question prefetch, emails) in tracked threads and lets them finish on shutdown. | `background.py` was a generic/ambiguous name; moved into the `platform_support/` group folder |
| 65 | `backend/app/services/common.py` | `backend/app/services/platform_support/audit_and_notification_helpers.py` | Small shared helpers: audit log entries, in-app notifications, pagination, platform settings and skill normalisation. | `common.py` was a generic/ambiguous name; moved into the `platform_support/` group folder |
| 66 | `backend/app/services/consent.py` | `backend/app/services/platform_support/hosted_ai_consent.py` | Asks students to agree once before their data is sent to a hosted AI (Gemini). Not needed with the local model. | name now states the responsibility; moved into the `platform_support/` group folder |
| 67 | `backend/app/services/limiter.py` | `backend/app/services/platform_support/rate_limiter.py` | Sliding-window counters used for login lockout, password-reset limits and voice/monitoring rate limits (memory or Redis). | `limiter.py` was a generic/ambiguous name; moved into the `platform_support/` group folder |
| 68 | `backend/app/services/live_events.py` | `backend/app/services/platform_support/live_notification_events.py` | Delivers 'something changed' signals to open browser tabs over Server-Sent Events. | name now states the responsibility; moved into the `platform_support/` group folder |
| 69 | `backend/app/services/mailer.py` | `backend/app/services/platform_support/email_sender.py` | Sends plain-text emails over SMTP when configured; otherwise logs them. | `mailer.py` was a generic/ambiguous name; moved into the `platform_support/` group folder |
| 70 | `backend/app/services/insights.py` | `backend/app/services/student_progress/student_performance_insights.py` | Skill-gap analysis and dashboard data. | `insights.py` was a generic/ambiguous name; moved into the `student_progress/` group folder |
| 71 | `backend/app/services/rewards.py` | `backend/app/services/student_progress/rewards_and_badges.py` | Points, badges, streaks, challenges and mentor-goal progress, with anti-gaming rules. | `rewards.py` was a generic/ambiguous name; moved into the `student_progress/` group folder |

## Frontend: renamed files

| # | Old filename | New filename | Purpose | Reason for renaming |
|---|---|---|---|---|
| 1 | `frontend/src/api.js` | `frontend/src/apiClient.js` | HTTP client (wrapper around fetch) for all /api calls. | `api.js` was a generic/ambiguous name |
| 2 | `frontend/src/auth.jsx` | `frontend/src/AuthContext.jsx` | React context for authentication (login, logout, current user). | `auth.jsx` was a generic/ambiguous name |
| 3 | `frontend/src/components/ui.jsx` | `frontend/src/components/SharedUiComponents.jsx` | Reusable UI building blocks so all pages look and behave the same. | `ui.jsx` was a generic/ambiguous name |
| 4 | `frontend/src/components/charts.jsx` | `frontend/src/components/DashboardCharts.jsx` | Ready-made chart components (built on Recharts) used by the dashboards, progress pages and reports. | `charts.jsx` was a generic/ambiguous name |
| 5 | `frontend/src/components/Readiness.jsx` | `frontend/src/components/PlacementReadinessCard.jsx` | Shows the student's placement-readiness score: overall score, level and per-area bars. | name now states the responsibility |
| 6 | `frontend/src/components/Tabs.jsx` | `frontend/src/components/UrlTabs.jsx` | Tabs whose selected tab is kept in the page URL (?tab=...), so tabs can be linked and the back button works. | `Tabs.jsx` was a generic/ambiguous name |
| 7 | `frontend/src/components/useSpeech.jsx` | `frontend/src/components/useSpeechAndPreferences.jsx` | Browser speech helpers for the English practice pages: speech-to-text, text-to-speech, subtitles and voice preferences. | name now states the responsibility |
| 8 | `frontend/src/components/codeRunner.js` | `frontend/src/components/browserCodeRunner.js` | Lets a student test their JavaScript coding answer against sample test cases inside the browser. | name now states the responsibility |
| 9 | `frontend/src/components/scoreBand.js` | `frontend/src/components/scoreBandLabel.js` | Turns a 0-100 interview score into a band label such as 'Strong (75-89)'. | name now states the responsibility |
| 10 | `frontend/src/components/scoreBand.test.js` | `frontend/src/components/scoreBandLabel.test.js` | Unit tests for scoreBandLabel.js. | name now states the responsibility |
| 11 | `frontend/src/components/AIConsent.jsx` | `frontend/src/components/HostedAiConsentGate.jsx` | Asks a student to agree to the AI data notice when the server uses the hosted Google Gemini AI. | name now states the responsibility |
| 12 | `frontend/src/components/DailyPlan.jsx` | `frontend/src/components/EnglishDailyPlan.jsx` | Shows 'Today's English plan' - small daily tasks that tick themselves when the student does them. | name now states the responsibility |
| 13 | `frontend/src/components/MistakeProfile.jsx` | `frontend/src/components/EnglishMistakeProfile.jsx` | Shows the student's recurring English mistakes (for example verb tense or articles). | name now states the responsibility |
| 14 | `frontend/src/components/Layout.jsx` | `frontend/src/components/AppShellLayout.jsx` | Application shell (navigation + notifications) for all four portals. | `Layout.jsx` was a generic/ambiguous name |
| 15 | `frontend/src/english/vocab.js` | `frontend/src/english/vocabularyReview.js` | Pure helpers for the English word list, the review session and the daily plan display. | `vocab.js` was a generic/ambiguous name |
| 16 | `frontend/src/english/vocab.test.js` | `frontend/src/english/vocabularyReview.test.js` | Unit tests for vocabularyReview.js. | `vocab.test.js` was a generic/ambiguous name |
| 17 | `frontend/src/monitoring/MonitorBar.jsx` | `frontend/src/monitoring/InterviewMonitorBar.jsx` | Shows the candidate the live status of camera, microphone, face tracking, connection and monitoring, and lets them review events afterwards. | name now states the responsibility |
| 18 | `frontend/src/monitoring/monitoring.test.js` | `frontend/src/monitoring/frameAnalysisAndSignals.test.js` | Unit tests for frameAnalysis.js and signalTracker.js. | name now states the responsibility |
| 19 | `frontend/src/monitoring/guards.test.js` | `frontend/src/monitoring/browserGuards.test.js` | Unit tests for pasteGuard.js, screenGuard.js and objectMonitor.js. | name now states the responsibility |
| 20 | `frontend/src/monitoring/security.test.js` | `frontend/src/monitoring/interviewSecurity.test.js` | Scenario tests for the whole interview security module. | `security.test.js` was a generic/ambiguous name |
| 21 | `frontend/src/pages/Settings.jsx` | `frontend/src/pages/AccountSettings.jsx` | Account settings for every role. | `Settings.jsx` was a generic/ambiguous name |
| 22 | `frontend/src/pages/Profile.jsx` | `frontend/src/pages/ProfileEditor.jsx` | Profile editor for each role. | `Profile.jsx` was a generic/ambiguous name |
| 23 | `frontend/src/pages/admin/Dashboard.jsx` | `frontend/src/pages/admin/AdminDashboard.jsx` | Admin analytics home page. | `Dashboard.jsx` was a generic/ambiguous name |
| 24 | `frontend/src/pages/admin/Assignments.jsx` | `frontend/src/pages/admin/MentorAssignments.jsx` | Assign students to mentors. | `Assignments.jsx` was a generic/ambiguous name |
| 25 | `frontend/src/pages/admin/Jobs.jsx` | `frontend/src/pages/admin/AdminJobPostings.jsx` | Admin view of all job postings from all recruiters. | `Jobs.jsx` was a generic/ambiguous name |
| 26 | `frontend/src/pages/admin/Monitoring.jsx` | `frontend/src/pages/admin/AdminMonitoring.jsx` | Admin monitoring centre in tabs. | `Monitoring.jsx` was a generic/ambiguous name |
| 27 | `frontend/src/pages/admin/Reports.jsx` | `frontend/src/pages/admin/PlacementReports.jsx` | Placement report table with CSV export. | `Reports.jsx` was a generic/ambiguous name |
| 28 | `frontend/src/pages/admin/Rewards.jsx` | `frontend/src/pages/admin/AdminRewardRules.jsx` | Manage badges and reward rules. | `Rewards.jsx` was a generic/ambiguous name |
| 29 | `frontend/src/pages/admin/Settings.jsx` | `frontend/src/pages/admin/PlatformSettings.jsx` | Editor for platform settings (key/value). | `Settings.jsx` was a generic/ambiguous name |
| 30 | `frontend/src/pages/admin/Users.jsx` | `frontend/src/pages/admin/UserManagement.jsx` | User management for admins. | `Users.jsx` was a generic/ambiguous name |
| 31 | `frontend/src/pages/mentor/Dashboard.jsx` | `frontend/src/pages/mentor/MentorDashboard.jsx` | Mentor home page. | `Dashboard.jsx` was a generic/ambiguous name |
| 32 | `frontend/src/pages/mentor/Sessions.jsx` | `frontend/src/pages/mentor/MentorSessions.jsx` | The mentor's follow-up sessions. | `Sessions.jsx` was a generic/ambiguous name |
| 33 | `frontend/src/pages/mentor/StudentDetail.jsx` | `frontend/src/pages/mentor/MentorStudentDetail.jsx` | Everything a mentor needs about one student, in tabs. | name now states the responsibility |
| 34 | `frontend/src/pages/mentor/Students.jsx` | `frontend/src/pages/mentor/MentorStudentList.jsx` | List of the mentor's students with search. | `Students.jsx` was a generic/ambiguous name |
| 35 | `frontend/src/pages/recruiter/Dashboard.jsx` | `frontend/src/pages/recruiter/RecruiterDashboard.jsx` | Recruiter home page. | `Dashboard.jsx` was a generic/ambiguous name |
| 36 | `frontend/src/pages/recruiter/Jobs.jsx` | `frontend/src/pages/recruiter/RecruiterJobPostings.jsx` | Recruiter's job postings: create, edit, publish, close, delete. | `Jobs.jsx` was a generic/ambiguous name |
| 37 | `frontend/src/pages/recruiter/JobDetail.jsx` | `frontend/src/pages/recruiter/RecruiterJobApplicants.jsx` | Applicants for one job, with match scores and status changes. | name now states the responsibility |
| 38 | `frontend/src/pages/recruiter/Candidates.jsx` | `frontend/src/pages/recruiter/CandidateSearch.jsx` | Search students for recruiters. | `Candidates.jsx` was a generic/ambiguous name |
| 39 | `frontend/src/pages/recruiter/compare.test.js` | `frontend/src/pages/recruiter/CompareCandidates.test.js` | Unit tests for the helpers of CompareCandidates.jsx. | name now states the responsibility |
| 40 | `frontend/src/pages/shared/chips.js` | `frontend/src/pages/shared/filterChipStyle.js` | One shared CSS class helper for the filter 'chips' on list pages. | `chips.js` was a generic/ambiguous name |
| 41 | `frontend/src/pages/student/Dashboard.jsx` | `frontend/src/pages/student/StudentDashboard.jsx` | The student's home page. | `Dashboard.jsx` was a generic/ambiguous name |
| 42 | `frontend/src/pages/student/Applications.jsx` | `frontend/src/pages/student/JobApplications.jsx` | The student's job applications. | `Applications.jsx` was a generic/ambiguous name |
| 43 | `frontend/src/pages/student/Assessments.jsx` | `frontend/src/pages/student/StudentAssessments.jsx` | Student assessments: take timed tests and see results. | `Assessments.jsx` was a generic/ambiguous name |
| 44 | `frontend/src/pages/student/Drives.jsx` | `frontend/src/pages/student/PlacementDrives.jsx` | Campus placement drives for students. | `Drives.jsx` was a generic/ambiguous name |
| 45 | `frontend/src/pages/student/English.jsx` | `frontend/src/pages/student/EnglishPracticeHome.jsx` | Home page of English conversation practice. | `English.jsx` was a generic/ambiguous name |
| 46 | `frontend/src/pages/student/Interviews.jsx` | `frontend/src/pages/student/MockInterviewHome.jsx` | Start page and history of mock interviews. | `Interviews.jsx` was a generic/ambiguous name |
| 47 | `frontend/src/pages/student/Jobs.jsx` | `frontend/src/pages/student/StudentJobOpenings.jsx` | Job openings for students. | `Jobs.jsx` was a generic/ambiguous name |
| 48 | `frontend/src/pages/student/Mentoring.jsx` | `frontend/src/pages/student/StudentMentoring.jsx` | The student's view of mentoring. | `Mentoring.jsx` was a generic/ambiguous name |
| 49 | `frontend/src/pages/student/Opportunities.jsx` | `frontend/src/pages/student/JobsAndDrives.jsx` | 'Jobs & drives' area with two URL tabs. | `Opportunities.jsx` was a generic/ambiguous name |
| 50 | `frontend/src/pages/student/Progress.jsx` | `frontend/src/pages/student/ProgressOverview.jsx` | Progress overview with charts and AI recommendations. | `Progress.jsx` was a generic/ambiguous name |
| 51 | `frontend/src/pages/student/Resume.jsx` | `frontend/src/pages/student/ResumeUploadAndAnalysis.jsx` | Resume upload and AI resume analysis page. | `Resume.jsx` was a generic/ambiguous name |
| 52 | `frontend/src/pages/student/Rewards.jsx` | `frontend/src/pages/student/StudentRewards.jsx` | Points, badges, streaks, challenges and leaderboard. | `Rewards.jsx` was a generic/ambiguous name |
| 53 | `frontend/src/pages/student/Vocabulary.jsx` | `frontend/src/pages/student/VocabularyTrainer.jsx` | English word list and spaced-repetition review. | `Vocabulary.jsx` was a generic/ambiguous name |
| 54 | `frontend/src/pages/student/VoiceInterview.jsx` | `frontend/src/pages/student/LiveVoiceInterview.jsx` | The live voice interview room with an animated interviewer (route /student/interviews/:id/live). | name now states the responsibility |
| 55 | `frontend/src/voice/Avatar.jsx` | `frontend/src/voice/SvgAvatar2D.jsx` | A simpler 2D illustrated interviewer ('Aria') drawn in SVG, used when 3D is not available. | `Avatar.jsx` was a generic/ambiguous name |

## New folders created

| Folder | Contains |
|---|---|
| `backend/app/mongodb_data_layer/` | The MongoDB data layer (was `backend/app/odm/`) |
| `backend/app/services/ai_models/` | Language-model clients, model routing, embeddings, the question classifier |
| `backend/app/services/interview/` | AI interview questions and scoring, interview rules, personalities, report metrics, score bands |
| `backend/app/services/resume_and_jobs/` | Resume text extraction and AI analysis, skill normalisation, job matching, smaller AI tasks |
| `backend/app/services/english/` | English companion: AI conversation, memory, mistake profile, vocabulary |
| `backend/app/services/voice/` | Speech-to-text, text-to-speech, streamed sentence splitting |
| `backend/app/services/monitoring/` | Integrity rules, visual attention report, performance timing |
| `backend/app/services/student_progress/` | Performance insights and readiness, rewards and badges |
| `backend/app/services/platform_support/` | Audit/notifications, background jobs, email, consent, rate limiter, live events, record access |
| `documentation/` | The documents of this documentation set |

## How to undo

All changes are on the git branch `restructure-and-document`. `main` is unchanged. A full archive of the project
taken before any change is in the session scratchpad (`hiresense_backup_before_restructure.tgz`).

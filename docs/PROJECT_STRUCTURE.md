# HireSense — Project Structure and Code Flow

This document describes the project **as it is**: which file does what, who calls it, and how the main features
flow through the code. It is a map for reading the code, not a design proposal. Paths are relative to the project
root (`hiresense/`). For setup and running, see `README.md`; for the AI models, see `docs/AI_MODELS_AND_SCORING.md` and `docs/AI_ML_Use.md`.

Last checked against the code: 2026-11-05 (after the stage 6 module split).

---

## 1. The big picture

```
Browser (React, port 5173)                      Server (FastAPI, port 8000)                 AI
──────────────────────────                      ───────────────────────────                 ─────────────────────
pages/*.jsx  ──calls──>  apiClient.js  ──/api/...──>  routers/*.py  ──calls──>  services/*.py  ──>  Gemini (default) / Ollama qwen3:4b (LLM)
   │                    (fetch +                   │ checks login             │                  MiniLM (embeddings)
   │                     cookie)                   │ (authentication_dependencies.py)                │                  Whisper (speech→text)
components/SharedUiComponents.jsx                                  ▼                          ▼                  Kokoro (text→speech)
voice/*, monitoring/*                         database_models.py  <──app/mongodb_data_layer (pymongo)──>  MongoDB
```

- In development, Vite proxies every `/api/...` request to FastAPI (`frontend/vite.config.js`), so the login
  cookie stays on one origin.
- The language model is Google Gemini by default (`LOCAL_AI_PROVIDER=gemini`, needs `GEMINI_API_KEY`) with Ollama as fallback; `LOCAL_AI_PROVIDER=ollama` keeps everything local. Embeddings, Whisper, Kokoro and MediaPipe run locally.
- **Routers** (`backend/app/routers/`) receive HTTP requests, check who is calling and validate input.
  **Services** (`backend/app/services/`) hold the business logic and the AI calls. **Models**
  (`backend/app/database_models.py`) define the MongoDB collections through the small data layer in `backend/app/mongodb_data_layer/`.

---

## 2. Backend files (`backend/`)

### 2.1 Application core (`backend/app/`)

| File | Purpose | Main functions / contents | Depends on | Used by | Feature affected |
|---|---|---|---|---|---|
| `main.py` | Server entry point | Creates the FastAPI `app`, registers all routers, adds security headers, logs unhandled errors to `ErrorLog`, warms up the AI models in a background thread at startup | `config`, `database`, all routers, `local_llm`, `embeddings`, `tts`, `stt` | `uvicorn app.main:app` (`start-backend.bat`) | Everything |
| `application_configuration.py` | Settings from `backend/.env` | `Settings` (pydantic-settings), `get_settings()` | `.env` | Almost every module | DB URL, secret key, AI model names, limits |
| `database_connection.py` | Database connection | MongoDB client, `SessionLocal`, `get_db()` dependency (one session per request), `init_db()` creates indexes and unique constraints at startup | `config`, `odm` | Routers, background threads | All data access |
| `odm/` | MongoDB data layer with a SQLAlchemy-style API | `coltypes`, `expressions`, `statements`, `mapping`, `connection`, `query`, `session` (select/where/join, `Session` with commit/rollback, cascades, `after_commit` hooks); `from app.mongodb_data_layer import …` still works | pymongo | `database_models.py`, `database_connection.py` | All data access |
| `database_models.py` | Collections (~45 classes) | `User`, profiles, `Resume`, `InterviewSession` → `InterviewQuestion` → `InterviewAnswer`, `EnglishSession`/`EnglishMessage`, `Assessment`/`AssessmentResult`, `Job`/`JobApplication`, mentoring, rewards, `Notification`, `AuditLog`, `AIUsageLog`, `PerfMetric`, `IntegrityEvent`, `PlatformSetting`, English vocabulary … | `odm` | Routers, services | All stored data |
| `request_validation_schemas.py` | Request validation | Pydantic models for request bodies (e.g. `InterviewStart`, `AnswerIn`, `TurnIn`, `StudentRegister`), password-strength rule | pydantic | Routers | Input validation / error messages |
| `api_response_serializers.py` | ORM → JSON | `profile_out`, `interview_out`, … — the single place that decides which fields each role may see | models | Routers | API responses |
| `password_and_token_security.py` | Passwords and tokens | `hash_password`/`verify_password` (Argon2), `create_access_token`/`decode_access_token` (JWT), password-reset tokens | `config`, argon2, PyJWT | `authentication_dependencies.py`, `routers/authentication_routes.py` | Login, password reset |
| `authentication_dependencies.py` | Request dependencies | `get_current_user` (reads the cookie, 401/403), `require_student/recruiter/mentor/admin`, `ensure_mentor_access` | `security`, `database`, models | Every protected router endpoint | Authentication and authorisation |
| `seed_initial_data.py` | Initial data | Admin account, badges, reward rules, interview categories, question bank, rubrics and sample assessments. Safe to run repeatedly | models | `start-backend.bat`, CI | First run |

### 2.2 Routers (`backend/app/routers/`) — the HTTP API

All routes are under `/api`. Interactive documentation: `http://127.0.0.1:8000/docs`.

| File | Purpose | Main endpoints | Used by (frontend) |
|---|---|---|---|
| `authentication_routes.py` | Accounts and sessions | `POST /auth/register/student`, `/auth/register/recruiter`, `/auth/login`, `/auth/logout`, `GET /auth/me`, forgot/reset/change password, `DELETE /auth/me` | `AuthContext.jsx`, `Login`, `Register`, `ForgotPassword`, `ResetPassword`, `Settings` |
| `interview_routes.py` + `live_voice_interview_routes.py` | AI mock interviews | `POST /student/interviews` (start), `GET` list/one, `POST …/answer` (text), `POST …/turn` (live voice, streamed; in `live_voice_interview_routes.py`), `POST …/next-question`, `POST …/complete`, `POST …/retry-evaluation`, `DELETE` (abandon), `GET /interviewers` | `Interviews`, `InterviewSession`, `VoiceInterview`, `voice/turnStream.js` |
| `voice_speech_routes.py` | Speech for the avatar | `GET /voice/status`, `POST /voice/speak` (Kokoro audio + mouth shapes), `/voice/speak/stream`, `/voice/warmup`, `POST …/transcribe` (Whisper) for interviews and English | `VoiceInterview`, `EnglishAvatarSession`, `InterviewerPicker` |
| `english_practice_routes.py` | English conversation practice | `POST /student/english` (start), `…/message`, `…/message/stream`, `…/end` (evaluate), `GET` list/one/stats/companion, vocabulary, `daily-plan`, `progress` | `English`, `EnglishSession`, `EnglishAvatarSession` |
| `skill_assessment_routes.py` | Timed MCQ / coding tests | Create/edit/AI-generate (staff), start/submit/results/evaluate (students) | `Assessments`, `AssessmentManager` |
| `student_portal_routes.py` | Student portal data | `/student/dashboard`, `/progress`, `/report`, `/history`, resumes (upload, analyse; `/resumes/{id}/download` for permitted roles), rewards, mentoring, recommendations | Student pages |
| `jobs/` (`common`, `student`, `recruiter`, `screening`) | Jobs and applications | Student job search/apply/withdraw, drives; recruiter jobs, applicants, matching, comparison of 2-4 applicants, printable report (`/recruiter/applications/{id}/report`), status changes, candidates | `student/Jobs`, `Applications`, `Drives`, recruiter pages |
| `mentor_portal_routes.py` | Mentor portal | Dashboard, assigned students, feedback, plans, goals, sessions | Mentor pages |
| `admin/` (`analytics`, `people`, `content`, `operations`) | Admin portal | Users, assignments, question bank/categories/rubrics, badges/rules, settings, flagged activity, AI usage, errors, audit log, reports | Admin pages |
| `interview_monitoring_routes.py` | Interview integrity + performance | Monitoring policy and consent, integrity events, review for staff, `/admin/performance` | `InterviewSetup`, `MonitorBar`, `IntegrityReview`, admin `Monitoring` |
| `profile_and_notification_routes.py` | Shared by all roles | `/profile`, `/notifications`, `/notifications/stream` (Server-Sent Events), `/settings` (user preferences) | `Profile`, `Notifications`, `Layout`, `Settings` |

### 2.3 Services (`backend/app/services/`) — business logic and AI

| File | Purpose | Main functions | Used by | Feature affected |
|---|---|---|---|---|
| `ai_interview_service.py` + `ai_structured_call_base.py`, `ai_resume_analyzer.py`, `ai_english_conversation.py`, `ai_career_and_assessment_tasks.py` | **All language-model features** (prompts + validation); `ai_interview_service.py` holds the interview prompts and re-exports the rest | `_structured_call` (single gateway to the LLM), `ai_status`, `analyze_resume`, `next_interview_question`, `score_answer` (fast), `answer_feedback` (slow, background), `evaluate_answer`, `apply_answer_rules`, `next_difficulty`, `interview_report`, `english_reply`, `english_evaluate`, `match_review`, `generate_assessment`, `evaluate_code`, recommendations | Routers | Resume, interviews, English, matching, assessments |
| `language_model_client.py` + `gemini_api_client.py`, `ai_task_model_router.py` | LLM clients (Ollama; Gemini with backup models and cooldowns; per-task model tiers) | `chat_json` (JSON-schema output, streaming), `runtime_status`, `warmup`, `interactive_hold` (pauses background AI work while a student waits) | `ai_interview_service.py`, `interview_routes.py` | Every AI call |
| `interview_intelligence_rules.py` | Interview logic that does **not** use the LLM | `candidate_context`, `coverage`, `stage`, `answer_signals`, `is_duplicate`, `validate_question`, `fallback_question` | `interview_routes.py`, `ai_interview_service.py` | Question quality, no repeats, fallbacks |
| `interviewer_personalities.py` | The 4 interviewer personalities (Aria, Victor, Marcus, Elena) | `INTERVIEWERS`, `get()`; voice, style, difficulty thresholds | `interview_routes.py`, `ai_interview_service.py` | Interviewer behaviour (not scores) |
| `interview_report_metrics.py` | Deterministic report numbers | `report_metrics(session)` | `interview_routes.py` | Interview report |
| `question_type_classifier.py` | Custom ML model (scikit-learn) | `predict(text)` → question type/difficulty | `interview_routes.py` | Question metadata |
| `sentence_embedding_model.py` | MiniLM sentence embeddings | `embed`, `status`, `warmup` | `ai_interview_service.py`, `semantic_job_matcher.py`, `interview_intelligence_rules.py` | Off-topic check, job matching |
| `semantic_job_matcher.py` | Job ↔ student matching | `candidate_profile`, `job_profile`, `compute_match` (skill checks + embedding similarity, explainable score) | `jobs.py` | Job matching |
| `english_companion_memory.py`, `english_mistake_profile.py`, `english_vocabulary_trainer.py` | English companion config; recurring-mistake profile; vocabulary (Leitner boxes), daily plan and progress | learning modes, topic memory, patterns, reviews | `english_practice_routes.py`, `ai_interview_service.py` | English practice |
| `speech_to_text.py` / `text_to_speech.py` / `streamed_reply_sentence_splitter.py` | Whisper speech-to-text / Kokoro text-to-speech / turning a streamed reply into spoken sentences | `transcribe`, `synthesize`, sentence splitter | `voice_speech_routes.py`, `interview_routes.py` | Voice interview, English avatar |
| `student_performance_insights.py` | Read-only performance views | `student_summary`, `readiness_score`, `practice_history`, `weekly_progress`, `record_progress` | `student_portal_routes.py`, `mentor_portal_routes.py`, `interview_routes.py` | Dashboards, progress, history |
| `rewards_and_badges.py` | Points, badges, goals | `award_points`, `after_activity`, `rule_requirements` | `interview_routes.py`, `english_practice_routes.py`, … | Rewards, mentor goals |
| `interview_integrity_rules.py`, `visual_attention_report.py` | Monitoring policy and severity rules; visual attention percentage | disclosure text, severity, neutral labels, risk summary | `interview_monitoring_routes.py` | Interview monitoring |
| `score_band_labels.py` | Score → band (Needs work … Outstanding) | `band(score)` | interviews, serializers | Reports |
| `hosted_ai_consent.py` | AI data consent when the provider is hosted | `required`, `has`, `check` (428 until the student agrees; `users.ai_data_consent_at`) | AI routers | Privacy |
| `rate_limiter.py` | Login lockout and rate limits | `hit`, `count`, `clear`; Redis when `REDIS_URL` is set, memory otherwise | `authentication_routes.py`, `voice_speech_routes.py`, `interview_monitoring_routes.py` | Security |
| `live_notification_events.py` | In-process fan-out for the notification stream | `publish`, `subscribe` (signalled after commit) | `audit_and_notification_helpers.notify`, `profile_and_notification_routes.py` router | Live notifications |
| `background_jobs.py` | Tracked background threads, drained on shutdown | `spawn`, `drain`, `stopping` | `main.py`, routers | Graceful shutdown |
| `performance_timing.py` | Timing of each pipeline step | `record`, `timer` | `interview_routes.py`, `ai_interview_service.py` | Admin performance tab |
| `audit_and_notification_helpers.py` | Small helpers | `audit`, `notify`, `paginate`, `get_setting` | Most routers | Audit log, notifications, settings |
| `student_record_access.py`, `skill_name_normalizer.py`, `resume_text_extractor.py`, `email_sender.py` | Who may view a student; skill-name normalisation; PDF/DOCX text extraction; optional SMTP email | — | Routers/services | Access control, resume, password-reset email |

### 2.4 Other backend folders

| Path | Purpose |
|---|---|
| `backend/eval/calibrate_scoring.py`, `calibration_set.json` | Score calibration against 16 hand-labelled answers. |
| `backend/requirements-cloud.txt`, `.env.cloud.example`, `Dockerfile` | Slim cloud profile (no torch/Whisper/Kokoro) used by Docker, Render and CI. |
| `backend/ml/` | Training script and data for the question classifier (`train_question_classifier.py`). |
| `backend/eval/` | Evaluation harness for interview quality (`run_eval.py`, `scenarios.json`). |
| `backend/tests/` | Fast automated tests — the AI is replaced by a stub (`conftest.py`). Run: `python -m pytest tests -q`. |
| `backend/tests_integration/` | Tests against the real models (Gemini key and/or Ollama). |
| `backend/tests_e2e/` | Browser tests with Playwright (voice interview, interviewers, English avatar, accounts, security module, consent, CI smoke test). |
| `backend/tests_perf/` | Latency benchmarks of the interview pipeline. |
| `backend/.env` | Local configuration and secrets. **Never commit or overwrite.** Template: `.env.example`. |

---

## 3. Frontend files (`frontend/src/`)

### 3.1 Core

| File | Purpose | Depends on | Used by |
|---|---|---|---|
| `main.jsx` | Entry point: renders `<App>` inside the router, `AuthProvider` and `ToastProvider` | `App`, `auth`, `ui` | `index.html` |
| `App.jsx` | All routes (pages lazy-loaded except sign-in/registration/reset/privacy); `RequireRole` sends users to their own portal; signed-out users see only login/register/reset | every page, `auth`, `Layout` | `main.jsx` |
| `AuthContext.jsx` | Login state (`useAuth`): loads `/auth/me` on start, `login()`, `logout()`, reacts to 401s | `apiClient.js` | `App`, `Layout`, pages |
| `apiClient.js` | `fetch` wrapper: prefixes `/api` (or `VITE_API_URL` via `apiUrl()`), sends the cookie, turns errors into readable `ApiError` messages; `get/post/put/patch/del/download` | — | Every page |
| `index.css`, `tailwind.config.js` | Tailwind setup, shared classes (`card`, `input`, `label`, `th`, `td`), brand colours | — | Everything |

### 3.2 Shared components (`components/`)

| File | Purpose |
|---|---|
| `SharedUiComponents.jsx` | UI kit: `useApi` (load data with loading/error state), toasts, `Button`, `Card`, `Table`, `Modal`, `ConfirmButton`, `Pagination`, `Tabs`, `ErrorBox`, `EmptyState`, `Spinner`, `Field`, `ScoreBar`, `TagInput`, date helpers |
| `AppShellLayout.jsx` | Signed-in shell: sidebar menu per role, header with notification bell and profile link |
| `UrlTabs.jsx` | Tabs stored in the URL (`?tab=`) for merged pages |
| `DashboardCharts.jsx` | Recharts wrappers used by dashboards and reports |
| `PlacementReadinessCard.jsx` | Placement-readiness card |
| `useSpeechAndPreferences.jsx` | Browser speech recognition/synthesis (English text pages) and user voice preferences |
| `ConversationMemory.jsx` | What Aria remembers during English practice |
| `EnglishDailyPlan.jsx`, `EnglishProgress.jsx` | English daily plan card and progress charts |
| `scoreBandLabel.js` | Score band labels (same bands as the backend) |
| `browserCodeRunner.js` | Runs a student's JavaScript in a Web Worker for self-checking (never decides scores) |

### 3.3 Pages (`pages/`)

| Folder | Pages |
|---|---|
| `pages/` | `Login`, `Register`, `ForgotPassword`, `ResetPassword` (inside `AuthShell`), `Profile`, `Settings`, `Notifications`, `Privacy`, `NotFound` |
| `pages/student/` | `Dashboard`, `Resume`, `Interviews` (+ `InterviewerPicker`), `InterviewSession` (text mode + results), `VoiceInterview` (+ `InterviewSetup`, `InterviewerFeedback`), `English`, `EnglishSession` (+ `EnglishAvatarSession`), `Vocabulary`, `Assessments`, `ProgressHub` (= `Progress` + `PerformanceReport` + `PracticeHistory`), `Rewards`, `Opportunities` (= `Jobs` + `Drives`), `Applications`, `Mentoring` |
| `pages/recruiter/` | `Dashboard`, `Jobs`, `JobDetail`, `CompareCandidates`, `CandidateReport`, `Candidates`, `CandidateDetail` |
| `pages/mentor/` | `Dashboard`, `Students`, `StudentDetail`, `Sessions` |
| `pages/admin/` | `Dashboard`, `Users`, `Assignments`, `Jobs`, `InterviewConfig`, `Rewards`, `Monitoring`, `SecuritySettings`, `AuditLogs`, `Reports`, `Settings` |
| `pages/shared/` | `AssessmentManager` (recruiter + admin), `IntegrityReview` (admin + authorised mentors) |

Every page file starts with a short comment saying what it shows and which API endpoints it calls.

### 3.4 Voice interview engine (`voice/`) and monitoring (`monitoring/`)

| File | Purpose |
|---|---|
| `voice/interviewMachine.js` | Pure state machine of the live interview (loading → speaking → listening → recording → transcribing → evaluating → …). Unit-tested. |
| `voice/turnStream.js` | Client for the streamed `POST …/turn` endpoint (Server-Sent Events) |
| `voice/speechPlayer.js`, `speechQueue.js` | Play the interviewer's audio in order and expose the current mouth shape |
| `voice/recorder.js` | Microphone capture for one answer, sent to the server for Whisper transcription |
| `voice/Avatar3D.jsx`, `SvgAvatar2D.jsx` | 3D (three.js) interviewer and the 2D SVG fallback |
| `voice/avatarStates.js`, `faceRig.js`, `motion.js`, `visemes.js` | Expressions, blendshape mapping, idle motion and lip-sync maths |
| `voice/useInterviewers.js`, `englishMachine.js` | Interviewer list from the server; English-practice conversation loop |
| `voice/RoomParts.jsx`, `RoomSidePanels.jsx`, `RoomSettingsPanel.jsx`, `AnswerDock.jsx`, `ControlBar.jsx`, `roomUtils.js` | Display parts of the live interview room, split out of `LiveVoiceInterview.jsx` |
| `live/notificationStream.js` | One shared Server-Sent Events connection per tab for notifications (backoff, polling fallback) |
| `english/vocabularyReview.js` | Vocabulary review session logic |
| `monitoring/*` | Camera session, on-device face/phone detection (MediaPipe), paste and fullscreen guards, event reporting, `MonitorBar` |

---

## 4. Code flows

### 4.1 User authentication — **complete**

1. `pages/Login.jsx` calls `login(email, password)` from `AuthContext.jsx`.
2. `AuthContext.jsx` → `apiClient.js` → `POST /api/auth/login` → `routers/authentication_routes.py::login`.
3. `login` checks the brute-force limiter, loads the `User`, verifies the password (`security.verify_password`),
   rejects pending/suspended accounts, writes an audit entry and sets the **httpOnly cookie** with a JWT
   (`security.create_access_token`).
4. `AuthContext.jsx` then calls `GET /api/auth/me` and stores the user. `App.jsx` sends them to `/student`, `/recruiter`,
   `/mentor` or `/admin`.
5. On every later request the browser sends the cookie. Protected endpoints use `deps.get_current_user` (401 if the
   token is missing/expired) and a role check such as `require_student` (403 for the wrong role).
6. When any request returns 401, `apiClient.js` fires `hs:unauthorized` and `AuthContext.jsx` signs the user out on screen.

Registration is similar (`POST /auth/register/student|recruiter`); recruiters may stay "pending" until an admin
approves them.

### 4.2 Starting an interview — **complete**

1. `pages/student/MockInterviewHome.jsx`: choose an interviewer (`InterviewerPicker`), role, category, text/voice mode,
   number of questions and response mode.
2. `POST /api/student/interviews` → `interview_routes.py::start_interview` checks the limits, creates an
   `InterviewSession` and decides the question source (`ai` if `ai.ai_status()` says available, else
   `question_bank`).
3. Text mode: the first question is created immediately. Voice mode: it is written in the background
   (`_start_prefetch`) while the student goes through `InterviewSetup` (monitoring consent, camera/mic check).
4. The browser opens `/student/interviews/:id` (text) or `/student/interviews/:id/live` (voice).

### 4.3 Generating interview questions — **complete**

`interview_routes.py::_add_next_question` builds the context and tries, in order:

1. **AI question** — `ai.next_interview_question` with the resume summary, skills, previous questions and answers,
   difficulty (`_next_level` → `ai.next_difficulty`), interviewer personality and coverage plan
   (`interview_engine.coverage`). Each result is checked by `interview_engine.is_duplicate` (text, meaning and
   topic) and `validate_question`; rejected questions are retried (2 tries live, 3 in text mode).
2. **Resume template question** — `interview_engine.fallback_question` about something not yet covered.
3. **Admin question bank** — `_bank_question` (prefers the same difficulty and job role).
4. **General role template** — so an interview never gets stuck. Only if all four fail does the API return 503.

### 4.4 Submitting answers — **complete**

- **Text mode:** `InterviewSession.jsx` → `POST …/answer` → `submit_answer`: checks it is the current question
  (`_check_current`), saves it (`_save_answer`, which also runs the paste/copy checks in `_check_suspicious`),
  scores it, adds the next question.
- **Voice mode:** `LiveVoiceInterview.jsx` records with `voice/recorder.js`, transcribes via
  `POST …/transcribe` (Whisper), then sends the text with `voice/turnStream.js` → `POST …/turn`. The server
  answers with a stream of events (`scored`, `sentence`, `audio`, `done`); the next question is spoken sentence by
  sentence while it is still being written. A second submission of the same turn gets 409.

### 4.5 Evaluating answers — **complete** (real-model quality and calibration: see `docs/AI_MODELS_AND_SCORING.md`)

1. **Fast score** (the student waits for this): `interview_routes.py::_evaluate(full=False)` → `ai.score_answer`. The model
   gives 0–10 for relevance, correctness, completeness, clarity, communication; `apply_answer_rules` caps scores
   for off-topic (embedding similarity) or very short answers; the 0–100 score is the weighted average using the
   admin rubric (`_rubric`). Answer status becomes `scored`.
2. **Detailed feedback** (background): `feedback_job` → `_add_feedback` → `ai.answer_feedback` writes strengths,
   missing concepts, improvements and a sample answer. It pauses whenever a student is waiting for the AI.
   Status becomes `completed`.
3. If the AI is unavailable, answers stay unscored and the student can press **Retry evaluation**
   (`POST …/retry-evaluation`).

Scores never depend on which interviewer was chosen.

### 4.6 Displaying results — **complete**

1. Finish → `POST …/complete` → `complete_interview` removes the unanswered last question, then
   `_finalize_scores_and_report` (overall score = average of scored answers; `ai.interview_report` writes the summary;
   `report_metrics` adds deterministic numbers) and `_post_completion` (progress records, points, badges, mentor
   alerts).
2. The frontend shows `InterviewReport` (in `InterviewSession.jsx`); voice interviews first show
   `InterviewerFeedback` (closing remarks spoken by the avatar). Mentors see the same report in
   `mentor/MentorStudentDetail.jsx`.

### 4.7 Interview history — **complete**

- Interview list: `MockInterviewHome.jsx` → `GET /api/student/interviews` (paginated, newest first).
- All practice in one list: `ProgressHub` → `PracticeHistory.jsx` → `GET /api/student/history`
  (`insights.practice_history`).
- Progress and report: `GET /student/progress` and `GET /student/report` (`services/student_progress/student_performance_insights.py`).

### 4.8 Known incomplete or unverified parts

- Voice features have **not been tested with a real human microphone**, only with automated fake-microphone tests.
- Every AI feature has been run against the real models (2026-11-04, `tests_integration/test_real_features.py`); the full behaviour eval (`eval/run_eval.py`) needs a re-run after it ran out of memory.
- Speaking drills ("English Learning") were removed from the student portal; the old route redirects to English
  conversation. The `PracticeExercise` table (and its old data) is kept; `ai.speaking_feedback` was removed
  on 2026-11-04 as dead code.

---

## 5. Where to change what (safely)

| You want to… | Edit | Be careful with |
|---|---|---|
| Change a page's look or text | the page in `frontend/src/pages/` | Keep API calls and button actions as they are |
| Change buttons, cards, tables everywhere | `frontend/src/components/SharedUiComponents.jsx` | Used by every page — run `npm test` and `npm run build` |
| Change a menu item | `NAV` in `frontend/src/components/AppShellLayout.jsx` | The route must exist in `App.jsx` |
| Change interview scoring or prompts | `backend/app/services/interview/ai_interview_service.py` | Affects all scores; run `pytest tests` and the eval harness |
| Add a database field | `database_models.py` (no migration: older documents get the default when read) | Add an index in the model if you query by it |
| Change platform defaults | `seed_initial_data.py` or the admin Settings page | Existing databases keep their stored values |

---

## 6. API route groups

FastAPI generates interactive docs at **http://127.0.0.1:8000/docs** (Swagger) and **/redoc** (203 endpoints).

| Prefix | Who | Purpose |
|---|---|---|
| `/api/auth` | everyone | register (student/recruiter), login, logout, me, change/forgot/reset password, delete account, privacy info, AI data consent |
| `/api/profile`, `/api/notifications` | any signed-in user | profile CRUD, notifications and the live notification stream |
| `/api/student/...` | student | dashboard, resumes, interviews, english (incl. vocabulary, daily plan, progress), assessments, progress, rewards, leaderboard, jobs, applications, mentoring, recommendations |
| `/api/resumes/{id}` | owner / assigned mentor / recruiter with application / admin | view and download a resume |
| `/api/recruiter/...` | recruiter | dashboard, jobs CRUD and publish/close, applications, status updates, AI match, compare, printable report, candidate search and detail |
| `/api/assessments` | admin, recruiter | assessment CRUD, results, AI question drafting |
| `/api/mentor/...` | mentor | dashboard, students, student detail, feedback/notes, plans/goals, sessions, AI recommendations |
| `/api/admin/...` | admin | analytics, users, assignments, jobs, categories, question bank, rubrics, badges, reward rules, flagged review, AI usage, performance, errors, audit logs, settings, security settings, backup, placement report (JSON/CSV) |
| `/api/monitoring/...` | admin, authorised mentors and recruiters | integrity sessions, events and reviews |
| `/api/voice/...` | signed in | TTS status, speak, warm-up |
| `/api/health/live`, `/api/health/ready` | anyone | liveness and readiness (AI parts reported as degraded, never faked) |

## 7. How the portals connect

- **Students** upload a resume and get an AI analysis. They take mock interviews and receive scores and a report. These are stored as progress records, which feed badges and points, update mentor goals, and alert the mentor if a score is low.
- **Mentors** see their assigned students' resume analysis, interviews, English sessions, and assessments. They write feedback and private notes, create improvement plans with goals and deadlines, and schedule sessions. Students are notified, and goals tied to interviews, English, or assessments complete automatically when the student does the work.
- **Recruiters** publish jobs. Eligible students apply and get an instant rule-based match. The recruiter can then run an AI match explanation, compare 2-4 candidates side by side, print a candidate report, and update the status. Every change notifies the student (live, over Server-Sent Events) and is recorded in the status history.
- **Admins** approve recruiters, assign mentors, and configure question banks, rubrics, badges, reward rules, security settings and platform settings. They review flagged activity, which can revoke points, monitor AI usage, speed and errors, and export placement reports. Admin actions are written to the audit log.

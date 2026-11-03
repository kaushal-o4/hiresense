# HireSense — Project Structure and Code Flow

This document describes the project **as it is**: which file does what, who calls it, and how the main features
flow through the code. It is a map for reading the code, not a design proposal. Paths are relative to the project
root (`hiresense/`). For setup and running, see `README.md`; for the AI models, see `docs/AI_ML_Use.md`.

Last checked against the code: 2026-10-22.

---

## 1. The big picture

```
Browser (React, port 5173)                      Server (FastAPI, port 8000)                 Local AI (same laptop)
──────────────────────────                      ───────────────────────────                 ─────────────────────
pages/*.jsx  ──calls──>  api.js  ──/api/...──>  routers/*.py  ──calls──>  services/*.py  ──>  Ollama qwen3:4b (LLM)
   │                    (fetch +                   │ checks login             │                  MiniLM (embeddings)
   │                     cookie)                   │ (deps.py)                │                  Whisper (speech→text)
components/ui.jsx                                  ▼                          ▼                  Kokoro (text→speech)
voice/*, monitoring/*                         models.py  <──SQLAlchemy──>  SQLite file (hiresense.db) or PostgreSQL
```

- In development, Vite proxies every `/api/...` request to FastAPI (`frontend/vite.config.js`), so the login
  cookie stays on one origin.
- All AI runs locally. No API keys or cloud services are used.
- **Routers** (`backend/app/routers/`) receive HTTP requests, check who is calling and validate input.
  **Services** (`backend/app/services/`) hold the business logic and the AI calls. **Models**
  (`backend/app/models.py`) define the database tables.

---

## 2. Backend files (`backend/`)

### 2.1 Application core (`backend/app/`)

| File | Purpose | Main functions / contents | Depends on | Used by | Feature affected |
|---|---|---|---|---|---|
| `main.py` | Server entry point | Creates the FastAPI `app`, registers all routers, adds security headers, logs unhandled errors to `ErrorLog`, warms up the AI models in a background thread at startup | `config`, `database`, all routers, `local_llm`, `embeddings`, `tts`, `stt` | `uvicorn app.main:app` (`start-backend.bat`) | Everything |
| `config.py` | Settings from `backend/.env` | `Settings` (pydantic-settings), `get_settings()` | `.env` | Almost every module | DB URL, secret key, AI model names, limits |
| `database.py` | Database connection | SQLAlchemy `engine`, `SessionLocal`, `get_db()` dependency (one session per request), SQLite WAL mode | `config` | Routers, background threads | All data access |
| `models.py` | Database tables (~45 classes) | `User`, profiles, `Resume`, `InterviewSession` → `InterviewQuestion` → `InterviewAnswer`, `EnglishSession`/`EnglishMessage`, `Assessment`/`AssessmentResult`, `Job`/`JobApplication`, mentoring, rewards, `Notification`, `AuditLog`, `AIUsageLog`, `PerfMetric`, `IntegrityEvent`, `PlatformSetting` … | SQLAlchemy | Routers, services, Alembic | All stored data |
| `schemas.py` | Request validation | Pydantic models for request bodies (e.g. `InterviewStart`, `AnswerIn`, `TurnIn`, `StudentRegister`), password-strength rule | pydantic | Routers | Input validation / error messages |
| `serializers.py` | ORM → JSON | `profile_out`, `interview_out`, … — the single place that decides which fields each role may see | models | Routers | API responses |
| `security.py` | Passwords and tokens | `hash_password`/`verify_password` (Argon2), `create_access_token`/`decode_access_token` (JWT), password-reset tokens | `config`, argon2, PyJWT | `deps.py`, `routers/auth.py` | Login, password reset |
| `deps.py` | Request dependencies | `get_current_user` (reads the cookie, 401/403), `require_student/recruiter/mentor/admin`, `ensure_mentor_access` | `security`, `database`, models | Every protected router endpoint | Authentication and authorisation |
| `seed.py` | Initial data | Admin account, badges, reward rules, interview categories, question bank, rubrics and sample assessments; `--demo` adds clearly-labelled demo users. Safe to run repeatedly | models | `start-backend.bat`, CI | First run |

### 2.2 Routers (`backend/app/routers/`) — the HTTP API

All routes are under `/api`. Interactive documentation: `http://127.0.0.1:8000/docs`.

| File | Purpose | Main endpoints | Used by (frontend) |
|---|---|---|---|
| `auth.py` | Accounts and sessions | `POST /auth/register/student`, `/auth/register/recruiter`, `/auth/login`, `/auth/logout`, `GET /auth/me`, forgot/reset/change password, `DELETE /auth/me` | `auth.jsx`, `Login`, `Register`, `ForgotPassword`, `ResetPassword`, `Settings` |
| `interviews.py` | AI mock interviews | `POST /student/interviews` (start), `GET` list/one, `POST …/answer` (text), `POST …/turn` (live voice, streamed), `POST …/next-question`, `POST …/complete`, `POST …/retry-evaluation`, `DELETE` (abandon), `GET /interviewers` | `Interviews`, `InterviewSession`, `VoiceInterview`, `voice/turnStream.js` |
| `voice.py` | Speech for the avatar | `GET /voice/status`, `POST /voice/speak` (Kokoro audio + mouth shapes), `/voice/speak/stream`, `/voice/warmup`, `POST …/transcribe` (Whisper) for interviews and English | `VoiceInterview`, `EnglishAvatarSession`, `InterviewerPicker` |
| `english.py` | English conversation practice | `POST /student/english` (start), `…/message`, `…/end` (evaluate), `GET` list/one/stats/companion | `English`, `EnglishSession`, `EnglishAvatarSession` |
| `assessments.py` | Timed MCQ / coding tests | Create/edit/AI-generate (staff), start/submit/results/evaluate (students) | `Assessments`, `AssessmentManager` |
| `students.py` | Student portal data | `/student/dashboard`, `/progress`, `/report`, `/history`, resumes (upload, analyse; `/resumes/{id}/download` for permitted roles), rewards, mentoring, recommendations | Student pages |
| `jobs.py` | Jobs and applications | Student job search/apply/withdraw, drives; recruiter jobs, applicants, matching, comparison, status changes, candidates | `student/Jobs`, `Applications`, `Drives`, recruiter pages |
| `mentors.py` | Mentor portal | Dashboard, assigned students, feedback, plans, goals, sessions | Mentor pages |
| `admin.py` | Admin portal | Users, assignments, question bank/categories/rubrics, badges/rules, settings, flagged activity, AI usage, errors, audit log, reports | Admin pages |
| `monitoring.py` | Interview integrity + performance | Monitoring policy and consent, integrity events, review for staff, `/admin/performance` | `InterviewSetup`, `MonitorBar`, `IntegrityReview`, admin `Monitoring` |
| `common.py` | Shared by all roles | `/profile`, `/notifications`, `/settings` (user preferences) | `Profile`, `Notifications`, `Layout`, `Settings` |

### 2.3 Services (`backend/app/services/`) — business logic and AI

| File | Purpose | Main functions | Used by | Feature affected |
|---|---|---|---|---|
| `ai.py` | **All language-model features** (prompts + validation) | `_structured_call` (single gateway to the LLM), `ai_status`, `analyze_resume`, `next_interview_question`, `score_answer` (fast), `answer_feedback` (slow, background), `evaluate_answer`, `apply_answer_rules`, `next_difficulty`, `interview_report`, `english_reply`, `english_evaluate`, `match_review`, `generate_assessment`, `evaluate_code`, recommendations | Routers | Resume, interviews, English, matching, assessments |
| `local_llm.py` | Client for Ollama | `chat_json` (JSON-schema output, streaming), `runtime_status`, `warmup`, `interactive_hold` (pauses background AI work while a student waits) | `ai.py`, `interviews.py` | Every AI call |
| `interview_engine.py` | Interview logic that does **not** use the LLM | `candidate_context`, `coverage`, `stage`, `answer_signals`, `is_duplicate`, `validate_question`, `fallback_question` | `interviews.py`, `ai.py` | Question quality, no repeats, fallbacks |
| `interviewers.py` | The 4 interviewer personalities (Aria, Victor, Marcus, Elena) | `INTERVIEWERS`, `get()`; voice, style, difficulty thresholds | `interviews.py`, `ai.py` | Interviewer behaviour (not scores) |
| `report_metrics.py` | Deterministic report numbers | `report_metrics(session)` | `interviews.py` | Interview report |
| `question_classifier.py` | Custom ML model (scikit-learn) | `predict(text)` → question type/difficulty | `interviews.py` | Question metadata |
| `embeddings.py` | MiniLM sentence embeddings | `embed`, `status`, `warmup` | `ai.py`, `matching.py`, `interview_engine.py` | Off-topic check, job matching |
| `matching.py` | Job ↔ student matching | `candidate_profile`, `job_profile`, `compute_match` (skill checks + embedding similarity, explainable score) | `jobs.py` | Job matching |
| `english_companion.py` | English companion config | learning modes, topic memory | `english.py`, `ai.py` | English practice |
| `stt.py` / `tts.py` / `speech_stream.py` | Whisper speech-to-text / Kokoro text-to-speech / turning a streamed reply into spoken sentences | `transcribe`, `synthesize`, sentence splitter | `voice.py`, `interviews.py` | Voice interview, English avatar |
| `insights.py` | Read-only performance views | `student_summary`, `readiness_score`, `practice_history`, `weekly_progress`, `record_progress` | `students.py`, `mentors.py`, `interviews.py` | Dashboards, progress, history |
| `rewards.py` | Points, badges, goals | `award_points`, `after_activity`, `rule_requirements` | `interviews.py`, `english.py`, … | Rewards, mentor goals |
| `integrity.py` | Monitoring policy and severity rules | disclosure text, severity, neutral labels | `monitoring.py` | Interview monitoring |
| `perf.py` | Timing of each pipeline step | `record`, `timer` | `interviews.py`, `ai.py` | Admin performance tab |
| `common.py` | Small helpers | `audit`, `notify`, `paginate`, `get_setting` | Most routers | Audit log, notifications, settings |
| `access.py`, `skills.py`, `resume_parser.py`, `mailer.py` | Who may view a student; skill-name normalisation; PDF/DOCX text extraction; optional SMTP email | — | Routers/services | Access control, resume, password-reset email |

### 2.4 Other backend folders

| Path | Purpose |
|---|---|
| `backend/alembic/` | Database migrations (`alembic upgrade head`). **Do not edit existing migration files.** |
| `backend/ml/` | Training script and data for the question classifier (`train_question_classifier.py`). |
| `backend/eval/` | Evaluation harness for interview quality (`run_eval.py`, `scenarios.json`). |
| `backend/tests/` | Fast automated tests — the AI is replaced by a stub (`conftest.py`). Run: `python -m pytest tests -q`. |
| `backend/tests_integration/` | Tests against the real local models (need Ollama running). |
| `backend/tests_e2e/` | Browser tests with Playwright (voice interview, interviewers, English avatar, accounts). |
| `backend/tests_perf/` | Latency benchmarks of the interview pipeline. |
| `backend/.env` | Local configuration and secrets. **Never commit or overwrite.** Template: `.env.example`. |

---

## 3. Frontend files (`frontend/src/`)

### 3.1 Core

| File | Purpose | Depends on | Used by |
|---|---|---|---|
| `main.jsx` | Entry point: renders `<App>` inside the router, `AuthProvider` and `ToastProvider` | `App`, `auth`, `ui` | `index.html` |
| `App.jsx` | All routes; `RequireRole` sends users to their own portal; signed-out users see only login/register/reset | every page, `auth`, `Layout` | `main.jsx` |
| `auth.jsx` | Login state (`useAuth`): loads `/auth/me` on start, `login()`, `logout()`, reacts to 401s | `api.js` | `App`, `Layout`, pages |
| `api.js` | `fetch` wrapper: prefixes `/api`, sends the cookie, turns errors into readable `ApiError` messages; `get/post/put/patch/del/download` | — | Every page |
| `index.css`, `tailwind.config.js` | Tailwind setup, shared classes (`card`, `input`, `label`, `th`, `td`), brand colours | — | Everything |

### 3.2 Shared components (`components/`)

| File | Purpose |
|---|---|
| `ui.jsx` | UI kit: `useApi` (load data with loading/error state), toasts, `Button`, `Card`, `Table`, `Modal`, `ConfirmButton`, `Pagination`, `Tabs`, `ErrorBox`, `EmptyState`, `Spinner`, `Field`, `ScoreBar`, `TagInput`, date helpers |
| `Layout.jsx` | Signed-in shell: sidebar menu per role, header with notification bell and profile link |
| `Tabs.jsx` | Tabs stored in the URL (`?tab=`) for merged pages |
| `charts.jsx` | Recharts wrappers used by dashboards and reports |
| `Readiness.jsx` | Placement-readiness card |
| `useSpeech.jsx` | Browser speech recognition/synthesis (English text pages) and user voice preferences |
| `ConversationMemory.jsx` | What Aria remembers during English practice |
| `codeRunner.js` | Runs a student's JavaScript in a Web Worker for self-checking (never decides scores) |

### 3.3 Pages (`pages/`)

| Folder | Pages |
|---|---|
| `pages/` | `Login`, `Register`, `ForgotPassword`, `ResetPassword` (inside `AuthShell`), `Profile`, `Settings`, `Notifications`, `NotFound` |
| `pages/student/` | `Dashboard`, `Resume`, `Interviews` (+ `InterviewerPicker`), `InterviewSession` (text mode + results), `VoiceInterview` (+ `InterviewSetup`, `InterviewerFeedback`), `English`, `EnglishSession` (+ `EnglishAvatarSession`), `Assessments`, `ProgressHub` (= `Progress` + `PerformanceReport` + `PracticeHistory`), `Rewards`, `Opportunities` (= `Jobs` + `Drives`), `Applications`, `Mentoring` |
| `pages/recruiter/` | `Dashboard`, `Jobs`, `JobDetail`, `Candidates`, `CandidateDetail` |
| `pages/mentor/` | `Dashboard`, `Students`, `StudentDetail`, `Sessions` |
| `pages/admin/` | `Dashboard`, `Users`, `Assignments`, `Jobs`, `InterviewConfig`, `Rewards`, `Monitoring`, `AuditLogs`, `Reports`, `Settings` |
| `pages/shared/` | `AssessmentManager` (recruiter + admin), `IntegrityReview` (admin + authorised mentors) |

Every page file starts with a short comment saying what it shows and which API endpoints it calls.

### 3.4 Voice interview engine (`voice/`) and monitoring (`monitoring/`)

| File | Purpose |
|---|---|
| `voice/interviewMachine.js` | Pure state machine of the live interview (loading → speaking → listening → recording → transcribing → evaluating → …). Unit-tested. |
| `voice/turnStream.js` | Client for the streamed `POST …/turn` endpoint (Server-Sent Events) |
| `voice/speechPlayer.js`, `speechQueue.js` | Play the interviewer's audio in order and expose the current mouth shape |
| `voice/recorder.js` | Microphone capture for one answer, sent to the server for Whisper transcription |
| `voice/Avatar3D.jsx`, `Avatar.jsx` | 3D (three.js) interviewer and the 2D SVG fallback |
| `voice/avatarStates.js`, `faceRig.js`, `motion.js`, `visemes.js` | Expressions, blendshape mapping, idle motion and lip-sync maths |
| `voice/useInterviewers.js`, `englishMachine.js` | Interviewer list from the server; English-practice conversation loop |
| `monitoring/*` | Camera session, on-device face/phone detection (MediaPipe), paste and fullscreen guards, event reporting, `MonitorBar` |

---

## 4. Code flows

### 4.1 User authentication — **complete**

1. `pages/Login.jsx` calls `login(email, password)` from `auth.jsx`.
2. `auth.jsx` → `api.js` → `POST /api/auth/login` → `routers/auth.py::login`.
3. `login` checks the brute-force limiter, loads the `User`, verifies the password (`security.verify_password`),
   rejects pending/suspended accounts, writes an audit entry and sets the **httpOnly cookie** with a JWT
   (`security.create_access_token`).
4. `auth.jsx` then calls `GET /api/auth/me` and stores the user. `App.jsx` sends them to `/student`, `/recruiter`,
   `/mentor` or `/admin`.
5. On every later request the browser sends the cookie. Protected endpoints use `deps.get_current_user` (401 if the
   token is missing/expired) and a role check such as `require_student` (403 for the wrong role).
6. When any request returns 401, `api.js` fires `hs:unauthorized` and `auth.jsx` signs the user out on screen.

Registration is similar (`POST /auth/register/student|recruiter`); recruiters may stay "pending" until an admin
approves them.

### 4.2 Starting an interview — **complete**

1. `pages/student/Interviews.jsx`: choose an interviewer (`InterviewerPicker`), role, category, text/voice mode,
   number of questions and response mode.
2. `POST /api/student/interviews` → `interviews.py::start_interview` checks the limits, creates an
   `InterviewSession` and decides the question source (`ai` if `ai.ai_status()` says available, else
   `question_bank`).
3. Text mode: the first question is created immediately. Voice mode: it is written in the background
   (`_start_prefetch`) while the student goes through `InterviewSetup` (monitoring consent, camera/mic check).
4. The browser opens `/student/interviews/:id` (text) or `/student/interviews/:id/live` (voice).

### 4.3 Generating interview questions — **complete**

`interviews.py::_add_next_question` builds the context and tries, in order:

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
- **Voice mode:** `VoiceInterview.jsx` records with `voice/recorder.js`, transcribes via
  `POST …/transcribe` (Whisper), then sends the text with `voice/turnStream.js` → `POST …/turn`. The server
  answers with a stream of events (`scored`, `sentence`, `audio`, `done`); the next question is spoken sentence by
  sentence while it is still being written. A second submission of the same turn gets 409.

### 4.5 Evaluating answers — **complete** (real-model quality: see README §9)

1. **Fast score** (the student waits for this): `interviews.py::_evaluate(full=False)` → `ai.score_answer`. The model
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
   `mentor/StudentDetail.jsx`.

### 4.7 Interview history — **complete**

- Interview list: `Interviews.jsx` → `GET /api/student/interviews` (paginated, newest first).
- All practice in one list: `ProgressHub` → `PracticeHistory.jsx` → `GET /api/student/history`
  (`insights.practice_history`).
- Progress and report: `GET /student/progress` and `GET /student/report` (`services/insights.py`).

### 4.8 Known incomplete or unverified parts

- Voice features have **not been tested with a real human microphone**, only with automated fake-microphone tests.
- Some AI features are not yet verified with the real model (see README §9 "Known limitations").
- Speaking drills ("English Learning") were removed from the student portal; the old route redirects to English
  conversation, and `ai.speaking_feedback` / the `PracticeExercise` table are kept but unused.

---

## 5. Where to change what (safely)

| You want to… | Edit | Be careful with |
|---|---|---|
| Change a page's look or text | the page in `frontend/src/pages/` | Keep API calls and button actions as they are |
| Change buttons, cards, tables everywhere | `frontend/src/components/ui.jsx` | Used by every page — run `npm test` and `npm run build` |
| Change a menu item | `NAV` in `frontend/src/components/Layout.jsx` | The route must exist in `App.jsx` |
| Change interview scoring or prompts | `backend/app/services/ai.py` | Affects all scores; run `pytest tests` and the eval harness |
| Add a database column | `models.py` **plus** a new Alembic migration | Never edit old migrations |
| Change platform defaults | `seed.py` or the admin Settings page | Existing databases keep their stored values |

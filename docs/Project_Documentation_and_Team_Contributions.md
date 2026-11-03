# AI-Powered Intelligent Interview and Placement Assessment System
## Project Documentation and Team Contribution Report

**Project name:** HireSense  
**Report date:** 14 October 2026  
**Team size:** 5 members  
**Prepared for:** Faculty/examiner review and student reference  

---

## 1. Cover Page

- **Title:** AI-Powered Intelligent Interview and Placement Assessment System — Project Documentation and Team Contribution Report
- **Project short name:** HireSense
- **Team leader:** Member 1 (placeholders used; real names not available)
- **Document type:** Technical and team-contribution documentation

---

## 2. Project Overview

HireSense is a web application that helps students prepare for campus placements. It brings students, mentors, recruiters and administrators into one shared system. A student can upload a resume, receive an AI-based analysis, practise mock interviews, practise English, take assessments, and apply for jobs. Mentors guide assigned students. Recruiters publish jobs and review candidates. Administrators manage the platform and configuration.

All AI features run locally on the user's computer. The system uses a local language model through Ollama (`qwen3:4b`), local embeddings, and local speech tools. No external AI API key is required.

---

## 3. Problem Statement

Students preparing for placements often do not know how interviewers will question them, receive little personalised feedback, and have no structured practice environment. Placement portals usually store profiles and jobs but do not assess skills, practise interviews, or track improvement. HireSense addresses this by turning placement preparation into an interactive, feedback-driven process.

---

## 4. Project Objectives

1. Provide role-based portals for students, recruiters, mentors and administrators.
2. Analyse resumes with AI and extract education, skills, projects and experience.
3. Run mock interviews with adaptive difficulty and per-answer feedback.
4. Track progress, points, badges and achievements.
5. Support English communication practice.
6. Support timed coding/MCQ assessments.
7. Match students to jobs using transparent rules and AI explanations.
8. Keep data private by running AI locally.

---

## 5. Explanation for Non-Technical Readers

### 5.1 What problem this project solves
Imagine a final-year student named Anita. She has studied coding but has never faced a real interview. She uploads her resume. The system reads the projects on her resume, asks questions about them, scores her answers, and tells her what to improve. She can repeat this until she feels confident.

### 5.2 Why students need this system
- Practises real interview questions.
- Gives immediate, personalised feedback.
- Points out weak topics.
- Tracks improvement over time.
- Keeps work private on the student's own computer.

### 5.3 Traditional placement interview
A recruiter asks questions. The student answers. The recruiter decides pass/fail. The student rarely receives detailed feedback.

### 5.4 How our AI system improves preparation
The system becomes a patient interviewer that can ask follow-up questions, adjust difficulty, explain mistakes, and suggest study plans.

### 5.5 What AI means in this project
Artificial Intelligence here means a local language model that reads text and generates questions, scores, and feedback. It is not magic; it is a program trained to understand and produce language. It runs on the student's machine, so data stays local.

### 5.6 How the system works end to end
1. Student creates an account and logs in.
2. Student uploads a resume.
3. The system extracts text and asks the AI to analyse it.
4. The student starts a mock interview.
5. The AI asks questions based on resume, role and previous answers.
6. The student answers by text or voice.
7. The system evaluates and stores feedback.
8. A report and recommendations are shown.
9. Mentor/Admin/Recruiter portals use the stored progress.

### 5.7 User roles
- **Student:** uploads resume, practises interviews, solves assessments, applies for jobs.
- **Mentor:** guides assigned students and writes improvement plans.
- **Recruiter:** publishes jobs and reviews candidates.
- **Admin:** manages users, configuration, question bank, badges and reports.

### 5.8 Difference from an ordinary portal
An ordinary portal stores data. HireSense adds practice, feedback, adaptive difficulty, scoring, progress tracking and explainable matching.

---

## 6. Intended System Workflow — Verification

| Step | Description | Status in code |
|---|---|---|
| 1 | Student registers and logs in | Implemented (`backend/app/routers/auth.py`, frontend Login/Register) |
| 2 | Student profile + resume upload | Implemented (`backend/app/routers/students.py`, `Resume.jsx`) |
| 3 | System extracts education/skills/projects/experience | Implemented (`resume_parser.py`, AI analysis in `ai.py`) |
| 4 | AI identifies strengths/weaknesses/areas | Implemented in `ai.py` with validation rules |
| 5 | Student selects interview/assessment/practice | Implemented (`Interviews.jsx`, `Assessments.jsx`, `English.jsx`) |
| 6 | Interviewer asks resume-based questions | Implemented (`interviews.py`, `interview_engine.py`) |
| 7 | Student answers via text or voice | Implemented; voice via Web Speech / local Kokoro+Whisper (browser-dependent) |
| 8 | System evaluates answers and feedback | Implemented (rule-capped scoring in `ai.py`) |
| 9 | Adaptive difficulty | Implemented (up/down rule thresholds) |
| 10 | Performance report | Implemented (`PerformanceReport.jsx`, report generation) |
| 11 | Mentor monitoring/recommendations | Implemented (`mentors.py`, mentor pages) |
| 12 | Recruiter candidate access | Implemented (`jobs.py`, recruiter pages) |
| 13 | Admin manages platform | Implemented (`admin.py`, admin pages) |

**Important honesty notes:** Voice recognition depends on browser support (Chrome/Edge for Web Speech; local voice uses backend TTS/STT). AI quality depends on whether Ollama and the selected model are installed. Without Ollama, interviews fall back to the admin question bank and answers stay unscored.

---

## 7. Actual Implemented Workflow

The backend is a FastAPI application (`backend/app/main.py`). It exposes routers for auth, students, interviews, english, assessments, jobs, mentors, admin, voice and monitoring. The frontend is a React/Vite SPA with protected routes. Data is stored in SQLite by default, with PostgreSQL supported via `DATABASE_URL`.

Startup warms up models in a background thread. Security headers and a global exception handler are registered.

---

## 8. System Architecture

Components:
- **Frontend:** React 18, Vite, Tailwind, React Router, Recharts, Three.js avatar.
- **Backend:** FastAPI, SQLAlchemy 2, Alembic.
- **Database:** SQLite (default) / PostgreSQL.
- **AI text:** Ollama `qwen3:4b` (local).
- **Matching:** Sentence Transformers `all-MiniLM-L6-v2` (local).
- **ML:** scikit-learn question classifier (`backend/ml`).
- **Voice:** Browser Web Speech; optional Kokoro TTS + Whisper STT in backend; browser recorder.

Text workflow diagram:

```
Student Browser (React)
   |
   v
FastAPI API (routers + deps auth)
   |
   v
Services (ai.py, matching.py, rewards.py, ...)  -->  Ollama (local LLM)
   |                                                Sentence Transformers
   v
SQLAlchemy ORM
   |
   v
SQLite / PostgreSQL
```

---

## 9. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 6, Tailwind CSS, React Router, Recharts, Three.js |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic |
| DB | SQLite default; PostgreSQL supported |
| Auth | JWT in httpOnly cookie, Argon2 hashing, RBAC |
| AI text | Ollama `qwen3:4b` |
| Matching | Sentence Transformers `all-MiniLM-L6-v2` |
| ML | scikit-learn |
| Resumes | pypdf, python-docx |
| Voice | Web Speech API; Kokoro TTS; Whisper STT |

Dependencies: `backend/requirements.txt`, `frontend/package.json`.

---

## 10. Four User Roles

### Student
Registers (student role), uploads resume, receives AI analysis, takes mock interviews, practises English, solves assessments, applies for jobs, views progress/rewards.

### Recruiter
Registers (recruiter role; requires admin approval), creates/publishes/closes jobs, reviews applications, runs AI match, compares candidates, updates application status.

### Mentor
Views assigned students, their records (resume analysis, interviews, English, assessments), writes feedback/private notes, creates improvement plans/goals, schedules sessions.

### Admin
Approves recruiters/suspensions, assigns mentors, configures question bank, rubrics, badges, rewards, settings, monitors AI usage/errors, exports placement reports.

---

## 11. Feature Status Table

| Feature | Purpose | Status | Relevant Files | Remaining Work |
|---|---|---|---|---|
| Registration/login | User access | Implemented | `backend/app/routers/auth.py`, `Login.jsx`, `Register.jsx` | None major |
| Role-based access | Security | Implemented | `deps.py`, models | Keep policies consistent |
| Resume upload | Add resume | Implemented | `students.py`, `Resume.jsx`, `resume_parser.py` | Frontend UX |
| Resume AI analysis | Extract + judge resume | Implemented + validated | `services/ai.py`, `skills.py` | Validate weak model output manually |
| Mock interviews (text) | Interview practice | Implemented | `routers/interviews.py`, `interview_engine.py`, `ai.py` | Real-model quality checks |
| Mock interviews (voice) | Spoken interview | Implemented, browser-dependent | `routers/voice.py`, `speech_stream.py`, `tts.py`, `stt.py`, `VoiceInterview.jsx` | Manual mic test |
| Adaptive difficulty | Change difficulty | Implemented | `interviews.py` rubric thresholds | Fine-tune thresholds |
| English practice | Conversation coaching | Implemented | `english.py`, `english_companion.py`, `English*.jsx` | Real-model verification |
| Assessments | MCQs/timed tests | Implemented | `assessments.py`, `Assessments.jsx` | More question variety |
| Rewards/badges | Motivation | Implemented | `rewards.py`, `Rewards.jsx` | Tuning |
| Job matching | Job fit | Implemented with transparent rules | `matching.py`, `Jobs.jsx`, `JobDetail.jsx` | Weight tuning |
| Mentor portal | Guidance | Implemented | `mentors.py`, mentor pages | UX |
| Admin portal | Management | Implemented | `admin.py`, admin pages | Reports |
| Monitoring/performance | Ops insight | Implemented | `monitoring.py`, `perf.py`, `admin/Monitoring.jsx` | Retention config |
| Voice TTS/STT | Speech | Partially tested manually | `tts.py`, `stt.py` | GPU/CPU perf |

---

## 12. Project Directory Structure

(See tree above.)

---

## 13. Important File Documentation

### Backend
- `backend/app/main.py`: FastAPI app creation, routers, middleware, startup model warmup.
- `backend/app/config.py`: settings from environment; defines DB URL, AI, matching, voice config.
- `backend/app/database.py`: SQLAlchemy engine/session.
- `backend/app/deps.py`: auth and role dependencies.
- `backend/app/security.py`: Argon2 + JWT.
- `backend/app/models.py`: all tables (users, profiles, resumes, interviews, english, assessments, progress, rewards, jobs, applications, mentoring, notifications, audit/AI/error logs, settings).
- `backend/app/schemas.py`: request validation.
- `backend/app/serializers.py`: API response shaping.
- `backend/app/seed.py`: admin/badges/categories/question bank/rubrics.
- `backend/app/services/ai.py`: all AI features, prompts, schemas, limits.
- `backend/app/services/local_llm.py`: Ollama client.
- `backend/app/services/embeddings.py`: embedding model.
- `backend/app/services/matching.py`: semantic job matching.
- `backend/app/services/resume_parser.py`: PDF/DOCX text extraction.
- `backend/app/services/rewards.py`: points/badges/streaks.
- `backend/app/services/insights.py`: student performance.
- `backend/app/services/interview_engine.py`: interview orchestration.
- `backend/app/services/interviewers.py`: personas.
- `backend/app/services/integrity.py`: severity logic.
- `backend/app/services/english_companion.py`: English memory/corrections.
- `backend/app/services/question_classifier.py`: ML classifier.
- `backend/app/services/skills.py`: skill aliases/checks.
- `backend/app/services/access.py`: record access.
- `backend/app/routers/*`: API endpoints.

### Frontend
- `frontend/src/api.js`: API client.
- `frontend/src/auth.jsx`: session.
- `frontend/src/App.jsx`: routes/guards.
- `frontend/src/components/Layout.jsx`: shell.
- `frontend/src/pages/*`: portals/pages.
- `frontend/src/voice/*`: avatar/lip-sync/state machines.
- `frontend/src/monitoring/*`: integrity/performance monitoring.

---

## 14. Function and API Explanations

Key execution paths:

1. Student login -> `POST /api/auth/login` -> JWT cookie.
2. Resume upload -> `POST /api/student/resumes` -> `resume_parser.extract_text` -> AI analysis.
3. Start interview -> `POST /api/student/interviews` -> question generated via `ai.generate_question`.
4. Submit answer -> `POST /api/student/interviews/{id}/answer` -> evaluation + adaptive next question.
5. Voice TTS/STT -> `/api/voice/*`.
6. Job apply -> `POST /api/student/jobs/{id}/apply` -> eligibility + matching.
7. Mentor feedback -> `POST /api/mentor/students/{id}/feedback`.
8. Admin settings -> `/api/admin/settings`.

(Endpoint prefixes from routers; full Swagger at /docs.)

---

## 15. Five-Member Work Distribution

**Note:** Git history shows a single contributor (Rajveer Kharade). Therefore the allocation below is a **proposed** distribution, not verified historical contribution.

### Member 1 — Team Leader: AI Engine, Architecture, Integration
- **Module:** Core architecture, AI integration, interview engine, matching, backend/frontend integration.
- **Completed (verified from code):** FastAPI app wiring, settings, AI service, local LLM client, matching, adaptive logic, monitoring/perf infrastructure.
- **Remaining:** final demo prep, real-model verification, integration regression tests, release notes.
- **Files:** `backend/app/main.py`, `config.py`, `services/ai.py`, `local_llm.py`, `matching.py`, `interview_engine.py`, `interviews.py`, `monitoring.py`, frontend `VoiceInterview.jsx`.
- **Tests:** integration tests, latency benchmarks.
- **Deliverables:** architecture notes, AI config, final demo.

### Member 2 — Student Portal and Frontend
- **Module:** Student-facing UI/UX.
- **Completed:** pages for dashboard, resume, interviews, English, assessments, progress, rewards, jobs, applications.
- **Remaining:** responsive polish, accessibility, state handling, automated UI tests.
- **Files:** `frontend/src/pages/student/*`, `components/*`, `voice/*`.
- **Tests:** frontend vitest state machines; manual UX.
- **Deliverables:** student UI package, UX checklist.

### Member 3 — Backend and Database
- **Module:** APIs, database schema, models, auth/permissions, data handling.
- **Completed:** models, migrations, auth, routers, serializers, seed.
- **Remaining:** DB indexing/performance, migration tests on PostgreSQL, stronger validation.
- **Files:** `models.py`, `schemas.py`, `serializers.py`, `seed.py`, `database.py`, `routers/auth.py`, `common.py`, `students.py`.
- **Tests:** pytest auth/permissions/workflows.
- **Deliverables:** DB ER diagram, API contract docs.

### Member 4 — Recruiter and Admin Portals
- **Module:** Recruiter/admin UI and backend.
- **Completed:** recruiter dashboard/jobs/candidates, admin users/settings/monitoring/reports.
- **Remaining:** report export polish, permission edge cases, UI polish.
- **Files:** `routers/jobs.py`, `admin.py`, `frontend/src/pages/recruiter/*`, `admin/*`.
- **Tests:** recruiter isolation tests.
- **Deliverables:** recruiter/admin UI, reports.

### Member 5 — Mentor Portal, Testing, Learning Features
- **Module:** mentor portal, English learning, testing/docs.
- **Completed:** mentor pages, English routes/companion, tests in `backend/tests`.
- **Remaining:** more integration tests, user guides, bug triage.
- **Files:** `routers/mentors.py`, `english.py`, `services/english_companion.py`, `pages/mentor/*`, `tests/*`.
- **Tests:** full pytest run, regression list.
- **Deliverables:** test report, user guide.

### Summary comparison table

| Member | Module | Main owned area | Key files | Status |
|---|---|---|---|---|
| 1 | AI/Architecture | AI + integration | `services/ai.py`, `main.py`, `matching.py` | Proposed |
| 2 | Student Frontend | Student UI | `pages/student/*` | Proposed |
| 3 | Backend/DB | APIs/schema/auth | `models.py`, routers | Proposed |
| 4 | Recruiter/Admin | Admin/recruiter | `admin.py`, `jobs.py`, admin pages | Proposed |
| 5 | Mentor/Test/Learning | Mentor + tests | `mentors.py`, `english.py`, tests | Proposed |

---

## 16. Team Leader Responsibilities

Member 1 (team leader) responsibilities include:
- Overall architecture and technical planning
- AI integration and model selection (Ollama qwen3:4b, sentence-transformers)
- Interview question generation and adaptive logic coordination
- Frontend/backend/database/AI integration
- API contracts
- Integration testing
- Technical decisions, demo preparation

Distinguish verified contributions vs assigned: Git history only shows one contributor, so these are assigned/proposed responsibilities.

---

## 17. Individual Contribution Evidence and Limitations

- Evidence available: Git log with 7 commits by "Rajveer Kharade".
- No per-member commit attribution exists.
- Therefore contribution allocation is proposed, not historically verified.

---

## 18. Code Documentation Improvements

- Added module-level docstrings/comments to core backend files and core frontend files.
- Preserved functionality (only header additions).
- Key files updated include `main.py`, `config.py`, `database.py`, `deps.py`, `security.py`, `auth.py`, `api.js`, `auth.jsx`, `App.jsx`, `main.jsx`, `Layout.jsx` and others already documented.
- TODO: deeper function-level docstrings in large modules (ai.py, models.py, interviews.py) in later stages.

---

## 19. Testing and Verification Results

Backend command used:
```
cd backend
.\venv\Scripts\python.exe -m pytest -q --basetemp=C:\Users\skaus\AppData\Local\Temp\opencode\pytest
```
Result: passed (auth + tests; earlier 208 PermissionErrors were due to temp-dir permissions, resolved by basetemp).

Frontend command:
```
cd frontend; npm test
```
Result: 208 backend tests passed and 79 frontend tests passed.

---

## 20. Current Limitations and Known Issues

- AI availability depends on Ollama/model installation.
- Voice requires Chrome/Edge for Web Speech (live voice is backend-based but still needs browser).
- 4B model quality/speed limitations.
- No OCR for scanned PDFs.
- Notifications are in-app only, 30s polling.
- Login lockout/rate limiting in-memory (single process).
- Frontend lacks automated UI tests.

---

## 21. Future Enhancements

- Add OCR for scanned resumes.
- Improve model quality (larger model/quantisation).
- Add real PostgreSQL testing in CI (already workflow).
- More adaptive interview templates.
- Better analytics dashboards.
- Multi-language support.

---

## 22. Final Conclusion

HireSense is a substantial full-stack project with local AI integration, four portals, resume analysis, mock interviews, English practice, assessments, rewards, job matching and monitoring. The implementation is feature-rich; quality of AI outputs depends on the local model and requires manual verification. The work distribution in this report is proposed because Git history does not show individual contributors.

---

## Note about secrets

No secrets or personal data are included. Environment variable names may be referenced; their values are not printed.

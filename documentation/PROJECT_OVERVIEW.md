# HireSense AI: Project Overview

**HireSense AI: AI-Based Student Interview and Placement Assessment System**

HireSense is a web platform that helps engineering students prepare for campus placements, and helps the
placement cell, recruiters and mentors evaluate students. Students practise mock interviews with an AI
interviewer (typed, or spoken with a 3D talking avatar). They get scores and feedback on every answer, a final
report and a placement-readiness score. Recruiters post jobs and see applicants ranked by a transparent match
score. Mentors follow their assigned students. Admins configure the platform and see analytics.

> HireSense is an **AI-assisted first-level assessment and practice tool**. It does not replace human
> recruiters: every AI score is labelled as an estimate, integrity signals are shown only to human reviewers, and
> hiring decisions stay with people.

## Who uses it

| Role | Main things they do |
|---|---|
| **Student** | Register, fill in a profile, upload a resume (AI analysis), take AI mock interviews (text or live voice), English practice, skill tests, follow their progress, apply to jobs and drives |
| **Recruiter** | Post jobs, see applicants ranked by match score, compare candidates, open a candidate report, change application status, create tests |
| **Mentor** | See assigned students, their weak areas and trends, give feedback, create improvement plans and goals, schedule sessions |
| **Admin** (placement cell) | Manage users and recruiter approval, interview categories / question bank / scoring rubric, placement drives, announcements, analytics, monitoring and logs |

## Technology in one line

- **Frontend:** React 18 with Vite, Tailwind CSS, Recharts and three.js.
- **Backend:** FastAPI (Python 3.14).
- **Database:** MongoDB.
- **AI:**
  - local Ollama `qwen3:4b`, or Google Gemini
  - Sentence Transformers embeddings
  - the project's own scikit-learn classifier
  - Whisper speech-to-text and Kokoro text-to-speech

Details: `TECHNOLOGY_STACK.md`.

## Feature status (checked against the code, 2026-11-14)

"Implemented" means the code exists end to end (page, API and storage) and is covered by the automated tests
(AI mocked). See section "What was tested" for what was run with the real AI model.

| # | Intended feature | Status | Where (main files) |
|---|---|---|---|
| 1 | Student registration and login | **Implemented** (Argon2 passwords, JWT cookie, lockout, password reset) | `routers/authentication_routes.py`, `pages/Register.jsx`, `pages/Login.jsx` |
| 2 | Student profile creation | **Implemented** | `routers/profile_and_notification_routes.py`, `pages/ProfileEditor.jsx` |
| 3 | Resume upload and analysis | **Implemented** (PDF/DOCX, AI extraction checked against the text, completeness score) | `student_portal_routes.upload_resume`, `services/resume_and_jobs/ai_resume_analyzer.py` |
| 4 | Job role / interview category selection | **Implemented** (role, 5 categories, difficulty, question count, 4 interviewer personalities) | `pages/student/MockInterviewHome.jsx`, `interview_routes.start_interview` |
| 5 | AI-generated interview questions | **Implemented** (resume-grounded; question-bank and template fallbacks) | `ai_interview_service.next_interview_question`, `interview_routes._add_next_question` |
| 6 | Interactive interview sessions | **Implemented** (text mode, and live voice mode with a 3D avatar) | `InterviewSession.jsx`, `LiveVoiceInterview.jsx`, `live_voice_interview_routes.py` |
| 7 | Technical and HR questions | **Implemented** (categories technical, hr, behavioral, communication, mixed) | `database_models.INTERVIEW_CATEGORIES`, `seed_initial_data.py` |
| 8 | Adaptive follow-up questions | **Implemented** (difficulty from the last score; follow-ups from answer signals) | `ai.next_difficulty`, `interview_intelligence_rules.answer_signals` |
| 9 | Student answer evaluation | **Implemented** (5 criteria, rule caps, background feedback with sample answer) | `ai.score_answer`, `apply_answer_rules`, `answer_feedback` |
| 10 | Communication and confidence assessment | **Partially implemented.** Communication and clarity are scored for every answer, and the report shows observable indicators (pace, filler words, response time). There is **no separate "confidence" score** in interviews. English practice has a motivational confidence meter that is not a grade. | `ai_interview_service.py`, `interview_report_metrics.py`, `english_practice_routes.confidence_meter` |
| 11 | Coding and problem-solving assessment | **Implemented with a limit.** MCQ tests are graded on the server. Coding answers are **reviewed by the AI against the test cases, not executed** on the server. Students can self-check JavaScript in the browser. | `skill_assessment_routes.py`, `ai_career_and_assessment_tasks.evaluate_code`, `components/browserCodeRunner.js` |
| 12 | Overall interview performance | **Implemented** (average of answer scores; score bands; readiness score) | `interview_routes._finalize_scores_and_report`, `student_performance_insights.readiness_score` |
| 13 | Skill identification and skill-gap analysis | **Implemented** (resume skills, job-match missing skills, weak-area remedies, missing concepts per answer) | `ai_resume_analyzer.py`, `semantic_job_matcher.py`, `student_performance_insights.remedies` |
| 14 | Interview report generation | **Implemented** (AI summary + calculated metrics, retry when the AI was down) | `ai.interview_report`, `interview_report_metrics.py` |
| 15 | Student performance dashboard | **Implemented** | `pages/student/StudentDashboard.jsx`, `ProgressHub.jsx` |
| 16 | Recruiter dashboard | **Implemented** | `pages/recruiter/*`, `routers/jobs/recruiter_job_routes.py` |
| 17 | Placement administrator dashboard | **Implemented** | `pages/admin/*`, `routers/admin/*` |
| 18 | Interview history and performance tracking | **Implemented** (history, weekly progress, attempt-to-attempt comparison) | `student_portal_routes.history/progress`, `student_performance_insights.py` |

Extra features found in the code that were not in the original list:
- the mentor portal
- English communication practice with an AI companion (vocabulary cards, mistake profile, daily plan)
- points, badges and challenges
- placement drives and job applications
- opt-in interview integrity monitoring (on-device camera checks; signals for a human reviewer only)
- live notifications
- an admin performance dashboard

Backend-only features, which have an API but no screen yet (see `API_DOCUMENTATION.md`):
- recruiter bulk AI screening
- applicant CSV export
- recruiter-student application messages
- assigning a test to an applicant
- mentor CSV reports

## What was tested during the restructuring

See the final section of `FILE_RENAMING_MAPPING.md` and the summary below.
- Backend automated tests (`pytest tests`, AI mocked): **369 passed, 2 skipped**, the same as before the restructuring.
- Frontend unit tests (`vitest`): **141 / 141 passed**. Production build (`vite build`): **succeeds**.
- All 203 API endpoints are still registered (checked against FastAPI's OpenAPI schema).
- Real-model integration tests (`pytest tests_integration`, local Ollama `qwen3:4b`, Whisper, Kokoro, embeddings):
  **14 passed**.
- Live end-to-end run against a started server with local Ollama `qwen3:4b` (throwaway database):
  - **12 of 12 steps passed**: health, register, login, `/auth/me`, profile update, resume upload + AI analysis,
    interview start with an AI question, three answers scored with adaptive follow-ups, completion with the AI
    report, dashboard and history
  - the overall score (38.3) was exactly the average of the three answer scores (86.0, 0.0, 28.8)
  - this run had the voice engines switched off: with every model loaded at once, the 16 GB development laptop ran
    out of memory and the server process crashed
- Not tested by hand: the Gemini provider (the API key's quota is used up), and a real person using a real
  microphone or camera.

## How to run

See `README.md`. In short, on Windows:
1. Install Python 3.14, Node.js, MongoDB Community Server and Ollama.
2. Run `ollama pull qwen3:4b`.
3. Double-click `start.bat`.
4. Open http://localhost:5173. The backend API is at http://127.0.0.1:8000/docs.

## Documentation map

| Document | Contents |
|---|---|
| `PROJECT_OVERVIEW.md` | this page |
| `PROJECT_FOLDER_STRUCTURE.md` | folders and where to find things |
| `PROJECT_ARCHITECTURE.md` | architecture diagram, layers, data-flow directions |
| `PROJECT_WORKFLOW.md` | the 11 stages from registration to dashboard, with real files and endpoints |
| `TECHNOLOGY_STACK.md` | every technology, where and why it is used |
| `API_DOCUMENTATION.md` | all 203 endpoints |
| `DATABASE_DOCUMENTATION.md` | MongoDB, 49 collections, fields, keys, ER diagram |
| `FILE_BY_FILE_EXPLANATION.md` | every source file (275) explained |
| `FILE_RENAMING_MAPPING.md` | old name to new name for every renamed file |
| `PROJECT_VIVA_EXPLANATION.md` | presentation script and 40 viva questions with answers |

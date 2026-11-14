# HireSense AI: Project Workflow

This document follows one student from registration to the final dashboard and names the **real** files,
functions, API endpoints and database collections involved at every stage. All paths are relative to the
repository root. Frontend API calls are written without the `/api` prefix the way the code writes them
(`frontend/src/apiClient.js` adds `/api`).

```
Student (browser)                                Backend (FastAPI)                          Storage / AI
-----------------                                -----------------                          ------------
React page  --fetch via apiClient.js-->  router file (app/routers/*)  --> service (app/services/*) --> MongoDB
                                                                                              \--> LLM (Ollama qwen3:4b
                                                                                                    or Gemini)
                                                                                              \--> Whisper / Kokoro
            <------------------------- JSON / Server-Sent Events -----------------------------
```

---

## Stage 1: Student registration and login

**What happens:** The student creates an account (name, email, strong password, college details). The account
is active immediately and the student is signed in. Later visits use the login form. Recruiters register the
same way but may need admin approval. Mentors are created by the admin.

| Item | Real implementation |
|---|---|
| Frontend | `frontend/src/pages/Register.jsx`, `frontend/src/pages/Login.jsx`, `frontend/src/AuthContext.jsx` (keeps the signed-in user), `frontend/src/App.jsx` (`RequireRole` guards) |
| Backend | `backend/app/routers/authentication_routes.py`: `register_student()`, `register_recruiter()`, `login()`, `me()`, `logout()` |
| API | `POST /api/auth/register/student`, `POST /api/auth/register/recruiter`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Database | `users` (email, Argon2 `password_hash`, role, status), `student_profiles`, `recruiter_profiles`, `audit_logs` |
| AI | None |
| Output | An httpOnly cookie `hs_session` that holds a signed JWT (user id + role), plus the user's profile JSON |

```
Register.jsx --POST /auth/register/student--> register_student()
                                               |-- validate StudentRegister (request_validation_schemas.py)
                                               |-- hash_password() (password_and_token_security.py, Argon2)
                                               |-- save User + StudentProfile
                                               '-- create_access_token() -> Set-Cookie hs_session
AuthContext.jsx <--- user JSON --- App.jsx routes the student to /student (StudentDashboard.jsx)
```

Every later request sends the cookie automatically. `get_current_user()` in
`backend/app/authentication_dependencies.py` decodes it, and `require_student` / `require_recruiter` /
`require_mentor` / `require_admin` reject the wrong role with HTTP 403. Eight wrong passwords for one email within 15 minutes
lock login (HTTP 429) (`services/platform_support/rate_limiter.py`).

---

## Stage 2: Resume upload and analysis

**What happens:** The student uploads a PDF or DOCX resume. The text is extracted. The AI pulls out the name,
education, skills, projects, experience and certifications. Every item is then checked against the resume text
so invented skills are removed, and a completeness score (0-100) is calculated.

| Item | Real implementation |
|---|---|
| Frontend | `frontend/src/pages/student/ResumeUploadAndAnalysis.jsx` |
| Backend | `backend/app/routers/student_portal_routes.py`: `upload_resume()`, `_run_analysis()`, `reanalyze()`, `correct_analysis()`, `apply_skills()` |
| Services | `services/resume_and_jobs/resume_text_extractor.py` (`detect_kind`, `extract_text`), `services/resume_and_jobs/ai_resume_analyzer.py` (`analyze_resume`, `validate_resume_extraction`, `resume_completeness`), `services/resume_and_jobs/skill_name_normalizer.py` |
| API | `POST /api/student/resumes` (multipart file), `POST /api/student/resumes/{id}/analyze`, `PATCH /api/student/resumes/{id}/analysis`, `POST /api/student/resumes/{id}/apply-skills` |
| Database | `resumes` (file path, `raw_text`, `analysis`, `analysis_status`), `resume_skills`; the file itself is stored under `backend/uploads/<student id>/` |
| AI | Yes: the language model, feature name `resume_analysis` |
| Output | The analysis JSON (skills, projects, education, completeness score), shown on the resume page |

```
file -> size/type check -> extract_text() -> save file + Resume(status=pending)
     -> analyze_resume(): LLM returns JSON (ResumeExtraction schema)
     -> validate_resume_extraction(): drop items not found in the text
     -> resume_completeness() -> Resume.analysis, status=completed
```

If the AI is unavailable, the resume is still saved with `analysis_status = "unavailable"` and the student can
press *Retry*. No result is faked.

---

## Stage 3: Interview configuration

**What happens:** The student picks an interviewer personality (Aria, Victor, Marcus or Elena), then sets the
job role, category (technical / hr / behavioral / communication / mixed), text or voice mode, number of
questions, difficulty and response mode.

| Item | Real implementation |
|---|---|
| Frontend | `frontend/src/pages/student/MockInterviewHome.jsx`, `frontend/src/pages/student/InterviewerPicker.jsx`, `frontend/src/voice/useInterviewers.js` |
| Backend | `backend/app/routers/interview_routes.py`: `list_interviewers()`, `start_interview()` |
| API | `GET /api/interviewers`, `POST /api/student/interviews` (body `InterviewStart`) |
| Database | Creates an `interview_sessions` document (`job_role`, `category`, `mode`, `difficulty`, `planned_questions`, `interviewer`, `question_source`, `resume_id`) |
| AI | `ai.ai_status()` decides `question_source`: `"ai"` if the model is ready, otherwise `"question_bank"` |
| Output | The new session with its first question (text mode). In voice mode the first question is written in the background (`_start_prefetch()`). |

Limits enforced in `start_interview()`: at most `max_interview_questions` questions (admin setting) and at most 3
interviews in progress per student.

---

## Stage 4: AI question generation

**What happens:** For every question, `_add_next_question()` in `interview_routes.py` builds the context and asks
the model for one question in JSON form.

Inputs collected for the prompt:
- the job role, category, position (e.g. question 3 of 5) and the chosen difficulty
- the resume analysis summary, the student's skills and project names (`current_resume()`)
- `interview_intelligence_rules.candidate_context()`: the only resume facts a question may present as fact
- the interview history (previous questions, answers and scores)
- `answer_signals()`, `coverage()` and `stage()` from `services/interview/interview_intelligence_rules.py`
- the interviewer's personality rules (`services/interview/interviewer_personalities.py`)

Generation and checks:
1. `ai.next_interview_question()` (`services/interview/ai_interview_service.py`) calls the model through
   `_structured_call()` (`services/ai_models/ai_structured_call_base.py`) with the `NextQuestion` JSON schema.
2. The question is rejected and regenerated if `is_duplicate()` or `validate_question()` finds a problem (up to 3
   attempts in text mode, 2 in voice mode).
3. Fallbacks, so an interview never gets stuck:
   - first, a resume-based template question (`fallback_question()`)
   - then the admin question bank (`_bank_question()`, collection `question_bank`)
   - then general role questions
4. The project's own scikit-learn classifier (`services/ai_models/question_type_classifier.py`) predicts the
   question's type and difficulty. The prediction is stored in `InterviewQuestion.meta` as a cross-check only.

**Database:** `interview_questions` (`text`, `question_type`, `difficulty`, `is_followup`, `preface`, `meta`).
**AI:** Yes. Feature `interview_question` on the configured provider: Gemini (as in `.env.example`) or local Ollama `qwen3:4b`, which is also the fallback.

---

## Stage 5: Interview execution

**Text mode**
- Frontend: `frontend/src/pages/student/InterviewSession.jsx`
- The student types an answer, which is sent with `POST /api/student/interviews/{id}/answer` (body `AnswerIn`).
- Backend `submit_answer()` checks that this is the current question, saves the answer through
  `_save_answer()` (which also records word count and timing), and runs `_check_suspicious()`.

**Voice mode (live interview room)**
- Frontend:
  - `frontend/src/pages/student/LiveVoiceInterview.jsx` runs the room
  - `frontend/src/pages/student/InterviewSetup.jsx` handles consent and the device check
  - `frontend/src/voice/*` holds the recorder, avatar, speech player and the state machine (`interviewMachine.js`)
- The microphone recording is transcribed with `POST /api/student/interviews/{id}/transcribe`
  (`backend/app/routers/voice_speech_routes.py`, which uses Whisper in `services/voice/speech_to_text.py`).
- The transcript is sent as one streamed turn with `POST /api/student/interviews/{id}/turn`
  (`backend/app/routers/live_voice_interview_routes.py`).
- The reply arrives as Server-Sent Events:
  1. the answer's score
  2. the next question, sentence by sentence
  3. audio for each sentence with lip-sync data (Kokoro in `services/voice/text_to_speech.py`)
- The avatar (`frontend/src/voice/Avatar3D.jsx`) speaks the question.

**Optional monitoring:**
- Only runs if the student consents in `InterviewSetup.jsx`.
- The camera is analysed in the browser (`frontend/src/monitoring/*`). Only event records are sent:
  - `POST /api/student/interviews/{id}/integrity-events`
  - `PUT /api/student/interviews/{id}/attention`
- These are stored in the `integrity_events` collection and never change scores.

---

## Stage 6: Adaptive interviewing (implemented)

The next question depends on the previous answer in two ways:

1. **Difficulty.**
   - `_next_level()` calls `ai.next_difficulty(previous_level, score, up, down)`.
   - A score of `up` or more (default 75) moves one level up (easy, then medium, then hard).
   - A score below `down` (default 45) moves one level down.
   - Each interviewer personality sets its own `up` / `down` values.
   - A "hard" interview starts with a medium warm-up question.
   - Below 45 the student counts as *struggling*, and one simpler follow-up is allowed.
2. **Content.**
   - `answer_signals()` reads the last answer and spots gaps:
     - vague "we did it" without the student's own role
     - an improvement claim without numbers
     - unexplained AI, very short answers, uncertainty, or a request to repeat the question
   - Each signal comes with a suggested follow-up that goes into the prompt.
   - `coverage()` lists the resume topics already explored and the ones still open.

```
answer -> score_answer() -> score
score  -> next_difficulty() ----------------------> level of next question
answer -> answer_signals() -> follow-up hints ----> prompt of next question
history-> coverage()        -> topics still open -^
```

---

## Stage 7: Answer evaluation

Evaluation is done in two steps so the next question is not delayed.

1. **Fast scoring** (`ai.score_answer()`, called by `_evaluate(full=False)`):
   - The model gives five integer scores from 0 to 10: relevance, correctness, completeness, clarity and
     communication (schema `QuickScore`). The system prompt `EVALUATOR_SYSTEM` tells it to ignore accent,
     grammar (except in communication) and personal characteristics.
   - `apply_answer_rules()` then applies fixed rules:
     - Off-topic answers (meaning similarity below 0.20, or the model says the answer does not address the
       question): relevance and completeness are capped at 2.
     - "I don't know" or empty answers: every criterion is capped at 1.
     - Answers under 8 words: every criterion is capped at 3.
     - Answers under 25 words: completeness is capped at 5.
     - An answer that repeats the question: every criterion is capped at 1.
     - Correctness can be at most relevance + 3.
     - A mostly wrong technical answer (correctness 3 or less) also limits relevance, completeness and clarity.
     - If the model names an important missing point, completeness is capped at 7.
   - The answer gets `evaluation_status = "scored"`.
2. **Detailed feedback** (`ai.answer_feedback()`):
   - Runs in the background through `feedback_job()`.
   - Produces strengths, missing concepts, improvements, a "better answer" tip and a sample answer.
   - The status becomes `"completed"`. If the student is waiting for the next question, this job pauses and
     retries.

**Database:** `interview_answers` (`scores`, `score`, `feedback`, `sample_answer`, `details`, `evaluation_status`)
and `ai_usage_logs`, which store status, latency and token counts but never content.

---

## Stage 8: Performance scoring

Formula, from `weighted_score()` in `services/interview/ai_interview_service.py`:

```
rubric weights (default, interview_routes.DEFAULT_RUBRIC; admins can change them):
    relevance 0.25, correctness 0.30, clarity 0.25, communication 0.20

base  = (sum of criterion x weight / sum of weights) x 10           -> 0-100
if the rubric gives completeness no weight:
score = base x 0.8 + completeness x 10 x 0.2                         (COMPLETENESS_SHARE = 0.20)
```

- **Overall interview score:** `_finalize_scores_and_report()` in `interview_routes.py` takes the average of the
  scored answers, rounded to 1 decimal place. It is saved in `interview_sessions.overall_score`.
- **Score band:** `services/interview/score_band_labels.py` turns a score into a label such as
  "Strong (75-89)". The same table is in `frontend/src/components/scoreBandLabel.js`.
- **Placement readiness:** `readiness_score()` in `services/student_progress/student_performance_insights.py`
  uses these weights:
  - interviews 30%
  - assessments 20%
  - English 20%
  - resume 20%
  - profile 10%

  Missing parts count as 0.

---

## Stage 9: Skill-gap analysis

Implemented in several places, all rule-based except where stated:

- **Per answer:** `missing_concepts` and `improvements` from `answer_feedback()` (AI).
- **Per interview:** `report_metrics()` in `services/interview/interview_report_metrics.py`
  - Technical (content) and communication dimensions are averaged separately, so weak English does not look
    like weak knowledge.
  - It also counts observable indicators: words, response time, speaking pace and filler words.
- **Across all practice:**
  - `student_summary()` and `trend_label()` mark each area as improving, struggling or stable.
  - `remedies()` turns weak areas into suggested goals (`student_performance_insights.py`).
- **For jobs:** `compute_match()` in `services/resume_and_jobs/semantic_job_matcher.py`
  - lists matched, partial and missing required/preferred skills
  - adds meaning similarity from all-MiniLM-L6-v2 sentence embeddings
- **English:** `services/english/english_mistake_profile.py` finds recurring grammar mistakes.

---

## Stage 10: Report generation

`complete_interview()` (`POST /api/student/interviews/{id}/complete`) does the following:
1. Removes the trailing unanswered question and sets the status to `completed`.
2. Runs `_finalize_scores_and_report()`:
   - computes the overall score
   - calls `ai.interview_report()` (schema `InterviewReport`) for the summary, strengths, weaknesses,
     suggestions, recommended practice and closing remarks
   - merges in `report_metrics()`

   If the AI is unavailable, only the computed metrics are stored and `report_status = "unavailable"`. The
   student can use `POST .../retry-evaluation` later.
3. Runs `_post_completion()`:
   - adds progress records (`progress_records`)
   - awards points and badges (`services/student_progress/rewards_and_badges.py`, only for real answers of at
     least 8 words, and never for flagged sessions)
   - updates goals
   - sends mentor alerts (`notifications`) when the score is low, drops, or improves

**Database:** `interview_sessions.report`, `report_status`, `overall_score`, `completed_at`.
**Frontend:** the report view inside `InterviewSession.jsx` (`InterviewReport` component) and
`InterviewerFeedback.jsx` (the interviewer speaks the closing remarks).

---

## Stage 11: Dashboards

| Role | Frontend page | API | Backend |
|---|---|---|---|
| Student | `pages/student/StudentDashboard.jsx`, `ProgressHub.jsx` (`ProgressOverview.jsx`, `PerformanceReport.jsx`, `PracticeHistory.jsx`) | `GET /api/student/dashboard`, `/api/student/progress`, `/api/student/report`, `/api/student/history` | `student_portal_routes.py` + `student_performance_insights.py` |
| Recruiter | `pages/recruiter/RecruiterDashboard.jsx`, `RecruiterJobApplicants.jsx`, `CompareCandidates.jsx`, `CandidateReport.jsx` | `GET /api/recruiter/dashboard`, `/api/recruiter/jobs/{id}/applications`, `POST /api/recruiter/jobs/{id}/compare`, `GET /api/recruiter/applications/{id}/report` | `routers/jobs/recruiter_job_routes.py`, `job_shared_helpers.py` |
| Mentor | `pages/mentor/MentorDashboard.jsx`, `MentorStudentDetail.jsx` | `GET /api/mentor/dashboard`, `/api/mentor/students/{id}` | `routers/mentor_portal_routes.py` |
| Admin | `pages/admin/AdminDashboard.jsx`, `PlacementReports.jsx`, `AdminMonitoring.jsx` | `GET /api/admin/dashboard`, `/api/admin/reports/placements`, `/api/admin/performance` | `routers/admin/admin_analytics_routes.py`, `admin_operations_routes.py` |

Charts are drawn with Recharts (`frontend/src/components/DashboardCharts.jsx`). New notifications reach open pages
instantly through `GET /api/notifications/stream` (Server-Sent Events, `frontend/src/live/notificationStream.js`).

---

## Other implemented workflows (short)

- **Jobs:**
  1. A recruiter posts a job (`POST /api/recruiter/jobs`).
  2. A student browses and applies (`GET /api/student/jobs`, `POST /api/student/jobs/{id}/apply`).
  3. The recruiter sees applicants ranked by match score and changes their status. The student is notified.
- **Assessments:**
  - Students take tests: `POST /api/student/assessments/{id}/start` and `.../results/{id}/submit`.
  - MCQs are graded on the server. Coding answers are reviewed by the AI and the code is not executed.
- **English practice:**
  - Students chat with Aria by text or voice: `POST /api/student/english`, then `.../{id}/message`.
  - Corrections become vocabulary cards, and the session is scored at the end.
- **Mentoring:** mentors create improvement plans and goals that tick automatically from student activity.

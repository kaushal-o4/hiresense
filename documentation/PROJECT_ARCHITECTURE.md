# HireSense AI: Project Architecture

HireSense is a **three-tier web application**:
1. a React single-page app in the browser
2. a FastAPI REST API (Python)
3. MongoDB for data, plus AI models that run next to the API

There are four user portals: **Student, Recruiter, Mentor, Admin**. They all share the same API, and the API
checks the role on every request.

## 1. Architecture diagram

```
┌──────────────────────────────────────────── BROWSER (React 18, Vite) ─────────────────────────────────────────────┐
│                                                                                                                  │
│  Student UI                 Recruiter UI               Mentor UI                Admin UI                         │
│  pages/student/*            pages/recruiter/*          pages/mentor/*           pages/admin/*   pages/shared/*   │
│  StudentDashboard           RecruiterDashboard         MentorDashboard          AdminDashboard                   │
│  ResumeUploadAndAnalysis    RecruiterJobApplicants     MentorStudentDetail      UserManagement                   │
│  MockInterviewHome          CompareCandidates          MentorSessions           InterviewConfig, AdminMonitoring │
│  InterviewSession (text)    CandidateReport                                     PlacementReports                 │
│  LiveVoiceInterview (voice) ─┬─ voice/* (Avatar3D three.js, recorder, speechPlayer, interviewMachine)             │
│  EnglishPracticeHome        └─ monitoring/* (MediaPipe face/object checks, opt-in, on-device)                    │
│                                                                                                                  │
│  App.jsx (routes + RequireRole) ── AuthContext.jsx (who is signed in) ── components/* (shared UI, charts)        │
│                                        │                                                                         │
│                              apiClient.js  (fetch, credentials: include → httpOnly JWT cookie)                   │
│                              voice/turnStream.js, live/notificationStream.js (Server-Sent Events)                │
└────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┘
                                         │  HTTPS / HTTP JSON  /api/*      (dev: Vite proxy :5173 → :8000)
┌────────────────────────────────────────▼──────────────────── BACKEND (FastAPI, uvicorn) ─────────────────────────┐
│  main.py: CORS, security headers + request id middleware, global error handler → error_logs, startup warm-up      │
│                                                                                                                  │
│  ┌───────────── Authentication system ─────────────┐   request_validation_schemas.py (Pydantic input checks)    │
│  │ authentication_routes.py  register/login/reset  │   api_response_serializers.py   (what each role may see)   │
│  │ authentication_dependencies.py get_current_user,│                                                            │
│  │   require_student/recruiter/mentor/admin        │                                                            │
│  │ password_and_token_security.py Argon2 + JWT     │                                                            │
│  └─────────────────────────────────────────────────┘                                                            │
│                                                                                                                  │
│  API ROUTES (routers/)                                                                                           │
│   student_portal_routes ── interview_routes ── live_voice_interview_routes ── voice_speech_routes                │
│   english_practice_routes ── skill_assessment_routes ── jobs/* ── mentor_portal_routes ── admin/*                │
│   interview_monitoring_routes ── profile_and_notification_routes                                                  │
│                         │                                                                                        │
│  SERVICES (services/)   ▼                                                                                        │
│   Interview management ......... interview/ai_interview_service, interview_intelligence_rules,                   │
│                                  interviewer_personalities                                                       │
│   AI question generator ........ ai_interview_service.next_interview_question                                    │
│   AI answer evaluator .......... ai_interview_service.score_answer / answer_feedback                             │
│   Scoring engine ............... apply_answer_rules, weighted_score, next_difficulty, score_band_labels,         │
│                                  student_progress/student_performance_insights.readiness_score                   │
│   Report generator ............. ai_interview_service.interview_report + interview/interview_report_metrics       │
│   Resume analyzer .............. resume_and_jobs/resume_text_extractor, ai_resume_analyzer, skill_name_normalizer │
│   Job matching ................. resume_and_jobs/semantic_job_matcher (+ ai_career_and_assessment_tasks)          │
│   English companion ............ english/*                                                                       │
│   Voice ........................ voice/speech_to_text, text_to_speech, streamed_reply_sentence_splitter          │
│   Monitoring ................... monitoring/interview_integrity_rules, visual_attention_report, performance_timing│
│   Gamification / progress ...... student_progress/rewards_and_badges, student_performance_insights               │
│   Platform ..................... platform_support/* (audit, notify, rate limiter, background jobs, email, SSE)   │
│                         │                                       │                                                │
│   AI gateway: ai_models/ai_structured_call_base._structured_call (limits, JSON schema, validation, usage log)    │
│                         │                                       │                                                │
└─────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────┘
                          ▼                                       ▼
   ┌──────────── DATA ────────────┐     ┌────────────────────────── AI MODELS ──────────────────────────────┐
   │ database_connection.get_db() │     │ language_model_client → Ollama (qwen3:4b, local :11434)           │
   │ mongodb_data_layer (Session, │     │                       or gemini_api_client → Google Gemini API    │
   │   select, relationship)      │     │ sentence_embedding_model (all-MiniLM-L6-v2, CPU)                  │
   │ MongoDB: 49 collections      │     │ question_type_classifier (own scikit-learn model, ml/models/)     │
   │ uploads/ (resume files)      │     │ Whisper (faster-whisper) speech-to-text, Kokoro-82M text-to-speech │
   └──────────────────────────────┘     └───────────────────────────────────────────────────────────────────┘
```

## 2. Layers and their responsibilities

| Layer | Folder | Responsibility | Must not |
|---|---|---|---|
| Presentation | `frontend/src/pages`, `components`, `voice`, `monitoring` | Show data, collect input, record audio, run on-device camera checks | access the database, or decide scores |
| API client | `frontend/src/apiClient.js`, `AuthContext.jsx` | One way to call the API, plus session state | store the token (it is an httpOnly cookie) |
| HTTP / routing | `backend/app/routers/*` | URLs, input validation, role/ownership checks, transactions | contain long AI prompts or scoring maths |
| Security | `authentication_dependencies.py`, `password_and_token_security.py`, `services/platform_support/rate_limiter.py`, `student_record_access.py` | who is calling, what they may access | |
| Business logic | `backend/app/services/*` | interview flow rules, scoring, matching, rewards, insights | know about HTTP requests |
| AI gateway | `services/ai_models/*` | the single path to the language model: limits, schemas, validation, logging | let invalid JSON through |
| Data | `database_models.py`, `mongodb_data_layer/` | schema and persistence | |

## 3. Direction of data flow

**Request path (top to bottom):**
1. A user action happens in a page.
2. `apiClient.js` sends the request.
3. The router runs. Pydantic validates the body and `Depends` checks the cookie and role.
4. The service does the work, and calls the AI gateway when needed.
5. The model returns JSON, which is validated.
6. The service saves to MongoDB through the data layer.

**Response path (bottom to top):**
1. Database objects are converted to JSON by `api_response_serializers.py`.
2. The router returns them.
3. `apiClient.js` parses the JSON.
4. The page updates its React state and re-renders.

**Push path (server to browser, Server-Sent Events):**
- **Live interview turn:**
  1. `POST .../turn` streams events: `scored`, then `sentence` and `audio` (repeated), then `done`.
  2. `voice/turnStream.js` receives them.
  3. `speechPlayer.js` plays the audio and `Avatar3D.jsx` moves the lips.
- **Notifications:**
  1. A router calls `notify()`.
  2. After the commit, `live_notification_events.publish()` sends a signal.
  3. The open stream `GET /api/notifications/stream` passes it on.
  4. `live/notificationStream.js` receives it and the page re-fetches `/api/notifications`.

**Background path:**
- `background_jobs.spawn()` runs the slow AI tasks after the response has been sent, for example detailed
  answer feedback and the first question of a live interview.
- Because of this the student never waits for them. Results appear when the page reloads data.

## 4. Example: one text-interview answer through the architecture

```
InterviewSession.jsx
   │ post(`/student/interviews/${id}/answer`, {question_id, answer, response_seconds})
   ▼
interview_routes.submit_answer()            ← require_student, AnswerIn validation, ownership check
   │ _save_answer() → interview_answers (MongoDB)
   │ _evaluate(full=False) → ai.score_answer()
   │        → _structured_call("answer_scoring") → Ollama/Gemini → QuickScore JSON
   │        → apply_answer_rules() → weighted_score() → next_difficulty()
   │ _add_next_question() → ai.next_interview_question() (+ duplicate/validity checks, fallbacks)
   │ background: feedback_job() → ai.answer_feedback()
   ▼
interview_out(session)  →  JSON  →  InterviewSession.jsx shows the score band and the next question
```

## 5. Cross-cutting design decisions (and why)

- **The AI is a tool, not the judge.**
  - The model only writes text and 0-10 criterion scores.
  - Fixed, testable rules cap the scores, and the 0-100 score and the next difficulty are calculated in code.
  - The job-match score is fully calculated in code; the AI only explains it.
  - Interviewer personalities never change scores.
- **Honest failure.** When the AI is unavailable the app:
  - uses the question bank and labels it
  - stores `evaluation_status="unavailable"` and offers *Retry evaluation*
  - never invents a score
- **Privacy.**
  - Passwords are Argon2 hashes, and the login token is in an httpOnly cookie.
  - Camera analysis runs in the browser and stores event records only.
  - AI logs never contain answer or resume text.
  - Recruiters see a student's detailed records (resume, interviews) only after that student applies to one of
    their jobs. Candidate search only lists students who chose "share with recruiters" in their profile.
- **Local AI available.** Whisper, Kokoro, the embedding model and the classifier always run on the same computer.
  The language model is Gemini (as configured in `.env.example`, with student consent) or local Ollama
  `qwen3:4b`, which is also the automatic fallback when Gemini fails.
- **Swap-able storage.** The project's own data layer keeps the SQL-style code readable while storing data in
  MongoDB.

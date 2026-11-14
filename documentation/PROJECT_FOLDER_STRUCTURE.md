# HireSense AI: Project Folder Structure

The project has two applications in one repository:
- a **React** frontend (`frontend/`)
- a **FastAPI** backend (`backend/`) that stores data in **MongoDB**

The structure below is the real one after the restructuring (2026-11-14). Numbers in brackets are file counts.
Every source file starts with a "comment index" that explains it, and `FILE_BY_FILE_EXPLANATION.md` explains
each file in detail.

```
hiresense/
├── README.md                     how to install and run the project
├── PROJECT_SPEC.md               the original requirements of the project
├── start.bat                     one-click start on Windows: checks prerequisites, opens backend + frontend
├── start-backend.bat             creates the Python venv if needed, seeds the database, starts uvicorn :8000
├── start-frontend.bat            starts the Vite dev server :5173
├── docker-compose.yml            MongoDB + backend + frontend in containers
├── render.yaml                   hosting configuration (Render.com)
├── .github/workflows/tests.yml   CI: backend tests, slim "cloud" profile, frontend tests and build
│
├── documentation/                ← THIS documentation set (overview, workflow, API, database, viva ...)
├── docs/                         older, deeper technical notes (voice, security, performance, deployment)
│
├── backend/                      Python / FastAPI server
│   ├── requirements.txt          full local install (AI models, voice)
│   ├── requirements-cloud.txt    slim install for hosting without local models
│   ├── .env.example              copy to .env and edit (real .env is never committed)
│   ├── Dockerfile, pytest.ini
│   │
│   ├── app/                      [85] the application
│   │   ├── main.py                       entry point: creates the FastAPI app, registers routers
│   │   ├── application_configuration.py  all settings (read from .env)
│   │   ├── database_connection.py        MongoDB connection, get_db() per request
│   │   ├── database_models.py            49 data models = 49 MongoDB collections
│   │   ├── request_validation_schemas.py Pydantic models that validate request bodies
│   │   ├── api_response_serializers.py   database objects -> JSON responses
│   │   ├── authentication_dependencies.py get_current_user, require_student/recruiter/mentor/admin
│   │   ├── password_and_token_security.py Argon2 password hashing, JWT tokens
│   │   ├── seed_initial_data.py          first-run data: admin, categories, rubrics, question bank
│   │   ├── seed_sample_jobs.py           optional demo jobs and drives
│   │   ├── reset_admin_password.py       recovery tool for the admin password
│   │   │
│   │   ├── mongodb_data_layer/   [8]  SQLAlchemy-style API on top of MongoDB (select, Session, relationship)
│   │   │
│   │   ├── routers/              [21] the API endpoints (203 in total)
│   │   │   ├── authentication_routes.py         /api/auth      register, login, logout, password reset
│   │   │   ├── profile_and_notification_routes.py /api/profile, /api/settings, /api/notifications
│   │   │   ├── student_portal_routes.py         /api/student   dashboard, resume upload + analysis, progress
│   │   │   ├── interview_routes.py              /api/student/interviews  start, answer, complete, report
│   │   │   ├── live_voice_interview_routes.py   /api/student/interviews/{id}/turn  streamed voice turns
│   │   │   ├── voice_speech_routes.py           /api/voice + .../transcribe  text-to-speech, speech-to-text
│   │   │   ├── english_practice_routes.py       /api/student/english  English practice with Aria
│   │   │   ├── skill_assessment_routes.py       /api/student/assessments, /api/assessments  tests
│   │   │   ├── mentor_portal_routes.py          /api/mentor
│   │   │   ├── interview_monitoring_routes.py   opt-in integrity monitoring, security settings, perf
│   │   │   ├── jobs/   job_shared_helpers, student_job_routes, recruiter_job_routes, recruiter_screening_routes
│   │   │   └── admin/  admin_analytics_routes, admin_user_management_routes, admin_content_routes,
│   │   │               admin_operations_routes
│   │   │
│   │   └── services/             [44] business logic, grouped by area
│   │       ├── ai_models/        language_model_client (Ollama/Gemini), gemini_api_client,
│   │       │                     ai_structured_call_base (validated JSON calls), ai_task_model_router,
│   │       │                     sentence_embedding_model, question_type_classifier
│   │       ├── interview/        ai_interview_service (questions, scoring, feedback, report),
│   │       │                     interview_intelligence_rules, interviewer_personalities,
│   │       │                     interview_report_metrics, score_band_labels
│   │       ├── resume_and_jobs/  resume_text_extractor, ai_resume_analyzer, skill_name_normalizer,
│   │       │                     semantic_job_matcher, ai_career_and_assessment_tasks
│   │       ├── english/          ai_english_conversation, english_companion_memory,
│   │       │                     english_mistake_profile, english_vocabulary_trainer
│   │       ├── voice/            speech_to_text (Whisper), text_to_speech (Kokoro),
│   │       │                     streamed_reply_sentence_splitter
│   │       ├── monitoring/       interview_integrity_rules, visual_attention_report, performance_timing
│   │       ├── student_progress/ student_performance_insights (readiness, trends), rewards_and_badges
│   │       └── platform_support/ audit_and_notification_helpers, background_jobs, email_sender,
│   │                             hosted_ai_consent, rate_limiter, live_notification_events,
│   │                             student_record_access
│   │
│   ├── ml/                       our own ML model: train_question_classifier.py, data/, models/
│   ├── eval/                     scripts that measure the real AI model's scoring/behaviour
│   ├── tests/                    [27] automated pytest tests (AI mocked) - run in CI
│   ├── tests_integration/        tests with the REAL local AI models
│   ├── tests_e2e/                real-browser tests (Playwright)
│   └── tests_perf/               latency benchmarks
│
└── frontend/                     React (Vite) single-page application
    ├── index.html                the HTML page; loads src/main.jsx
    ├── package.json              npm dependencies and scripts (dev, build, test)
    ├── vite.config.js            dev server :5173, /api proxy to the backend, bundle splitting
    ├── tailwind.config.js, postcss.config.js   styling setup
    ├── public/                   static files: 3D avatar models (.glb), MediaPipe models
    ├── avatar-src/               scripts used once to convert/compress the avatar models
    └── src/                      [128]
        ├── main.jsx              React entry: renders <App/> inside AuthProvider and ToastProvider
        ├── App.jsx               all page routes + RequireRole guard per role
        ├── apiClient.js          fetch wrapper used for every /api call (sends the login cookie)
        ├── AuthContext.jsx       who is signed in (GET /auth/me), login(), logout()
        ├── index.css             theme colours (CSS variables) and global styles
        ├── components/           shared UI: SharedUiComponents (buttons, cards, tables, useApi),
        │                         AppShellLayout (sidebar + header), DashboardCharts, PlacementReadinessCard,
        │                         HostedAiConsentGate, EnglishDailyPlan, scoreBandLabel, ...
        ├── pages/
        │   ├── Login, Register, ForgotPassword, ResetPassword, AuthShell, ProfileEditor,
        │   │   AccountSettings, Notifications, Privacy, NotFound
        │   ├── student/          StudentDashboard, ResumeUploadAndAnalysis, MockInterviewHome,
        │   │                     InterviewerPicker, InterviewSession, InterviewSetup, LiveVoiceInterview,
        │   │                     EnglishPracticeHome, EnglishSession, VocabularyTrainer, StudentAssessments,
        │   │                     JobsAndDrives, StudentJobOpenings, JobApplications, ProgressHub, ...
        │   ├── recruiter/        RecruiterDashboard, RecruiterJobPostings, RecruiterJobApplicants,
        │   │                     CandidateSearch, CandidateDetail, CompareCandidates, CandidateReport
        │   ├── mentor/           MentorDashboard, MentorStudentList, MentorStudentDetail, MentorSessions
        │   ├── admin/            AdminDashboard, UserManagement, MentorAssignments, AdminJobPostings,
        │   │                     InterviewConfig, AdminRewardRules, AdminMonitoring, SecuritySettings,
        │   │                     AuditLogs, PlacementReports, PlatformSettings
        │   └── shared/           AssessmentManager, IntegrityReview, filterChipStyle
        ├── voice/                live interview room: 3D avatar, speech player, recorder, state machines
        ├── monitoring/           on-device camera/microphone/browser checks for opt-in proctoring
        ├── english/              vocabulary review helpers
        └── live/                 live notification stream (Server-Sent Events)
```

## How the folders depend on each other

```
frontend/src/pages/*  ->  frontend/src/apiClient.js  --HTTP /api-->  backend/app/routers/*
backend/app/routers/* ->  backend/app/services/*      ->  backend/app/database_models.py -> mongodb_data_layer -> MongoDB
                                                      ->  services/ai_models/* -> Ollama / Gemini / embeddings / classifier
                                                      ->  services/voice/*     -> Whisper / Kokoro
```

Rules the code follows:
- Pages never talk to the database. They call the API.
- Routers handle HTTP (input validation, access checks) and call services.
- Services hold the logic and never import routers.
- A few routers reuse helpers from another router: `live_voice_interview_routes.py` uses `interview_routes.py`,
  `recruiter_job_routes.py` uses `interview_monitoring_routes.integrity_overview()`, and
  `recruiter_screening_routes.py` uses `recruiter_job_routes.py`.

## Where to find things quickly

| I want to understand... | Open |
|---|---|
| how the server starts | `backend/app/main.py` |
| login / registration | `backend/app/routers/authentication_routes.py`, `frontend/src/AuthContext.jsx` |
| how questions are generated | `backend/app/routers/interview_routes.py` (`_add_next_question`), `backend/app/services/interview/ai_interview_service.py` (`next_interview_question`) |
| how answers are scored | `ai_interview_service.py`: `score_answer`, `apply_answer_rules`, `weighted_score` |
| resume analysis | `backend/app/services/resume_and_jobs/ai_resume_analyzer.py` |
| job match score | `backend/app/services/resume_and_jobs/semantic_job_matcher.py` |
| the database tables | `backend/app/database_models.py`, `documentation/DATABASE_DOCUMENTATION.md` |
| all page URLs | `frontend/src/App.jsx` |
| all API URLs | `documentation/API_DOCUMENTATION.md` or http://127.0.0.1:8000/docs |

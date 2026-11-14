# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# docs/team_report/content.py
#
# FILE PURPOSE:
# Content of the HireSense team work-distribution report (facts taken from the repository and its
# docs).
#
# IMPORTANT VARIABLES / SETTINGS:
#    PROJECT, SUBTITLE, DATE, TEAM, DESCRIPTION, TECH_TABLE, MEMBERS, TIMELINE, COLLABORATION,
#    SIMPLE_ARCH_TEXT, STUDENT_FLOW, STUDENT_FLOW_TEXT, RECRUITER_FLOW, ADMIN_FLOW,
#    OTHER_FLOW_TEXT, ARCHITECTURE, CONCLUSION
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Content of the HireSense team work-distribution report (facts taken from the repository and its docs)."""

PROJECT = "HireSense"
SUBTITLE = "AI-Powered Intelligent Interview and Placement Assessment System"
DATE = "5 November 2026"

TEAM = ["Yash", "Kaushal", "Samrath", "Aryan", "Shardha"]

DESCRIPTION = {
    "Introduction": [
        "HireSense is a full-stack web platform that prepares engineering students for campus placements and helps "
        "the placement cell, recruiters and mentors run the whole placement process in one place. Students practise "
        "mock interviews with a speaking 3D interviewer, get their resume analysed, practise spoken English, take "
        "timed assessments and apply to jobs. Recruiters screen and compare candidates with explainable scores, "
        "mentors follow the progress of their assigned students, and administrators manage users, content and the "
        "placement drive.",
        "The system has four portals (Student, Recruiter, Mentor and Admin) served by a single FastAPI backend and a "
        "MongoDB database. The language model is Google Gemini by default, with a local Ollama model (qwen3:4b) as an "
        "automatic fallback, so the platform keeps working when the cloud model is busy or offline. Speech "
        "recognition, the interviewer's voice and camera monitoring run locally.",
    ],
    "Objective": [
        "Give every student unlimited, realistic interview practice with immediate, fair and explainable feedback.",
        "Measure placement readiness from real activity: interviews, resume quality, English, assessments.",
        "Help recruiters shortlist faster with transparent job matching and side-by-side comparison.",
        "Let mentors and the placement cell spot struggling students early and act on data.",
        "Keep candidate data private: disclosed monitoring, explicit AI-data consent and role-based access.",
    ],
    "Problem Statement": [
        "Students usually get one or two mock interviews before placements, often without useful feedback. Spoken "
        "English and confidence are rarely practised. Placement cells track students in spreadsheets, recruiters "
        "screen hundreds of resumes by hand, and mentors have no single view of a student's progress. Existing "
        "online interview tools are generic, are not connected to the college's own jobs and drives, and give scores "
        "that cannot be explained.",
    ],
    "Proposed Solution": [
        "A single platform in which every activity feeds a shared student profile. An AI interviewer asks questions "
        "built from the student's own resume, adapts the difficulty, and scores each answer on a calibrated rubric "
        "(relevance, correctness, completeness, clarity, communication) with score bands such as \"Strong 75-89\". "
        "Four interviewer personalities (Aria, Victor, Marcus, Elena) speak through a 3D avatar with live captions. "
        "An English companion corrects mistakes and turns them into spaced-repetition vocabulary. Job matching "
        "combines required and preferred skills, meaning similarity and experience, and always shows why a candidate "
        "matched. Every model call goes through one gateway that validates the output and logs usage, and when AI is "
        "unavailable the system says so instead of inventing results.",
    ],
    "Expected Outcomes": [
        "Students: more practice, specific feedback per answer, a visible readiness score and a daily plan.",
        "Recruiters: shortlists backed by explainable match scores, interview reports and a printable candidate report.",
        "Mentors and admins: dashboards, alerts for struggling students, audit logs and CSV placement reports.",
        "Measured so far: score-to-quality rank correlation 0.80 → 0.95 after calibration, answer scoring about "
        "1.1 s on Gemini, resume analysis 56 s → 5.3 s, first page load 1,130 kB → 236 kB of JavaScript.",
    ],
    "Scope of the Project": [
        "In scope: the four portals, AI resume analysis, typed and live voice mock interviews, English practice, "
        "assessments, jobs and placement drives, applications, mentoring, rewards and badges, notifications, "
        "on-device interview monitoring, analytics and deployment configuration (Docker, Render, Vercel).",
        "Out of scope (current limits): OCR for scanned PDFs, languages other than English for voice, face "
        "recognition (deliberately not built), and production load testing. Voice and camera features have so far "
        "been tested with simulated devices only.",
    ],
}

TECH_TABLE = [
    ("Frontend", "React 18, Vite 6, Tailwind CSS, React Router, Recharts, three.js, MediaPipe Tasks Vision, Vitest"),
    ("Backend", "Python 3.14, FastAPI, Pydantic, pydantic-settings, a MongoDB data layer with a SQLAlchemy-style API"),
    ("Database", "MongoDB (local service, Docker or MongoDB Atlas)"),
    ("Language models", "Google Gemini 3.5 Flash / Flash-Lite with automatic switching; Ollama qwen3:4b (local)"),
    ("Speech", "faster-whisper base.en (speech-to-text), Kokoro-82M (text-to-speech), browser speech as fallback"),
    ("Machine learning", "Sentence Transformers all-MiniLM-L6-v2, scikit-learn question-type classifier"),
    ("Security", "JWT in an httpOnly cookie, Argon2 passwords, role guards, Redis-or-memory rate limiting"),
    ("Testing", "pytest (369 backend tests), Vitest (141 frontend tests), Playwright browser end-to-end tests"),
    ("DevOps", "Git and GitHub, GitHub Actions CI, Docker, docker compose, Render blueprint, Vercel config"),
]

MEMBERS = [
    {
        "name": "Yash",
        "pct": 30,
        "role": "Project Lead, System Architect, AI Engine, Testing and Documentation",
        "summary": "Yash designed the overall architecture, built the AI engine that every feature depends on, owned "
                   "integration, the GitHub repository and deployment, and led testing, continuous integration and "
                   "documentation.",
        "responsibilities": [
            "Defined the overall architecture: four portals, one FastAPI backend, one MongoDB database, one AI gateway.",
            "Set up the FastAPI application, router registration, security headers, request IDs and the global error handler (app/main.py).",
            "Built the central configuration with pydantic-settings, so every option lives in backend/.env (app/application_configuration.py).",
            "Built the AI gateway (services/ai_models/ai_structured_call_base.py): daily limits, JSON-schema validation with one retry, usage logging without storing personal text.",
            "Integrated Google Gemini (services/ai_models/gemini_api_client.py) with automatic switching to backup models on HTTP 429/503 or a slow first token.",
            "Integrated the local Ollama model as a fallback (services/ai_models/language_model_client.py) and per-task model tiers (services/ai_models/ai_task_model_router.py).",
            "Wrote the interview engine (services/interview/interview_intelligence_rules.py): resume-based questions, adaptive difficulty, repeat detection by meaning, follow-ups for vague answers.",
            "Designed the scoring rubric and caps, and calibrated it on 16 hand-labelled answers (backend/eval/calibrate_scoring.py).",
            "Added score bands shown to students, such as \"Strong 75-89\" (services/interview/score_band_labels.py).",
            "Built AI resume analysis (services/resume_and_jobs/ai_resume_analyzer.py, resume_text_extractor.py) with a check that removes anything not found in the resume text.",
            "Built explainable job matching with sentence embeddings and skill weights (services/resume_and_jobs/semantic_job_matcher.py, sentence_embedding_model.py).",
            "Added a validator that rejects AI replies which copy the prompt's instructions instead of answering.",
            "Led the backend test suite with pytest: 369 tests on a separate MongoDB test database (backend/tests/).",
            "Wrote Playwright browser tests, including the CI smoke test that opens 15 pages (tests_e2e/ci_smoke_browser.py).",
            "Created the GitHub repository, branch workflow and GitHub Actions pipeline (.github/workflows/tests.yml).",
            "Prepared deployment: slim cloud requirements, Dockerfiles, docker-compose.yml, render.yaml and frontend/vercel.json.",
            "Kept the regression list, verified fixes before each merge and ran the final end-to-end demo.",
            "Wrote the project documentation (README.md, docs/AI_MODELS_AND_SCORING.md, docs/TESTING.md, docs/FEATURE_STATUS.md).",
        ],
        "modules": [
            "backend/app/main.py, application_configuration.py",
            "backend/app/services/interview/ai_interview_service.py, ai_structured_call_base.py, ai_resume_analyzer.py, ai_career_and_assessment_tasks.py, gemini_api_client.py, language_model_client.py, ai_task_model_router.py",
            "backend/app/services/interview/interview_intelligence_rules.py, score_band_labels.py, semantic_job_matcher.py, sentence_embedding_model.py, question_type_classifier.py",
            "backend/eval/ (run_eval.py, calibrate_scoring.py, calibration_set.json), backend/ml/",
            "backend/tests/, backend/tests_e2e/, backend/tests_perf/, docs/",
            ".github/workflows/tests.yml, backend/Dockerfile, docker-compose.yml, render.yaml, frontend/vercel.json",
        ],
        "deliverables": [
            "Working AI gateway with Gemini → Gemini backup → Ollama fallback chain",
            "Adaptive interview engine and calibrated scoring (rank correlation 0.80 → 0.95; answers scored 100: 5 → 0)",
            "Resume analysis (56 s → 5.3 s on Gemini) and explainable job matching",
            "Test suites: 369 backend tests (2 Redis-only skipped), browser end-to-end tests and the CI smoke test",
            "Public GitHub repository with CI on every push, plus Docker / Render / Vercel deployment configuration",
            "README and project documentation, feature status and test reports",
        ],
        "tech": ["Python 3.14", "FastAPI", "Pydantic", "Google Gemini API", "Ollama (qwen3:4b)", "Sentence Transformers",
                 "scikit-learn", "httpx", "pytest", "Playwright", "Git / GitHub", "GitHub Actions", "Docker", "Markdown"],
        "workflow": [
            "Studied the project specification and drew the module and data-flow architecture.",
            "Set up the repository, the FastAPI skeleton and configuration so others could start in parallel.",
            "Built the AI gateway first, then each AI feature on top of it (resume, questions, scoring, matching).",
            "Measured every AI step with benchmark scripts (backend/tests_perf/) and optimised the slowest.",
            "Calibrated scoring with a fixed labelled set and compared before/after numbers.",
            "Wrote tests for each feature, especially access rules, and ran the full suites before every merge.",
            "Prepared CI and deployment files and wrote the documentation after each feature was finished.",
        ],
        "challenges": [
            ("Gemini returned HTTP 429 (quota) or 503 (overloaded) on many requests, so every call waited about 20 s.",
             "Automatic model switching (3.5 Flash → Flash-Lite), a cool-down for busy models and fallback to the local Ollama model."),
            ("On Windows, every connection to Ollama via \"localhost\" tried IPv6 first and lost about 2.1 s.",
             "The Ollama address is rewritten to 127.0.0.1 and one kept-alive HTTP connection is reused."),
            ("The small model scored strong-but-incomplete answers 100/100.",
             "Anchored scale, \"name the missing point first\", completeness weight and rule caps, verified on the calibration set."),
            ("A model sometimes copied the prompt's instructions (\"2-4 sentence summary\") into the report.",
             "Prompt rewritten and a generic validator rejects echoed placeholders, retries once, else shows \"unavailable\"."),
            ("Tests sometimes failed on Windows because of temp-folder permissions, and MongoDB 8 would not start on the CI machines.",
             "A pytest.ini with a project-local temp folder, and MongoDB 7 in CI, so the tests run everywhere."),
        ],
        "learning": {
            "Skills learned": "LLM integration, prompt design, JSON-schema validation, API design, test design, CI/CD, Docker.",
            "Technical knowledge": "Model fallback strategies, embeddings for semantic matching, calibration with rank correlation, latency profiling, browser automation.",
            "Contribution to success": "Every AI feature runs through the gateway and engine Yash built, and the tests keep the whole system working.",
            "Personal improvement": "Leading a team, splitting work so members can work in parallel, reviewing code and writing clearly.",
        },
    },
    {
        "name": "Kaushal",
        "pct": 30,
        "role": "Voice Interview, 3D Avatars, Monitoring, English Learning and Portals Developer",
        "summary": "Kaushal built the live voice interview room with the 3D interviewers and disclosed monitoring, the English "
                   "learning module, and the mentor, recruiter and admin portals.",
        "responsibilities": [
            "Built the live voice interview room and its state machine (pages/student/LiveVoiceInterview.jsx, voice/interviewMachine.js).",
            "Integrated local speech-to-text with faster-whisper and live captions every ~1.2 s (services/voice/speech_to_text.py, voice/recorder.js).",
            "Integrated local text-to-speech with Kokoro-82M and sentence-by-sentence playback (services/voice/text_to_speech.py, voice/speechPlayer.js).",
            "Built the streamed interview turn: the next question is spoken while it is still being written (routers/live_voice_interview_routes.py, services/voice/streamed_reply_sentence_splitter.py).",
            "Built the 3D interviewer renderer with three.js: lip sync from visemes, blinking, idle motion (voice/Avatar3D.jsx, visemes.js, faceRig.js).",
            "Converted Rocketbox avatars with Blender and created the four interviewer personalities: Aria, Victor, Marcus, Elena (services/interview/interviewer_personalities.py).",
            "Compressed the avatar models with meshopt and WebP: 16.5 MB → 5.4 MB (frontend/avatar-src/compress_avatars.py).",
            "Built camera monitoring with MediaPipe in the browser: face visible, more than one face, approximate gaze (monitoring/faceMonitor.js).",
            "Built phone/notes detection in a Web Worker and the integrity event engine with a risk summary (services/monitoring/interview_integrity_rules.py, routers/interview_monitoring_routes.py).",
            "Built the visual attention percentage (services/monitoring/visual_attention_report.py, monitoring/attentionMeter.js).",
            "Built the English conversation companion with three learning modes and topic memory (services/english/english_companion_memory.py).",
            "Built spaced-repetition vocabulary review with five boxes (1, 2, 4, 7, 14 days) and the self-ticking daily plan (services/english/english_vocabulary_trainer.py, pages/student/VocabularyTrainer.jsx).",
            "Built the rewards system: points, badges, streaks, challenges and reward rules (services/student_progress/rewards_and_badges.py).",
            "Built the mentor portal: assigned students, feedback, private notes, improvement plans, sessions, alerts (routers/mentor_portal_routes.py, pages/mentor/).",
            "Built the recruiter portal, the side-by-side candidate comparison and the printable candidate report (routers/jobs/, pages/recruiter/).",
            "Built the admin portal: analytics, users and approvals, interview setup, assessments, settings, audit logs, reports (routers/admin/, pages/admin/).",
            "Built timed MCQ assessments with server-side grading (routers/skill_assessment_routes.py).",
            "Measured and reduced voice latency: answer → next question from 19 s to about 4-7 s on the local model.",
        ],
        "modules": [
            "frontend/src/voice/ (interviewMachine, recorder, speechPlayer, turnStream, Avatar3D, visemes, faceRig, room components)",
            "frontend/src/monitoring/; backend/app/services/voice/speech_to_text.py, text_to_speech.py, streamed_reply_sentence_splitter.py, interviewer_personalities.py, interview_integrity_rules.py, visual_attention_report.py",
            "backend/app/routers/voice_speech_routes.py, live_voice_interview_routes.py, interview_monitoring_routes.py; frontend/public/avatars/",
            "backend/app/services/english/english_companion_memory.py, english_mistake_profile.py, english_vocabulary_trainer.py, ai_english_conversation.py, rewards_and_badges.py",
            "backend/app/routers/english_practice_routes.py, mentor_portal_routes.py, skill_assessment_routes.py, jobs/, admin/",
            "frontend/src/pages/student/English*.jsx, VocabularyTrainer.jsx; pages/mentor/, recruiter/, admin/",
        ],
        "deliverables": [
            "Live voice interview with four 3D interviewer personalities and live captions",
            "Local speech pipeline: a 16 s answer transcribed in 0.8 s (was 4.2-4.9 s)",
            "On-device, disclosed interview monitoring with a reviewer view and risk summary",
            "English module: conversation companion, vocabulary review, daily plan, progress and rewards",
            "Mentor, recruiter and admin portals including candidate comparison and the printable report",
            "Documentation: docs/VOICE_INTERVIEW.md, docs/INTERVIEW_SECURITY.md, docs/ENGLISH.md",
        ],
        "tech": ["three.js", "WebGL", "Blender", "faster-whisper", "Kokoro-82M", "Web Audio API", "MediaPipe Tasks Vision",
                 "Web Workers", "Server-Sent Events", "React", "FastAPI", "Recharts", "Playwright"],
        "workflow": [
            "Built the voice room as a state machine first, with typed answers, so the flow could be tested without audio.",
            "Added text-to-speech, then speech-to-text, then streaming between them, then the 3D avatar with lip sync.",
            "Added monitoring as independent detectors that send events through one event engine.",
            "Built the English module and the three portals backend-first, then the pages on the shared components.",
            "Measured each step with benchmark scripts and optimised the slowest part each time.",
            "Tested everything with Playwright using a fake camera and microphone.",
        ],
        "challenges": [
            ("Whisper sometimes \"heard\" repeated phrases in silence (hallucination loops).",
             "A transcript cleaner removes repeated loops, and the question text is passed as a prompt (fixes words like \"FastAPI\")."),
            ("Transcription took 4-5 s after the student stopped speaking.",
             "Switched to faster-whisper and reused the last live caption, so the transcript is ready immediately."),
            ("Phone detection blocked the page for ~73 ms every second and made the avatar stutter.",
             "Moved detection to a Web Worker; avatar frame pacing and automatic quality step-down."),
            ("The English companion repeated itself and copied the student's sentences.",
             "Higher temperature (0.2 → 0.7) and a duplicate-reply check with one retry."),
            ("Recruiters must never see other companies' applicants or non-consented integrity data.",
             "Central access rules plus tests: another recruiter gets 404, a student gets 403, unshared sessions stay hidden."),
        ],
        "learning": {
            "Skills learned": "Real-time audio, 3D graphics and computer vision in the browser, full-stack feature development.",
            "Technical knowledge": "Speech recognition and synthesis, visemes and lip sync, MediaPipe, Web Workers, spaced repetition, gamification.",
            "Contribution to success": "The live 3D voice interview that makes HireSense stand out, plus three of the four portals.",
            "Personal improvement": "Measuring before optimising, and designing monitoring that respects privacy.",
        },
    },
    {
        "name": "Samrath",
        "pct": 14,
        "role": "Backend Developer and Database Engineer",
        "summary": "Samrath built the data layer on MongoDB, authentication and security, access control and the core "
                   "REST APIs, plus live notifications.",
        "responsibilities": [
            "Designed the MongoDB collections for users, profiles, interviews, answers, jobs, applications, English, rewards and logs (app/database_models.py).",
            "Built the MongoDB data layer with a SQLAlchemy-style API: sessions, queries, statements, auto-increment ids (app/mongodb_data_layer/).",
            "Migrated the project from SQLite to MongoDB and created indexes and unique constraints at start-up (app/database_connection.py).",
            "Wrote request and response schemas with Pydantic validation (app/request_validation_schemas.py, serializers).",
            "Implemented authentication: registration, login, JWT in an httpOnly cookie, Argon2 password hashing (routers/authentication_routes.py, password_and_token_security.py).",
            "Implemented login lockout, password reset by email (SMTP) and account deletion (services/platform_support/email_sender.py).",
            "Implemented role guards and data-access rules, e.g. recruiters see only their own applicants (authentication_dependencies.py, services/platform_support/student_record_access.py).",
            "Built the student and common routers: profile, settings, notifications, dashboard data (routers/student_portal_routes.py, profile_and_notification_routes.py).",
            "Wrote the repeatable seed: question bank, rubrics, badges, reward rules, challenges, assessments (app/seed_initial_data.py).",
            "Built the shared rate limiter with optional Redis and in-memory fallback (services/platform_support/rate_limiter.py).",
            "Built AI-data consent recording and the privacy endpoint (services/platform_support/hosted_ai_consent.py).",
            "Built live notifications over Server-Sent Events with heartbeat and per-user limits (services/platform_support/live_notification_events.py).",
        ],
        "modules": [
            "backend/app/mongodb_data_layer/ (connection, session, query, statements, mapping, expressions, coltypes)",
            "backend/app/database_models.py, request_validation_schemas.py, database_connection.py, password_and_token_security.py, authentication_dependencies.py, seed_initial_data.py, reset_admin_password.py",
            "backend/app/routers/authentication_routes.py, profile_and_notification_routes.py, student_portal_routes.py",
            "backend/app/services/platform_support/student_record_access.py, rate_limiter.py, hosted_ai_consent.py, live_notification_events.py, email_sender.py, background_jobs.py",
        ],
        "deliverables": [
            "MongoDB data layer and schema for the whole platform",
            "Secure authentication with lockout, password reset and role-based access control",
            "Core REST API used by all four portals, documented automatically at /docs (Swagger)",
            "Live notifications (a new application reached the recruiter's open page in about 25 ms in testing)",
            "Health checks (/api/health/live, /api/health/ready) and database documentation (docs/DATABASE.md)",
        ],
        "tech": ["Python 3.14", "FastAPI", "MongoDB", "pymongo", "Pydantic", "JWT", "Argon2", "Redis (optional)",
                 "Server-Sent Events", "SMTP", "pytest"],
        "workflow": [
            "Derived the entities and relations from the specification and designed the collections.",
            "Built the data layer and models, then the authentication flow.",
            "Implemented the routers endpoint by endpoint, each with tests for success and permission failures.",
            "Wrote the seed data so a fresh database is ready in one command.",
            "Moved from SQLite to MongoDB without changing the code of the other modules.",
            "Added production features: rate limiting, consent, live notifications and health checks.",
        ],
        "challenges": [
            ("With SQLite, background AI work and requests collided and caused \"database is locked\" errors.",
             "First WAL mode and committing before AI calls; later the move to MongoDB, which handles concurrent writes."),
            ("Moving to MongoDB would have meant rewriting every router and service.",
             "A small data layer with the same SQLAlchemy-style API (select, where, session), so the routers stayed unchanged."),
            ("Login lockout and rate limits lived in one process's memory and would break with several servers.",
             "A shared limiter that uses Redis when REDIS_URL is set and falls back to memory."),
            ("Notifications only refreshed every 30 seconds.",
             "Server-Sent Events: the browser re-fetches as soon as something changes, with polling as a fallback."),
        ],
        "learning": {
            "Skills learned": "Database design, REST API design, authentication and authorisation, backend testing.",
            "Technical knowledge": "MongoDB indexing, JWT and cookie security, rate limiting, server push with SSE.",
            "Contribution to success": "Every portal reads and writes data through the APIs and data layer Samrath built.",
            "Personal improvement": "Thinking about security and data privacy from the start, not as an afterthought.",
        },
    },
    {
        "name": "Aryan",
        "pct": 13,
        "role": "Frontend Foundation and Design System Developer",
        "summary": "Aryan set up the React frontend, built the design system and shared components used by all four "
                   "portals, the API layer, and made the application fast to load.",
        "responsibilities": [
            "Set up the React 18 + Vite + Tailwind CSS project and the build configuration (vite.config.js, tailwind.config.js).",
            "Built routing for the four portals with role-based route guards (frontend/src/App.jsx).",
            "Made every page load on demand with React.lazy and split vendor chunks: first load 1,130 kB → 236 kB.",
            "Designed the \"Dark premium\" theme with all colours as CSS variables, so the theme changes in one place (src/index.css).",
            "Built the shared component library: cards, buttons, tables, tabs, status pills, empty states, spinners (components/SharedUiComponents.jsx, UrlTabs.jsx).",
            "Built the application layout with a grouped sidebar, header, notification bell and user menu (components/AppShellLayout.jsx, Logo.jsx).",
            "Built the chart components used on dashboards and reports (components/DashboardCharts.jsx, Recharts).",
            "Wrote the API client with httpOnly-cookie authentication and error handling (src/apiClient.js).",
            "Built the login state and session handling for the whole app (src/AuthContext.jsx).",
            "Built the live-notification client: one stream per tab, reconnect with backoff, polling fallback (live/notificationStream.js).",
            "Built the sign-in, registration and password-reset screens (pages/Login.jsx, Register.jsx, AuthShell.jsx).",
            "Made the layout responsive and accessible (labels, focus states, keyboard navigation).",
        ],
        "modules": [
            "frontend/src/App.jsx, main.jsx, apiClient.js, AuthContext.jsx, index.css, tailwind.config.js, vite.config.js",
            "frontend/src/components/ (SharedUiComponents.jsx, AppShellLayout.jsx, Logo.jsx, UrlTabs.jsx, DashboardCharts.jsx)",
            "frontend/src/live/notificationStream.js",
            "frontend/src/pages/ (Login, Register, AuthShell, ForgotPassword, ResetPassword, NotFound)",
        ],
        "deliverables": [
            "Frontend project setup, routing and route guards for four portals",
            "Design system and reusable UI component library used by every page",
            "Bundle optimisation: initial JavaScript 1,130 kB → 236 kB (76 kB gzipped)",
            "API client, authentication state and live-notification client",
        ],
        "tech": ["React 18", "Vite 6", "Tailwind CSS", "React Router 6", "Recharts", "lucide-react icons",
                 "JavaScript (ES2022)", "EventSource (SSE)", "Chrome DevTools"],
        "workflow": [
            "Set up the project and the folder structure so other members could add pages.",
            "Built the design tokens and component library first, then the layout and routing.",
            "Wrote the API client and authentication state against Samrath's endpoints.",
            "Measured the bundle with the Vite build report and introduced lazy loading and chunk splitting.",
            "Reviewed pages at desktop and mobile widths and fixed shared-component issues.",
        ],
        "challenges": [
            ("The first version looked generic (\"AI-style\" gradients, inconsistent colours) and was rated poorly in review.",
             "A full redesign with one design system: colours as CSS variables, one brand colour, consistent components."),
            ("The whole app (1.13 MB of JavaScript) downloaded before the login page appeared.",
             "Route-level lazy loading with React.lazy and Suspense, plus separate chunks for React, three.js and charts."),
            ("The logo gradient disappeared when the logo appeared twice on a page.",
             "Each logo instance gets a unique SVG gradient id with React's useId."),
        ],
        "learning": {
            "Skills learned": "Component-based UI architecture, design systems, routing, performance optimisation.",
            "Technical knowledge": "React hooks and context, code splitting, CSS-variable theming, cookie-based auth in the browser.",
            "Contribution to success": "Every page of all four portals is built on Aryan's components, layout and API layer.",
            "Personal improvement": "Keeping a large UI consistent and measuring performance before optimising.",
        },
    },
    {
        "name": "Shardha",
        "pct": 13,
        "role": "Student Portal Pages and Frontend Testing",
        "summary": "Shardha built the student portal pages that students use every day and the frontend unit tests.",
        "responsibilities": [
            "Built the student dashboard: greeting, readiness score, quick actions, stat cards and challenges (pages/student/StudentDashboard.jsx).",
            "Built the mock-interview pages: setup form, interviewer picker, typed interview session and history.",
            "Built the interview report page: overall score with band, skill breakdown, strengths, weaknesses and per-question feedback.",
            "Built the resume page: upload, AI analysis view and student corrections (pages/student/ResumeUploadAndAnalysis.jsx).",
            "Built the jobs, placement drives, applications and opportunities pages with eligibility and match explanations.",
            "Built the progress hub with charts of interview, English and assessment progress (pages/student/ProgressHub.jsx).",
            "Built the student rewards page: points, badges and challenges (pages/student/StudentRewards.jsx).",
            "Built the profile, account settings and notifications pages (pages/ProfileEditor.jsx, AccountSettings.jsx, Notifications.jsx).",
            "Built the privacy page and the AI-consent notice shown before AI features (pages/Privacy.jsx).",
            "Built score-band display helpers used on reports (components/scoreBandLabel.js).",
            "Wrote frontend unit tests with Vitest: 141 tests for state machines and helpers.",
        ],
        "modules": [
            "frontend/src/pages/student/ (Dashboard, Interviews, InterviewSetup, InterviewerPicker, InterviewSession, PerformanceReport, Resume, Jobs, Drives, Applications, Opportunities, ProgressHub, Rewards)",
            "frontend/src/pages/ (Profile, Settings, Notifications, Privacy)",
            "frontend/src/components/ (PlacementReadinessCard.jsx, scoreBandLabel.js); frontend/src/**/*.test.js",
        ],
        "deliverables": [
            "Complete student portal (about 20 pages) on the shared design system",
            "Interview report page with score bands and per-question feedback",
            "Frontend unit tests (141 Vitest tests) and the UI screenshots in docs/screenshots/",
        ],
        "tech": ["React 18", "Tailwind CSS", "React Router 6", "Recharts", "JavaScript (ES2022)", "Vitest",
                 "Chrome DevTools"],
        "workflow": [
            "Collected the student-side requirements from the specification and sketched page layouts.",
            "Built each page on Aryan's components and connected it to the backend APIs.",
            "Checked each page in the browser with real data and fixed layout and wording issues.",
            "Wrote unit tests for page logic and helpers and fixed issues found in team reviews.",
        ],
        "challenges": [
            ("Long AI texts and many numbers made report pages hard to read.",
             "Score bands, skill bars, two-column strengths/weaknesses and collapsible per-question details."),
            ("Daily-plan items completed outside the English pages (e.g. an interview) were not shown as done.",
             "The plan is evaluated when it is viewed, so the dashboard card always shows the current state."),
            ("AI features must not run before the student agrees to send data to the AI provider.",
             "A consent notice on interview, resume and English pages, with a toggle in Settings to withdraw."),
        ],
        "learning": {
            "Skills learned": "Building data-driven pages, user-friendly report design, frontend testing.",
            "Technical knowledge": "React state and effects, API integration, charts, unit testing with Vitest.",
            "Contribution to success": "The student portal is the main face of HireSense; every demo starts on Shardha's pages.",
            "Personal improvement": "Thinking like a user and turning review feedback into clearer pages.",
        },
    },
]

TIMELINE = [  # phase, dates, lead, support
    ("Requirement analysis and specification", "9-10 Oct 2026", "Yash", "All members"),
    ("Architecture and database design", "10 Oct", "Yash", "Samrath"),
    ("Frontend setup, UI design and design system", "10-12 Oct", "Aryan", "Shardha"),
    ("Backend core, authentication and APIs", "10-14 Oct", "Samrath", "Yash"),
    ("AI integration (resume, questions, scoring, matching)", "10-25 Oct", "Yash", "Samrath"),
    ("Student portal pages", "10-20 Oct", "Shardha", "Aryan"),
    ("Live voice interview and 3D avatars", "10-11 Oct, refined to 29 Oct", "Kaushal", "Yash"),
    ("English learning module", "10-11 Oct, extended 5 Nov", "Kaushal", "Yash"),
    ("Recruiter, mentor and admin portals", "12-25 Oct", "Kaushal", "Samrath"),
    ("Interview monitoring and security module", "11-25 Oct", "Kaushal", "Samrath"),
    ("Move from SQLite to MongoDB", "late Oct", "Samrath", "Yash"),
    ("Performance and latency optimisation", "11 Oct - 4 Nov", "Kaushal", "Aryan, Yash"),
    ("UI redesign (Dark premium theme)", "4 Nov", "Aryan", "Shardha"),
    ("Score calibration and real-model verification", "4-5 Nov", "Yash", "Kaushal"),
    ("Testing (unit, API, browser E2E, CI)", "throughout; CI 5 Nov", "Yash", "All members"),
    ("Deployment preparation (Docker, Render, Vercel)", "5 Nov", "Yash", "Samrath"),
    ("Documentation and final presentation", "5 Nov", "Yash", "All members"),
]

COLLABORATION = [
    ("Communication", "A group chat for daily updates and quick questions, plus a short stand-up during working days "
                      "where each member said what was done, what was next and what was blocking."),
    ("Task management", "Work was split by module (see the responsibility matrix), so members could build in "
                        "parallel. Each task had one owner and a reviewer."),
    ("Version control", "Git with a public GitHub repository (github.com/kaushal-o4/hiresense). Each feature was "
                        "built on its own branch and merged into main after review and passing tests."),
    ("Meetings", "A weekly review meeting to demo finished features, agree on the API contract between frontend and "
                 "backend, and re-plan the next week."),
    ("Issue tracking", "Bugs and open items were tracked in a shared list and in docs/FEATURE_STATUS.md, with the "
                       "status Done, Partial, Verified or Not built."),
    ("Code reviews", "Every merge was checked by another member and by the automated test suites on GitHub Actions "
                     "(backend tests, frontend tests and build, cloud-profile check, browser smoke test)."),
]

# ---- simple architecture and workflow (section 2) ----
SIMPLE_ARCH_TEXT = [
    "HireSense has three layers, like most web applications. The first layer is what the user sees: the website in "
    "the browser. The second is the backend server, which contains the rules of the system. The third is where data "
    "is stored and where the AI models run.",
    "The browser layer is a React website with four portals: Student, Recruiter, Mentor and Admin. When a student "
    "takes a voice interview, the browser also uses the camera and microphone.",
    "The browser never talks to the database directly. It sends requests (for example \"save this answer\") to the "
    "backend over HTTPS, and the backend replies with data in JSON format.",
    "The backend is built with FastAPI (Python). It checks who is logged in, runs the interview engine, analyses "
    "resumes, matches students to jobs, runs the English coach and sends live notifications.",
    "All data (users, interviews, answers, jobs, applications, scores) is saved in a MongoDB database.",
    "For AI work the backend sends a prompt to Google Gemini on the internet. If Gemini is busy or offline, it "
    "automatically uses Ollama, a smaller AI model running on the laptop. Whisper turns the student's speech into "
    "text, and Kokoro turns the interviewer's text into a voice.",
]

STUDENT_FLOW = [
    ("Register / Login", "Student creates an account"),
    ("Upload resume", "PDF or text file"),
    ("AI analyses resume", "skills, projects, gaps"),
    ("Start mock interview", "choose an interviewer"),
    ("Interviewer asks", "question spoken in 3D voice"),
    ("Student answers", "speech becomes text"),
    ("AI scores answer", "picks the next question"),
    ("Final report", "score and band"),
    ("Apply to jobs", "match % shown"),
    ("Recruiter compares", "candidates side by side"),
    ("Mentor guides", "feedback and plan"),
]

STUDENT_FLOW_TEXT = [
    "The student first creates an account and logs in. Then the student uploads a resume, and the AI reads it and "
    "lists the skills, projects and weak points.",
    "Next the student starts a mock interview and chooses one of four interviewers (Aria, Victor, Marcus or Elena). "
    "The interviewer appears as a 3D character and speaks each question aloud.",
    "The student answers by speaking. Whisper converts the speech into text, which is shown as live captions.",
    "The AI scores the answer (relevance, correctness, completeness, clarity) and uses the score to choose the next "
    "question: harder if the answer was good, easier if it was weak.",
    "At the end the student gets a report with an overall score, a band such as \"Strong 75-89\", strengths, "
    "weaknesses and tips for every question.",
    "The student can then apply to jobs. Each job shows a match percentage and the reason for it. Recruiters compare "
    "the applicants side by side, and the student's mentor sees the same results and gives guidance.",
]

RECRUITER_FLOW = [
    ("Recruiter registers", "admin approves the account"),
    ("Post a job", "skills and eligibility"),
    ("Students apply", "match % calculated"),
    ("Compare candidates", "2-4 side by side"),
    ("Shortlist / select", "student is notified"),
]

ADMIN_FLOW = [
    ("Admin logs in", ""),
    ("Approve users", "recruiters, mentors"),
    ("Set up content", "questions, tests, rewards"),
    ("Watch analytics", "usage, AI speed, errors"),
    ("Placement reports", "CSV export"),
]

OTHER_FLOW_TEXT = [
    "A recruiter registers and waits for the admin to approve the account. The recruiter then posts a job with the "
    "required skills and eligibility (branch, CGPA, graduation year).",
    "When students apply, the system calculates a match percentage from the student's skills and experience and "
    "explains it. The recruiter can compare two to four candidates side by side and print a report as a PDF.",
    "When the recruiter changes an application status (shortlisted, selected or rejected), the student gets a live "
    "notification.",
    "The admin approves new users, sets up the question bank, assessments and rewards, watches the analytics "
    "dashboard (users, interviews, AI speed and errors) and downloads placement reports.",
]

ARCHITECTURE = [
    ("Frontend", "React 18 single-page app with four portals, built with Vite and Tailwind. Pages load on demand. The "
                 "3D interviewer uses three.js; camera monitoring uses MediaPipe in the browser."),
    ("Backend", "FastAPI application organised in routers (auth, students, interviews, english, jobs, mentors, admin, "
                "voice, monitoring) and services (AI, matching, rewards, integrity, speech)."),
    ("Database", "MongoDB through a small data layer (backend/app/mongodb_data_layer/). Indexes and unique constraints are created "
                 "at start-up; the seed adds reference data."),
    ("AI module", "One gateway (services/ai_models/ai_structured_call_base.py) for every model call: Gemini first, backup Gemini models, then "
                  "local Ollama. Outputs are validated against JSON schemas; usage is logged without personal text."),
    ("APIs", "REST over /api with automatic Swagger documentation, plus Server-Sent Events for live notifications and "
             "the streamed voice-interview turn."),
    ("Authentication", "JWT in an httpOnly, SameSite cookie, Argon2 password hashes, role guards on every endpoint, "
                       "login lockout and rate limits (memory or Redis), AI-data consent."),
    ("Admin panel", "Analytics, user approval, question bank, rubrics, rewards, security settings, AI usage and speed "
                    "per model, error and audit logs, CSV placement reports."),
]

CONCLUSION = [
    "HireSense meets its main objective: a working placement-preparation platform in which students practise realistic "
    "interviews with a speaking 3D interviewer, receive calibrated and explainable feedback, improve their English, "
    "and apply to jobs, while recruiters, mentors and the placement cell work with the same data. The platform is "
    "backed by 369 backend tests, 141 frontend tests, browser end-to-end tests and automated checks on every push.",
    "The project was a team effort. Yash's architecture, AI engine, testing and documentation; Kaushal's voice "
    "interview, 3D avatars, monitoring, English module and three portals; Samrath's database, security and APIs; "
    "Aryan's frontend foundation and design system; and Shardha's student portal pages and frontend tests each form "
    "an essential part; no portal works without the others.",
    "Future improvements: testing the voice and camera features with real users and tuning the detector thresholds, "
    "OCR for scanned resumes, more languages for voice practice, a hosted deployment with a paid AI quota, load "
    "testing with many simultaneous users, and a mobile-friendly interview room.",
]

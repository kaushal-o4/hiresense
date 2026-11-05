"""Content of the HireSense team work-distribution report (facts taken from the repository and its docs)."""

PROJECT = "HireSense"
SUBTITLE = "AI-Powered Intelligent Interview and Placement Assessment System"
DATE = "5 November 2026"

TEAM = ["Kaushal", "Yash", "Samrath", "Aryan", "Shardha"]

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
        "name": "Kaushal",
        "role": "Project Lead, System Architect and AI Engine Developer",
        "summary": "Kaushal designed the overall architecture, built the AI engine that every feature depends on, "
                   "and owned integration, the GitHub repository, continuous integration and deployment.",
        "responsibilities": [
            "Defined the overall architecture: four portals, one FastAPI backend, one MongoDB database, one AI gateway.",
            "Set up the FastAPI application, router registration, security headers, request IDs and the global error handler (app/main.py).",
            "Built the central configuration with pydantic-settings, so every option lives in backend/.env (app/config.py).",
            "Built the AI gateway (services/ai_base.py): daily limits, JSON-schema validation with one retry, usage logging without storing personal text.",
            "Integrated Google Gemini (services/gemini_llm.py) with automatic switching to backup models on HTTP 429/503 or a slow first token.",
            "Integrated the local Ollama model as a fallback (services/local_llm.py) and per-task model tiers (services/model_router.py).",
            "Wrote the interview engine (services/interview_engine.py): resume-based questions, adaptive difficulty, repeat detection by meaning, follow-ups for vague answers.",
            "Designed the scoring rubric and caps, and calibrated it on 16 hand-labelled answers (backend/eval/calibrate_scoring.py).",
            "Added score bands shown to students, such as \"Strong 75-89\" (services/scoring_bands.py).",
            "Built AI resume analysis (services/ai_resume.py, resume_parser.py) with a check that removes anything not found in the resume text.",
            "Built explainable job matching with sentence embeddings and skill weights (services/matching.py, embeddings.py).",
            "Added a validator that rejects AI replies which copy the prompt's instructions instead of answering.",
            "Created the GitHub repository, branch workflow and GitHub Actions pipeline (.github/workflows/tests.yml).",
            "Prepared deployment: slim cloud requirements, Dockerfiles, docker-compose.yml, render.yaml and frontend/vercel.json.",
            "Coordinated integration between all members' modules and ran the final end-to-end demo.",
        ],
        "modules": [
            "backend/app/main.py, config.py",
            "backend/app/services/ai.py, ai_base.py, ai_resume.py, ai_tasks.py, gemini_llm.py, local_llm.py, model_router.py",
            "backend/app/services/interview_engine.py, scoring_bands.py, matching.py, embeddings.py, question_classifier.py",
            "backend/eval/ (run_eval.py, calibrate_scoring.py, calibration_set.json), backend/ml/",
            ".github/workflows/tests.yml, backend/Dockerfile, docker-compose.yml, render.yaml, frontend/vercel.json",
        ],
        "deliverables": [
            "Working AI gateway with Gemini → Gemini backup → Ollama fallback chain",
            "Adaptive interview engine and calibrated scoring (rank correlation 0.80 → 0.95; answers scored 100: 5 → 0)",
            "Resume analysis (56 s → 5.3 s on Gemini) and explainable job matching",
            "Public GitHub repository with CI, plus Docker / Render / Vercel deployment configuration",
            "Architecture notes and the AI section of the documentation (docs/AI_MODELS_AND_SCORING.md)",
        ],
        "tech": ["Python 3.14", "FastAPI", "Pydantic", "Google Gemini API", "Ollama (qwen3:4b)", "Sentence Transformers",
                 "scikit-learn", "httpx", "Git / GitHub", "GitHub Actions", "Docker"],
        "workflow": [
            "Studied the project specification and drew the module and data-flow architecture.",
            "Set up the repository, the FastAPI skeleton and configuration so others could start in parallel.",
            "Built the AI gateway first, then each AI feature on top of it (resume, questions, scoring, matching).",
            "Measured every AI step with benchmark scripts (backend/tests_perf/) and optimised the slowest.",
            "Calibrated scoring with a fixed labelled set and compared before/after numbers.",
            "Integrated the other modules, reviewed pull requests and ran the full test suites before each merge.",
            "Prepared CI and deployment files and documented the setup.",
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
        ],
        "learning": {
            "Skills learned": "LLM integration, prompt design, JSON-schema validation, API design, CI/CD, Docker.",
            "Technical knowledge": "Model fallback strategies, embeddings for semantic matching, calibration with rank correlation, latency profiling.",
            "Contribution to success": "Every AI feature of the platform runs through the gateway and engine Kaushal built.",
            "Personal improvement": "Leading a team, splitting work so members can work in parallel, and reviewing code.",
        },
    },
    {
        "name": "Yash",
        "role": "Frontend Developer and UI/UX Designer (Student Portal)",
        "summary": "Yash built the React frontend foundation, the design system and the complete student portal, "
                   "and made the application fast to load.",
        "responsibilities": [
            "Set up the React 18 + Vite + Tailwind CSS project, routing and role-based route guards (frontend/src/App.jsx).",
            "Designed the \"Dark premium\" visual theme with all colours as CSS variables, so the theme changes in one place (src/index.css).",
            "Built the shared component library: cards, buttons, tables, tabs, status pills, empty states, spinners (components/ui.jsx, Tabs.jsx).",
            "Built the application layout with a grouped sidebar, header, notification bell and user menu (components/Layout.jsx, Logo.jsx).",
            "Built the student dashboard: greeting, readiness score, quick actions, stat cards and challenges (pages/student/Dashboard.jsx).",
            "Built the mock-interview pages: setup form, interviewer picker, typed interview session and history.",
            "Built the interview report page: overall score with band, skill breakdown, strengths, weaknesses and per-question feedback.",
            "Built the resume page: upload, AI analysis view and student corrections (pages/student/Resume.jsx).",
            "Built jobs, placement drives, applications and opportunities pages with eligibility and match explanations.",
            "Built the progress hub and rewards pages with charts (components/charts.jsx, Recharts).",
            "Wrote the thin API client with httpOnly-cookie authentication and error handling (src/api.js, auth.jsx).",
            "Made every page load on demand (React.lazy) and split vendor chunks: first load 1,130 kB → 236 kB.",
            "Made the layout responsive and accessible (labels, focus states, keyboard navigation).",
            "Wrote frontend unit tests with Vitest for state logic and helpers.",
        ],
        "modules": [
            "frontend/src/App.jsx, main.jsx, api.js, auth.jsx, index.css, tailwind.config.js, vite.config.js",
            "frontend/src/components/ (ui.jsx, Layout.jsx, Logo.jsx, Tabs.jsx, charts.jsx, Readiness.jsx, scoreBand.js)",
            "frontend/src/pages/student/ (Dashboard, Interviews, InterviewSetup, InterviewSession, PerformanceReport, Resume, Jobs, Drives, Applications, ProgressHub, Rewards)",
            "frontend/src/pages/ (Login, Register, AuthShell, Profile, Settings, NotFound)",
        ],
        "deliverables": [
            "Complete student portal (about 20 pages) in a consistent design system",
            "Reusable UI component library used by all four portals",
            "Bundle optimisation: initial JavaScript 1,130 kB → 236 kB (76 kB gzipped)",
            "Frontend part of the 141 Vitest tests and the UI screenshots in docs/screenshots/",
        ],
        "tech": ["React 18", "Vite 6", "Tailwind CSS", "React Router 6", "Recharts", "lucide-react icons",
                 "JavaScript (ES2022)", "Vitest", "Figma-style mock-ups", "Chrome DevTools"],
        "workflow": [
            "Collected the student-side requirements from the specification and sketched page layouts.",
            "Built the design tokens and component library first, then the pages on top of them.",
            "Connected pages to Samrath's and Kaushal's APIs using the shared API client.",
            "Reviewed each page in the browser at desktop and mobile widths and fixed layout issues.",
            "Measured the bundle with the Vite build report and introduced lazy loading and chunk splitting.",
            "Wrote unit tests and fixed issues found in team reviews.",
        ],
        "challenges": [
            ("The first version looked generic (\"AI-style\" gradients, inconsistent colours) and was rated poorly in review.",
             "A full redesign with one design system: colours as CSS variables, one brand colour, consistent components."),
            ("The whole app (1.13 MB of JavaScript) downloaded before the login page appeared.",
             "Route-level lazy loading with React.lazy and Suspense, plus separate chunks for React, three.js and charts."),
            ("The logo gradient disappeared when the logo appeared twice on a page.",
             "Each logo instance gets a unique SVG gradient id with React's useId."),
            ("Long AI texts and many numbers made report pages hard to read.",
             "Score bands, skill bars, two-column strengths/weaknesses and collapsible per-question details."),
        ],
        "learning": {
            "Skills learned": "Component-based UI architecture, design systems, responsive layout, performance optimisation.",
            "Technical knowledge": "React hooks and context, code splitting, CSS variables theming, accessibility basics.",
            "Contribution to success": "The student portal is the main face of HireSense; every demo starts on Yash's pages.",
            "Personal improvement": "Turning feedback into design decisions and keeping a large UI consistent.",
        },
    },
    {
        "name": "Samrath",
        "role": "Backend Developer and Database Engineer",
        "summary": "Samrath built the data layer on MongoDB, authentication and security, access control and the core "
                   "REST APIs, plus live notifications.",
        "responsibilities": [
            "Designed the MongoDB collections for users, profiles, interviews, answers, jobs, applications, English, rewards and logs (app/models.py).",
            "Built the MongoDB data layer with a SQLAlchemy-style API: sessions, queries, statements, auto-increment ids (app/odm/).",
            "Migrated the project from SQLite to MongoDB and created indexes and unique constraints at start-up (app/database.py).",
            "Wrote request and response schemas with Pydantic validation (app/schemas.py, serializers).",
            "Implemented authentication: registration, login, JWT in an httpOnly cookie, Argon2 password hashing (routers/auth.py, security.py).",
            "Implemented login lockout, password reset by email (SMTP) and account deletion (services/mailer.py).",
            "Implemented role guards and data-access rules, e.g. recruiters see only their own applicants (deps.py, services/access.py).",
            "Built the student and common routers: profile, settings, notifications, dashboard data (routers/students.py, common.py).",
            "Wrote the repeatable seed: question bank, rubrics, badges, reward rules, challenges, assessments (app/seed.py).",
            "Built the shared rate limiter with optional Redis and in-memory fallback (services/limiter.py).",
            "Built AI-data consent recording and the privacy endpoint (services/consent.py).",
            "Built live notifications over Server-Sent Events with heartbeat and per-user limits (services/live_events.py).",
            "Added health checks (/api/health/live, /api/health/ready), request IDs and the error log.",
            "Wrote backend tests for authentication, permissions and workflows.",
        ],
        "modules": [
            "backend/app/odm/ (connection, session, query, statements, mapping, expressions, coltypes)",
            "backend/app/models.py, schemas.py, database.py, security.py, deps.py, seed.py, reset_admin.py",
            "backend/app/routers/auth.py, common.py, students.py",
            "backend/app/services/access.py, limiter.py, consent.py, live_events.py, mailer.py, background.py",
        ],
        "deliverables": [
            "MongoDB data layer and schema for the whole platform",
            "Secure authentication with lockout, password reset and role-based access control",
            "Core REST API used by all four portals, documented automatically at /docs (Swagger)",
            "Live notifications (a new application reached the recruiter's open page in about 25 ms in testing)",
            "Database documentation (docs/DATABASE.md) and the authentication and permission tests",
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
        "role": "Voice Interview, 3D Avatar and Monitoring Developer",
        "summary": "Aryan built the live voice interview room: speech in and out, the 3D interviewers, and the "
                   "disclosed on-device interview monitoring.",
        "responsibilities": [
            "Built the live voice interview room and its state machine (pages/student/VoiceInterview.jsx, voice/interviewMachine.js).",
            "Integrated local speech-to-text with faster-whisper and live captions every ~1.2 s (services/stt.py, voice/recorder.js).",
            "Integrated local text-to-speech with Kokoro-82M and sentence-by-sentence playback (services/tts.py, voice/speechPlayer.js).",
            "Built the streamed interview turn: the next question is spoken while it is still being written (routers/interview_live.py, services/speech_stream.py).",
            "Built the 3D interviewer renderer with three.js: lip sync from visemes, blinking, idle motion (voice/Avatar3D.jsx, visemes.js, faceRig.js).",
            "Converted Rocketbox avatars with Blender and created the four interviewer personalities: Aria, Victor, Marcus, Elena (services/interviewers.py).",
            "Built the avatar behaviour states: listening, thinking, speaking (voice/avatarStates.js).",
            "Compressed the avatar models with meshopt and WebP: 16.5 MB → 5.4 MB (frontend/avatar-src/compress_avatars.py).",
            "Built camera monitoring with MediaPipe in the browser: face visible, more than one face, approximate gaze (monitoring/faceMonitor.js).",
            "Built phone/notes detection in a Web Worker so it does not freeze the avatar (public/mediapipe/object-worker.js).",
            "Built the integrity event engine and risk summary on the backend (services/integrity.py, routers/monitoring.py).",
            "Built the visual attention percentage (services/attention.py, monitoring/attentionMeter.js).",
            "Added tab, fullscreen, paste and second-voice signals, which never change the score.",
            "Measured and reduced latency: answer → next question from 19 s to about 4-7 s on the local model.",
        ],
        "modules": [
            "frontend/src/voice/ (interviewMachine, recorder, speechPlayer, speechQueue, turnStream, Avatar3D, visemes, faceRig, motion, room components)",
            "frontend/src/monitoring/ (faceMonitor, objectMonitor, interviewMonitor, attentionMeter, audioMonitor, guards)",
            "backend/app/services/stt.py, tts.py, speech_stream.py, interviewers.py, integrity.py, attention.py",
            "backend/app/routers/voice.py, interview_live.py, monitoring.py; frontend/public/avatars/",
        ],
        "deliverables": [
            "Live voice interview with four 3D interviewer personalities and live captions",
            "Local speech pipeline: 16 s answer transcribed in 0.8 s (was 4.2-4.9 s)",
            "On-device, disclosed interview monitoring with a reviewer view and risk summary",
            "Browser end-to-end tests for the voice room and monitoring (backend/tests_e2e/)",
            "Documentation: docs/VOICE_INTERVIEW.md, docs/INTERVIEW_SECURITY.md, docs/ATTENTION_MONITORING.md",
        ],
        "tech": ["three.js", "WebGL", "Blender", "faster-whisper", "Kokoro-82M", "Web Audio API", "MediaPipe Tasks Vision",
                 "Web Workers", "Server-Sent Events", "Playwright", "JavaScript", "Python"],
        "workflow": [
            "Built the room as a state machine first, with typed answers, so the flow could be tested without audio.",
            "Added text-to-speech, then speech-to-text, then streaming between them.",
            "Added the 3D avatar and connected lip sync to the audio.",
            "Added monitoring as independent detectors that send events through one event engine.",
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
            ("Headless browser tests were 3-20× slower than real use because the 3D avatar was software-rendered.",
             "GPU flag for tests (HS_E2E_GPU=1) and timing measured on the server side instead."),
        ],
        "learning": {
            "Skills learned": "Real-time audio, 3D graphics in the browser, computer vision in the browser, latency engineering.",
            "Technical knowledge": "Speech recognition and synthesis models, visemes and lip sync, MediaPipe, Web Workers.",
            "Contribution to success": "The live 3D voice interview is the feature that makes HireSense stand out.",
            "Personal improvement": "Measuring before optimising, and designing monitoring that respects privacy.",
        },
    },
    {
        "name": "Shardha",
        "role": "English Learning, Portals (Mentor/Recruiter/Admin) and Quality Assurance Lead",
        "summary": "Shardha built the English learning module, the mentor, recruiter and admin portals, and led "
                   "testing and documentation.",
        "responsibilities": [
            "Built the English conversation companion with three learning modes and topic memory (services/english_companion.py).",
            "Built the recurring-mistake profile from English sessions (services/english_profile.py).",
            "Built spaced-repetition vocabulary review with five boxes (1, 2, 4, 7, 14 days) (services/english_vocab.py, pages/student/Vocabulary.jsx).",
            "Built the daily plan that ticks itself off and the English progress view (components/DailyPlan.jsx, EnglishProgress.jsx).",
            "Built the rewards system: points, badges, streaks, challenges and reward rules (services/rewards.py).",
            "Built the mentor portal: assigned students, feedback, private notes, improvement plans, sessions, alerts (routers/mentors.py, pages/mentor/).",
            "Built the recruiter portal: jobs, applicants, explainable screening and status updates (routers/jobs/, pages/recruiter/).",
            "Built the side-by-side candidate comparison (2-4 candidates) and the printable candidate report.",
            "Built the admin portal: analytics, users and approvals, interview setup, assessments, rewards, settings, audit logs, reports (routers/admin/, pages/admin/).",
            "Built timed MCQ assessments with server-side grading (routers/assessments.py).",
            "Led the backend test suite with pytest: 369 tests on a separate MongoDB test database.",
            "Wrote Playwright browser tests, including the CI smoke test that opens 15 pages (tests_e2e/ci_smoke_browser.py).",
            "Kept the regression list and verified fixes before each merge.",
            "Wrote the user and project documentation (README.md, docs/ENGLISH.md, docs/TESTING.md, docs/FEATURE_STATUS.md).",
        ],
        "modules": [
            "backend/app/services/english_companion.py, english_profile.py, english_vocab.py, ai_english.py, rewards.py, insights.py",
            "backend/app/routers/english.py, mentors.py, assessments.py, jobs/, admin/",
            "frontend/src/pages/student/English*.jsx, Vocabulary.jsx; pages/mentor/, recruiter/, admin/; src/english/",
            "backend/tests/, backend/tests_e2e/ci_smoke_browser.py, docs/",
        ],
        "deliverables": [
            "English module: conversation companion, vocabulary review, daily plan, progress and rewards",
            "Mentor, recruiter and admin portals including candidate comparison and printable report",
            "Test suites: 369 backend tests (2 Redis-only skipped), CI browser smoke test",
            "User documentation, feature status and test reports",
        ],
        "tech": ["Python", "FastAPI", "React", "Tailwind CSS", "Recharts", "pytest", "Vitest", "Playwright",
                 "GitHub Actions", "Markdown"],
        "workflow": [
            "Listed the mentor, recruiter and admin requirements and the English-learning features from the specification.",
            "Built the backend endpoints and services first, then the pages, using the shared component library.",
            "Wrote tests for each feature, especially access rules (who can see which student).",
            "Ran the full test suites before every merge and tracked regressions.",
            "Wrote and updated documentation after each feature was finished.",
        ],
        "challenges": [
            ("The English companion repeated itself and copied the student's sentences.",
             "Higher temperature (0.2 → 0.7) and a duplicate-reply check with one retry."),
            ("Recruiters must never see other companies' applicants or non-consented integrity data.",
             "Central access rules plus tests: another recruiter gets 404, a student gets 403, unshared sessions stay hidden."),
            ("Daily-plan items completed outside the English pages (e.g. an interview) were not detected.",
             "The plan is evaluated when it is viewed and pays points at most once per day."),
            ("Tests sometimes failed on Windows because of temp-folder permissions.",
             "A pytest.ini with a project-local temp folder, so a plain \"pytest tests\" works on every machine."),
        ],
        "learning": {
            "Skills learned": "Full-stack feature development, test design, documentation writing.",
            "Technical knowledge": "Spaced repetition, gamification design, access control testing, browser automation.",
            "Contribution to success": "Three of the four portals and the quality checks that keep the whole system working.",
            "Personal improvement": "Thinking like a user and a tester, and explaining features clearly in writing.",
        },
    },
]

TIMELINE = [  # phase, dates, lead, support
    ("Requirement analysis and specification", "9-10 Oct 2026", "Kaushal", "All members"),
    ("Architecture and database design", "10 Oct", "Kaushal", "Samrath"),
    ("UI design and design system", "10-12 Oct", "Yash", "Shardha"),
    ("Backend core, authentication and APIs", "10-14 Oct", "Samrath", "Kaushal"),
    ("AI integration (resume, questions, scoring, matching)", "10-25 Oct", "Kaushal", "Samrath"),
    ("Student portal frontend", "10-20 Oct", "Yash", "Aryan"),
    ("Live voice interview and 3D avatars", "10-11 Oct, refined to 29 Oct", "Aryan", "Yash"),
    ("English learning module", "10-11 Oct, extended 5 Nov", "Shardha", "Kaushal"),
    ("Recruiter, mentor and admin portals", "12-25 Oct", "Shardha", "Samrath"),
    ("Interview monitoring and security module", "11-25 Oct", "Aryan", "Samrath"),
    ("Move from SQLite to MongoDB", "late Oct", "Samrath", "Kaushal"),
    ("Performance and latency optimisation", "11 Oct - 4 Nov", "Aryan", "Yash, Kaushal"),
    ("UI redesign (Dark premium theme)", "4 Nov", "Yash", "Shardha"),
    ("Score calibration and real-model verification", "4-5 Nov", "Kaushal", "Shardha"),
    ("Testing (unit, API, browser E2E, CI)", "throughout; CI 5 Nov", "Shardha", "All members"),
    ("Deployment preparation (Docker, Render, Vercel)", "5 Nov", "Kaushal", "Samrath"),
    ("Documentation and final presentation", "5 Nov", "Shardha", "All members"),
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

ARCHITECTURE = [
    ("Frontend", "React 18 single-page app with four portals, built with Vite and Tailwind. Pages load on demand. The "
                 "3D interviewer uses three.js; camera monitoring uses MediaPipe in the browser."),
    ("Backend", "FastAPI application organised in routers (auth, students, interviews, english, jobs, mentors, admin, "
                "voice, monitoring) and services (AI, matching, rewards, integrity, speech)."),
    ("Database", "MongoDB through a small data layer (backend/app/odm/). Indexes and unique constraints are created "
                 "at start-up; the seed adds reference data."),
    ("AI module", "One gateway (services/ai_base.py) for every model call: Gemini first, backup Gemini models, then "
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
    "The project was a team effort. Kaushal's architecture and AI engine, Yash's design system and student portal, "
    "Samrath's database, security and APIs, Aryan's voice interview, avatars and monitoring, and Shardha's English "
    "module, three portals and quality assurance each form an essential part; no portal works without the others.",
    "Future improvements: testing the voice and camera features with real users and tuning the detector thresholds, "
    "OCR for scanned resumes, more languages for voice practice, a hosted deployment with a paid AI quota, load "
    "testing with many simultaneous users, and a mobile-friendly interview room.",
]

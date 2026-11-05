# Team Task Matrix — HireSense

Module ownership for the five team members, as agreed on 2026-11-05. Each member owns complete areas (backend logic,
UI, tests and docs for that area). Shares: Yash 30%, Kaushal 30%, Samrath 14%, Aryan 13%, Shardha 13%. The full
report with responsibilities, workflow, challenges, learning outcomes and a simple architecture and workflow section is
[HireSense_Team_Work_Distribution.pdf](HireSense_Team_Work_Distribution.pdf) (source: [team_report/](team_report/),
rebuild with `backend\venv\Scripts\python docs\team_report\build.py`).
The Git history shows one committer, so this table records ownership, not commit authorship.

## Matrix by member

| Member | Share | Role | Module ownership | Key files | Depends on | Testing | Deliverables |
|---|---|---|---|---|---|---|---|
| **Yash** | 30% | Project lead, architect, AI engine, testing and documentation | App wiring and config, AI gateway, Gemini + Ollama fallback, interview engine, scoring and calibration, resume analysis, job matching, test suites, CI, deployment, documentation | `backend/app/main.py`, `config.py`, `services/ai*.py`, `gemini_llm.py`, `local_llm.py`, `model_router.py`, `interview_engine.py`, `scoring_bands.py`, `matching.py`, `embeddings.py`; `backend/eval/`; `backend/tests/`, `tests_e2e/`; `.github/workflows/`; Docker / Render / Vercel files; `docs/` | All modules | Full pytest (369), real-model checks, calibration script, CI smoke test, latency benchmarks | AI engine, calibrated scoring, test suites, CI, deployment configs, documentation, final demo |
| **Kaushal** | 30% | Voice interview, 3D avatars, monitoring, English learning and portals | Live voice room, speech-to-text, text-to-speech, streamed turn, 3D interviewers, avatar compression, camera monitoring, integrity, attention; English companion, vocabulary, daily plan, rewards; mentor, recruiter (compare, report) and admin portals; assessments | `frontend/src/voice/`, `monitoring/`, `pages/student/VoiceInterview.jsx`, `English*.jsx`, `Vocabulary.jsx`, `pages/mentor/`, `recruiter/`, `admin/`; `backend/app/services/stt.py`, `tts.py`, `speech_stream.py`, `interviewers.py`, `integrity.py`, `attention.py`, `english_*.py`, `rewards.py`; `routers/voice.py`, `interview_live.py`, `monitoring.py`, `english.py`, `mentors.py`, `assessments.py`, `jobs/`, `admin/` | AI engine (Yash), API (Samrath), UI kit (Aryan) | Playwright E2E with fake camera/mic, access-rule tests | Live 3D voice interview, monitoring, English module, three portals |
| **Samrath** | 14% | Backend developer, database engineer | MongoDB data layer, models and schemas, authentication, access control, core routers, seed, rate limiting, consent, live notifications, health checks | `backend/app/odm/`, `models.py`, `schemas.py`, `database.py`, `security.py`, `deps.py`, `seed.py`, `routers/auth.py`, `common.py`, `students.py`, `services/access.py`, `limiter.py`, `consent.py`, `live_events.py` | AI (Yash), portals (Kaushal, Shardha) | pytest auth, permissions, workflows | Data layer, secure auth, REST API, SSE notifications |
| **Aryan** | 13% | Frontend foundation and design system | React/Vite setup, routing and guards, lazy loading, Dark premium design system, shared components, layout, charts, API client, auth state, live-notification client, sign-in screens | `frontend/src/App.jsx`, `main.jsx`, `api.js`, `auth.jsx`, `index.css`, `vite.config.js`, `components/ui.jsx`, `Layout.jsx`, `Logo.jsx`, `Tabs.jsx`, `charts.jsx`, `live/notificationStream.js`, `pages/Login.jsx`, `Register.jsx` | Backend APIs (Samrath) | Build report, manual UX review | Component library, routing, 1,130 → 236 kB first load |
| **Shardha** | 13% | Student portal pages and frontend testing | Student dashboard, interview pages and report, resume page, jobs, drives, applications, progress hub, rewards, profile, settings, notifications, privacy page, Vitest tests | `frontend/src/pages/student/` (Dashboard, Interviews, InterviewSetup, InterviewSession, PerformanceReport, Resume, Jobs, Applications, ProgressHub, Rewards), `pages/Profile.jsx`, `Settings.jsx`, `Privacy.jsx`, `components/scoreBand.js` | UI kit (Aryan), APIs (Samrath), AI results (Yash) | Vitest (141 tests) | Student portal, report page, frontend tests |

## Module responsibility matrix

| Major module | Owner | Supporting |
|---|---|---|
| System architecture, configuration, integration | Yash | All |
| AI engine (Gemini/Ollama, interview engine, scoring, resume, matching) | Yash | Samrath |
| Testing, CI and documentation | Yash | All |
| Deployment (Docker, Render, Vercel) | Yash | Samrath |
| Live voice interview, speech, 3D avatars | Kaushal | Yash |
| Interview monitoring and security module | Kaushal | Samrath |
| English learning, vocabulary, daily plan, rewards | Kaushal | Yash |
| Mentor, recruiter and admin portals | Kaushal | Samrath, Shardha |
| Database (MongoDB data layer), models, seed | Samrath | Yash |
| Authentication, security, access control, notifications | Samrath | Aryan |
| Frontend setup, design system, layout, API client | Aryan | Shardha |
| Student portal pages and frontend tests | Shardha | Aryan |

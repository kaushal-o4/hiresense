# Team Task Matrix — HireSense

Module ownership for the five team members, as agreed on 2026-11-05. Each member owns one complete area (backend
logic, UI, tests and docs for that area) and contributes an equal 20%. The full report with responsibilities,
workflow, challenges and learning outcomes is [HireSense_Team_Work_Distribution.pdf](HireSense_Team_Work_Distribution.pdf)
(source: [team_report/](team_report/), rebuild with `backend\venv\Scripts\python docs\team_report\build.py`).
The Git history shows one committer, so this table records ownership, not commit authorship.

## Matrix by member

| Member | Role | Module ownership | Key files | Depends on | Testing | Deliverables |
|---|---|---|---|---|---|---|
| **Kaushal** | Project lead, architect, AI engine | App wiring and config, AI gateway, Gemini + Ollama fallback, interview engine, scoring and calibration, resume analysis, job matching, CI and deployment | `backend/app/main.py`, `config.py`, `services/ai*.py`, `gemini_llm.py`, `local_llm.py`, `model_router.py`, `interview_engine.py`, `scoring_bands.py`, `matching.py`, `embeddings.py`; `backend/eval/`; `.github/workflows/`; Docker / Render / Vercel files | All modules | Real-model checks (`tests_integration`), calibration script, latency benchmarks | AI engine, calibrated scoring, CI, deployment configs, final demo |
| **Yash** | Frontend developer, UI/UX (student portal) | React app setup, design system, layout, student pages, charts, bundle performance | `frontend/src/App.jsx`, `api.js`, `auth.jsx`, `index.css`, `components/`, `pages/student/` (dashboard, interviews, report, resume, jobs, applications, progress, rewards) | Backend APIs (Samrath), AI results (Kaushal) | Vitest, manual UX review | Student portal, component library, 1,130 → 236 kB first load |
| **Samrath** | Backend developer, database engineer | MongoDB data layer, models and schemas, authentication, access control, core routers, seed, rate limiting, consent, live notifications, health checks | `backend/app/odm/`, `models.py`, `schemas.py`, `database.py`, `security.py`, `deps.py`, `seed.py`, `routers/auth.py`, `common.py`, `students.py`, `services/access.py`, `limiter.py`, `consent.py`, `live_events.py` | AI (Kaushal), portals (Yash, Shardha) | pytest auth, permissions, workflows | Data layer, secure auth, REST API, SSE notifications |
| **Aryan** | Voice interview, 3D avatar, monitoring | Live voice room, speech-to-text, text-to-speech, streamed turn, 3D interviewers, avatar compression, camera monitoring, integrity module, attention meter | `frontend/src/voice/`, `frontend/src/monitoring/`, `pages/student/VoiceInterview.jsx`; `backend/app/services/stt.py`, `tts.py`, `speech_stream.py`, `interviewers.py`, `integrity.py`, `attention.py`; `routers/voice.py`, `interview_live.py`, `monitoring.py` | AI engine (Kaushal), API (Samrath) | Playwright E2E with fake camera/mic, latency benchmarks | Live 3D voice interview, local speech pipeline, monitoring |
| **Shardha** | English learning, portals, QA lead | English companion, vocabulary review, daily plan, rewards, mentor portal, recruiter portal (compare, report), admin portal, assessments, test suites, documentation | `backend/app/services/english_*.py`, `rewards.py`, `routers/english.py`, `mentors.py`, `assessments.py`, `jobs/`, `admin/`; `frontend/src/pages/mentor/`, `recruiter/`, `admin/`, `English*.jsx`, `Vocabulary.jsx`; `backend/tests/`, `tests_e2e/ci_smoke_browser.py`; `docs/` | Backend (Samrath), UI kit (Yash) | Full pytest (369), CI smoke test, regression list | English module, three portals, test reports, user docs |

## Module responsibility matrix

| Major module | Owner | Supporting |
|---|---|---|
| System architecture, configuration, integration | Kaushal | All |
| AI engine (Gemini/Ollama, interview engine, scoring, resume, matching) | Kaushal | Samrath |
| Design system and student portal frontend | Yash | Shardha |
| Database (MongoDB data layer), models, seed | Samrath | Kaushal |
| Authentication, security, access control, notifications | Samrath | Shardha |
| Live voice interview, speech, 3D avatars | Aryan | Yash |
| Interview monitoring and security module | Aryan | Samrath |
| English learning, vocabulary, daily plan, rewards | Shardha | Kaushal |
| Mentor, recruiter and admin portals | Shardha | Samrath, Yash |
| Testing, CI and documentation | Shardha | All |
| Deployment (Docker, Render, Vercel) | Kaushal | Samrath |

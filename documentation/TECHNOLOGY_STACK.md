# HireSense AI: Technology Stack

Every technology below was found in the project's dependency files (`frontend/package.json`,
`backend/requirements.txt`, `backend/requirements-cloud.txt`) or configuration files (Dockerfiles,
`docker-compose.yml`, `.github/workflows/tests.yml`, `render.yaml`, `frontend/vercel.json`), and is used by the
files named.

## Overview

```
 Browser                          Server                                  Data / AI
 -------                          ------                                  ---------
 React 18 + React Router          FastAPI (Python 3.14) on uvicorn        MongoDB (pymongo)
 Tailwind CSS, lucide-react       Pydantic validation                     Ollama -> qwen3:4b (local LLM)
 Recharts (charts)                JWT (PyJWT) + Argon2 passwords          or Google Gemini API (hosted LLM)
 three.js (3D avatar)             pypdf / python-docx (resume text)       Sentence Transformers (embeddings)
 MediaPipe (on-device camera)     httpx (calls Ollama / Gemini)           scikit-learn (own classifier)
 Vite (dev server + build)        Server-Sent Events (streaming)          Whisper (speech-to-text)
 Vitest (unit tests)              pytest (tests)                          Kokoro-82M (text-to-speech)
```

Communication:
- browser to server: HTTP/JSON over `fetch` and Server-Sent Events, with an httpOnly cookie for login
- server to database: the MongoDB wire protocol (pymongo)
- server to Ollama/Gemini: HTTP (httpx)
- Whisper, Kokoro, the embedding model and the classifier: run inside the backend process

---

## 1. Programming languages

| Language | Where | Why |
|---|---|---|
| **Python 3.14** | `backend/` (all of `app/`, tests, ML training, scripts) | FastAPI and every AI/ML library used (Transformers, scikit-learn, Whisper) are Python |
| **JavaScript (ES modules) + JSX** | `frontend/src/` | React user interface |
| **CSS** (Tailwind utility classes + `index.css`) | `frontend/src/index.css`, class names in `.jsx` files | Styling and theme |
| **HTML** | `frontend/index.html` | The single page that React renders into |

## 2. Frontend

| Technology | Type | Where it is used | What it does / why |
|---|---|---|---|
| **React 18** (`react`, `react-dom`) | UI library | Every `.jsx` file; entry `src/main.jsx` | Builds the interface from components. State comes from hooks (`useState`, `useEffect`) and context (`AuthContext.jsx`). |
| **React Router 6** (`react-router-dom`) | Routing | `src/App.jsx`, `src/main.jsx` (`BrowserRouter`), pages using `useParams`/`useNavigate` | Maps URLs such as `/student/interviews/:id` to pages. Pages are lazy-loaded with `lazy()`. |
| **Vite 6** | Build tool / dev server | `vite.config.js`, `index.html` | Fast dev server on port 5173. Proxies `/api` to the backend so the login cookie is same-origin. Builds the production bundle. |
| **Tailwind CSS 3** + PostCSS + autoprefixer | Styling | `tailwind.config.js`, `postcss.config.js`, `src/index.css`, class names in components | Utility classes. Theme colours are CSS variables in `index.css`. |
| **lucide-react** | Icon set | Most pages and `components/AppShellLayout.jsx` | Icons. |
| **Recharts** | Charts | `src/components/DashboardCharts.jsx` (used by the dashboards and reports) | Bar, line, radar and timeline charts of scores and progress. |
| **three.js** | 3D graphics | `src/voice/Avatar3D.jsx`, `components/InterviewerStage.jsx` | Draws the 3D interviewer (`public/avatars/*.glb`) with lip sync and facial expressions. |
| **@mediapipe/tasks-vision** | On-device computer vision | `src/monitoring/faceMonitor.js`, `objectMonitor.js` | Face landmarks and object detection run in the browser for opt-in interview monitoring. No video is uploaded. |
| **Web APIs**: Fetch, Web Audio, MediaDevices, Web Workers, Fullscreen API | Browser | `apiClient.js`, `voice/recorder.js`, `voice/speechPlayer.js`, `monitoring/*`, `components/browserCodeRunner.js` | API calls, microphone recording, audio playback, camera, sandboxed code self-check. |
| **Vitest 3** | Test runner | `src/**/*.test.js` (14 files, 141 tests) | Unit tests of pure logic (state machines, lip-sync maths, monitoring rules). Run with `npm test`. |

## 3. Backend

| Technology | Type | Where it is used | What it does / why |
|---|---|---|---|
| **FastAPI** | Web framework | `app/main.py`, every file in `app/routers/` | Defines the 203 REST endpoints. Uses dependency injection (`Depends`) for the DB session and the logged-in user, and generates Swagger docs at `/docs`. |
| **uvicorn** | ASGI server | `start-backend.bat`, `backend/Dockerfile` | Runs the FastAPI app (`uvicorn app.main:app`). |
| **Pydantic 2** | Data validation | `app/request_validation_schemas.py`; AI output schemas in `services/**` | Validates request bodies (HTTP 422 on bad input) and the AI model's JSON output. |
| **pydantic-settings** | Configuration | `app/application_configuration.py` | Loads settings from `backend/.env` / environment variables. |
| **PyJWT** | Tokens | `app/password_and_token_security.py` | Signs and checks the login token (HS256) and password-reset tokens. |
| **argon2-cffi** | Password hashing | `app/password_and_token_security.py` | Stores passwords as salted Argon2 hashes. |
| **email-validator** | Validation | `request_validation_schemas.py` (`EmailStr`) | Valid email addresses. |
| **python-multipart** | Uploads | `student_portal_routes.upload_resume`, `voice_speech_routes` | Lets FastAPI receive file uploads (resumes, audio). |
| **pypdf**, **python-docx** | Document parsing | `services/resume_and_jobs/resume_text_extractor.py` | Extract text from PDF and DOCX resumes. |
| **httpx** | HTTP client | `services/ai_models/language_model_client.py`, `gemini_api_client.py` | Calls Ollama's local API and the Gemini API (streaming supported). |
| **Server-Sent Events** | Streaming | `live_voice_interview_routes.py`, `english_practice_routes.py`, `profile_and_notification_routes.py` | Streams the live interview turn, English replies and notification signals to the browser. |
| **redis** (optional, cloud profile) | Shared counters | `services/platform_support/rate_limiter.py` | Login lockout and rate limits shared between servers. Memory is used when it is not set. |
| **SMTP** (Python `smtplib`, optional) | Email | `services/platform_support/email_sender.py` | Password-reset and status emails when `SMTP_HOST` is set. |

## 4. Database

| Technology | Where | Why |
|---|---|---|
| **MongoDB** (Community Server locally; `mongo:7` in Docker and CI; Atlas when hosted) | All persistent data, in 49 collections | A document database: JSON-like reports, resume analyses and scores fit naturally |
| **pymongo** | `app/mongodb_data_layer/mongo_connection.py` | The official MongoDB driver |
| **Own data layer** `app/mongodb_data_layer/` | Used by every router and service | Keeps a SQLAlchemy-style API (`select`, `Session`, `relationship`) on MongoDB. See `DATABASE_DOCUMENTATION.md`. |

## 5. Artificial intelligence and machine learning

| Technology | Task | Files | Notes |
|---|---|---|---|
| **Ollama + qwen3:4b** (local; also the automatic fallback) | Writes interview questions, scores answers, feedback, reports, resume extraction, English replies, recommendations, MCQ drafts, code review | `services/ai_models/language_model_client.py` (client), `ai_structured_call_base.py` (validated JSON calls), `services/interview/ai_interview_service.py`, `services/resume_and_jobs/*`, `services/english/ai_english_conversation.py` | Runs on the same computer with `LOCAL_AI_PROVIDER=ollama` (`OLLAMA_MODEL=qwen3:4b`). The code default when nothing is configured is Ollama. Every reply is forced into a JSON schema and validated. |
| **Google Gemini API** (the provider set in `.env.example`) | Same tasks, hosted | `services/ai_models/gemini_api_client.py` | `LOCAL_AI_PROVIDER=gemini`. Retries and backup models are built in. Students must accept a data notice first (`hosted_ai_consent.py`). |
| **Sentence Transformers**, model `all-MiniLM-L6-v2` (+ PyTorch CPU) | Meaning similarity: job matching, off-topic answer check, duplicate-question check | `services/ai_models/sentence_embedding_model.py`, `semantic_job_matcher.py`, `ai_interview_service.answer_similarity` | Runs locally on the CPU (about 90 MB). |
| **scikit-learn** + **joblib** | The project's own classifier for question type and difficulty | Training: `backend/ml/train_question_classifier.py`. Runtime: `services/ai_models/question_type_classifier.py`. | Trained offline on `ml/data/interview_questions_dev.csv`. Used as a cross-check only. |
| **Whisper** via **faster-whisper** (default) or **transformers** | Speech-to-text of spoken answers | `services/voice/speech_to_text.py` | `STT_ENGINE=faster`, `STT_MODEL=base.en`, local CPU. |
| **Kokoro-82M** + **misaki**, **phonemizer-fork**, **espeakng-loader**, **soundfile** | Text-to-speech for the interviewer, with a mouth-shape timeline | `services/voice/text_to_speech.py` | Local CPU. Kokoro is installed with `--no-deps` (see README). espeak-ng is GPL-3.0. |
| **numpy** | Audio and vector maths | `speech_to_text.py`, `sentence_embedding_model.py` | |

Not AI, but important: many decisions are **plain rule-based Python** on purpose, so they are explainable:
- answer score caps
- adaptive difficulty
- the job-match formula
- readiness score
- skill-gap remedies
- monitoring severity

## 6. Testing and quality

| Tool | Where | What |
|---|---|---|
| **pytest** | `backend/tests/` (27 files), `tests_integration/` | API and logic tests with a mocked AI and a separate `hiresense_test` database. Integration tests use the real models. |
| **Vitest** | `frontend/src/**/*.test.js` | Frontend unit tests |
| **Playwright** (Chromium) | `backend/tests_e2e/` | Real-browser end-to-end checks (installed separately, run manually) |
| **GitHub Actions** | `.github/workflows/tests.yml` | Runs backend tests, a slim "cloud" profile and frontend tests + build on every push |

## 7. Deployment and tooling

| Technology | Files | Purpose |
|---|---|---|
| **Windows batch scripts** | `start.bat`, `start-backend.bat`, `start-frontend.bat` | One-click local start for the team |
| **Docker** + **docker-compose** | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | Containers for MongoDB, the API and the frontend |
| **nginx** | `frontend/nginx.conf.template` | Serves the built frontend and forwards `/api` in the container |
| **Render** / **Vercel** | `render.yaml`, `frontend/vercel.json` | Hosting configuration for a public demo |
| **Blender** (offline) | `frontend/avatar-src/*.py` | Converting and compressing the 3D avatar models (run once, not part of the app) |
| **npm**, **pip/venv** | `package.json`, `requirements*.txt` | Dependency management |

## 8. How the technologies talk to each other

1. **React page to FastAPI.**
   - `apiClient.js` calls `fetch("/api/...", {credentials: "include"})`.
   - In development, Vite proxies `/api` to `http://127.0.0.1:8000`.
   - The httpOnly cookie carries the JWT.
2. **FastAPI to MongoDB.**
   - `Depends(get_db)` gives each request a Session of the data layer, which uses pymongo.
3. **FastAPI to the AI model.**
   - A service calls `_structured_call()`, then `language_model_client.chat_json()`.
   - That sends an HTTP POST to Ollama (`127.0.0.1:11434/api/chat`) or to the Gemini API, with a JSON schema.
   - The reply is validated by Pydantic.
4. **Voice.**
   - The browser records WAV and uploads it. Whisper turns it into text.
   - The text is scored like a typed answer.
   - The next question is streamed: sentences go to Kokoro, and audio plus mouth shapes come back over
     Server-Sent Events to `speechPlayer.js` and `Avatar3D.jsx` (three.js).
5. **Monitoring.**
   - MediaPipe runs in the browser, and only small event records are posted to FastAPI.

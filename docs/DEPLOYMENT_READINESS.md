# Deployment readiness

Status as of 2026-11-04. "Verified" means run on the development laptop (Windows). **Nothing has run on a real
hosting provider yet.** Step-by-step hosting guide: [DEPLOY.md](DEPLOY.md).

There are two ways to run HireSense:

- **Local profile** (development laptop): Ollama `qwen3:4b` or Gemini, Kokoro voice, faster-whisper speech
  recognition, sentence embeddings. `requirements.txt`, `backend/.env.example`.
- **Cloud profile** (hosted demo): Gemini only, browser voice, Gemini speech recognition, keyword matching.
  `requirements-cloud.txt` (no PyTorch/numpy), `backend/.env.cloud.example`, `backend/Dockerfile`.

| Area | Status | Evidence / gap |
|---|---|---|
| Automated tests | Verified | 320 backend tests pass (mocked models, MongoDB test database) plus 124 frontend tests. `tests/test_deploy.py` also passes in a clean `requirements-cloud.txt` environment, where the Redis tests run against fakeredis. CI (`.github/workflows/tests.yml`) runs the mocked suite with a MongoDB service. `tests_integration` (real models) and `tests_e2e` (Playwright) are run by hand. |
| Cloud profile without heavy packages | Verified | The API was started from a venv with only `requirements-cloud.txt` installed (no torch, numpy, transformers, kokoro, faster-whisper, sentence-transformers). Health, registration, consent, a voice-mode interview from the question bank, a typed answer and a Gemini-STT request (clear 503 without a key) all worked with no errors in the log. Fixed on the way: `embeddings.embed` imported numpy even with embeddings off. |
| Configuration | Verified (tests) | `SECRET_KEY` placeholder: the app warns, and refuses to start when `COOKIE_SECURE=true`. Render generates the key. All settings come from environment variables. |
| Database | Partial | MongoDB (`app/odm.py`), indexes created at start-up, seed is idempotent (run twice in CI). docker-compose enables MongoDB authentication. **Not yet run against MongoDB Atlas**; `mongodb+srv://` support (dnspython) is installed. No backup schedule: Atlas M0 has none, so take `mongodump` exports for anything you keep. |
| Auth / cookies | Verified (tests) | httpOnly session cookie, `SameSite=Lax` by default; `COOKIE_SAMESITE=none` (Secure forced) for an API on another domain; logout repeats the attributes. Login lockout (8 failures / 15 min), password reset. |
| Rate limiting | Verified (tests) | One sliding-window limiter (`services/limiter.py`) for login lockout, reset requests, voice and monitoring limits. It uses Redis when `REDIS_URL` is set (shared by all workers, survives restarts) and falls back to memory if Redis is down. Plus a per-user daily AI cap. Still no general per-IP API limit. |
| Multi-process state | Limit | With `REDIS_URL` the limits are shared. The AI concurrency gate, the streamed-reply guard and per-interview turn locks are still in process memory: run **one** API instance. |
| Proxy / client IP | Verified (simulated) | The container runs uvicorn with `--proxy-headers`; with `X-Forwarded-For` set, the audit log recorded the forwarded client IP. |
| Health checks | Verified | `/api/health/live` (process up: Docker HEALTHCHECK, Render health check) and `/api/health/ready` (database required; AI parts reported as `degraded`, never faked). |
| Graceful shutdown | Verified (tests) | Background jobs (answer feedback, prefetch, streamed turns, emails) are tracked (`services/background.py`) and drained for up to `SHUTDOWN_GRACE_SECONDS` (20 s) on shutdown. uvicorn's `--timeout-graceful-shutdown 25`; compose `stop_grace_period: 30s`. An answer whose feedback is cut off keeps its score; its feedback can be regenerated ("retry evaluation"). |
| Containers | Written, not built | `backend/Dockerfile` (python:3.14-slim, non-root, healthcheck), `frontend/Dockerfile` + `nginx.conf.template` (SPA fallback, unbuffered SSE proxy, immutable asset caching), `docker-compose.yml`. **Docker is not installed on the development laptop, so the images have not been built.** The container's start command and file layout were reproduced outside Docker and worked. |
| Hosting configs | Written, not deployed | `render.yaml` (free Docker web service), `frontend/vercel.json` (`/api` rewrite, SPA fallback, caching). The API host placeholder in `vercel.json` must be replaced. Not yet checked: streamed replies and ~5 MB uploads through Vercel's external rewrite (DEPLOY.md has option B for that case). |
| Privacy / consent | Verified (tests + browser) | With Gemini, students agree to a data notice (registration checkbox, an in-page notice before interviews, resume analysis and English practice, a Settings toggle to withdraw). The agreement is stored as `users.ai_data_consent_at` and in the audit log. AI endpoints return 428 until then. `/privacy` describes the configured provider. `tests_e2e/consent_browser.py`: 11/11. The wording has not been reviewed by a lawyer. |
| Logging | Partial | Prompt, answer and audio content is never logged. Errors go to `ErrorLog` (traceback, no body). Request IDs on every response. No log shipping or metrics export. |
| Uploads | Partial | Size and type checks, not served publicly, no antivirus scan. On Render's free plan the disk is temporary: resume files are lost on restart (the text and analysis stay in MongoDB). |
| AI inference | Depends on Google | The cloud profile needs a Gemini key with enough quota. With `AI_FALLBACK_TO_OLLAMA=false` a Gemini outage means interviews fall back to the question bank and evaluation waits. Measured on the laptop with Gemini 3.5 Flash: scoring ~1.1 s, feedback/report ~2.3 s, resume ~5 s (`tests_perf/results/prompts_*.json`). Gemini speech recognition latency is **unmeasured**. |
| Voice in the cloud | Reduced | Interviewer voice = the browser's speech synthesis (approximate lip sync). Recognition = Gemini per speech segment, no live captions. The local profile keeps Kokoro + faster-whisper. |
| Real-user testing | Not done | Voice and camera have only been tested with fake devices, never a real person's mic/camera, on either profile. |

## Before go-live (demo)

1. Atlas cluster, user and network access (DEPLOY.md step 1).
2. Gemini key with a quota alert.
3. Render blueprint with `MONGODB_URL`, `GEMINI_API_KEY`, `ADMIN_PASSWORD`, `FRONTEND_URL`, `CORS_ORIGINS`.
4. Replace the API host in `frontend/vercel.json`, import `frontend/` into Vercel.
5. Try one live interview and one resume upload through the Vercel URL, with a real microphone.

## Before go-live (a real placement cell)

Everything above, plus: a paid always-on API instance with a persistent disk, Redis, Atlas backups (M10+), a
reviewed privacy notice and data-processing terms with Google, load testing of `AI_MAX_CONCURRENT` against the Gemini
quota, and log shipping.

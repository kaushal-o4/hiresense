# Deployment readiness

Status as of 2026-10-25. "Verified" means run on the development laptop only. **Nothing here has been tested on a
production host.**

| Area | Status | Evidence / gap |
|---|---|---|
| Automated tests | Verified | 254 backend tests pass (mocked models); `tests_integration` (real models) and `tests_e2e` (Playwright) are run by hand. CI (`.github/workflows/tests.yml`) runs the mocked suite only. |
| Configuration | Partial | `backend/.env.example` is complete and has no secrets. `SECRET_KEY` has a public placeholder default: **must be changed**. The app warns at startup and refuses to start with a placeholder or short key when `COOKIE_SECURE=true`; with `COOKIE_SECURE=false` it only warns. |
| Database | Partial | SQLite (WAL) in development; PostgreSQL documented (`requirements-postgres.txt`, README §4) but **not tested** with this code. Alembic migrations exist. |
| Auth / roles | Verified (tests) | Cookie sessions, role checks, login throttle (15 min lockout), password reset. `COOKIE_SECURE=true` required behind HTTPS. |
| Rate limiting | Partial | Login, voice (TTS/STT/warmup), monitoring events, and a per-user daily AI cap exist. No general per-IP API limit and none on English messages other than the daily AI cap. |
| Multi-process state | Limit | Login lockout, voice rate limits, the AI concurrency gate and the streaming-reply guard are in process memory. Run **one** API worker, or move them to Redis first. |
| Health checks | Added 2026-10-25 | `/api/health/live`, `/api/health/ready` (database required; AI components reported as `degraded`, never faked). |
| Request IDs | Added 2026-10-25 | `X-Request-ID` returned on every response; slow requests are logged with path only. |
| Logging | Partial | Prompt and answer text are never logged. Errors go to `ErrorLog` (traceback, no body). No log shipping or metrics export. |
| Graceful shutdown | Not implemented | Background threads (warm-up, feedback) are daemon threads; no drain on SIGTERM. |
| Container / process manager | Not implemented | No Dockerfile or service definition. `start.bat` is for development. |
| AI inference host | **Blocker** | The app assumes an Ollama server on `OLLAMA_BASE_URL` with the model already pulled. The production host must have Ollama, the model files, and enough RAM/VRAM (qwen3:4b needs ~3.5 GB). No GPU is assumed; CPU-only token speed has **not been measured**. |
| Voice models | **Blocker** | Kokoro and Whisper download from Hugging Face on first use and run in the API process (CPU torch). Needs ~0.5 GB disk and RAM headroom, plus outbound network on first start or pre-baked model files. |
| Concurrency | Limit | `AI_MAX_CONCURRENT=1`: one generation at a time, interactive before background. Several simultaneous students will queue; capacity under load is **unmeasured**. |
| Uploads | Partial | Size limit (`MAX_UPLOAD_MB`), type checks. Not served publicly. No antivirus scan. |
| Real-user testing | Not done | Voice and camera were only exercised with fake devices, never a real person's mic/camera. |

## Hosted vs local inference (decision needed)
Local inference costs no per-request fees and keeps resumes and answers on your server, but one 4B model on a laptop
GPU generates ~20 tokens/s, so a full interview turn is 7-11 s and parallel users queue. A hosted model would reduce
latency and hardware needs but sends candidate data to a third party, which needs a privacy review and candidate
consent text. Nothing hosted is wired in. Recommendation: keep local-first, measure on the real server, and only add a
hosted option behind an explicit setting.

## Before go-live
1. Choose the inference host; install Ollama there; `ollama pull` the model(s); set `OLLAMA_BASE_URL`.
2. Set a real `SECRET_KEY`, `COOKIE_SECURE=true`, `CORS_ORIGINS`, `FRONTEND_URL`, SMTP.
3. Decide SQLite vs PostgreSQL; if PostgreSQL, run the full suite against it.
4. Run `tests_perf/bench_interview_latency.py` and `bench_models.py` on that host.
5. Put the API behind HTTPS and a reverse proxy; point the orchestrator at `/api/health/live` and `/api/health/ready`.
6. Try one full interview and one English session with a real microphone and camera.

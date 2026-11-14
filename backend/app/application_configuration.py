# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/application_configuration.py
#
# FILE PURPOSE:
# Holds every configurable setting of the backend (database URL, secret key, AI provider, model names,
# limits, email, cookies) and loads their values from environment variables or backend/.env.
#
# MAIN RESPONSIBILITY:
# Single source of truth for application settings.
#
# WHAT THIS FILE DOES:
# 1. Defines the `Settings` class with a default value for every option.
# 2. Reads overrides from backend/.env and environment variables using pydantic-settings.
# 3. Provides derived helpers such as the CORS origin list and cookie SameSite mode.
# 4. Returns one cached Settings object through get_settings().
#
# HOW THIS FILE WORKS:
# pydantic-settings maps each field (e.g. `mongodb_url`) to an environment variable (MONGODB_URL).
# get_settings() is wrapped in a cache so the .env file is read only once per process.
#
# IMPORTANT FUNCTIONS:
#    - get_settings()
#        Returns the cached Settings object used by the whole backend.
#
# IMPORTANT CLASSES:
#    - Settings
#
# IMPORTANT VARIABLES / SETTINGS:
#    BASE_DIR
#
# INPUT:
# Environment variables and the backend/.env file.
#
# OUTPUT:
# A Settings object (e.g. settings.secret_key, settings.ollama_model, settings.mongodb_url).
#
# FILES CONNECTED TO THIS FILE:
#    Used by: app/database_connection.py, app/main.py, app/password_and_token_security.py,
#    app/reset_admin_password.py, app/routers/authentication_routes.py,
#    app/routers/jobs/job_shared_helpers.py, app/routers/live_voice_interview_routes.py,
#    app/routers/profile_and_notification_routes.py, app/routers/student_portal_routes.py,
#    app/routers/voice_speech_routes.py, app/seed_initial_data.py,
#    app/services/ai_models/ai_structured_call_base.py,
#    app/services/ai_models/ai_task_model_router.py, app/services/ai_models/gemini_api_client.py,
#    app/services/ai_models/language_model_client.py,
#    app/services/ai_models/question_type_classifier.py,
#    app/services/ai_models/sentence_embedding_model.py,
#    app/services/monitoring/performance_timing.py, app/services/platform_support/email_sender.py,
#    app/services/platform_support/hosted_ai_consent.py,
#    app/services/platform_support/rate_limiter.py,
#    app/services/resume_and_jobs/ai_resume_analyzer.py,
#    app/services/resume_and_jobs/semantic_job_matcher.py, app/services/voice/speech_to_text.py,
#    app/services/voice/text_to_speech.py
#    Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/conftest.py,
#    tests/test_account_security.py, tests/test_deploy.py, tests/test_features.py,
#    tests/test_gemini.py, tests/test_health_and_routing.py, tests/test_latency_and_monitoring.py,
#    tests/test_live_notifications_and_recruiter.py, tests/test_voice.py,
#    tests_integration/conftest.py, tests_perf/bench_interview_latency.py,
#    tests_perf/bench_models.py, tests_perf/bench_prompts.py, tests_perf/bench_stt.py
#
# EXECUTION FLOW:
#    Module imported
#       |
#       v
#    get_settings() called
#       |
#       v
#    Values read from .env / environment
#       |
#       v
#    Same Settings object reused
#
# IMPORTANT DEPENDENCIES:
#    pydantic_settings
#
# IMPORTANT NOTE:
# Secrets are never hard-coded here; real values live in backend/.env, which is not committed to git.
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Application settings loaded from environment variables / backend/.env.

Uses pydantic-settings. Secrets such as SECRET_KEY are never hard-coded.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_name: str = "HireSense"
    environment: str = "development"
    # MongoDB server and database name. The local Windows service listens on 127.0.0.1:27017 by default.
    mongodb_url: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "hiresense"

    secret_key: str = "change-me-in-production-please-use-a-long-random-string"
    access_token_minutes: int = 60 * 12
    cookie_secure: bool = False
    # "lax" (default) when the frontend reaches the API on the same site (Vite proxy, Vercel /api rewrite, nginx).
    # "none" only when the browser calls the API on a different domain (VITE_API_URL); it requires COOKIE_SECURE=true.
    cookie_samesite: str = "lax"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional Redis for the login lockout and rate limits (shared by all API workers). Empty = in process memory.
    redis_url: str = ""
    # Seconds to let running background jobs (answer feedback, reports, emails) finish when the server stops.
    shutdown_grace_seconds: float = 20.0
    # Store per-step timings for the admin performance dashboard (never stores candidate content)
    perf_metrics_enabled: bool = True
    # Live notifications (GET /api/notifications/stream, Server-Sent Events). A comment line is sent every
    # heartbeat so proxies keep the connection open; each stream ends after max_seconds and the browser reconnects
    # (this also re-checks the login, so a stream never outlives its session).
    notifications_heartbeat_seconds: float = 20.0
    notifications_stream_max_seconds: float = 600.0

    # Initial admin account, created by `python -m app.seed_initial_data`. Leave the password empty to have the seed generate a
    # random one and print it once. Never ship the old published default.
    admin_email: str = "admin@hiresense.app"
    admin_password: str = ""

    # Outgoing email (password resets, application updates). Empty SMTP_HOST = email off: reset links are then
    # printed to the server log so an administrator can pass them on.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "HireSense <no-reply@hiresense.local>"
    smtp_starttls: bool = True
    frontend_url: str = "http://localhost:5173"  # used to build links in emails
    password_reset_minutes: int = 30

    # Language model. With the "ollama" provider everything runs on this computer; with "gemini" prompts go to Google.
    ai_enabled: bool = True
    # "gemini" (Google Gemini API, hosted: prompts incl. resumes and answers are sent to Google), "ollama" (local)
    # or "none". See services/ai_models/gemini_api_client.py.
    local_ai_provider: str = "ollama"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    # "gemini-flash-latest" is Google's alias for the newest Flash model. If the configured model is not offered to
    # this key, the newest available Flash model is used instead (see gemini_llm.runtime_status).
    gemini_model: str = "gemini-flash-latest"
    gemini_model_fast: str = ""  # optional per-tier models (empty = gemini_model), same tiers as Ollama
    gemini_model_strong: str = ""
    # Thinking makes replies slower; JSON scoring/chat here doesn't need it. minimal | low | medium | high | off
    gemini_thinking: str = "minimal"
    # Longest wait for Gemini's first/next streamed piece. Measured 2026-10-29: when Gemini is overloaded, requests
    # hang for minutes or end in 503, so give up early and let the Ollama fallback answer.
    gemini_timeout_seconds: float = 20.0
    # Other Gemini models to try, in order, when the chosen one is overloaded (503/429/5xx) or has not started
    # answering within gemini_switch_after_seconds. Measured 2026-11-04: gemini-flash-latest (3.8) hung or returned
    # 503 "high demand" for most requests while 3.5 Flash / Flash-Lite answered in ~1.7 s. Comma separated.
    gemini_backup_models: str = "gemini-3.5-flash,gemini-3.5-flash-lite"
    # How long to wait for the first streamed piece before moving on to the next model (when one is left).
    gemini_switch_after_seconds: float = 8.0
    # A model that was overloaded is skipped for this long (other models are tried first).
    gemini_model_cooldown_seconds: float = 180.0
    gemini_max_concurrent: int = 8
    gemini_retries: int = 2  # on rate limits (429), Google-side errors (5xx) and dropped connections, with backoff
    # If Gemini fails (no key, network down, quota used up), answer with the local Ollama model instead.
    ai_fallback_to_ollama: bool = True
    # After Gemini fails (timeout, overload, quota), send requests straight to Ollama for this long, so only one
    # request pays for the failed attempt. 0 = try Gemini first every time.
    gemini_cooldown_seconds: float = 120.0
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    # Optional per-tier models (empty = use ollama_model). See services/ai_models/ai_task_model_router.py.
    ollama_model_fast: str = ""
    ollama_model_strong: str = ""
    # Context window in tokens (prompt + answer). 4096 holds the largest prompt the app sends (~2,700 tokens measured,
    # role recommendations) and is small enough for the whole qwen3:4b to fit on a 4 GB GPU (8192 left 45% on the CPU).
    ollama_num_ctx: int = 4096
    # Model layers placed on the GPU: 99 = all, -1 = let Ollama decide. Ollama keeps ~1 GB of VRAM spare and so put
    # only 23 of 37 layers on the 4 GB RTX 3050; the CPU half then slowed generation (17 vs 25 tokens/s) and starved the
    # speech engine running beside it. If loading with all layers fails, local_llm falls back to Ollama's choice.
    ollama_num_gpu: int = 99
    ollama_keep_alive: str = "30m"  # how long Ollama keeps the model in memory after a request
    ai_temperature: float = 0.2
    ai_max_output_tokens: int = 4096  # upper limit for any single model reply
    ai_timeout_seconds: float = 240.0
    ai_max_concurrent: int = 1  # simultaneous generations; keep at 1 on a laptop
    ai_daily_limit_per_user: int = 200
    max_resume_chars: int = 9000  # resume text sent to the model is truncated to this length (fits OLLAMA_NUM_CTX)

    # Sentence-embedding model for semantic job matching ("none" disables it).
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Job-match weights (re-normalised over the parts that apply to a job). See services/resume_and_jobs/semantic_job_matcher.py.
    match_weight_required: float = 0.50
    match_weight_preferred: float = 0.15
    match_weight_semantic: float = 0.20
    match_weight_experience: float = 0.15

    # Voice interview: local text-to-speech (Kokoro-82M) and speech-to-text (Whisper). Both run on this computer.
    tts_enabled: bool = True
    tts_voice: str = "af_heart"  # female US English; see services/voice/text_to_speech.py VOICES
    tts_speed: float = 1.0
    stt_enabled: bool = True
    # "faster" (faster-whisper, default) or "transformers"; see services/voice/speech_to_text.py. Model: base.en / small.en / ...
    stt_engine: str = "faster"
    stt_model: str = "base.en"
    stt_threads: int = 0  # CPU threads for faster-whisper (0 = its default)
    voice_max_answer_seconds: int = 180
    # End-of-answer detection in the browser (silence after speech). Students can change it in the room settings;
    # coaching mode waits longer so slower speakers and beginners are not cut off. Measured (tests_e2e/
    # partial_transcript_check.py): an ordinary pause between two spoken sentences reads as 1.3-2 s of "silence"
    # to the detector (soft sentence endings fall below its level threshold), so 1.0 s cut answers off after the
    # first sentence. 2.0 s / 3.0 s did not.
    voice_end_of_speech_ms: int = 2000
    voice_end_of_speech_coaching_ms: int = 3000
    voice_min_speech_ms: int = 1200  # this much speech must be heard before a pause can end the answer
    # CPU threads for Kokoro (0 = PyTorch default). Fewer threads leave CPU for Ollama while both run at once.
    tts_torch_threads: int = 0

    # Trained question classifier (see backend/ml/train_question_classifier.py)
    question_classifier_path: str = str(BASE_DIR / "ml" / "models" / "question_classifier.joblib")

    upload_dir: str = str(BASE_DIR / "uploads")
    max_upload_mb: int = 5

    @property
    def samesite(self) -> str:
        v = self.cookie_samesite.strip().lower()
        return v if v in ("lax", "strict", "none") else "lax"

    @property
    def sends_data_to_google(self) -> bool:
        """True when resumes/answers go to the hosted Gemini API (the consent text is then shown)."""
        return self.ai_enabled and self.local_ai_provider.strip().lower() == "gemini"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

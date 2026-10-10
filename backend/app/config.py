from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_name: str = "HireSense"
    environment: str = "development"
    database_url: str = f"sqlite:///{(BASE_DIR / 'hiresense.db').as_posix()}"

    secret_key: str = "change-me-in-production-please-use-a-long-random-string"
    access_token_minutes: int = 60 * 12
    cookie_secure: bool = False

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Store per-step timings for the admin performance dashboard (never stores candidate content)
    perf_metrics_enabled: bool = True

    # Initial admin account, created by `python -m app.seed`
    admin_email: str = "admin@hiresense.app"
    admin_password: str = "Admin@12345"

    # Local AI. Everything runs on this computer; no student data is sent to an external service.
    ai_enabled: bool = True
    local_ai_provider: str = "ollama"  # "ollama" or "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_num_ctx: int = 8192  # context window in tokens (prompt + answer)
    ollama_keep_alive: str = "30m"  # how long Ollama keeps the model in memory after a request
    ai_temperature: float = 0.2
    ai_max_output_tokens: int = 4096  # upper limit for any single model reply
    ai_timeout_seconds: float = 240.0
    ai_max_concurrent: int = 1  # simultaneous generations; keep at 1 on a laptop
    ai_daily_limit_per_user: int = 200
    max_resume_chars: int = 12000  # resume text sent to the model is truncated to this length

    # Sentence-embedding model for semantic job matching ("none" disables it).
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Job-match weights (re-normalised over the parts that apply to a job). See services/matching.py.
    match_weight_required: float = 0.50
    match_weight_preferred: float = 0.15
    match_weight_semantic: float = 0.20
    match_weight_experience: float = 0.15

    # Voice interview: local text-to-speech (Kokoro-82M) and speech-to-text (Whisper). Both run on this computer.
    tts_enabled: bool = True
    tts_voice: str = "af_heart"  # female US English; see services/tts.py VOICES
    tts_speed: float = 1.0
    stt_enabled: bool = True
    stt_model: str = "openai/whisper-base.en"
    voice_max_answer_seconds: int = 180
    # End-of-answer detection in the browser (silence after speech). Students can change it in the room settings;
    # coaching mode waits longer so slower speakers and beginners are not cut off.
    voice_end_of_speech_ms: int = 1000
    voice_end_of_speech_coaching_ms: int = 1800
    voice_min_speech_ms: int = 1200  # this much speech must be heard before a pause can end the answer
    # CPU threads for Kokoro (0 = PyTorch default). Fewer threads leave CPU for Ollama while both run at once.
    tts_torch_threads: int = 0

    # Trained question classifier (see backend/ml/train_question_classifier.py)
    question_classifier_path: str = str(BASE_DIR / "ml" / "models" / "question_classifier.joblib")

    upload_dir: str = str(BASE_DIR / "uploads")
    max_upload_mb: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

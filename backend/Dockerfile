# HireSense API - cloud profile (Gemini, no PyTorch/Ollama/Whisper/Kokoro). ~250 MB image.
# Build:  docker build -t hiresense-api backend
# Run:    docker run -p 8000:8000 --env-file backend/.env.cloud hiresense-api
# Used by docker-compose.yml and by Render (render.yaml). Settings: backend/.env.cloud.example.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    UPLOAD_DIR=/data/uploads \
    LOCAL_AI_PROVIDER=gemini \
    AI_FALLBACK_TO_OLLAMA=false \
    EMBEDDING_PROVIDER=none \
    TTS_ENABLED=false \
    STT_ENGINE=gemini

WORKDIR /app
COPY requirements-cloud.txt .
RUN pip install -r requirements-cloud.txt

# Non-root user; uploads go to /data (mount a volume there to keep resume files across restarts)
RUN useradd --create-home --uid 10001 hiresense && mkdir -p /data/uploads && chown -R hiresense /data
COPY --chown=hiresense app ./app
COPY --chown=hiresense ml ./ml
USER hiresense

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health/live', timeout=4)"

# Seed is idempotent (admin account, badges, question bank); then serve. --proxy-headers: real client IPs behind
# Render/nginx. On SIGTERM uvicorn finishes open requests, then the app drains background jobs (SHUTDOWN_GRACE_SECONDS).
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 25"]

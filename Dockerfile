# StudyWise AI — FastAPI API image for Render (or any container host).
# Build from the repository root so ml/models is available to ml_service.BASE_DIR.
#
#   docker build -t studywise-api .
#   docker run --rm -p 8000:8000 --env-file backend/.env studywise-api
#
# Do not put secrets in this file. Configure them on the host.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System CA bundle for MongoDB Atlas TLS
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt

# Application code (WORKDIR for uvicorn imports = backend/)
COPY backend/app /app/backend/app
COPY ml/models /app/ml/models

# Local PDF/RAG dirs for free-tier / ephemeral hosts (files may vanish on restart).
# Paid Render plans can override via PDF_STORAGE_DIR / RAG_STORAGE_DIR to a mounted disk.
RUN mkdir -p /tmp/studywise/documents /tmp/studywise/rag \
    /app/backend/storage/documents /app/backend/storage/rag

WORKDIR /app/backend

# Single worker: in-process auth rate limits + local PDF/RAG indexes are process-local.
# Use shell form so $PORT from the platform is expanded.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1

FROM node:20-slim AS ui
WORKDIR /ui
COPY src/oipulse/frontend/package.json src/oipulse/frontend/package-lock.json ./
RUN npm ci
COPY src/oipulse/frontend/ ./
RUN npm run build

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for curl_cffi (libcurl-impersonate ships its own binary, but we
# need basic libs for building wheels of pandas/numpy on slim).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Kolkata

COPY pyproject.toml requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
COPY --from=ui /ui/dist src/oipulse/frontend/dist

RUN mkdir -p data logs data/raw data/parquet data/exports

EXPOSE 8000

# Default: FastAPI + React UI. Override with `docker run ... python orchestrator.py ...`
CMD ["uvicorn", "src.oipulse.main:app", "--host", "0.0.0.0", "--port", "8000"]

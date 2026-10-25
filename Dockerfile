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

RUN mkdir -p data logs data/raw data/parquet data/exports

EXPOSE 8501

# Default: launch the dashboard. Override with `docker run ... python orchestrator.py ...`
CMD ["streamlit", "run", "src/webapp/Home.py", "--server.address", "0.0.0.0", "--server.port", "8501"]

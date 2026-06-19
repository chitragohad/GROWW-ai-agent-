# Groww Pulse — Railway API & worker image (Python 3.11 + ML deps)
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY pulse/ pulse/
COPY config/ config/
COPY scripts/railway-weekly-pulse.sh scripts/railway-weekly-pulse.sh

RUN pip install --no-cache-dir -e ".[web]" \
    && chmod +x scripts/railway-weekly-pulse.sh

ENV PULSE_DATA_DIR=/data \
    HF_HOME=/data/hf-cache \
    PYTHONUNBUFFERED=1

EXPOSE 8001

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8001') + '/health')"

CMD ["sh", "-c", "uvicorn pulse.api.server:app --host 0.0.0.0 --port ${PORT:-8001}"]

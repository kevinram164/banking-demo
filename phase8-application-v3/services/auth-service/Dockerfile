# Multi-stage + venv --copies: Kaniko hay miss symlink venv → thiếu /app/venv/bin/uvicorn
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_USER=0 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY phase8-application-v3/common /app/common
COPY phase8-application-v3/services/auth-service /app

RUN python -m venv --copies /app/venv \
    && rm -f /app/venv/lib64 \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install --no-cache-dir -r common/requirements.txt \
    && /app/venv/bin/python -c "import uvicorn; print(uvicorn.__file__)" \
    && test -x /app/venv/bin/uvicorn

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/venv/bin:$PATH" \
    VIRTUAL_ENV=/app/venv

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app /app
RUN chmod -R a+rX /app/venv && test -x /app/venv/bin/uvicorn

EXPOSE 8001
CMD ["/app/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

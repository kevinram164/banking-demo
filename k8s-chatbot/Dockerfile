# Multi-stage: build frontend + backend
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /app/dist ./frontend/dist

EXPOSE 8080
# Auto-instrumentation: wrap uvicorn, gửi traces tới OTEL Collector (không sửa code app)
# Format: opentelemetry-instrument [opts] python -m uvicorn ... (không dùng subcommand "run" — gây execv NoneType)
CMD ["opentelemetry-instrument", "--traces_exporter", "otlp", "python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

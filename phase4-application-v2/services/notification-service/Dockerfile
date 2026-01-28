FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy common library
COPY phase4-application-v2/common /app/common

# Copy service files
COPY phase4-application-v2/services/notification-service /app

# Install dependencies
RUN pip install --no-cache-dir -r common/requirements.txt

EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]

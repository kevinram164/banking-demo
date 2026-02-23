FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY phase8-application-v3/common /app/common
COPY phase8-application-v3/services/account-service /app

RUN pip install --no-cache-dir -r common/requirements.txt

EXPOSE 9999
CMD ["python", "main.py"]

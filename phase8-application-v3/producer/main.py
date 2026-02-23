"""
API Producer — Phase 8
Receives HTTP from Kong, publishes to RabbitMQ, waits for response via Redis.
"""
import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aio_pika
from redis.asyncio import Redis

from common.rabbitmq_utils import path_to_queue, publish_and_wait
from common.redis_utils import create_redis_client
from common.logging_utils import get_json_logger, log_event
from common.observability import instrument_fastapi

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
CORS_ORIGINS = "http://localhost:3000,https://npd-banking.co,http://npd-banking.co"

logger = get_json_logger("api-producer")

redis: Redis | None = None
rmq_connection: aio_pika.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis, rmq_connection
    redis = await create_redis_client(REDIS_URL)
    rmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
    yield
    if redis:
        await redis.close()
    if rmq_connection:
        await rmq_connection.close()


app = FastAPI(title="API Producer", lifespan=lifespan)
instrument_fastapi(app, "api-producer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check — phải định nghĩa TRƯỚC catch-all /{path:path}."""
    try:
        if redis:
            await redis.ping()
        return {"status": "healthy", "service": "api-producer", "redis": "ok"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_queue(request: Request, path: str):
    """Forward all requests to appropriate queue based on path."""
    full_path = f"/{path}" if path else "/"
    if request.url.path:
        full_path = request.url.path

    queue_name = path_to_queue(full_path)
    if not queue_name:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    # Parse body and headers
    body = {}
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = {}
    elif request.method == "GET":
        body = dict(request.query_params)

    headers = {
        "x-session": request.headers.get("X-Session", ""),
        "x-admin-secret": request.headers.get("X-Admin-Secret", ""),
    }

    # Determine action from path (e.g. /api/auth/register -> register)
    parts = full_path.rstrip("/").split("/")
    action = parts[-1] if parts else ""

    payload = {
        "action": action,
        "path": full_path,
        "method": request.method,
        "payload": body,
        "headers": headers,
    }

    try:
        async with rmq_connection.channel() as channel:
            result = await publish_and_wait(redis, channel, queue_name, payload, headers)
    except TimeoutError as e:
        log_event(logger, "producer_timeout", path=full_path, error=str(e))
        return JSONResponse(status_code=504, content={"detail": "Gateway timeout"})
    except Exception as e:
        log_event(logger, "producer_error", path=full_path, error=str(e))
        return JSONResponse(status_code=502, content={"detail": str(e)})

    # Result format: { "status": 200, "body": {...} } or { "status": 401, "body": {"detail": "..."} }
    status = result.get("status", 200)
    resp_body = result.get("body", result)
    return JSONResponse(status_code=status, content=resp_body)

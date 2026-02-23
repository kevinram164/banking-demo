"""
Notification Service — Phase 8 Consumer + WebSocket
- Consumer: GET /notifications (via queue)
- WebSocket: /ws (direct) — runs alongside consumer
"""
import os
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from redis.asyncio import Redis

from common.db import SessionLocal, engine, Base
from common.models import Notification
from common.redis_utils import get_user_id_from_session, set_presence, create_redis_client
from common.rabbitmq_utils import store_response
from common.logging_utils import get_json_logger, log_event

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

logger = get_json_logger("notification-service")
redis: Redis | None = None


async def handle_notifications(payload: dict, headers: dict) -> dict:
    """GET /notifications — list user notifications."""
    from fastapi import HTTPException
    try:
        user_id = await get_user_id_from_session(redis, headers.get("x-session") or headers.get("X-Session"))
    except Exception:
        return {"status": 401, "body": {"detail": "Invalid/expired session"}}
    db = SessionLocal()
    try:
        items = db.execute(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(50)).scalars().all()
        return {"status": 200, "body": [{"id": x.id, "message": x.message, "is_read": x.is_read, "created_at": x.created_at.isoformat() + "Z"} for x in items]}
    finally:
        db.close()


async def process_message(message):
    from aio_pika import IncomingMessage
    async with message.process():
        body = {}
        try:
            body = json.loads(message.body.decode())
            correlation_id = body.get("correlation_id")
            action = body.get("action", "")
            payload = body.get("payload", {})
            headers = body.get("headers", {})
            if action == "health":
                result = {"status": 200, "body": {"status": "healthy", "service": "notification", "database": "ok", "redis": "ok"}}
            else:
                result = await handle_notifications(payload, headers)
            await store_response(redis, correlation_id, result)
        except Exception as e:
            log_event(logger, "consumer_error", error=str(e))
            if body.get("correlation_id"):
                await store_response(redis, body["correlation_id"], {"status": 500, "body": {"detail": str(e)}})


async def consume():
    import aio_pika
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await channel.declare_queue("notification.requests", durable=True)
    await queue.consume(process_message)
    log_event(logger, "notification_consumer_started", queue="notification.requests")
    await asyncio.Future()


# --- WebSocket server (runs alongside consumer) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = await create_redis_client(REDIS_URL)
    consumer_task = asyncio.create_task(consume())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    if redis:
        await redis.close()

app = FastAPI(title="Notification Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in CORS_ORIGINS], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """WebSocket — real-time notifications (bypasses queue)."""
    from fastapi import HTTPException
    session = websocket.query_params.get("session")
    if not session:
        await websocket.close(code=1008)
        return
    try:
        user_id = await get_user_id_from_session(redis, session)
    except HTTPException:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"notify:{user_id}")

    async def presence_loop():
        try:
            while True:
                await set_presence(redis, user_id, True)
                await asyncio.sleep(20)
        except Exception:
            pass

    async def notify_loop():
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    await websocket.send_json({"type": "notification", "message": msg["data"]})
                await asyncio.sleep(0.05)
        except Exception:
            pass

    p_task = asyncio.create_task(presence_loop())
    n_task = asyncio.create_task(notify_loop())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        p_task.cancel()
        n_task.cancel()
        await set_presence(redis, user_id, False)
        try:
            await pubsub.unsubscribe(f"notify:{user_id}")
            await pubsub.close()
        except Exception:
            pass


@app.get("/health")
async def health():
    try:
        if redis:
            await redis.ping()
        db = SessionLocal()
        try:
            db.execute(select(1))
            db_status = "ok"
        except Exception:
            db_status = "error"
        finally:
            db.close()
        return {"status": "healthy", "service": "notification-service", "database": db_status, "redis": "ok"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}



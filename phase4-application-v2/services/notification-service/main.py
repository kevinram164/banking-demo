import os, asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from redis.asyncio import Redis

from common.db import SessionLocal, engine, Base
from common.models import Notification
from common.redis_utils import get_user_id_from_session, set_presence, create_redis_client
from common.observability import instrument_fastapi
from common.logging_utils import get_json_logger, RequestLogMiddleware, log_event

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

logger = get_json_logger("notification-service")

redis: Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = await create_redis_client(REDIS_URL)
    yield
    if redis:
        await redis.close()

app = FastAPI(title="Notification Service", lifespan=lifespan)
instrument_fastapi(app, "notification-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RequestLogMiddleware,
    logger=logger,
    service_name="notification-service",
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/notifications")
async def list_notifications(x_session: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Get user notifications"""
    user_id = await get_user_id_from_session(redis, x_session)
    items = (
        db.execute(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(50))
        .scalars()
        .all()
    )

    log_event(logger, "notifications_list_success", user_id=user_id, count=len(items))

    return [{
        "id": x.id,
        "message": x.message,
        "is_read": x.is_read,
        "created_at": x.created_at.isoformat() + "Z",
    } for x in items]

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications"""
    session = websocket.query_params.get("session")
    if not session:
        log_event(logger, "ws_rejected", reason="MISSING_SESSION", client=str(websocket.client))
        await websocket.close(code=1008)
        return

    try:
        user_id = await get_user_id_from_session(redis, session)
    except HTTPException:
        log_event(logger, "ws_rejected", reason="INVALID_SESSION", client=str(websocket.client))
        await websocket.close(code=1008)
        return

    await websocket.accept()
    log_event(logger, "ws_connected", user_id=user_id, client=str(websocket.client))

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
                    log_event(logger, "ws_push", user_id=user_id, message=msg["data"])
                await asyncio.sleep(0.05)
        except Exception:
            pass

    p_task = asyncio.create_task(presence_loop())
    n_task = asyncio.create_task(notify_loop())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        log_event(logger, "ws_disconnected", user_id=user_id)
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
async def health_check():
    """Health check endpoint"""
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
        
        redis_status = "ok" if redis else "error"
        
        if db_status == "ok" and redis_status == "ok":
            return {"status": "healthy", "service": "notification-service", "database": db_status, "redis": redis_status}
        else:
            raise HTTPException(503, detail={"status": "unhealthy", "database": db_status, "redis": redis_status})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, detail=f"Health check failed: {str(e)}")

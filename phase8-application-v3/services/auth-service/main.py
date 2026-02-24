"""
Auth Service — Phase 8 Consumer
Consumes from auth.requests, processes, stores response in Redis.
"""
import os
import asyncio
import json
import secrets
from contextlib import asynccontextmanager, nullcontext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select
from redis.asyncio import Redis
import aio_pika
from aio_pika import IncomingMessage

from common.db import SessionLocal, engine, Base, log_db_pool_status
from common.models import User
from common.auth import hash_password, verify_password
from common.redis_utils import create_session, create_redis_client, get_user_for_login, set_user_for_login_cache
from common.rabbitmq_utils import store_response
from common.logging_utils import get_json_logger, log_event, log_error_event, should_log_request_flow
from common.health_server import start_health_background
from common.observability import init_tracing, get_tracer

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

logger = get_json_logger("auth-service")

redis: Redis | None = None


def _gen_account_number() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(12))


def _mask_phone(phone: str) -> str:
    phone = phone.strip()
    if len(phone) <= 4:
        return "*" * len(phone)
    return phone[:2] + ("*" * (len(phone) - 4)) + phone[-2:]


async def handle_register(payload: dict) -> dict:
    """Business logic — same as v2."""
    phone = (payload.get("phone") or "").strip()
    username = (payload.get("username") or "").strip()
    password = payload.get("password", "")
    if not phone.isdigit():
        return {"status": 400, "body": {"detail": "Phone must be digits only"}}
    db = SessionLocal()
    try:
        exists = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
        if exists:
            return {"status": 409, "body": {"detail": "Phone already exists"}}
        account_number = None
        for _ in range(20):
            candidate = _gen_account_number()
            if not db.execute(select(User).where(User.account_number == candidate)).scalar_one_or_none():
                account_number = candidate
                break
        if not account_number:
            return {"status": 503, "body": {"detail": "Cannot generate account number"}}
        pw_hash = await asyncio.to_thread(hash_password, password)
        u = User(phone=phone, account_number=account_number, username=username, password_hash=pw_hash)
        db.add(u)
        db.commit()
        db.refresh(u)
        log_event(logger, "register_success", user_id=u.id, username=u.username)
        return {"status": 200, "body": {"id": u.id, "phone": _mask_phone(u.phone), "username": u.username, "account_number": u.account_number, "balance": u.balance}}
    except IntegrityError:
        db.rollback()
        return {"status": 409, "body": {"detail": "User already exists"}}
    finally:
        db.close()


async def handle_login(payload: dict) -> dict:
    """Business logic — same as v2. User lookup cached in Redis."""
    phone = (payload.get("phone") or "").strip()
    username = (payload.get("username") or "").strip()
    password = payload.get("password", "")
    lookup_key = f"phone:{phone}" if phone else f"username:{username}"

    if not phone and not username:
        log_event(logger, "login_failed", reason="missing_input", detail="Missing phone/username")
        return {"status": 400, "body": {"detail": "Missing phone/username"}}
    if phone and not phone.isdigit():
        log_event(logger, "login_failed", reason="invalid_format", lookup=lookup_key, detail="Phone must be digits only")
        return {"status": 400, "body": {"detail": "Phone must be digits only"}}

    u = await get_user_for_login(redis, phone, username)
    if u is None:
        db = SessionLocal()
        try:
            if phone:
                row = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
            else:
                row = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if not row:
                log_event(logger, "login_failed", reason="user_not_found", lookup=lookup_key)
                return {"status": 401, "body": {"detail": "Invalid credentials"}}
            u = {"id": row.id, "phone": row.phone, "username": row.username, "account_number": row.account_number, "password_hash": row.password_hash, "balance": row.balance}
            await set_user_for_login_cache(redis, u)
        finally:
            db.close()
    if not await asyncio.to_thread(verify_password, password, u["password_hash"]):
        log_event(logger, "login_failed", reason="invalid_password", user_id=u["id"], lookup=lookup_key)
        return {"status": 401, "body": {"detail": "Invalid credentials"}}

    sid = await create_session(redis, u["id"])
    log_event(logger, "login_success", user_id=u["id"], username=u["username"])
    return {"status": 200, "body": {"session": sid, "phone": _mask_phone(u["phone"]), "username": u["username"], "account_number": u["account_number"], "balance": u["balance"]}}


async def process_message(message: IncomingMessage):
    """Process incoming message from auth.requests queue."""
    async with message.process():
        body = {}
        try:
            body = json.loads(message.body.decode())
            correlation_id = body.get("correlation_id")
            action = body.get("action", "")
            payload = body.get("payload", {})
            tracer = get_tracer("auth-service")
            span_ctx = tracer.start_as_current_span("auth.process", attributes={"messaging.operation": "process", "action": action, "correlation_id": str(correlation_id or "")}) if tracer else nullcontext()
            with span_ctx:
                if should_log_request_flow():
                    log_event(logger, "rmq_message_received", queue="auth.requests", correlation_id=correlation_id, action=action)
                if action == "health":
                    result = {"status": 200, "body": {"status": "healthy", "service": "auth", "database": "ok", "redis": "ok"}}
                elif action == "register":
                    result = await handle_register(payload)
                elif action in ("login", ""):
                    result = await handle_login(payload)
                else:
                    result = {"status": 404, "body": {"detail": f"Unknown action: {action}"}}
                await store_response(redis, correlation_id, result, logger=logger)
        except Exception as e:
            log_error_event(logger, "consumer_error", exc=e, correlation_id=body.get("correlation_id"), service="auth-service", queue="auth.requests")
            if body.get("correlation_id"):
                await store_response(redis, body["correlation_id"], {"status": 500, "body": {"detail": str(e)}}, logger=logger)


async def consume():
    """Main consumer loop."""
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await channel.declare_queue("auth.requests", durable=True)
    await queue.consume(process_message)
    log_event(logger, "rabbitmq_connected")
    log_event(logger, "auth_consumer_started", queue="auth.requests")
    await asyncio.Future()  # Run forever


async def main():
    init_tracing("auth-service")
    global redis
    redis = await create_redis_client(REDIS_URL, logger=logger)
    log_db_pool_status(logger)
    start_health_background(port=9999, service_name="auth-service")
    await consume()


if __name__ == "__main__":
    asyncio.run(main())

"""
Transfer Service — Phase 8 Consumer
Consumes from transfer.requests, processes, stores response in Redis.
After success: nếu CK vào STK chủ shop + note NOLI-* → gọi shop-bridge confirm-payment.
"""
import os
import re
import asyncio
import json
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import select
from redis.asyncio import Redis
from aio_pika import IncomingMessage
from fastapi import FastAPI

from common.db import SessionLocal, engine, Base, log_db_pool_status, ensure_schema
from common.models import User, Transfer, Notification
from common.redis_utils import get_user_id_from_session, publish_notify, create_redis_client
from common.rabbitmq_utils import store_response
from common.logging_utils import get_json_logger, log_event, log_error_event, mask_amount, mask_account_number, should_log_request_flow
from common.observability import instrument_fastapi, get_tracer, consumer_span

Base.metadata.create_all(bind=engine)
ensure_schema()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
SHOP_BRIDGE_URL = os.getenv("SHOP_BRIDGE_URL", "http://shop-bridge:8010").rstrip("/")
SHOP_MERCHANT_ACCOUNT = os.getenv("SHOP_MERCHANT_ACCOUNT_NUMBER", "").strip()
SHOP_NOTE_PREFIX = os.getenv("SHOP_TRANSFER_NOTE_PREFIX", "NOLI").strip().upper() or "NOLI"

logger = get_json_logger("transfer-service")
redis: Redis | None = None

_NOTE_RE = re.compile(rf"\b({re.escape(SHOP_NOTE_PREFIX)}-[A-Z0-9]+)\b", re.IGNORECASE)


def _normalize_note(raw: str) -> str:
    note = (raw or "").strip().upper()
    if not note:
        return ""
    m = _NOTE_RE.search(note.replace(" ", ""))
    if m:
        return m.group(1).upper()
    # Cho phép gửi đúng "NOLI-XXXX" thuần
    compact = note.replace(" ", "")
    if compact.startswith(f"{SHOP_NOTE_PREFIX}-"):
        return compact
    return note[:64]


async def _notify_shop_bridge(transfer_ref: str, amount_vnd: int) -> None:
    """Best-effort: không fail transfer nếu bridge lỗi."""
    if not SHOP_BRIDGE_URL:
        return
    url = f"{SHOP_BRIDGE_URL}/api/shop/confirm-payment"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"transfer_ref": transfer_ref, "amount_vnd": int(amount_vnd)},
            )
            if resp.status_code >= 400:
                log_event(
                    logger,
                    "shop_bridge_confirm_failed",
                    status=resp.status_code,
                    detail=resp.text[:200],
                    transfer_ref=transfer_ref,
                    service="transfer-service",
                )
            else:
                log_event(
                    logger,
                    "shop_bridge_confirm_ok",
                    transfer_ref=transfer_ref,
                    amount_vnd=amount_vnd,
                    service="transfer-service",
                )
    except Exception as exc:
        log_event(
            logger,
            "shop_bridge_confirm_error",
            error=str(exc)[:200],
            transfer_ref=transfer_ref,
            service="transfer-service",
        )


async def handle_transfer(payload: dict, headers: dict, trace: dict) -> dict:
    """Business logic — same as v2 + optional note / shop matcher."""
    correlation_id = trace.get("correlation_id", "")
    path = trace.get("path", "")
    action = trace.get("action", "")

    x_session = headers.get("x-session") or headers.get("X-Session")
    user_id = await get_user_id_from_session(redis, x_session)
    body = payload
    amount = body.get("amount", 0)
    to_acct = (body.get("to_account_number") or "").strip()
    to_username = (body.get("to_username") or "").strip()
    note = _normalize_note(body.get("note") or body.get("content") or "")
    if amount <= 0:
        log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="amount_invalid", detail="Amount must be > 0", service="transfer-service")
        return {"status": 400, "body": {"detail": "Amount must be > 0"}}
    if not to_acct and not to_username:
        log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="missing_recipient", service="transfer-service")
        return {"status": 400, "body": {"detail": "Missing to_account_number/to_username"}}
    if to_acct and not to_acct.isdigit():
        log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="invalid_account_format", service="transfer-service")
        return {"status": 400, "body": {"detail": "to_account_number must be digits only"}}
    db = SessionLocal()
    try:
        sender = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
        if not sender:
            log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="sender_not_found", user_id=user_id, service="transfer-service")
            return {"status": 404, "body": {"detail": "Sender not found"}}
        if to_acct:
            receiver = db.execute(select(User).where(User.account_number == to_acct).with_for_update()).scalar_one_or_none()
        else:
            receiver = db.execute(select(User).where(User.username == to_username).with_for_update()).scalar_one_or_none()
        if not receiver:
            log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="receiver_not_found", to_account=to_acct or None, to_username=to_username or None, service="transfer-service")
            return {"status": 404, "body": {"detail": "Receiver not found"}}
        if receiver.id == sender.id:
            log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="self_transfer", from_user=sender.id, service="transfer-service")
            return {"status": 400, "body": {"detail": "Cannot transfer to yourself"}}
        if sender.balance < amount:
            log_event(logger, "transfer_rejected", correlation_id=correlation_id, path=path, action=action, reason="insufficient_balance", from_user=sender.id, amount_hash=mask_amount(amount), balance=sender.balance, service="transfer-service")
            return {"status": 400, "body": {"detail": "Insufficient balance"}}
        sender.balance -= amount
        receiver.balance += amount
        transfer = Transfer(from_user=sender.id, to_user=receiver.id, amount=amount, note=note)
        db.add(transfer)
        note_suffix = f" ({note})" if note else ""
        db.add(Notification(user_id=sender.id, message=f"Bạn đã chuyển {amount} đến {receiver.username}{note_suffix}"))
        db.add(Notification(user_id=receiver.id, message=f"Bạn nhận {amount} từ {sender.username}{note_suffix}"))
        db.commit()
        await publish_notify(redis, receiver.id, f"Bạn nhận {amount} từ {sender.username}{note_suffix}")
        log_event(
            logger,
            "transfer_success",
            correlation_id=correlation_id,
            path=path,
            action=action,
            transfer_id=transfer.id,
            from_user_id=sender.id,
            from_username=sender.username,
            from_account_masked=mask_account_number(sender.account_number),
            to_user_id=receiver.id,
            to_username=receiver.username,
            to_account_masked=mask_account_number(receiver.account_number),
            amount_hash=mask_amount(amount),
            note=note or None,
            service="transfer-service",
            queue="transfer.requests",
        )

        # Matcher: CK vào STK chủ shop + note NOLI-* → báo shop
        merchant = SHOP_MERCHANT_ACCOUNT
        if (
            merchant
            and receiver.account_number == merchant
            and note.startswith(f"{SHOP_NOTE_PREFIX}-")
        ):
            asyncio.create_task(_notify_shop_bridge(note, amount))

        return {
            "status": 200,
            "body": {
                "ok": True,
                "from": sender.username,
                "to": receiver.username,
                "to_account_number": receiver.account_number,
                "amount": amount,
                "note": note or None,
            },
        }
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


async def process_message(message: IncomingMessage):
    async with message.process():
        body = {}
        try:
            body = json.loads(message.body.decode())
            correlation_id = body.get("correlation_id", "")
            path = body.get("path", "")
            action = body.get("action", "")
            payload = body.get("payload", {})
            headers = body.get("headers", {})
            tracer = get_tracer("transfer-service")
            with consumer_span(tracer, "transfer.process", {"action": action, "correlation_id": str(correlation_id or "")}):
                if should_log_request_flow():
                    log_event(logger, "rmq_message_received", queue="transfer.requests", correlation_id=correlation_id, action=action, path=path)
                if action == "health":
                    result = {"status": 200, "body": {"status": "healthy", "service": "transfer", "database": "ok", "redis": "ok"}}
                else:
                    trace = {"correlation_id": correlation_id, "path": path, "action": action}
                    result = await handle_transfer(payload, headers, trace)
                await store_response(redis, correlation_id, result)
        except Exception as e:
            log_error_event(
                logger,
                "consumer_error",
                exc=e,
                correlation_id=body.get("correlation_id", ""),
                path=body.get("path", ""),
                action=body.get("action", ""),
                service="transfer-service",
                queue="transfer.requests",
            )
            if body.get("correlation_id"):
                await store_response(redis, body["correlation_id"], {"status": 500, "body": {"detail": str(e)}}, logger=logger)


async def consume():
    import aio_pika
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await channel.declare_queue("transfer.requests", durable=True)
    await queue.consume(process_message)
    log_event(logger, "rabbitmq_connected")
    log_event(
        logger,
        "transfer_consumer_started",
        queue="transfer.requests",
        service="transfer-service",
        prefetch=5,
        shop_merchant=SHOP_MERCHANT_ACCOUNT or None,
        shop_bridge=SHOP_BRIDGE_URL or None,
    )
    await asyncio.Future()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = await create_redis_client(REDIS_URL, logger=logger)
    log_db_pool_status(logger)
    consumer_task = asyncio.create_task(consume())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    if redis:
        await redis.close()


app = FastAPI(title="Transfer Service", lifespan=lifespan)
instrument_fastapi(app, "transfer-service")


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
        return {
            "status": "healthy",
            "service": "transfer-service",
            "database": db_status,
            "redis": "ok",
            "shop_matcher": bool(SHOP_MERCHANT_ACCOUNT),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

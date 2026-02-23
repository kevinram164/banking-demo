"""
Transfer Service — Phase 8 Consumer
Consumes from transfer.requests, processes, stores response in Redis.
"""
import os
import asyncio
import json
from sqlalchemy.orm import Session
from sqlalchemy import select
from redis.asyncio import Redis
from aio_pika import IncomingMessage

from common.db import SessionLocal, engine, Base
from common.models import User, Transfer, Notification
from common.redis_utils import get_user_id_from_session, publish_notify, create_redis_client
from common.rabbitmq_utils import store_response
from common.logging_utils import get_json_logger, log_event
from common.health_server import start_health_background

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

logger = get_json_logger("transfer-service")
redis: Redis | None = None


async def handle_transfer(payload: dict, headers: dict) -> dict:
    """Business logic — same as v2."""
    x_session = headers.get("x-session") or headers.get("X-Session")
    user_id = await get_user_id_from_session(redis, x_session)
    body = payload
    amount = body.get("amount", 0)
    to_acct = (body.get("to_account_number") or "").strip()
    to_username = (body.get("to_username") or "").strip()
    if amount <= 0:
        return {"status": 400, "body": {"detail": "Amount must be > 0"}}
    if not to_acct and not to_username:
        return {"status": 400, "body": {"detail": "Missing to_account_number/to_username"}}
    if to_acct and not to_acct.isdigit():
        return {"status": 400, "body": {"detail": "to_account_number must be digits only"}}
    db = SessionLocal()
    try:
        sender = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
        if not sender:
            return {"status": 404, "body": {"detail": "Sender not found"}}
        if to_acct:
            receiver = db.execute(select(User).where(User.account_number == to_acct).with_for_update()).scalar_one_or_none()
        else:
            receiver = db.execute(select(User).where(User.username == to_username).with_for_update()).scalar_one_or_none()
        if not receiver:
            return {"status": 404, "body": {"detail": "Receiver not found"}}
        if receiver.id == sender.id:
            return {"status": 400, "body": {"detail": "Cannot transfer to yourself"}}
        if sender.balance < amount:
            return {"status": 400, "body": {"detail": "Insufficient balance"}}
        sender.balance -= amount
        receiver.balance += amount
        db.add(Transfer(from_user=sender.id, to_user=receiver.id, amount=amount))
        db.add(Notification(user_id=sender.id, message=f"Bạn đã chuyển {amount} đến {receiver.username}"))
        db.add(Notification(user_id=receiver.id, message=f"Bạn nhận {amount} từ {sender.username}"))
        db.commit()
        await publish_notify(redis, receiver.id, f"Bạn nhận {amount} từ {sender.username}")
        log_event(logger, "transfer_success", from_user=sender.id, to_user=receiver.id, amount=amount)
        return {"status": 200, "body": {"ok": True, "from": sender.username, "to": receiver.username, "to_account_number": receiver.account_number, "amount": amount}}
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
            correlation_id = body.get("correlation_id")
            payload = body.get("payload", {})
            headers = body.get("headers", {})
            result = await handle_transfer(payload, headers)
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
    queue = await channel.declare_queue("transfer.requests", durable=True)
    await queue.consume(process_message)
    log_event(logger, "transfer_consumer_started", queue="transfer.requests")
    await asyncio.Future()


async def main():
    global redis
    redis = await create_redis_client(REDIS_URL)
    start_health_background(port=9999, service_name="transfer-service")
    await consume()


if __name__ == "__main__":
    asyncio.run(main())

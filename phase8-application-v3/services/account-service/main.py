"""
Account Service — Phase 8 Consumer
Consumes from account.requests, processes, stores response in Redis.
"""
import os
import asyncio
import json
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from redis.asyncio import Redis
from aio_pika import IncomingMessage

from common.db import SessionLocal, engine, Base
from common.models import User, Transfer, Notification
from common.redis_utils import get_user_id_from_session, create_redis_client
from common.rabbitmq_utils import store_response
from common.logging_utils import get_json_logger, log_event
from common.health_server import start_health_background

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "banking-admin-2025")

logger = get_json_logger("account-service")
redis: Redis | None = None


def _verify_admin(headers: dict) -> bool:
    return (headers.get("x-admin-secret") or headers.get("X-Admin-Secret")) == ADMIN_SECRET


async def handle_me(payload: dict, headers: dict) -> dict:
    user_id = await get_user_id_from_session(redis, headers.get("x-session") or headers.get("X-Session"))
    db = SessionLocal()
    try:
        u = db.get(User, user_id)
        if not u:
            return {"status": 404, "body": {"detail": "User not found"}}
        return {"status": 200, "body": {"id": u.id, "phone": u.phone, "username": u.username, "account_number": u.account_number, "balance": u.balance}}
    finally:
        db.close()


async def handle_balance(payload: dict, headers: dict) -> dict:
    user_id = await get_user_id_from_session(redis, headers.get("x-session") or headers.get("X-Session"))
    db = SessionLocal()
    try:
        u = db.get(User, user_id)
        if not u:
            return {"status": 404, "body": {"detail": "User not found"}}
        return {"status": 200, "body": {"balance": u.balance}}
    finally:
        db.close()


async def handle_lookup(payload: dict, headers: dict) -> dict:
    acct = (payload.get("account_number") or "").strip()
    if not acct.isdigit():
        return {"status": 400, "body": {"detail": "account_number must be digits only"}}
    db = SessionLocal()
    try:
        u = db.execute(select(User).where(User.account_number == acct)).scalar_one_or_none()
        if not u:
            return {"status": 404, "body": {"detail": "Account not found"}}
        return {"status": 200, "body": {"account_number": u.account_number, "username": u.username}}
    finally:
        db.close()


async def handle_admin_stats(payload: dict, headers: dict) -> dict:
    if not _verify_admin(headers):
        return {"status": 403, "body": {"detail": "Forbidden"}}
    db = SessionLocal()
    try:
        total_users = db.execute(select(func.count(User.id))).scalar()
        total_balance = db.execute(select(func.coalesce(func.sum(User.balance), 0))).scalar()
        total_transfers = db.execute(select(func.count(Transfer.id))).scalar()
        total_transfer_amount = db.execute(select(func.coalesce(func.sum(Transfer.amount), 0))).scalar()
        total_notifications = db.execute(select(func.count(Notification.id))).scalar()
        return {"status": 200, "body": {"total_users": total_users, "total_balance": total_balance, "total_transfers": total_transfers, "total_transfer_amount": total_transfer_amount, "total_notifications": total_notifications}}
    finally:
        db.close()


async def handle_admin_users(payload: dict, headers: dict) -> dict:
    if not _verify_admin(headers):
        return {"status": 403, "body": {"detail": "Forbidden"}}
    page = int(payload.get("page", 1))
    size = int(payload.get("size", 20))
    search = (payload.get("search") or "").strip()
    db = SessionLocal()
    try:
        query = select(User)
        if search:
            pattern = f"%{search}%"
            query = query.where((User.username.ilike(pattern)) | (User.phone.ilike(pattern)) | (User.account_number.ilike(pattern)))
        total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
        users = db.execute(query.order_by(User.id.desc()).offset((page - 1) * size).limit(size)).scalars().all()
        return {"status": 200, "body": {"users": [{"id": u.id, "phone": u.phone, "username": u.username, "account_number": u.account_number, "balance": u.balance} for u in users], "total": total, "page": page, "size": size, "pages": (total + size - 1) // size}}
    finally:
        db.close()


async def handle_admin_transfers(payload: dict, headers: dict) -> dict:
    if not _verify_admin(headers):
        return {"status": 403, "body": {"detail": "Forbidden"}}
    page = int(payload.get("page", 1))
    size = int(payload.get("size", 20))
    db = SessionLocal()
    try:
        total_count = db.execute(select(func.count(Transfer.id))).scalar()
        transfers = db.execute(select(Transfer).order_by(Transfer.created_at.desc()).offset((page - 1) * size).limit(size)).scalars().all()
        user_ids = {t.from_user for t in transfers} | {t.to_user for t in transfers}
        users = {u.id: u.username for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()} if user_ids else {}
        result = [{"id": t.id, "from_user": t.from_user, "from_username": users.get(t.from_user, f"#{t.from_user}"), "to_user": t.to_user, "to_username": users.get(t.to_user, f"#{t.to_user}"), "amount": t.amount, "created_at": t.created_at.isoformat() + "Z"} for t in transfers]
        return {"status": 200, "body": {"transfers": result, "total": total_count, "page": page, "size": size, "pages": (total_count + size - 1) // size}}
    finally:
        db.close()


async def handle_admin_notifications(payload: dict, headers: dict) -> dict:
    if not _verify_admin(headers):
        return {"status": 403, "body": {"detail": "Forbidden"}}
    page = int(payload.get("page", 1))
    size = int(payload.get("size", 20))
    user_id = payload.get("user_id")
    db = SessionLocal()
    try:
        query = select(Notification).order_by(Notification.created_at.desc())
        if user_id:
            query = query.where(Notification.user_id == int(user_id))
        total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
        items = db.execute(query.offset((page - 1) * size).limit(size)).scalars().all()
        user_ids = {n.user_id for n in items}
        users = {u.id: u.username for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()} if user_ids else {}
        result = [{"id": n.id, "user_id": n.user_id, "username": users.get(n.user_id, f"#{n.user_id}"), "message": n.message, "is_read": n.is_read, "created_at": n.created_at.isoformat() + "Z"} for n in items]
        return {"status": 200, "body": {"notifications": result, "total": total, "page": page, "size": size, "pages": (total + size - 1) // size}}
    finally:
        db.close()


async def handle_admin_user_detail(user_id: int, headers: dict) -> dict:
    if not _verify_admin(headers):
        return {"status": 403, "body": {"detail": "Forbidden"}}
    db = SessionLocal()
    try:
        u = db.get(User, user_id)
        if not u:
            return {"status": 404, "body": {"detail": "User not found"}}
        transfers = db.execute(select(Transfer).where((Transfer.from_user == user_id) | (Transfer.to_user == user_id)).order_by(Transfer.created_at.desc()).limit(20)).scalars().all()
        return {"status": 200, "body": {"id": u.id, "phone": u.phone, "username": u.username, "account_number": u.account_number, "balance": u.balance, "transfers": [{"id": t.id, "from_user": t.from_user, "to_user": t.to_user, "amount": t.amount, "direction": "out" if t.from_user == user_id else "in", "created_at": t.created_at.isoformat() + "Z"} for t in transfers]}}
    finally:
        db.close()


async def process_message(message: IncomingMessage):
    async with message.process():
        body = {}
        try:
            body = json.loads(message.body.decode())
            correlation_id = body.get("correlation_id")
            path = body.get("path", "")
            action = body.get("action", "")
            payload = body.get("payload", {})
            headers = body.get("headers", {})
            if action == "health":
                result = {"status": 200, "body": {"status": "healthy", "service": "account", "database": "ok", "redis": "ok"}}
            elif action == "me":
                result = await handle_me(payload, headers)
            elif action == "balance":
                result = await handle_balance(payload, headers)
            elif action == "lookup":
                result = await handle_lookup(payload, headers)
            elif action == "admin/stats" or "admin/stats" in path:
                result = await handle_admin_stats(payload, headers)
            elif action == "admin/users" or "admin/users" in path:
                if "/admin/users/" in path and path.split("/admin/users/")[-1].isdigit():
                    uid = int(path.split("/admin/users/")[-1].split("/")[0])
                    result = await handle_admin_user_detail(uid, headers)
                else:
                    result = await handle_admin_users(payload, headers)
            elif "admin/transfers" in (path or ""):
                result = await handle_admin_transfers(payload, headers)
            elif "admin/notifications" in (path or ""):
                result = await handle_admin_notifications(payload, headers)
            else:
                result = {"status": 404, "body": {"detail": f"Unknown action: {action}"}}
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
    queue = await channel.declare_queue("account.requests", durable=True)
    await queue.consume(process_message)
    log_event(logger, "account_consumer_started", queue="account.requests")
    await asyncio.Future()


async def main():
    global redis
    redis = await create_redis_client(REDIS_URL)
    start_health_background(port=9999, service_name="account-service")
    await consume()


if __name__ == "__main__":
    asyncio.run(main())

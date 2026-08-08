"""
Transfer Service — Phase 8 Consumer
Hold/pending lifecycle + business error codes + stale message reject.
After SUCCESS: nếu CK vào STK chủ shop + note NOLI-* → gọi shop-bridge confirm-payment.
"""
import os
import re
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from redis.asyncio import Redis
from aio_pika import IncomingMessage
from fastapi import FastAPI

from common.db import SessionLocal, engine, Base, log_db_pool_status, ensure_schema
from common.models import User, Transfer, Notification
from common.redis_utils import get_user_id_from_session, publish_notify, create_redis_client
from common.rabbitmq_utils import store_response, declare_request_queue, is_message_stale, MAX_MESSAGE_AGE_SEC
from common.logging_utils import get_json_logger, log_event, log_error_event, mask_amount, mask_account_number, should_log_request_flow
from common.observability import instrument_fastapi, get_tracer, consumer_span

Base.metadata.create_all(bind=engine)
ensure_schema()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
SHOP_BRIDGE_URL = os.getenv("SHOP_BRIDGE_URL", "http://shop-bridge:8010").rstrip("/")
SHOP_MERCHANT_ACCOUNT = os.getenv("SHOP_MERCHANT_ACCOUNT_NUMBER", "").strip()
SHOP_NOTE_PREFIX = os.getenv("SHOP_TRANSFER_NOTE_PREFIX", "NOLI").strip().upper() or "NOLI"
HOLD_TTL_SECONDS = int(os.getenv("HOLD_TTL_SECONDS", "300"))
EXPIRE_POLL_SECONDS = int(os.getenv("HOLD_EXPIRE_POLL_SECONDS", "30"))

TXN_TYPES = frozenset({"P2P", "DISBURSEMENT", "REPAYMENT", "BILL_PAY", "FEE", "MERCHANT_PAY"})

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
    compact = note.replace(" ", "")
    if compact.startswith(f"{SHOP_NOTE_PREFIX}-"):
        return compact
    return note[:64]


def _available(user: User) -> int:
    return int(user.balance or 0) - int(getattr(user, "held_balance", 0) or 0)


def _biz_fields(body: dict) -> dict:
    txn_type = (body.get("txn_type") or "P2P").strip().upper()
    if txn_type not in TXN_TYPES:
        txn_type = "P2P"
    purpose = (body.get("purpose") or "").strip()[:128]
    channel = (body.get("channel") or "mobile").strip()[:32] or "mobile"
    client_ref = (body.get("client_ref") or "").strip()[:64]
    return {"txn_type": txn_type, "purpose": purpose, "channel": channel, "client_ref": client_ref}


def _reject(
    *,
    status: int,
    error_code: str,
    detail: str,
    correlation_id: str,
    path: str,
    action: str,
    reason: str,
    **extra,
) -> dict:
    log_event(
        logger,
        "transfer_rejected",
        correlation_id=correlation_id,
        path=path,
        action=action,
        reason=reason,
        failure_code=error_code,
        outcome="failure",
        business_domain="banking",
        detail=detail,
        service="transfer-service",
        **extra,
    )
    body = {"error_code": error_code, "detail": detail, "status": "REJECTED"}
    for k in ("txn_type", "purpose", "channel", "client_ref"):
        if k in extra and extra[k] is not None:
            body[k] = extra[k]
    return {"status": status, "body": body}


def _transfer_dict(t: Transfer, sender: User, receiver: User) -> dict:
    return {
        "ok": True,
        "transfer_id": t.id,
        "status": t.status,
        "from": sender.username,
        "to": receiver.username,
        "to_account_number": receiver.account_number,
        "amount": t.amount,
        "note": t.note or None,
        "txn_type": t.txn_type,
        "purpose": t.purpose or None,
        "channel": t.channel,
        "client_ref": t.client_ref or None,
        "hold_until": t.hold_until.isoformat() + "Z" if t.hold_until else None,
        "failure_code": t.failure_code or None,
    }


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


def _maybe_shop_notify(receiver: User, note: str, amount: int) -> None:
    merchant = SHOP_MERCHANT_ACCOUNT
    if (
        merchant
        and receiver.account_number == merchant
        and note.startswith(f"{SHOP_NOTE_PREFIX}-")
    ):
        asyncio.create_task(_notify_shop_bridge(note, amount))


async def handle_create(payload: dict, headers: dict, trace: dict) -> dict:
    """Create PENDING hold (or instant settle if instant=true)."""
    correlation_id = trace.get("correlation_id", "")
    path = trace.get("path", "")
    action = trace.get("action", "")

    x_session = headers.get("x-session") or headers.get("X-Session")
    user_id = await get_user_id_from_session(redis, x_session)
    body = payload
    biz = _biz_fields(body)
    amount = body.get("amount", 0)
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = 0
    to_acct = (body.get("to_account_number") or "").strip()
    to_username = (body.get("to_username") or "").strip()
    note = _normalize_note(body.get("note") or body.get("content") or "")
    instant = bool(body.get("instant"))

    # Auto MERCHANT_PAY khi note NOLI
    if note.startswith(f"{SHOP_NOTE_PREFIX}-") and biz["txn_type"] == "P2P":
        biz["txn_type"] = "MERCHANT_PAY"
        if not biz["purpose"]:
            biz["purpose"] = "thanh toan don hang shop"

    common_extra = {**biz, "amount_hash": mask_amount(amount) if amount else None}

    if amount <= 0:
        return _reject(
            status=400,
            error_code="INVALID_AMOUNT",
            detail="Amount must be > 0",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="amount_invalid",
            **common_extra,
        )
    if not to_acct and not to_username:
        return _reject(
            status=400,
            error_code="MISSING_RECIPIENT",
            detail="Missing to_account_number/to_username",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="missing_recipient",
            **common_extra,
        )
    if to_acct and not to_acct.isdigit():
        return _reject(
            status=400,
            error_code="INVALID_ACCOUNT",
            detail="to_account_number must be digits only",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="invalid_account_format",
            **common_extra,
        )

    db = SessionLocal()
    try:
        if biz["client_ref"]:
            existing = db.execute(
                select(Transfer).where(Transfer.client_ref == biz["client_ref"])
            ).scalar_one_or_none()
            if existing:
                return _reject(
                    status=409,
                    error_code="DUPLICATE_CLIENT_REF",
                    detail=f"client_ref already used (transfer_id={existing.id})",
                    correlation_id=correlation_id,
                    path=path,
                    action=action,
                    reason="duplicate_client_ref",
                    transfer_id=existing.id,
                    **common_extra,
                )

        sender = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
        if not sender:
            return _reject(
                status=404,
                error_code="ACCOUNT_NOT_FOUND",
                detail="Sender not found",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="sender_not_found",
                user_id=user_id,
                **common_extra,
            )
        if to_acct:
            receiver = db.execute(
                select(User).where(User.account_number == to_acct).with_for_update()
            ).scalar_one_or_none()
        else:
            receiver = db.execute(
                select(User).where(User.username == to_username).with_for_update()
            ).scalar_one_or_none()
        if not receiver:
            return _reject(
                status=404,
                error_code="ACCOUNT_NOT_FOUND",
                detail="Receiver not found",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="receiver_not_found",
                to_account=to_acct or None,
                to_username=to_username or None,
                **common_extra,
            )
        if receiver.id == sender.id:
            return _reject(
                status=400,
                error_code="SELF_TRANSFER",
                detail="Cannot transfer to yourself",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="self_transfer",
                from_user=sender.id,
                **common_extra,
            )

        avail = _available(sender)
        if avail < amount:
            return _reject(
                status=400,
                error_code="INSUFFICIENT_FUNDS",
                detail="Insufficient available balance",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="insufficient_balance",
                from_user=sender.id,
                balance=sender.balance,
                held_balance=sender.held_balance,
                available=avail,
                **common_extra,
            )

        now = datetime.now(timezone.utc)
        hold_until = now + timedelta(seconds=HOLD_TTL_SECONDS)
        # Store naive UTC for Postgres TIMESTAMP without tz
        hold_until_db = hold_until.replace(tzinfo=None)

        note_suffix = f" ({note})" if note else ""
        purpose_bit = f" [{biz['txn_type']}]" if biz["txn_type"] else ""

        if instant:
            # Load-test path: settle ngay trong 1 txn (không để PENDING).
            sender.balance -= amount
            receiver.balance += amount
            transfer = Transfer(
                from_user=sender.id,
                to_user=receiver.id,
                amount=amount,
                note=note,
                txn_type=biz["txn_type"],
                purpose=biz["purpose"],
                channel=biz["channel"],
                client_ref=biz["client_ref"],
                status="SUCCESS",
                hold_until=None,
            )
            db.add(transfer)
            db.add(
                Notification(
                    user_id=sender.id,
                    message=f"SUCCESS{purpose_bit}: đã chuyển {amount} đến {receiver.username}{note_suffix}",
                )
            )
            db.add(
                Notification(
                    user_id=receiver.id,
                    message=f"SUCCESS{purpose_bit}: nhận {amount} từ {sender.username}{note_suffix}",
                )
            )
            db.commit()
            db.refresh(transfer)
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
                txn_type=biz["txn_type"],
                purpose=biz["purpose"] or None,
                channel=biz["channel"],
                client_ref=biz["client_ref"] or None,
                status="SUCCESS",
                outcome="success",
                business_domain="banking",
                instant=True,
                held_balance=sender.held_balance,
                available=_available(sender),
                service="transfer-service",
                queue="transfer.requests",
            )
            await publish_notify(
                redis,
                receiver.id,
                f"SUCCESS{purpose_bit}: nhận {amount} từ {sender.username}{note_suffix}",
            )
            _maybe_shop_notify(receiver, note, amount)
            return {"status": 200, "body": _transfer_dict(transfer, sender, receiver)}

        sender.held_balance = int(sender.held_balance or 0) + amount
        transfer = Transfer(
            from_user=sender.id,
            to_user=receiver.id,
            amount=amount,
            note=note,
            txn_type=biz["txn_type"],
            purpose=biz["purpose"],
            channel=biz["channel"],
            client_ref=biz["client_ref"],
            status="PENDING",
            hold_until=hold_until_db,
        )
        db.add(transfer)
        db.add(
            Notification(
                user_id=sender.id,
                message=f"PENDING{purpose_bit}: giữ {amount} chuyển tới {receiver.username}{note_suffix}",
            )
        )
        db.commit()
        db.refresh(transfer)

        log_event(
            logger,
            "transfer_pending",
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
            txn_type=biz["txn_type"],
            purpose=biz["purpose"] or None,
            channel=biz["channel"],
            client_ref=biz["client_ref"] or None,
            status="PENDING",
            outcome="pending",
            business_domain="banking",
            held_balance=sender.held_balance,
            available=_available(sender),
            hold_until=hold_until.isoformat(),
            service="transfer-service",
            queue="transfer.requests",
        )

        await publish_notify(
            redis,
            sender.id,
            f"PENDING{purpose_bit}: giữ {amount} tới {receiver.username}{note_suffix}",
        )

        return {"status": 200, "body": _transfer_dict(transfer, sender, receiver)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _settle_transfer(
    db,
    transfer: Transfer,
    sender: User,
    receiver: User,
    correlation_id: str,
    path: str,
    action: str,
) -> dict:
    """Confirm PENDING → SUCCESS (caller holds locks / same session)."""
    if transfer.status != "PENDING":
        return _reject(
            status=409,
            error_code="INVALID_STATE",
            detail=f"Transfer status is {transfer.status}, expected PENDING",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="invalid_state",
            transfer_id=transfer.id,
            transfer_status=transfer.status,
            txn_type=transfer.txn_type,
            purpose=transfer.purpose,
            client_ref=transfer.client_ref or None,
        )

    amount = transfer.amount
    held = int(sender.held_balance or 0)
    if held < amount:
        # Data inconsistency — still try to settle carefully
        sender.held_balance = 0
    else:
        sender.held_balance = held - amount

    if sender.balance < amount:
        # Release remaining hold already adjusted; mark failed
        transfer.status = "FAILED"
        transfer.failure_code = "INSUFFICIENT_FUNDS"
        transfer.hold_until = None
        db.commit()
        return _reject(
            status=400,
            error_code="INSUFFICIENT_FUNDS",
            detail="Insufficient balance at settle",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="insufficient_balance_settle",
            transfer_id=transfer.id,
            txn_type=transfer.txn_type,
            purpose=transfer.purpose,
            client_ref=transfer.client_ref or None,
        )

    sender.balance -= amount
    receiver.balance += amount
    transfer.status = "SUCCESS"
    transfer.failure_code = ""
    transfer.hold_until = None
    note = transfer.note or ""
    note_suffix = f" ({note})" if note else ""
    purpose_bit = f" [{transfer.txn_type}]"
    db.add(
        Notification(
            user_id=sender.id,
            message=f"SUCCESS{purpose_bit}: đã chuyển {amount} đến {receiver.username}{note_suffix}",
        )
    )
    db.add(
        Notification(
            user_id=receiver.id,
            message=f"SUCCESS{purpose_bit}: nhận {amount} từ {sender.username}{note_suffix}",
        )
    )
    db.commit()

    await publish_notify(
        redis,
        receiver.id,
        f"SUCCESS{purpose_bit}: nhận {amount} từ {sender.username}{note_suffix}",
    )

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
        txn_type=transfer.txn_type,
        purpose=transfer.purpose or None,
        channel=transfer.channel,
        client_ref=transfer.client_ref or None,
        status="SUCCESS",
        outcome="success",
        business_domain="banking",
        held_balance=sender.held_balance,
        available=_available(sender),
        service="transfer-service",
        queue="transfer.requests",
    )

    _maybe_shop_notify(receiver, note, amount)
    return {"status": 200, "body": _transfer_dict(transfer, sender, receiver)}


async def handle_confirm(payload: dict, headers: dict, trace: dict) -> dict:
    correlation_id = trace.get("correlation_id", "")
    path = trace.get("path", "")
    action = trace.get("action", "")
    x_session = headers.get("x-session") or headers.get("X-Session")
    user_id = await get_user_id_from_session(redis, x_session)

    transfer_id = payload.get("transfer_id") or payload.get("id")
    client_ref = (payload.get("client_ref") or "").strip()
    if not transfer_id and not client_ref:
        return _reject(
            status=400,
            error_code="TRANSFER_NOT_FOUND",
            detail="transfer_id or client_ref required",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="missing_transfer_id",
        )

    db = SessionLocal()
    try:
        q = select(Transfer)
        if transfer_id:
            q = q.where(Transfer.id == int(transfer_id))
        else:
            q = q.where(Transfer.client_ref == client_ref)
        transfer = db.execute(q.with_for_update()).scalar_one_or_none()
        if not transfer:
            return _reject(
                status=404,
                error_code="TRANSFER_NOT_FOUND",
                detail="Transfer not found",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="transfer_not_found",
            )
        if transfer.from_user != user_id:
            return _reject(
                status=403,
                error_code="INVALID_STATE",
                detail="Only sender can confirm",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="forbidden_confirm",
                transfer_id=transfer.id,
            )

        # Lock users in consistent order to avoid deadlock
        ids = sorted([transfer.from_user, transfer.to_user])
        users = {
            u.id: u
            for u in db.execute(select(User).where(User.id.in_(ids)).with_for_update()).scalars().all()
        }
        sender = users.get(transfer.from_user)
        receiver = users.get(transfer.to_user)
        if not sender or not receiver:
            return _reject(
                status=404,
                error_code="ACCOUNT_NOT_FOUND",
                detail="Sender or receiver missing",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="party_missing",
                transfer_id=transfer.id,
            )
        return await _settle_transfer(db, transfer, sender, receiver, correlation_id, path, action)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def handle_cancel(payload: dict, headers: dict, trace: dict) -> dict:
    correlation_id = trace.get("correlation_id", "")
    path = trace.get("path", "")
    action = trace.get("action", "")
    x_session = headers.get("x-session") or headers.get("X-Session")
    user_id = await get_user_id_from_session(redis, x_session)

    transfer_id = payload.get("transfer_id") or payload.get("id")
    client_ref = (payload.get("client_ref") or "").strip()
    if not transfer_id and not client_ref:
        return _reject(
            status=400,
            error_code="TRANSFER_NOT_FOUND",
            detail="transfer_id or client_ref required",
            correlation_id=correlation_id,
            path=path,
            action=action,
            reason="missing_transfer_id",
        )

    db = SessionLocal()
    try:
        q = select(Transfer)
        if transfer_id:
            q = q.where(Transfer.id == int(transfer_id))
        else:
            q = q.where(Transfer.client_ref == client_ref)
        transfer = db.execute(q.with_for_update()).scalar_one_or_none()
        if not transfer:
            return _reject(
                status=404,
                error_code="TRANSFER_NOT_FOUND",
                detail="Transfer not found",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="transfer_not_found",
            )
        if transfer.from_user != user_id:
            return _reject(
                status=403,
                error_code="INVALID_STATE",
                detail="Only sender can cancel",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="forbidden_cancel",
                transfer_id=transfer.id,
            )
        if transfer.status != "PENDING":
            return _reject(
                status=409,
                error_code="INVALID_STATE",
                detail=f"Transfer status is {transfer.status}, expected PENDING",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="invalid_state",
                transfer_id=transfer.id,
                transfer_status=transfer.status,
            )

        sender = db.execute(
            select(User).where(User.id == transfer.from_user).with_for_update()
        ).scalar_one_or_none()
        receiver = db.get(User, transfer.to_user)
        if not sender:
            return _reject(
                status=404,
                error_code="ACCOUNT_NOT_FOUND",
                detail="Sender not found",
                correlation_id=correlation_id,
                path=path,
                action=action,
                reason="sender_not_found",
            )

        amount = transfer.amount
        sender.held_balance = max(0, int(sender.held_balance or 0) - amount)
        transfer.status = "CANCELLED"
        transfer.failure_code = ""
        transfer.hold_until = None
        db.add(
            Notification(
                user_id=sender.id,
                message=f"CANCELLED [{transfer.txn_type}]: nhả giữ {amount}",
            )
        )
        db.commit()

        log_event(
            logger,
            "transfer_cancelled",
            correlation_id=correlation_id,
            path=path,
            action=action,
            transfer_id=transfer.id,
            from_user_id=sender.id,
            amount_hash=mask_amount(amount),
            txn_type=transfer.txn_type,
            purpose=transfer.purpose or None,
            client_ref=transfer.client_ref or None,
            status="CANCELLED",
            outcome="cancelled",
            business_domain="banking",
            held_balance=sender.held_balance,
            available=_available(sender),
            service="transfer-service",
        )
        body = _transfer_dict(transfer, sender, receiver or sender)
        return {"status": 200, "body": body}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def expire_holds_once() -> int:
    """Release expired PENDING holds. Returns count expired."""
    db = SessionLocal()
    expired = 0
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = (
            db.execute(
                select(Transfer)
                .where(Transfer.status == "PENDING")
                .where(Transfer.hold_until.isnot(None))
                .where(Transfer.hold_until < now)
                .with_for_update()
            )
            .scalars()
            .all()
        )
        for transfer in rows:
            sender = db.execute(
                select(User).where(User.id == transfer.from_user).with_for_update()
            ).scalar_one_or_none()
            if sender:
                sender.held_balance = max(0, int(sender.held_balance or 0) - transfer.amount)
            transfer.status = "FAILED"
            transfer.failure_code = "HOLD_EXPIRED"
            transfer.hold_until = None
            if sender:
                db.add(
                    Notification(
                        user_id=sender.id,
                        message=f"EXPIRED [{transfer.txn_type}]: hết hạn giữ {transfer.amount}",
                    )
                )
            log_event(
                logger,
                "transfer_expired",
                transfer_id=transfer.id,
                from_user_id=transfer.from_user,
                amount_hash=mask_amount(transfer.amount),
                txn_type=transfer.txn_type,
                purpose=transfer.purpose or None,
                client_ref=transfer.client_ref or None,
                status="FAILED",
                failure_code="HOLD_EXPIRED",
                outcome="failure",
                business_domain="banking",
                service="transfer-service",
            )
            expired += 1
        if expired:
            db.commit()
        return expired
    except Exception as e:
        db.rollback()
        log_error_event(logger, "hold_expire_error", exc=e, service="transfer-service")
        return 0
    finally:
        db.close()


async def hold_expire_loop():
    while True:
        try:
            n = await asyncio.to_thread(expire_holds_once)
            if n:
                log_event(logger, "hold_expire_batch", count=n, service="transfer-service")
        except Exception as e:
            log_error_event(logger, "hold_expire_loop_error", exc=e, service="transfer-service")
        await asyncio.sleep(EXPIRE_POLL_SECONDS)


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
            published_at = body.get("published_at")

            tracer = get_tracer("transfer-service")
            with consumer_span(tracer, "transfer.process", {"action": action, "correlation_id": str(correlation_id or "")}):
                if should_log_request_flow():
                    log_event(
                        logger,
                        "rmq_message_received",
                        queue="transfer.requests",
                        correlation_id=correlation_id,
                        action=action,
                        path=path,
                        published_at=published_at,
                    )

                if action == "health":
                    result = {
                        "status": 200,
                        "body": {"status": "healthy", "service": "transfer", "database": "ok", "redis": "ok"},
                    }
                elif is_message_stale(published_at):
                    log_event(
                        logger,
                        "message_expired",
                        correlation_id=correlation_id,
                        path=path,
                        action=action,
                        failure_code="MESSAGE_EXPIRED",
                        published_at=published_at,
                        max_age_sec=MAX_MESSAGE_AGE_SEC,
                        outcome="failure",
                        business_domain="banking",
                        service="transfer-service",
                        queue="transfer.requests",
                    )
                    result = {
                        "status": 410,
                        "body": {
                            "error_code": "MESSAGE_EXPIRED",
                            "detail": "Request message expired before processing",
                            "status": "REJECTED",
                        },
                    }
                else:
                    trace = {"correlation_id": correlation_id, "path": path, "action": action}
                    if action in ("transfer", ""):
                        result = await handle_create(payload, headers, trace)
                    elif action == "confirm":
                        result = await handle_confirm(payload, headers, trace)
                    elif action == "cancel":
                        result = await handle_cancel(payload, headers, trace)
                    else:
                        result = {"status": 404, "body": {"detail": f"Unknown action: {action}", "error_code": "INVALID_STATE"}}
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
                await store_response(
                    redis,
                    body["correlation_id"],
                    {"status": 500, "body": {"detail": str(e), "error_code": "INTERNAL_ERROR"}},
                    logger=logger,
                )


async def consume():
    import aio_pika

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await declare_request_queue(channel, "transfer.requests")
    await queue.consume(process_message)
    log_event(logger, "rabbitmq_connected")
    log_event(
        logger,
        "transfer_consumer_started",
        queue="transfer.requests",
        service="transfer-service",
        prefetch=5,
        hold_ttl_seconds=HOLD_TTL_SECONDS,
        max_message_age_sec=MAX_MESSAGE_AGE_SEC,
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
    expire_task = asyncio.create_task(hold_expire_loop())
    yield
    expire_task.cancel()
    consumer_task.cancel()
    for t in (expire_task, consumer_task):
        try:
            await t
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
            "hold_ttl_seconds": HOLD_TTL_SECONDS,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

"""Shop ↔ Banking Kafka bridge.

Consume orders.events (order.created) from npd-shop.
Produce payments.events (payment.completed) for shop payment-worker.

Lab: SHOP_BRIDGE_AUTO_CONFIRM=true → auto emit payment after delay.
Prod-ish: call POST /api/shop/confirm-payment when bank transfer matches NOLI-*.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.kafka_bus import publish_json

SERVICE = "shop-bridge"
log = logging.getLogger(SERVICE)
logging.basicConfig(level=logging.INFO)

# In-memory pending shop orders (transfer_ref → payload). Lab scale only.
_pending: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in ("1", "true", "yes", "on")


def _emit_payment(transfer_ref: str, amount_vnd: int, order_code: str | None = None) -> bool:
    topic = os.getenv("KAFKA_PAYMENTS_TOPIC", "payments.events")
    payload = {
        "event": "payment.completed",
        "transfer_ref": transfer_ref.strip().upper(),
        "amount_vnd": int(amount_vnd),
        "order_code": order_code,
        "source": SERVICE,
    }
    return publish_json(topic, payload, key=payload["transfer_ref"])


def _auto_confirm(transfer_ref: str, amount_vnd: int, order_code: str | None) -> None:
    delay = float(os.getenv("SHOP_BRIDGE_AUTO_CONFIRM_DELAY_SEC", "3"))
    time.sleep(max(0.0, delay))
    ok = _emit_payment(transfer_ref, amount_vnd, order_code)
    log.info(
        "auto-confirm transfer_ref=%s amount=%s ok=%s",
        transfer_ref,
        amount_vnd,
        ok,
    )
    with _lock:
        _pending.pop(transfer_ref.strip().upper(), None)


def _handle_order_created(data: dict[str, Any]) -> None:
    transfer_ref = str(data.get("transfer_ref") or "").strip().upper()
    if not transfer_ref:
        log.warning("order.created missing transfer_ref: %s", data)
        return
    amount = int(data.get("total_vnd") or data.get("amount_vnd") or 0)
    order_code = data.get("order_code")
    with _lock:
        _pending[transfer_ref] = {
            "order_code": order_code,
            "amount_vnd": amount,
            "status": data.get("status"),
        }
    log.info(
        "shop order seen order_code=%s transfer_ref=%s amount=%s",
        order_code,
        transfer_ref,
        amount,
    )
    if _env_bool("SHOP_BRIDGE_AUTO_CONFIRM", False):
        threading.Thread(
            target=_auto_confirm,
            args=(transfer_ref, amount, order_code),
            daemon=True,
        ).start()


def _kafka_loop(stop: threading.Event) -> None:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "").strip()
    if not bootstrap:
        log.warning("KAFKA_BOOTSTRAP empty — consumer disabled")
        return
    try:
        from kafka import KafkaConsumer
    except ImportError:
        log.warning("kafka-python not installed; consumer disabled")
        return

    from common.kafka_auth import kafka_client_kwargs

    topic = os.getenv("KAFKA_ORDERS_TOPIC", "orders.events")
    group = os.getenv("KAFKA_GROUP_ID", "banking-shop-bridge")
    consumer = KafkaConsumer(
        topic,
        **kafka_client_kwargs(),
        group_id=group,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=50,
    )
    log.info("Kafka consumer started topic=%s group=%s", topic, group)
    while not stop.is_set():
        records = consumer.poll(timeout_ms=1000)
        for _tp, msgs in records.items():
            for msg in msgs:
                data = msg.value or {}
                try:
                    if data.get("event") == "order.created":
                        _handle_order_created(data)
                    consumer.commit()
                except Exception:
                    log.exception("failed processing orders.events offset=%s", msg.offset)
    consumer.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop = threading.Event()
    t = threading.Thread(target=_kafka_loop, args=(stop,), daemon=True)
    t.start()
    yield
    stop.set()


app = FastAPI(title=SERVICE, lifespan=lifespan)


class ConfirmPaymentIn(BaseModel):
    transfer_ref: str = Field(min_length=4, max_length=64)
    amount_vnd: int = Field(gt=0)
    order_code: str | None = None


@app.get("/health")
def health():
    with _lock:
        pending_n = len(_pending)
    return {
        "status": "ok",
        "service": SERVICE,
        "kafka": bool(os.getenv("KAFKA_BOOTSTRAP", "").strip()),
        "auto_confirm": _env_bool("SHOP_BRIDGE_AUTO_CONFIRM", False),
        "pending_orders": pending_n,
    }


@app.get("/api/shop/pending")
def list_pending():
    with _lock:
        return [{"transfer_ref": k, **v} for k, v in _pending.items()]


@app.post("/api/shop/confirm-payment")
def confirm_payment(body: ConfirmPaymentIn):
    """Banking ops / transfer matcher → emit payment.completed for shop."""
    ref = body.transfer_ref.strip().upper()
    with _lock:
        known = _pending.get(ref)
    order_code = body.order_code or (known or {}).get("order_code")
    ok = _emit_payment(ref, body.amount_vnd, order_code)
    if not ok:
        raise HTTPException(502, "Kafka publish failed")
    with _lock:
        _pending.pop(ref, None)
    return {"ok": True, "transfer_ref": ref, "amount_vnd": body.amount_vnd, "order_code": order_code}

"""
RabbitMQ utilities for Phase 8 (queue-based architecture).
Propagates W3C trace context via message headers for Kibana APM waterfall.
"""
import json
import os
import time
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

import aio_pika
from aio_pika import Message, DeliveryMode
from redis.asyncio import Redis

if TYPE_CHECKING:
    from logging import Logger

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
RESPONSE_TIMEOUT = int(os.getenv("RABBITMQ_RESPONSE_TIMEOUT", "20"))
RESPONSE_TTL = int(os.getenv("RABBITMQ_RESPONSE_TTL", "60"))
# Message TTL (ms) — broker drop nếu consumer không lấy kịp. >= RESPONSE_TIMEOUT.
MESSAGE_TTL_MS = int(os.getenv("RABBITMQ_MESSAGE_TTL_MS", "30000"))
# App-level stale age (seconds)
MAX_MESSAGE_AGE_SEC = int(os.getenv("MAX_MESSAGE_AGE_SEC", "30"))

REQUEST_QUEUES = (
    "auth.requests",
    "account.requests",
    "transfer.requests",
    "notification.requests",
)


def path_to_queue(path: str) -> str | None:
    """Map API path to queue name."""
    if path.startswith("/api/auth"):
        return "auth.requests"
    if path.startswith("/api/account"):
        return "account.requests"
    if path.startswith("/api/transfer"):
        return "transfer.requests"
    if path.startswith("/api/notifications"):
        return "notification.requests"
    return None


async def create_connection():
    """Create RabbitMQ connection."""
    return await aio_pika.connect_robust(RABBITMQ_URL)


async def declare_request_queue(channel: aio_pika.Channel, queue_name: str) -> aio_pika.abc.AbstractQueue:
    """
    Declare durable request queue.
    Per-message expiration (publish) + app published_at check handle stale mess;
    avoid x-message-ttl on declare (PRECONDITION_FAILED nếu queue lab đã tồn tại không TTL).
    """
    return await channel.declare_queue(queue_name, durable=True)


async def publish_and_wait(
    redis: Redis,
    channel: aio_pika.Channel,
    queue_name: str,
    body: dict,
    headers: dict | None = None,
    logger: "Logger | None" = None,
) -> dict:
    """
    Publish message to queue and wait for response via Redis.
    Consumer stores result in Redis at response:{correlation_id}.
    Injects OTel traceparent into RMQ headers (same trace as HTTP producer).
    """
    from common.logging_utils import log_event, should_log_request_flow
    from common.observability import (
        current_trace_fields,
        get_tracer,
        inject_trace_headers,
        producer_span,
        set_span_attributes,
    )

    correlation_id = str(uuid.uuid4())
    body["correlation_id"] = correlation_id
    body["published_at"] = datetime.now(timezone.utc).isoformat()
    redis_key = f"response:{correlation_id}"

    await declare_request_queue(channel, queue_name)

    rmq_headers: dict[str, Any] = dict(headers or {})
    # Keep app auth headers in body; RMQ headers carry trace + correlation for brokers/UI
    rmq_headers["correlation_id"] = correlation_id
    if body.get("request_id"):
        rmq_headers["request_id"] = str(body["request_id"])

    tracer = get_tracer(os.getenv("OTEL_SERVICE_NAME", "api-producer"))
    with producer_span(
        tracer,
        "rmq.publish",
        {
            "messaging.destination": queue_name,
            "messaging.rabbitmq.routing_key": queue_name,
            "correlation_id": correlation_id,
            "request_id": body.get("request_id") or "",
        },
    ):
        rmq_headers = inject_trace_headers(rmq_headers)
        set_span_attributes(**{"messaging.destination": queue_name, "correlation_id": correlation_id})
        await channel.default_exchange.publish(
            Message(
                body=json.dumps(body).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                headers=rmq_headers,
                expiration=MESSAGE_TTL_MS,
            ),
            routing_key=queue_name,
        )

        if logger and should_log_request_flow():
            log_event(
                logger,
                "rmq_publish",
                queue=queue_name,
                correlation_id=correlation_id,
                request_id=body.get("request_id"),
                redis_key=redis_key,
                published_at=body["published_at"],
                message_ttl_ms=MESSAGE_TTL_MS,
                path=body.get("path"),
                action=body.get("action"),
            )

        wait_start = time.perf_counter()
        if logger and should_log_request_flow():
            log_event(
                logger,
                "redis_wait_start",
                correlation_id=correlation_id,
                request_id=body.get("request_id"),
                redis_key=redis_key,
                queue=queue_name,
            )

        for _ in range(RESPONSE_TIMEOUT * 10):  # 100ms intervals
            raw = await redis.get(redis_key)
            if raw:
                result = json.loads(raw)
                await redis.delete(redis_key)
                wait_ms = round((time.perf_counter() - wait_start) * 1000, 2)
                if logger and should_log_request_flow():
                    log_event(
                        logger,
                        "redis_response",
                        correlation_id=correlation_id,
                        request_id=body.get("request_id"),
                        status=result.get("status"),
                        wait_ms=wait_ms,
                        queue=queue_name,
                    )
                result["_correlation_id"] = correlation_id
                result["_trace_id"] = current_trace_fields().get("trace.id")
                return result
            await asyncio.sleep(0.1)

    raise TimeoutError(f"No response for {correlation_id} within {RESPONSE_TIMEOUT}s")


async def store_response(
    redis: Redis,
    correlation_id: str,
    result: dict,
    ttl: int = RESPONSE_TTL,
    logger: "Logger | None" = None,
):
    """Store response for producer to pick up."""
    from common.logging_utils import log_event, should_log_request_flow

    key = f"response:{correlation_id}"
    await redis.setex(key, ttl, json.dumps(result))
    if logger and should_log_request_flow():
        log_event(
            logger,
            "redis_store_response",
            correlation_id=correlation_id,
            redis_key=key,
            status=result.get("status"),
            ttl=ttl,
        )


def is_message_stale(published_at: str | None, max_age_sec: int | None = None) -> bool:
    """True if published_at older than max_age_sec (UTC ISO)."""
    if not published_at:
        return False
    age = max_age_sec if max_age_sec is not None else MAX_MESSAGE_AGE_SEC
    try:
        ts = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() > age
    except Exception:
        return False


def message_trace_carrier(message: Any) -> dict[str, Any]:
    """Build OTel carrier from aio_pika IncomingMessage headers (+ body fallback)."""
    carrier: dict[str, Any] = {}
    headers = getattr(message, "headers", None) or {}
    if isinstance(headers, dict):
        carrier.update(headers)
    return carrier

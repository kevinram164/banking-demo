"""
RabbitMQ utilities for Phase 8 (queue-based architecture).
"""
import json
import os
import uuid
import asyncio
from typing import Any

import aio_pika
from aio_pika import Message, DeliveryMode
from redis.asyncio import Redis

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
RESPONSE_TIMEOUT = int(os.getenv("RABBITMQ_RESPONSE_TIMEOUT", "30"))
RESPONSE_TTL = int(os.getenv("RABBITMQ_RESPONSE_TTL", "60"))


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


async def publish_and_wait(
    redis: Redis,
    channel: aio_pika.Channel,
    queue_name: str,
    body: dict,
    headers: dict | None = None,
) -> dict:
    """
    Publish message to queue and wait for response via Redis.
    Consumer stores result in Redis at response:{correlation_id}.
    """
    correlation_id = str(uuid.uuid4())
    body["correlation_id"] = correlation_id
    redis_key = f"response:{correlation_id}"

    # Ensure queue exists
    queue = await channel.declare_queue(queue_name, durable=True)
    await channel.default_exchange.publish(
        Message(
            body=json.dumps(body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=correlation_id,
            headers=headers or {},
        ),
        routing_key=queue_name,
    )

    # Wait for response in Redis (consumer will SET with TTL)
    for _ in range(RESPONSE_TIMEOUT * 10):  # 100ms intervals
        raw = await redis.get(redis_key)
        if raw:
            result = json.loads(raw)
            await redis.delete(redis_key)
            return result
        await asyncio.sleep(0.1)

    raise TimeoutError(f"No response for {correlation_id} within {RESPONSE_TIMEOUT}s")


async def store_response(redis: Redis, correlation_id: str, result: dict, ttl: int = RESPONSE_TTL):
    """Store response for producer to pick up."""
    key = f"response:{correlation_id}"
    await redis.setex(key, ttl, json.dumps(result))

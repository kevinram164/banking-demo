import os
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse, unquote
from redis.asyncio import Redis
from redis.asyncio.sentinel import Sentinel
from fastapi import HTTPException

if TYPE_CHECKING:
    from logging import Logger

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))


async def create_redis_client(url: str | None = None, logger: "Logger | None" = None) -> Redis:
    url = url or REDIS_URL
    if url.startswith("sentinel://"):
        parsed = urlparse(url)
        password = unquote(parsed.password) if parsed.password else None
        host = parsed.hostname or "localhost"
        port = parsed.port or 26379
        path_parts = parsed.path.strip("/").split("/")
        db = int(path_parts[0]) if path_parts[0] else 0
        service_name = path_parts[1] if len(path_parts) > 1 else "mymaster"
        sentinel = Sentinel(
            [(host, port)],
            sentinel_kwargs={"password": password},
            password=password,
            db=db,
            decode_responses=True,
        )
        client = sentinel.master_for(service_name)
    else:
        client = Redis.from_url(url, decode_responses=True)

    if logger:
        from common.logging_utils import log_event
        try:
            await client.ping()
            log_event(logger, "redis_connected")
        except Exception:
            pass  # Don't fail startup if ping fails
    return client


async def create_session(redis: Redis, user_id: int) -> str:
    sid = uuid.uuid4().hex
    await redis.setex(f"session:{sid}", SESSION_TTL, str(user_id))
    return sid


async def get_user_id_from_session(redis: Redis, x_session: str | None) -> int:
    if not x_session:
        raise HTTPException(401, "Missing session")
    v = await redis.get(f"session:{x_session}")
    if not v:
        raise HTTPException(401, "Invalid/expired session")
    return int(v)


async def set_presence(redis: Redis, user_id: int, online: bool):
    key = f"presence:{user_id}"
    if online:
        await redis.setex(key, 60, "online")
    else:
        await redis.delete(key)


async def publish_notify(redis: Redis, user_id: int, message: str):
    await redis.publish(f"notify:{user_id}", message)

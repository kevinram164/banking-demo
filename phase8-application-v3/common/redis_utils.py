import json
import os
import uuid
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, unquote
from redis.asyncio import Redis
from redis.asyncio.sentinel import Sentinel
from fastapi import HTTPException

if TYPE_CHECKING:
    from logging import Logger

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
USER_CACHE_TTL = int(os.getenv("USER_CACHE_TTL_SECONDS", "300"))  # 5 phút


def _sentinel_endpoints(host: str, port: int) -> list[tuple[str, int]]:
    """
    Bitnami ClusterIP:26379 often breaks redis-py AUTH from other namespaces.
    Prefer headless pod DNS (same as media-worker / redis-cli probe).
    Override: REDIS_SENTINEL_HOSTS=host1:26379,host2:26379,host3:26379
    """
    raw = os.getenv("REDIS_SENTINEL_HOSTS", "").strip()
    if raw:
        out: list[tuple[str, int]] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                h, p = part.rsplit(":", 1)
                out.append((h, int(p)))
            else:
                out.append((part, port))
        if out:
            return out

    if "redis-ha" in host and "headless" not in host:
        return [
            (
                f"redis-ha-node-{i}.redis-ha-headless.redis.svc.cluster.local",
                port,
            )
            for i in range(3)
        ]
    return [(host, port)]


async def create_redis_client(url: str | None = None, logger: "Logger | None" = None) -> Redis:
    url = url or REDIS_URL
    if url.startswith("sentinel://"):
        parsed = urlparse(url)
        password = unquote(parsed.password) if parsed.password else None
        host = parsed.hostname or "localhost"
        port = parsed.port or 26379
        path_parts = [p for p in parsed.path.strip("/").split("/") if p != ""]
        db = int(path_parts[0]) if path_parts else 0
        service_name = path_parts[1] if len(path_parts) > 1 else "mymaster"
        endpoints = _sentinel_endpoints(host, port)

        # password-only in sentinel_kwargs (Bitnami requirepass). Do not pass
        # username=default — that often yields MasterNotFoundError.
        sentinel_kwargs: dict[str, Any] = {"protocol": 2}
        master_kwargs: dict[str, Any] = {
            "db": db,
            "decode_responses": True,
            "protocol": 2,
        }
        if password is not None:
            sentinel_kwargs["password"] = password
            master_kwargs["password"] = password

        sentinel = Sentinel(
            endpoints,
            sentinel_kwargs=sentinel_kwargs,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
        client = sentinel.master_for(service_name, **master_kwargs)
    else:
        client = Redis.from_url(url, decode_responses=True)

    if logger:
        from common.logging_utils import log_event, log_error_event
        try:
            await client.ping()
            log_event(logger, "redis_connected")
        except Exception as exc:
            log_error_event(
                logger,
                "redis_connect_failed",
                exc,
                error=str(exc),
                error_type=type(exc).__name__,
            )
    return client


async def get_user_for_login(redis: Redis, phone: str, username: str) -> dict[str, Any] | None:
    """
    Lấy user để verify login — ưu tiên Redis cache, miss thì query DB (caller xử lý).
    Trả về dict {id, phone, username, account_number, password_hash, balance} hoặc None.
    """
    if phone:
        key = f"user_cache:phone:{phone}"
    elif username:
        key = f"user_cache:username:{username}"
    else:
        return None
    raw = await redis.get(key)
    if raw:
        return json.loads(raw)
    return None


async def set_user_for_login_cache(redis: Redis, user: dict[str, Any], ttl: int = USER_CACHE_TTL) -> None:
    """Cache user sau khi query DB — dùng cho login lần sau."""
    data = {
        "id": user["id"],
        "phone": user["phone"],
        "username": user["username"],
        "account_number": user["account_number"],
        "password_hash": user["password_hash"],
        "balance": user["balance"],
    }
    val = json.dumps(data)
    await redis.setex(f"user_cache:phone:{user['phone']}", ttl, val)
    if user.get("username"):
        await redis.setex(f"user_cache:username:{user['username']}", ttl, val)


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

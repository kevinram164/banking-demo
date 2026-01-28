import os, uuid
from redis.asyncio import Redis
from fastapi import HTTPException

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))

async def create_session(redis: Redis, user_id: int) -> str:
    """Create a new session for a user"""
    sid = uuid.uuid4().hex
    await redis.setex(f"session:{sid}", SESSION_TTL, str(user_id))
    return sid

async def get_user_id_from_session(redis: Redis, x_session: str | None) -> int:
    """Get user ID from session token"""
    if not x_session:
        raise HTTPException(401, "Missing session")
    v = await redis.get(f"session:{x_session}")
    if not v:
        raise HTTPException(401, "Invalid/expired session")
    return int(v)

async def set_presence(redis: Redis, user_id: int, online: bool):
    """Set user presence status"""
    key = f"presence:{user_id}"
    if online:
        await redis.setex(key, 60, "online")   # 60s TTL, websocket keep refreshing
    else:
        await redis.delete(key)

async def publish_notify(redis: Redis, user_id: int, message: str):
    """Publish notification to user's channel"""
    await redis.publish(f"notify:{user_id}", message)

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from redis.asyncio import Redis

from common.db import SessionLocal, engine, Base
from common.models import User
from common.redis_utils import get_user_id_from_session
from common.observability import instrument_fastapi
from common.logging_utils import get_json_logger, RequestLogMiddleware, log_event

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

logger = get_json_logger("account-service")

redis: Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    yield
    if redis:
        await redis.close()

app = FastAPI(title="Account Service", lifespan=lifespan)
instrument_fastapi(app, "account-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware, logger=logger, service_name="account-service")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/me")
async def me(x_session: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Get current user profile and balance"""
    user_id = await get_user_id_from_session(redis, x_session)
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return {
        "id": u.id,
        "phone": u.phone,
        "username": u.username,
        "account_number": u.account_number,
        "balance": u.balance,
    }

@app.get("/balance")
async def balance(x_session: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Get current user balance"""
    user_id = await get_user_id_from_session(redis, x_session)
    u = db.get(User, user_id)
    if not u:
        log_event(
            logger,
            "balance_failed",
            reason="USER_NOT_FOUND",
        )
        raise HTTPException(404, "User not found")
    return {"balance": u.balance}


@app.get("/lookup")
async def lookup(account_number: str, db: Session = Depends(get_db)):
    """Lookup receiver display name by account number (for transfer UI)."""
    acct = (account_number or "").strip()
    if not acct.isdigit():
        raise HTTPException(400, "account_number must be digits only")

    u = db.execute(select(User).where(User.account_number == acct)).scalar_one_or_none()
    if not u:
        log_event(
            logger,
            "account_lookup_failed",
            reason="ACCOUNT_NOT_FOUND",
            account_number=acct,
        )
        raise HTTPException(404, "Account not found")

    log_event(
        logger,
        "account_lookup_success",
        account_number=u.account_number,
        username=u.username,
    )
    return {"account_number": u.account_number, "username": u.username}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
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
        
        redis_status = "ok" if redis else "error"
        
        if db_status == "ok" and redis_status == "ok":
            return {"status": "healthy", "service": "account-service", "database": db_status, "redis": redis_status}
        else:
            raise HTTPException(503, detail={"status": "unhealthy", "database": db_status, "redis": redis_status})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, detail=f"Health check failed: {str(e)}")

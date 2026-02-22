import os
import secrets
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from common.db import SessionLocal, engine, Base
from common.models import User
from common.auth import hash_password, verify_password
from common.redis_utils import create_session
from common.observability import instrument_fastapi
from common.logging_utils import get_json_logger, RequestLogMiddleware, log_event

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

logger = get_json_logger("auth-service")

redis: Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    yield
    if redis:
        await redis.close()

app = FastAPI(title="Auth Service", lifespan=lifespan)
instrument_fastapi(app, "auth-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware, logger=logger, service_name="auth-service")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _gen_account_number() -> str:
    # 12-digit numeric, demo-friendly (không phải IBAN thật)
    return "".join(str(secrets.randbelow(10)) for _ in range(12))


def _mask_phone(phone: str) -> str:
    phone = phone.strip()
    if len(phone) <= 4:
        return "*" * len(phone)
    return phone[:2] + ("*" * (len(phone) - 4)) + phone[-2:]


class RegisterReq(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    username: str = Field(min_length=2, max_length=50)  # display name
    password: str = Field(min_length=6, max_length=128)

class LoginReq(BaseModel):
    # backward-compatible:
    # - v2: phone
    # - v1: username
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    username: str | None = Field(default=None, min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)

@app.post("/register")
async def register(body: RegisterReq, db: Session = Depends(get_db)):
    """Register a new user"""
    phone = body.phone.strip()
    username = body.username.strip()
    if not phone.isdigit():
        log_event(logger, "register_failed", reason="PHONE_NOT_DIGITS", phone=phone, username=username)
        raise HTTPException(400, "Phone must be digits only")

    exists_phone = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
    if exists_phone:
        log_event(logger, "register_failed", reason="PHONE_EXISTS", phone=phone, username=username)
        raise HTTPException(409, "Phone already exists")

    account_number = None
    for _ in range(20):
        candidate = _gen_account_number()
        taken = db.execute(select(User).where(User.account_number == candidate)).scalar_one_or_none()
        if not taken:
            account_number = candidate
            break
    if not account_number:
        log_event(logger, "register_failed", reason="ACCOUNT_NUMBER_GENERATION_EXHAUSTED", phone=phone, username=username)
        raise HTTPException(503, "Cannot generate account number, retry later")

    u = User(
        phone=phone,
        account_number=account_number,
        username=username,
        password_hash=hash_password(body.password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    log_event(
        logger,
        "register_success",
        user_id=u.id,
        phone=u.phone,
        username=u.username,
        account_number=u.account_number,
    )
    return {
        "id": u.id,
        "phone": _mask_phone(u.phone),
        "username": u.username,
        "account_number": u.account_number,
        "balance": u.balance,
    }

@app.post("/login")
async def login(body: LoginReq, db: Session = Depends(get_db)):
    """Login and create session"""
    phone = (body.phone or "").strip()
    username = (body.username or "").strip()

    if phone:
        if not phone.isdigit():
            log_event(logger, "login_failed", reason="PHONE_NOT_DIGITS", phone=phone)
            raise HTTPException(400, "Phone must be digits only")
        u = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
    elif username:
        u = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    else:
        log_event(logger, "login_failed", reason="MISSING_IDENTIFIER")
        raise HTTPException(400, "Missing phone/username")

    if not u or not verify_password(body.password, u.password_hash):
        log_event(
            logger,
            "login_failed",
            reason="INVALID_CREDENTIALS",
            phone=phone or username,
        )
        raise HTTPException(401, "Invalid credentials")

    sid = await create_session(redis, u.id)

    log_event(
        logger,
        "login_success",
        user_id=u.id,
        phone=u.phone,
        username=u.username,
        account_number=u.account_number,
    )
    return {
        "session": sid,
        "phone": _mask_phone(u.phone),
        "username": u.username,
        "account_number": u.account_number,
        "balance": u.balance,
    }

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
            return {"status": "healthy", "service": "auth-service", "database": db_status, "redis": redis_status}
        else:
            raise HTTPException(503, detail={"status": "unhealthy", "database": db_status, "redis": redis_status})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, detail=f"Health check failed: {str(e)}")

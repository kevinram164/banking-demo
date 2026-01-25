import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from redis.asyncio import Redis

from common.db import SessionLocal, engine, Base
from common.models import User
from common.auth import hash_password, verify_password
from common.redis_utils import create_session
from common.observability import instrument_fastapi

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterReq(BaseModel):
    username: str
    password: str

class LoginReq(BaseModel):
    username: str
    password: str

@app.post("/register")
async def register(body: RegisterReq, db: Session = Depends(get_db)):
    """Register a new user"""
    if len(body.username) < 3 or len(body.password) < 6:
        raise HTTPException(400, "Username >=3, password >=6")

    exists = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Username already exists")

    u = User(username=body.username, password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "username": u.username, "balance": u.balance}

@app.post("/login")
async def login(body: LoginReq, db: Session = Depends(get_db)):
    """Login and create session"""
    u = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")

    sid = await create_session(redis, u.id)
    return {"session": sid, "username": u.username, "balance": u.balance}

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

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from redis.asyncio import Redis

from common.db import SessionLocal, engine, Base
from common.models import User, Transfer, Notification
from common.redis_utils import get_user_id_from_session, create_redis_client
from common.observability import instrument_fastapi
from common.logging_utils import get_json_logger, RequestLogMiddleware, log_event, setup_exception_logging

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

logger = get_json_logger("account-service")

redis: Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    redis = await create_redis_client(REDIS_URL)
    yield
    if redis:
        await redis.close()

app = FastAPI(title="Account Service", lifespan=lifespan)
instrument_fastapi(app, "account-service")
setup_exception_logging(app, logger, "account-service")
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
        log_event(logger, "me_failed", reason="USER_NOT_FOUND", user_id=user_id)
        raise HTTPException(404, "User not found")
    log_event(logger, "me_success", user_id=u.id, username=u.username, account_number=u.account_number)
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
        log_event(logger, "balance_failed", reason="USER_NOT_FOUND", user_id=user_id)
        raise HTTPException(404, "User not found")
    log_event(logger, "balance_success", user_id=u.id, balance=u.balance)
    return {"balance": u.balance}


@app.get("/lookup")
async def lookup(account_number: str, db: Session = Depends(get_db)):
    """Lookup receiver display name by account number (for transfer UI)."""
    acct = (account_number or "").strip()
    if not acct.isdigit():
        log_event(logger, "account_lookup_failed", reason="ACCOUNT_NOT_DIGITS", account_number=acct)
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

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "banking-admin-2025")


def verify_admin(x_admin_secret: str | None = Header(default=None)):
    if not x_admin_secret or x_admin_secret != ADMIN_SECRET:
        raise HTTPException(403, "Forbidden")


@app.get("/admin/users")
async def admin_list_users(
    page: int = 1,
    size: int = 20,
    search: str = "",
    _: None = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """List all users with pagination and search."""
    query = select(User)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (User.username.ilike(pattern))
            | (User.phone.ilike(pattern))
            | (User.account_number.ilike(pattern))
        )

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    users = (
        db.execute(query.order_by(User.id.desc()).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )

    log_event(logger, "admin_list_users", page=page, size=size, search=search, total=total)
    return {
        "users": [
            {
                "id": u.id,
                "phone": u.phone,
                "username": u.username,
                "account_number": u.account_number,
                "balance": u.balance,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
    }


@app.get("/admin/stats")
async def admin_stats(_: None = Depends(verify_admin), db: Session = Depends(get_db)):
    """Dashboard statistics."""
    total_users = db.execute(select(func.count(User.id))).scalar()
    total_balance = db.execute(select(func.coalesce(func.sum(User.balance), 0))).scalar()
    total_transfers = db.execute(select(func.count(Transfer.id))).scalar()
    total_transfer_amount = db.execute(
        select(func.coalesce(func.sum(Transfer.amount), 0))
    ).scalar()
    total_notifications = db.execute(select(func.count(Notification.id))).scalar()

    log_event(logger, "admin_stats", total_users=total_users, total_transfers=total_transfers)
    return {
        "total_users": total_users,
        "total_balance": total_balance,
        "total_transfers": total_transfers,
        "total_transfer_amount": total_transfer_amount,
        "total_notifications": total_notifications,
    }


@app.get("/admin/users/{user_id}")
async def admin_user_detail(
    user_id: int,
    _: None = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """Get user detail with recent transfers."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")

    transfers = (
        db.execute(
            select(Transfer)
            .where((Transfer.from_user == user_id) | (Transfer.to_user == user_id))
            .order_by(Transfer.created_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )

    return {
        "id": u.id,
        "phone": u.phone,
        "username": u.username,
        "account_number": u.account_number,
        "balance": u.balance,
        "transfers": [
            {
                "id": t.id,
                "from_user": t.from_user,
                "to_user": t.to_user,
                "amount": t.amount,
                "direction": "out" if t.from_user == user_id else "in",
                "created_at": t.created_at.isoformat() + "Z",
            }
            for t in transfers
        ],
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
            return {"status": "healthy", "service": "account-service", "database": db_status, "redis": redis_status}
        else:
            raise HTTPException(503, detail={"status": "unhealthy", "database": db_status, "redis": redis_status})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, detail=f"Health check failed: {str(e)}")

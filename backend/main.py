import os, uuid, asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, selectinload
from pydantic import BaseModel
from passlib.context import CryptContext
from redis.asyncio import Redis

from db import SessionLocal, engine, Base
from models import User, Transfer, Notification

Base.metadata.create_all(bind=engine)

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

redis: Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global redis
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    yield
    # Shutdown
    if redis:
        await redis.close()

app = FastAPI(lifespan=lifespan)
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

def hash_password(pw: str) -> str:
    return pwd.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd.verify(pw, hashed)

async def create_session(user_id: int) -> str:
    sid = uuid.uuid4().hex
    await redis.setex(f"session:{sid}", SESSION_TTL, str(user_id))
    return sid

async def get_user_id_from_session(x_session: str | None) -> int:
    if not x_session:
        raise HTTPException(401, "Missing session")
    v = await redis.get(f"session:{x_session}")
    if not v:
        raise HTTPException(401, "Invalid/expired session")
    return int(v)

# presence: refresh TTL while websocket connected
async def set_presence(user_id: int, online: bool):
    key = f"presence:{user_id}"
    if online:
        await redis.setex(key, 60, "online")   # 60s TTL, websocket keep refreshing
    else:
        await redis.delete(key)

async def publish_notify(user_id: int, message: str):
    # publish realtime message to that user's channel
    await redis.publish(f"notify:{user_id}", message)

class RegisterReq(BaseModel):
    username: str
    password: str

class LoginReq(BaseModel):
    username: str
    password: str

class TransferReq(BaseModel):
    to_username: str
    amount: int

@app.post("/api/register")
def register(body: RegisterReq, db: Session = Depends(get_db)):
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

@app.post("/api/login")
async def login(body: LoginReq, db: Session = Depends(get_db)):
    u = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")

    sid = await create_session(u.id)
    return {"session": sid, "username": u.username, "balance": u.balance}

@app.get("/api/me")
async def me(x_session: str | None = Header(default=None), db: Session = Depends(get_db)):
    user_id = await get_user_id_from_session(x_session)
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return {"id": u.id, "username": u.username, "balance": u.balance}

@app.post("/api/transfer")
async def transfer(body: TransferReq, x_session: str | None = Header(default=None), db: Session = Depends(get_db)):
    user_id = await get_user_id_from_session(x_session)

    if body.amount <= 0:
        raise HTTPException(400, "Amount must be > 0")

    sender = db.get(User, user_id)
    if not sender:
        raise HTTPException(404, "Sender not found")

    receiver = db.execute(select(User).where(User.username == body.to_username)).scalar_one_or_none()
    if not receiver:
        raise HTTPException(404, "Receiver not found")

    if receiver.id == sender.id:
        raise HTTPException(400, "Cannot transfer to yourself")

    if sender.balance < body.amount:
        raise HTTPException(400, "Insufficient balance")

    # update balances + save transfer + notifications
    sender.balance -= body.amount
    receiver.balance += body.amount

    t = Transfer(from_user=sender.id, to_user=receiver.id, amount=body.amount)
    db.add(t)

    msg_sender = f"Bạn đã chuyển {body.amount} đến {receiver.username}"
    msg_receiver = f"Bạn nhận {body.amount} từ {sender.username}"

    db.add(Notification(user_id=sender.id, message=msg_sender))
    db.add(Notification(user_id=receiver.id, message=msg_receiver))

    db.commit()

    # realtime push via redis pubsub
    await publish_notify(receiver.id, msg_receiver)

    return {"ok": True, "from": sender.username, "to": receiver.username, "amount": body.amount}

@app.get("/api/notifications")
async def list_notifications(x_session: str | None = Header(default=None), db: Session = Depends(get_db)):
    user_id = await get_user_id_from_session(x_session)
    items = (
        db.execute(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(50))
        .scalars()
        .all()
    )
    return [{
        "id": x.id,
        "message": x.message,
        "is_read": x.is_read,
        "created_at": x.created_at.isoformat() + "Z",
    } for x in items]

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    # ws://localhost:8000/ws?session=...
    session = websocket.query_params.get("session")
    if not session:
        await websocket.close(code=1008)
        return

    try:
        user_id = await get_user_id_from_session(session)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    pubsub = redis.pubsub()
    await pubsub.subscribe(f"notify:{user_id}")

    async def presence_loop():
        try:
            while True:
                await set_presence(user_id, True)
                await asyncio.sleep(20)  # refresh TTL
        except Exception:
            pass

    async def notify_loop():
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    await websocket.send_json({"type": "notification", "message": msg["data"]})
                await asyncio.sleep(0.05)
        except Exception:
            pass

    p_task = asyncio.create_task(presence_loop())
    n_task = asyncio.create_task(notify_loop())

    try:
        while True:
            # receive to keep connection alive (client can send ping)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        p_task.cancel()
        n_task.cancel()
        await set_presence(user_id, False)
        try:
            await pubsub.unsubscribe(f"notify:{user_id}")
            await pubsub.close()
        except Exception:
            pass

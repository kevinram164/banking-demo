from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from common.db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # v2: đăng nhập bằng số điện thoại + mỗi user có số tài khoản (random, unique)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    account_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    # hiển thị UI
    username: Mapped[str] = mapped_column(String(50), index=True)

    password_hash: Mapped[str] = mapped_column(String(255))
    balance: Mapped[int] = mapped_column(Integer, default=100000)  # demo: 100k

class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    to_user: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from common.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    account_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    balance: Mapped[int] = mapped_column(Integer, default=10_000_000)
    # Phong tỏa — available = balance - held_balance
    held_balance: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    to_user: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    # Nội dung CK (vd NOLI-XXXX) — khớp đơn shop
    note: Mapped[str] = mapped_column(String(64), default="", server_default="")
    txn_type: Mapped[str] = mapped_column(String(32), default="P2P", server_default="P2P")
    purpose: Mapped[str] = mapped_column(String(128), default="", server_default="")
    channel: Mapped[str] = mapped_column(String(32), default="mobile", server_default="mobile")
    client_ref: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    status: Mapped[str] = mapped_column(String(16), default="SUCCESS", server_default="SUCCESS", index=True)
    failure_code: Mapped[str] = mapped_column(String(64), default="", server_default="")
    hold_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

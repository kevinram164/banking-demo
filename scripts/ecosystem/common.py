"""Shared helpers for ecosystem cron jobs."""
from __future__ import annotations

import json
import os
import random
import time
import warnings
from pathlib import Path

import requests

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Vũ", "Đặng", "Bùi", "Đỗ"]
TEN_DEM = ["Văn", "Thị", "Minh", "Thu", "Hồng", "Thanh", "Quang", "Anh", "Tuấn", ""]
TEN = [
    "An", "Bình", "Chi", "Dũng", "Hà", "Hương", "Khoa", "Lan", "Long", "Mai",
    "Nam", "Nga", "Phương", "Sơn", "Thảo", "Trung", "Tú", "Vy", "Yến", "Đức",
]


def load_env(path: str | None = None) -> None:
    env_path = Path(path or os.environ.get("ECOSYSTEM_ENV", "/home/sysadmin/npd-ecosystem/.env"))
    if not env_path.is_file():
        # Dev: scripts/ecosystem/.env
        alt = Path(__file__).resolve().parent / ".env"
        if alt.is_file():
            env_path = alt
        else:
            return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def cfg_int(key: str, default: int) -> int:
    try:
        return int(cfg(key, str(default)))
    except ValueError:
        return default


def cfg_float(key: str, default: float) -> float:
    try:
        return float(cfg(key, str(default)))
    except ValueError:
        return default


def verify_tls() -> bool:
    return cfg("VERIFY_TLS", "0") not in ("0", "false", "False", "no")


def bank_url() -> str:
    return cfg("BANK_URL", "https://npd-banking.co").rstrip("/")


def shop_url() -> str:
    return cfg("SHOP_URL", "https://npd-shop.co").rstrip("/")


def data_dir() -> Path:
    p = Path(cfg("DATA_DIR", str(Path(__file__).resolve().parent / "data")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def users_path() -> Path:
    return data_dir() / "users.json"


def ly_path() -> Path:
    return data_dir() / "huongly.json"


def setup_warnings() -> None:
    if not verify_tls():
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def random_vn_name(index: int, prefix: str = "") -> str:
    ho = random.choice(HO)
    dem = random.choice(TEN_DEM)
    ten = random.choice(TEN)
    name = f"{prefix}{ho} {dem} {ten}".replace("  ", " ").strip()
    return f"{name} {index}"


def phone_from_index(index: int) -> str:
    """09 + 8 digits unique theo index (tránh đụng Ly 0901234567)."""
    n = 20000000 + (index % 70000000)
    return f"09{n:08d}"


def save_users(users: list[dict]) -> None:
    users_path().write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def load_users() -> list[dict]:
    p = users_path()
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def load_ly() -> dict | None:
    p = ly_path()
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    acct = cfg("LY_ACCOUNT_NUMBER")
    if acct:
        return {
            "phone": cfg("LY_PHONE", "0901234567"),
            "username": cfg("LY_USERNAME", "Nguyễn Hương Ly"),
            "password": cfg("DEFAULT_PASSWORD", "123456"),
            "account_number": acct,
        }
    return None


def save_ly(data: dict) -> None:
    ly_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def bank_register(
    phone: str,
    username: str,
    password: str,
    initial_balance: int,
    session: requests.Session | None = None,
) -> tuple[str, dict | None, str]:
    s = session or requests.Session()
    url = f"{bank_url()}/api/auth/register"
    try:
        r = s.post(
            url,
            json={
                "phone": phone,
                "username": username,
                "password": password,
                "initial_balance": initial_balance,
            },
            timeout=30,
            verify=verify_tls(),
        )
        if r.status_code == 200:
            return "ok", r.json(), ""
        if r.status_code == 409:
            return "skip", None, "exists"
        return "fail", None, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return "fail", None, str(e)


def bank_login(phone: str, password: str, session: requests.Session | None = None) -> dict | None:
    s = session or requests.Session()
    for attempt in range(4):
        try:
            r = s.post(
                f"{bank_url()}/api/auth/login",
                json={"phone": phone, "password": password},
                timeout=30,
                verify=verify_tls(),
            )
            if r.status_code == 200:
                data = r.json()
                return {
                    "phone": phone,
                    "password": password,
                    "session": data["session"],
                    "username": data.get("username", ""),
                    "account_number": data.get("account_number", ""),
                    "balance": data.get("balance", 0),
                }
            return None
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    return None


def bank_credit(phone: str, balance: int) -> bool:
    r = requests.post(
        f"{bank_url()}/api/account/admin/credit",
        json={"phone": phone, "balance": balance},
        headers={"X-Admin-Secret": cfg("ADMIN_SECRET", "banking-admin-2025")},
        timeout=20,
        verify=verify_tls(),
    )
    return r.status_code == 200


def bank_transfer(
    session_token: str,
    to_account: str,
    amount: int,
    note: str = "",
    http: requests.Session | None = None,
) -> dict:
    s = http or requests.Session()
    body = {"to_account_number": to_account, "amount": int(amount)}
    if note:
        body["note"] = note
    try:
        r = s.post(
            f"{bank_url()}/api/transfer/transfer",
            json=body,
            headers={"X-Session": session_token},
            timeout=60,
            verify=verify_tls(),
        )
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "detail": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def shop_products() -> list[dict]:
    r = requests.get(f"{shop_url()}/api/products", timeout=30, verify=verify_tls())
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    return data.get("items") or data.get("products") or []


def product_price(p: dict) -> int:
    return int(p.get("price_vnd") or p.get("price") or 0)


def product_stock(p: dict) -> int:
    return int(p.get("stock") or 0)


def shop_checkout(
    product_id: int,
    quantity: int,
    customer_name: str,
    customer_phone: str,
) -> dict:
    r = requests.post(
        f"{shop_url()}/api/orders",
        json={
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_address": "NPD Lab Eco System, Q1, HCMC",
            "note": "ecosystem-cron",
            "items": [{"product_id": product_id, "quantity": quantity}],
        },
        timeout=40,
        verify=verify_tls(),
    )
    if r.status_code >= 400:
        raise RuntimeError(f"checkout {r.status_code}: {r.text[:300]}")
    return r.json()


def order_pay_fields(order: dict) -> tuple[str, int]:
    """(transfer_ref / NOLI-*, amount_vnd)."""
    pay = order.get("payment") or {}
    ref = (
        order.get("transfer_ref")
        or pay.get("transfer_ref")
        or order.get("payment_code")
        or ""
    )
    amount = int(
        order.get("total_vnd")
        or pay.get("amount_vnd")
        or order.get("total")
        or order.get("amount")
        or 0
    )
    return str(ref), amount

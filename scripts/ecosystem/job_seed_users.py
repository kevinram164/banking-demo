#!/usr/bin/env python3
"""Job 1 — Seed users (cron: tuần 1 lần).

- Đảm bảo Ly tồn tại, balance 50tr
- Bổ sung customers tới TARGET_CUSTOMERS, suppliers tới TARGET_SUPPLIERS
- Pass 123456, SĐT 09*, balance 10tr
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    bank_credit,
    bank_login,
    bank_register,
    cfg,
    cfg_int,
    load_env,
    load_users,
    phone_from_index,
    random_vn_name,
    save_ly,
    save_users,
    setup_warnings,
)


def ensure_ly() -> dict:
    phone = cfg("LY_PHONE", "0901234567")
    username = cfg("LY_USERNAME", "Nguyễn Hương Ly")
    password = cfg("DEFAULT_PASSWORD", "123456")
    bal = cfg_int("LY_BALANCE", 50_000_000)

    st, data, err = bank_register(phone, username, password, bal)
    if st == "ok" and data:
        out = {
            "phone": phone,
            "username": username,
            "password": password,
            "account_number": data.get("account_number", ""),
            "id": data.get("id"),
            "balance": data.get("balance"),
            "role": "merchant",
        }
    else:
        sess = bank_login(phone, password)
        if not sess:
            raise SystemExit(f"Ly register/login fail: {err}")
        out = {
            "phone": phone,
            "username": sess["username"] or username,
            "password": password,
            "account_number": sess["account_number"],
            "balance": sess.get("balance"),
            "role": "merchant",
        }

    # Luôn credit tuyệt đối — auth cũ có thể bỏ qua initial_balance (còn 100k)
    if bank_credit(phone, bal):
        out["balance"] = bal
        print(f"[ly] admin/credit OK → {bal}")
    else:
        print(f"[ly] WARN admin/credit FAIL — kiểm ADMIN_SECRET / rebuild account-service")

    save_ly(out)
    print(f"[ly] STK={out['account_number']} balance={out.get('balance')}")
    print(f"    → set SHOP_MERCHANT_ACCOUNT_NUMBER / BANK_ACCOUNT_NUMBER = {out['account_number']}")
    return out


def count_role(users: list[dict], role: str) -> int:
    return sum(1 for u in users if u.get("role") == role)


def seed_batch(role: str, need: int, start_index: int, balance: int, password: str) -> list[dict]:
    if need <= 0:
        return []
    prefix = "NCC " if role == "supplier" else ""
    created: list[dict] = []

    def one(i: int):
        idx = start_index + i
        phone = phone_from_index(idx if role == "customer" else 80_000_000 + idx)
        username = random_vn_name(idx, prefix=prefix)
        st, data, err = bank_register(phone, username, password, balance)
        if st == "ok" and data:
            return {
                "phone": phone,
                "username": username,
                "password": password,
                "account_number": data.get("account_number", ""),
                "id": data.get("id"),
                "balance": data.get("balance"),
                "role": role,
            }
        if st == "skip":
            sess = bank_login(phone, password)
            if sess:
                bank_credit(phone, balance)
                return {
                    "phone": phone,
                    "username": sess["username"],
                    "password": password,
                    "account_number": sess["account_number"],
                    "balance": balance,
                    "role": role,
                }
        print(f"  fail {phone}: {err}")
        return None

    workers = min(15, max(1, need))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, i) for i in range(need)]
        for f in as_completed(futs):
            u = f.result()
            if u:
                created.append(u)
    return created


def main() -> int:
    load_env()
    setup_warnings()
    password = cfg("DEFAULT_PASSWORD", "123456")
    user_bal = cfg_int("USER_BALANCE", 10_000_000)
    target_c = cfg_int("TARGET_CUSTOMERS", 2000)
    target_s = cfg_int("TARGET_SUPPLIERS", 200)
    batch = cfg_int("SEED_BATCH", 200)

    ensure_ly()
    users = load_users()
    # dedupe by phone
    by_phone = {u["phone"]: u for u in users if u.get("phone")}

    n_c = sum(1 for u in by_phone.values() if u.get("role") == "customer")
    n_s = sum(1 for u in by_phone.values() if u.get("role") == "supplier")
    need_c = min(batch, max(0, target_c - n_c))
    need_s = min(batch, max(0, target_s - n_s))

    print(f"[seed] customers {n_c}/{target_c} (+{need_c})  suppliers {n_s}/{target_s} (+{need_s})")

    start_c = 1000 + n_c
    start_s = 1000 + n_s
    for u in seed_batch("customer", need_c, start_c, user_bal, password):
        by_phone[u["phone"]] = u
    for u in seed_batch("supplier", need_s, start_s, user_bal, password):
        by_phone[u["phone"]] = u

    out = list(by_phone.values())
    save_users(out)
    print(
        f"[seed] done total={len(out)} "
        f"customers={sum(1 for u in out if u.get('role')=='customer')} "
        f"suppliers={sum(1 for u in out if u.get('role')=='supplier')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

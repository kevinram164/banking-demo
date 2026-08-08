#!/usr/bin/env python3
"""Job — Finance personas (Mcredit-style): DISBURSEMENT / REPAYMENT / FEE.

Cần ops users (ops-disburse, ops-fee) trong data/users.json — seed tạo nếu thiếu.
"""
from __future__ import annotations

import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    bank_credit,
    bank_login,
    bank_register,
    cfg,
    cfg_float,
    cfg_int,
    load_env,
    load_users,
    save_users,
    setup_warnings,
    transfer_then_settle,
)

OPS = [
    {
        "role": "ops_disburse",
        "phone": "0910000001",
        "username": "ops-disburse",
        "balance": 80_000_000,
    },
    {
        "role": "ops_fee",
        "phone": "0910000002",
        "username": "ops-fee",
        "balance": 5_000_000,
    },
]


def ensure_ops(password: str) -> list[dict]:
    users = load_users()
    by_phone = {u.get("phone"): u for u in users}
    changed = False
    for spec in OPS:
        phone = spec["phone"]
        if phone in by_phone and by_phone[phone].get("account_number"):
            bank_credit(phone, spec["balance"])
            by_phone[phone]["role"] = spec["role"]
            by_phone[phone]["balance"] = spec["balance"]
            continue
        st, data, err = bank_register(phone, spec["username"], password, spec["balance"])
        if st == "ok" and data:
            row = {
                "phone": phone,
                "username": spec["username"],
                "password": password,
                "account_number": data.get("account_number", ""),
                "id": data.get("id"),
                "balance": data.get("balance"),
                "role": spec["role"],
            }
            users.append(row)
            by_phone[phone] = row
            changed = True
            print(f"[finance] created {spec['username']} STK={row['account_number']}")
        else:
            sess = bank_login(phone, password)
            if not sess:
                print(f"[finance] WARN cannot ensure {phone}: {err}")
                continue
            bank_credit(phone, spec["balance"])
            row = {
                "phone": phone,
                "username": sess.get("username") or spec["username"],
                "password": password,
                "account_number": sess["account_number"],
                "balance": spec["balance"],
                "role": spec["role"],
            }
            users = [u for u in users if u.get("phone") != phone] + [row]
            by_phone[phone] = row
            changed = True
            print(f"[finance] ensured {spec['username']} STK={row['account_number']}")
    if changed:
        save_users(users)
    return [u for u in load_users() if u.get("role") in ("ops_disburse", "ops_fee")]


def main() -> int:
    load_env()
    setup_warnings()
    password = cfg("DEFAULT_PASSWORD", "123456")
    ops = ensure_ops(password)
    disburse = next((u for u in ops if u.get("role") == "ops_disburse"), None)
    fee_ops = next((u for u in ops if u.get("role") == "ops_fee"), None)
    customers = [u for u in load_users() if u.get("role") == "customer" and u.get("account_number")]
    if not customers:
        customers = [u for u in load_users() if u.get("account_number") and u.get("role") not in ("ops_disburse", "ops_fee", "merchant")]
    if not disburse or not customers:
        print("[finance] need ops-disburse + customers")
        return 1

    rounds = cfg_int("FINANCE_ROUNDS", 30)
    workers = cfg_int("FINANCE_WORKERS", 6)
    delay = cfg_float("FINANCE_CONFIRM_DELAY", 1.0)

    disburse_sess = bank_login(disburse["phone"], password)
    if not disburse_sess:
        print("[finance] ops-disburse login fail")
        return 1
    fee_sess = bank_login(fee_ops["phone"], password) if fee_ops else None

    def one(i: int) -> str:
        kind = random.choices(
            ["DISBURSEMENT", "REPAYMENT", "FEE"],
            weights=[0.35, 0.45, 0.20],
            k=1,
        )[0]
        cust = random.choice(customers)
        if kind == "DISBURSEMENT":
            amount = random.randint(1_000_000, 5_000_000)
            res = transfer_then_settle(
                disburse_sess["session"],
                cust["account_number"],
                amount,
                txn_type="DISBURSEMENT",
                purpose="giai ngan khoan vay",
                settle="confirm",
                delay_sec=delay,
            )
            tag = f"ops→{cust['phone']}"
        elif kind == "REPAYMENT":
            amount = random.randint(200_000, 1_500_000)
            sess = bank_login(cust["phone"], cust.get("password") or password)
            if not sess:
                return f"#{i} REPAYMENT login fail {cust['phone']}"
            res = transfer_then_settle(
                sess["session"],
                disburse["account_number"],
                amount,
                txn_type="REPAYMENT",
                purpose="tra gop ky",
                settle="confirm",
                delay_sec=delay,
            )
            tag = f"{cust['phone']}→ops"
        else:
            if not fee_sess or not fee_ops:
                return f"#{i} FEE skip no ops-fee"
            amount = random.randint(10_000, 50_000)
            sess = bank_login(cust["phone"], cust.get("password") or password)
            if not sess:
                return f"#{i} FEE login fail {cust['phone']}"
            res = transfer_then_settle(
                sess["session"],
                fee_ops["account_number"],
                amount,
                txn_type="FEE",
                purpose="phi dich vu",
                settle="confirm",
                delay_sec=delay,
            )
            tag = f"{cust['phone']}→fee"
        if res.get("ok"):
            return f"#{i} OK {kind} {tag} {amount}"
        return f"#{i} FAIL {kind} {res.get('detail')}"

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, i) for i in range(rounds)]
        for f in as_completed(futs):
            msg = f.result()
            print(msg)
            if " OK " in msg:
                ok += 1
            else:
                fail += 1
    print(f"[finance] done ok={ok} fail={fail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

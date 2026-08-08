#!/usr/bin/env python3
"""Job 2 — Peer CK giữa users (cron: mỗi 10 phút).

Create PENDING → confirm sau vài giây (hold/pending lifecycle).
Một tỷ lệ nhỏ cancel / leave pending (expire).
"""
from __future__ import annotations

import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    cfg,
    cfg_float,
    cfg_int,
    load_env,
    load_users,
    setup_warnings,
    bank_login,
    transfer_then_settle,
)


def main() -> int:
    load_env()
    setup_warnings()
    users = [u for u in load_users() if u.get("account_number") and u.get("phone")]
    if len(users) < 2:
        print("[transfer] need >=2 users in data/users.json — chạy job_seed_users trước")
        return 1

    amin = cfg_int("TRANSFER_MIN", 50_000)
    amax = cfg_int("TRANSFER_MAX", 500_000)
    rounds = cfg_int("TRANSFER_ROUNDS", 80)
    workers = cfg_int("TRANSFER_WORKERS", 20)
    password = cfg("DEFAULT_PASSWORD", "123456")
    delay = cfg_float("TRANSFER_CONFIRM_DELAY", 2.0)
    cancel_ratio = cfg_float("TRANSFER_CANCEL_RATIO", 0.05)
    leave_ratio = cfg_float("TRANSFER_LEAVE_RATIO", 0.02)

    sessions: dict[str, str] = {}

    def get_session(u: dict) -> str | None:
        phone = u["phone"]
        if phone in sessions:
            return sessions[phone]
        sess = bank_login(phone, u.get("password") or password)
        if not sess:
            return None
        sessions[phone] = sess["session"]
        return sessions[phone]

    def one_round(i: int) -> str:
        a, b = random.sample(users, 2)
        tok = get_session(a)
        if not tok:
            return f"#{i} login fail {a['phone']}"
        amount = random.randint(amin, amax)
        r = random.random()
        if r < leave_ratio:
            settle = "leave"
        elif r < leave_ratio + cancel_ratio:
            settle = "cancel"
        else:
            settle = "confirm"
        http = requests.Session()
        res = transfer_then_settle(
            tok,
            b["account_number"],
            amount,
            note=f"ECO-PEER-{i}-{random.randint(1000,9999)}",
            txn_type="P2P",
            purpose="chuyen khoan nguoi than",
            settle=settle,
            delay_sec=delay if settle == "confirm" else 0,
            http=http,
        )
        if res.get("ok"):
            tid = (res.get("data") or res.get("created") or {}).get("transfer_id")
            return f"#{i} OK {settle} {a['phone']}→{b['account_number']} {amount} tid={tid}"
        return f"#{i} FAIL {res.get('detail')}"

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one_round, i) for i in range(rounds)]
        for f in as_completed(futs):
            msg = f.result()
            if " OK " in msg:
                ok += 1
            else:
                fail += 1
            print(msg)

    print(f"[transfer] done ok={ok} fail={fail} range={amin}-{amax}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Job 2 — Peer CK giữa users (cron: mỗi 10 phút).

Số tiền: TRANSFER_MIN–TRANSFER_MAX (mặc định 50k–500k).
"""
from __future__ import annotations

import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    bank_login,
    bank_transfer,
    cfg,
    cfg_int,
    load_env,
    load_users,
    setup_warnings,
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

    # cache sessions
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
        note = f"ECO-PEER-{i}-{random.randint(1000,9999)}"
        http = requests.Session()
        res = bank_transfer(tok, b["account_number"], amount, note=note, http=http)
        if res.get("ok"):
            return f"#{i} OK {a['phone']}→{b['account_number']} {amount}"
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

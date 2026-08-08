#!/usr/bin/env python3
"""Dọn PENDING treo — confirm / cancel / expire hàng loạt (admin).

Ví dụ:
  run-job.sh settle              # confirm tối đa 500
  SETTLE_MODE=expire SETTLE_LIMIT=2000 run-job.sh settle
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    bank_admin_settle_pending,
    cfg,
    cfg_int,
    load_env,
    setup_warnings,
)


def main() -> int:
    load_env()
    setup_warnings()
    mode = cfg("SETTLE_MODE", "confirm")  # confirm | cancel | expire
    limit = cfg_int("SETTLE_LIMIT", 500)
    loops = cfg_int("SETTLE_LOOPS", 5)

    total_settled = 0
    total_failed = 0
    for i in range(loops):
        res = bank_admin_settle_pending(mode=mode, limit=limit)
        if not res.get("ok"):
            print(f"[settle] FAIL loop={i} {res.get('detail')}")
            return 1
        data = res.get("data") or {}
        settled = int(data.get("settled") or data.get("expired") or 0)
        failed = int(data.get("failed") or 0)
        total_settled += settled
        total_failed += failed
        print(f"[settle] loop={i} mode={mode} settled/expired={settled} failed={failed}")
        if settled == 0:
            break

    print(f"[settle] done total_settled={total_settled} total_failed={total_failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

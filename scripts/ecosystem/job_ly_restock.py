#!/usr/bin/env python3
"""Job 4 — Ly nhập hàng từ supplier (cron: 12:00 & 18:00).

Giá nhập = RESTOCK_COST_RATIO * giá catalog (mặc định 70%).
CK từ Ly → supplier với note RESTOCK-...
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    bank_login,
    bank_transfer,
    cfg,
    cfg_float,
    cfg_int,
    load_env,
    load_ly,
    load_users,
    product_price,
    setup_warnings,
    shop_products,
)


def main() -> int:
    load_env()
    setup_warnings()
    ly = load_ly()
    if not ly:
        print("[restock] thiếu Ly — chạy job_seed_users")
        return 1

    suppliers = [u for u in load_users() if u.get("role") == "supplier" and u.get("account_number")]
    if not suppliers:
        print("[restock] không có supplier — seed suppliers trước")
        return 1

    products = [p for p in shop_products() if product_price(p) > 0]
    if not products:
        print("[restock] catalog trống")
        return 1

    ratio = cfg_float("RESTOCK_COST_RATIO", 0.70)
    items = cfg_int("RESTOCK_ITEMS", 30)
    password = cfg("DEFAULT_PASSWORD", "123456")

    sess = bank_login(ly["phone"], ly.get("password") or password)
    if not sess:
        print("[restock] Ly login fail")
        return 1

    ok = fail = 0
    for i in range(items):
        p = random.choice(products)
        supplier = random.choice(suppliers)
        catalog_price = product_price(p)
        cost = max(1000, int(catalog_price * ratio))
        note = f"RESTOCK-{p.get('id')}-{random.randint(10000,99999)}"
        res = bank_transfer(sess["session"], supplier["account_number"], cost, note=note)
        if res.get("ok"):
            ok += 1
            print(
                f"#{i} OK →{supplier['phone']} product={p.get('id')} "
                f"cost={cost} ({int(ratio*100)}% of {catalog_price})"
            )
        else:
            fail += 1
            print(f"#{i} FAIL {res.get('detail')}")
            if "401" in str(res.get("detail")) or "session" in str(res.get("detail")).lower():
                sess = bank_login(ly["phone"], ly.get("password") or password)
                if not sess:
                    break

    print(f"[restock] done ok={ok} fail={fail} ratio={ratio}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Job 3 — Mua hàng shop (cron: mỗi 3 giờ).

Khách login banking → checkout shop → CK tới STK Ly với note = payment_code (NOLI-…).
"""
from __future__ import annotations

import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    bank_login,
    bank_transfer,
    cfg,
    cfg_int,
    load_env,
    load_ly,
    load_users,
    order_pay_fields,
    product_price,
    product_stock,
    setup_warnings,
    shop_checkout,
    shop_products,
)


def main() -> int:
    load_env()
    setup_warnings()
    ly = load_ly()
    if not ly or not ly.get("account_number"):
        print("[shop-buy] thiếu Ly STK — chạy job_seed_users + điền LY_ACCOUNT_NUMBER")
        return 1

    customers = [u for u in load_users() if u.get("role") == "customer"]
    if not customers:
        customers = load_users()
    if not customers:
        print("[shop-buy] không có users")
        return 1

    products = [p for p in shop_products() if product_stock(p) > 0 and product_price(p) > 0]
    if not products:
        print("[shop-buy] catalog trống / hết hàng")
        return 1

    count = cfg_int("SHOP_BUY_COUNT", 40)
    workers = cfg_int("SHOP_BUY_WORKERS", 8)
    password = cfg("DEFAULT_PASSWORD", "123456")
    merchant = ly["account_number"]

    def one(i: int) -> str:
        u = random.choice(customers)
        p = random.choice(products)
        qty = 1
        try:
            order = shop_checkout(
                product_id=int(p["id"]),
                quantity=qty,
                customer_name=u.get("username") or f"KH {u['phone']}",
                customer_phone=u["phone"],
            )
        except Exception as e:
            return f"#{i} checkout fail: {e}"

        pay_code, amount = order_pay_fields(order)
        if not amount:
            amount = product_price(p)
        if not pay_code or amount <= 0:
            return f"#{i} bad order resp keys={list(order.keys())}"

        sess = bank_login(u["phone"], u.get("password") or password)
        if not sess:
            return f"#{i} login fail {u['phone']}"
        res = bank_transfer(sess["session"], merchant, amount, note=str(pay_code))
        if res.get("ok"):
            return f"#{i} OK order pay={pay_code} amount={amount} from={u['phone']}"
        return f"#{i} transfer fail: {res.get('detail')}"

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, i) for i in range(count)]
        for f in as_completed(futs):
            msg = f.result()
            print(msg)
            if " OK " in msg:
                ok += 1
            else:
                fail += 1

    print(f"[shop-buy] done ok={ok} fail={fail} merchant={merchant}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

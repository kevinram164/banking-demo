#!/usr/bin/env python3
"""Seed chủ shop Nguyễn Hương Ly trên npd-banking.

  python scripts/seed_huongly.py --base-url https://npd-banking.co --insecure

Ghi: scripts/demo-huongly.json
Pass mặc định lab: 123456 — balance Ly: 50_000_000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

PHONE = "0901234567"
USERNAME = "Nguyễn Hương Ly"
PASSWORD = "123456"
LY_BALANCE = 50_000_000
BANK_NAME = "NPD Bank Demo"
ADMIN_SECRET = "banking-admin-2025"


def _credit(base_url: str, phone: str, balance: int, verify: bool) -> None:
    r = requests.post(
        f"{base_url.rstrip('/')}/api/account/admin/credit",
        json={"phone": phone, "balance": balance},
        headers={"X-Admin-Secret": ADMIN_SECRET},
        timeout=20,
        verify=verify,
    )
    if r.status_code != 200:
        print(f"Warning: admin/credit {r.status_code}: {r.text[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://npd-banking.co")
    ap.add_argument("--insecure", action="store_true", help="bỏ verify TLS")
    ap.add_argument("--password", default=PASSWORD)
    ap.add_argument("--balance", type=int, default=LY_BALANCE)
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "demo-huongly.json"),
    )
    args = ap.parse_args()
    verify = not args.insecure
    url = f"{args.base_url.rstrip('/')}/api/auth/register"
    payload = {
        "phone": PHONE,
        "username": USERNAME,
        "password": args.password,
        "initial_balance": args.balance,
    }

    r = requests.post(url, json=payload, timeout=20, verify=verify)
    if r.status_code == 409:
        login = requests.post(
            f"{args.base_url.rstrip('/')}/api/auth/login",
            json={"phone": PHONE, "password": args.password},
            timeout=20,
            verify=verify,
        )
        if login.status_code != 200:
            print(f"User exists nhưng login fail: {login.status_code} {login.text[:200]}")
            return 1
        data = login.json()
        print("User đã tồn tại — lấy thông tin từ login + set balance.")
        _credit(args.base_url, PHONE, args.balance, verify)
    elif r.status_code == 200:
        data = r.json()
        print("Đã tạo user Nguyễn Hương Ly.")
    else:
        print(f"Register fail: {r.status_code} {r.text[:300]}")
        return 1

    acct = data.get("account_number") or ""
    out = {
        "phone": PHONE,
        "username": data.get("username") or USERNAME,
        "password": args.password,
        "account_number": acct,
        "id": data.get("id"),
        "balance": args.balance,
        "bank_name": BANK_NAME,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    # Mirror sang ecosystem data nếu có thư mục
    eco = Path(__file__).resolve().parent / "ecosystem" / "data" / "huongly.json"
    eco.parent.mkdir(parents=True, exist_ok=True)
    eco.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print()
    print("--- Paste vào phase9-gitops-platform/gitops/values-ecosystem.yaml ---")
    print(f'    SHOP_MERCHANT_ACCOUNT_NUMBER: "{acct}"')
    print()
    print("--- Paste vào npd-shop gitops (order-service env) ---")
    print(f'    BANK_ACCOUNT_NAME: "{USERNAME}"')
    print(f'    BANK_ACCOUNT_NUMBER: "{acct}"')
    print(f'    BANK_NAME: "{BANK_NAME}"')
    print()
    print(f"Saved: {args.out}")
    print(f"Also:  {eco}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

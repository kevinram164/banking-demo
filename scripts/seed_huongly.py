#!/usr/bin/env python3
"""Seed chủ shop Nguyễn Hương Ly trên npd-banking.

  python scripts/seed_huongly.py --base-url https://npd-banking.co

Ghi: scripts/demo-huongly.json
In sẵn snippet values-ecosystem + npd-shop BANK_* để paste.
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

# Cố định — kịch bản demo
PHONE = "0901234567"
USERNAME = "Nguyễn Hương Ly"
PASSWORD = "LyShop@2026"
BANK_NAME = "NPD Bank Demo"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://npd-banking.co")
    ap.add_argument("--insecure", action="store_true", help="bỏ verify TLS")
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "demo-huongly.json"),
    )
    args = ap.parse_args()
    verify = not args.insecure
    url = f"{args.base_url.rstrip('/')}/api/auth/register"
    payload = {"phone": PHONE, "username": USERNAME, "password": PASSWORD}

    r = requests.post(url, json=payload, timeout=20, verify=verify)
    if r.status_code == 409:
        # Đã tồn tại — login lấy STK
        login = requests.post(
            f"{args.base_url.rstrip('/')}/api/auth/login",
            json={"phone": PHONE, "password": PASSWORD},
            timeout=20,
            verify=verify,
        )
        if login.status_code != 200:
            print(f"User exists nhưng login fail: {login.status_code} {login.text[:200]}")
            return 1
        data = login.json()
        print("User đã tồn tại — lấy thông tin từ login.")
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
        "password": PASSWORD,
        "account_number": acct,
        "id": data.get("id"),
        "balance": data.get("balance"),
        "bank_name": BANK_NAME,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print()
    print("--- Paste vào phase9-gitops-platform/gitops/values-ecosystem.yaml ---")
    print(f'    SHOP_MERCHANT_ACCOUNT_NUMBER: "{acct}"')
    print()
    print("--- Paste vào npd-shop gitops (order-service env) ---")
    print(f"    BANK_ACCOUNT_NAME: \"{USERNAME}\"")
    print(f'    BANK_ACCOUNT_NUMBER: "{acct}"')
    print(f'    BANK_NAME: "{BANK_NAME}"')
    print()
    print(f"Saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

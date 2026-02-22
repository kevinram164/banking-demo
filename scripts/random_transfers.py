#!/usr/bin/env python3
"""
Script mô phỏng giao dịch ngẫu nhiên giữa các users.
Login tất cả users → chọn ngẫu nhiên cặp (sender, receiver) → chuyển khoản.

Dùng:
  python random_transfers.py --password 123456
  python random_transfers.py --password 123456 --rounds 50 --workers 5
  python random_transfers.py --password 123456 --base-url https://npd-banking.co --no-verify

Cài đặt:
  pip install requests
"""

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("Cần cài: pip install requests")
    sys.exit(1)


def login(base_url: str, phone: str, password: str, verify: bool = True) -> dict | None:
    """Login và trả về session + account info."""
    url = f"{base_url}/api/auth/login"
    try:
        r = requests.post(url, json={"phone": phone, "password": password}, timeout=10, verify=verify)
        if r.status_code == 200:
            data = r.json()
            return {
                "phone": phone,
                "session": data["session"],
                "username": data.get("username", ""),
                "account_number": data.get("account_number", ""),
                "balance": data.get("balance", 0),
            }
        return None
    except Exception:
        return None


def get_balance(base_url: str, session: str, verify: bool = True) -> int | None:
    url = f"{base_url}/api/account/balance"
    try:
        r = requests.get(url, headers={"X-Session": session}, timeout=10, verify=verify)
        if r.status_code == 200:
            return r.json().get("balance", 0)
    except Exception:
        pass
    return None


def transfer(base_url: str, session: str, to_account: str, amount: int, verify: bool = True) -> dict:
    """Thực hiện chuyển khoản. Trả về dict {ok, detail}."""
    url = f"{base_url}/api/transfer/transfer"
    try:
        r = requests.post(
            url,
            json={"to_account_number": to_account, "amount": amount},
            headers={"X-Session": session},
            timeout=15,
            verify=verify,
        )
        if r.status_code == 200:
            return {"ok": True, "detail": r.json()}
        return {"ok": False, "detail": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def fetch_users_from_db(base_url: str, admin_secret: str, verify: bool = True) -> list[dict]:
    """Lấy danh sách users từ admin API."""
    users = []
    page = 1
    while True:
        url = f"{base_url}/api/account/admin/users?page={page}&size=100"
        try:
            r = requests.get(url, headers={"X-Admin-Secret": admin_secret}, timeout=10, verify=verify)
            if r.status_code != 200:
                break
            data = r.json()
            users.extend(data.get("users", []))
            if page >= data.get("pages", 1):
                break
            page += 1
        except Exception:
            break
    return users


def main():
    parser = argparse.ArgumentParser(description="Mô phỏng giao dịch ngẫu nhiên")
    parser.add_argument("--base-url", "-u", default="http://npd-banking.co", help="Base URL")
    parser.add_argument("--password", "-p", required=True, help="Password chung của tất cả users")
    parser.add_argument("--rounds", "-r", type=int, default=20, help="Số lượt chuyển khoản (default: 20)")
    parser.add_argument("--workers", "-w", type=int, default=5, help="Số workers song song (default: 5)")
    parser.add_argument("--min-amount", type=int, default=1000, help="Số tiền tối thiểu (default: 1000)")
    parser.add_argument("--max-amount", type=int, default=10000, help="Số tiền tối đa (default: 10000)")
    parser.add_argument("--delay", "-d", type=float, default=0.5, help="Delay giữa các round (giây, default: 0.5)")
    parser.add_argument("--admin-secret", default="banking-admin-2025", help="Admin secret để lấy danh sách users")
    parser.add_argument("--no-verify", action="store_true", help="Bỏ SSL verify")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    verify = not args.no_verify

    print("=" * 60)
    print("  RANDOM TRANSFER SIMULATOR")
    print("=" * 60)
    print(f"  Base URL:   {base_url}")
    print(f"  Rounds:     {args.rounds}")
    print(f"  Workers:    {args.workers}")
    print(f"  Amount:     {args.min_amount:,} - {args.max_amount:,} ₫")
    print(f"  Delay:      {args.delay}s")
    print()

    # --- Bước 1: Lấy danh sách users từ admin API ---
    print("[1/3] Fetching users from admin API...")
    db_users = fetch_users_from_db(base_url, args.admin_secret, verify)
    if len(db_users) < 2:
        print("  Cần ít nhất 2 users. Hãy chạy seed_users.py trước.")
        sys.exit(1)
    print(f"  Found {len(db_users)} users")

    # --- Bước 2: Login tất cả users ---
    print(f"[2/3] Logging in {len(db_users)} users...")
    sessions = []

    def do_login(user):
        return login(base_url, user["phone"], args.password, verify)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(do_login, u): u for u in db_users}
        for f in as_completed(futures):
            result = f.result()
            if result:
                sessions.append(result)

    if len(sessions) < 2:
        print(f"  Chỉ login được {len(sessions)} users. Cần ít nhất 2.")
        print("  Kiểm tra lại password (--password).")
        sys.exit(1)

    print(f"  Logged in: {len(sessions)}/{len(db_users)} users")
    print()

    # --- Bước 3: Chuyển khoản ngẫu nhiên ---
    print(f"[3/3] Running {args.rounds} random transfers...")
    print("-" * 60)

    success = 0
    failed = 0
    total_amount = 0
    errors = []

    def do_transfer(round_idx: int) -> dict:
        sender = random.choice(sessions)
        receiver = random.choice([s for s in sessions if s["phone"] != sender["phone"]])
        amount = random.randint(args.min_amount, args.max_amount)

        result = transfer(base_url, sender["session"], receiver["account_number"], amount, verify)
        return {
            "round": round_idx + 1,
            "from": sender["username"],
            "from_phone": sender["phone"],
            "to": receiver["username"],
            "to_account": receiver["account_number"],
            "amount": amount,
            "ok": result["ok"],
            "detail": result["detail"],
        }

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(do_transfer, i): i for i in range(args.rounds)}
        for f in as_completed(futures):
            r = f.result()
            symbol = "✓" if r["ok"] else "✗"
            status_color = "" if r["ok"] else " [FAIL]"

            if r["ok"]:
                success += 1
                total_amount += r["amount"]
                print(
                    f"  {symbol} #{r['round']:>4d}  {r['from']:<20s} → {r['to']:<20s}  "
                    f"{r['amount']:>8,} ₫{status_color}"
                )
            else:
                failed += 1
                detail_short = str(r["detail"])[:80]
                errors.append(detail_short)
                print(
                    f"  {symbol} #{r['round']:>4d}  {r['from']:<20s} → {r['to']:<20s}  "
                    f"{r['amount']:>8,} ₫  ERR: {detail_short}"
                )

    # --- Kết quả ---
    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print(f"  Total rounds:     {args.rounds}")
    print(f"  Successful:       {success}")
    print(f"  Failed:           {failed}")
    print(f"  Total transferred: {total_amount:,} ₫")
    print(f"  Success rate:     {success / args.rounds * 100:.1f}%")

    if errors:
        unique_errors = list(set(errors))
        print(f"\n  Errors ({len(unique_errors)} unique):")
        for i, e in enumerate(unique_errors[:5], 1):
            print(f"    {i}. {e}")

    print()


if __name__ == "__main__":
    main()

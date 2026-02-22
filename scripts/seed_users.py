#!/usr/bin/env python3
"""
Script tạo users giả lập để test dịch vụ banking.
Hỗ trợ cả API v1 (username, password) và v2 (phone, username, password).

Dùng:
  python seed_users.py [--count 1000] [--base-url URL] [--output users.json]
  python seed_users.py --count 500 --base-url http://npd-banking.co

Cài đặt:
  pip install requests
"""

import argparse
import json
import random
import string
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:
    print("Cần cài: pip install requests")
    sys.exit(1)

# Tên tiếng Việt phổ biến (để tạo dữ liệu giả lập)
HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Vũ", "Đặng", "Bùi", "Đỗ"]
TEN_DEM = ["Văn", "Thị", "Minh", "Thu", "Hồng", "Thanh", "Quang", "Anh", "Tuấn", ""]
TEN = [
    "An", "Bình", "Chi", "Dũng", "Hà", "Hương", "Khoa", "Lan", "Long", "Mai",
    "Nam", "Nga", "Phương", "Sơn", "Thảo", "Trung", "Tú", "Vy", "Yến", "Đức",
]


def random_phone(seed: int = 0) -> str:
    """Số điện thoại 10 số (09xxxxxxxx), unique theo seed."""
    n = 10000000 + (seed % 90000000)  # 8 chữ số sau 09
    return f"09{n:08d}"


def random_name(index: int | None = None) -> str:
    """Tên đầy đủ tiếng Việt, thêm số để tránh trùng."""
    ho = random.choice(HO)
    dem = random.choice(TEN_DEM)
    ten = random.choice(TEN)
    name = f"{ho} {dem} {ten}".replace("  ", " ").strip()
    if index is not None:
        name = f"{name} {index}"
    return name


def random_username(prefix: str = "user", index: int | None = None) -> str:
    """Username unique: prefix + index hoặc random."""
    if index is not None:
        return f"{prefix}_{index:06d}"
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}_{suffix}"


def random_password(length: int = 12) -> str:
    """Password đủ mạnh (chữ + số)."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


RESULT_OK = "ok"
RESULT_SKIP = "skip"
RESULT_FAIL = "fail"


def register_v2(
    base_url: str, session: requests.Session, verify: bool = True, index: int = 0
) -> tuple[str, dict | None, str | None]:
    """Đăng ký qua API v2. Returns (status, data, error)."""
    url = f"{base_url.rstrip('/')}/api/auth/register"
    phone = random_phone(index)
    username = random_name(index)
    password = random_password()
    payload = {"phone": phone, "username": username, "password": password}
    try:
        r = session.post(url, json=payload, timeout=15, verify=verify)
        if r.status_code == 200:
            data = r.json()
            return (
                RESULT_OK,
                {
                    "phone": phone,
                    "username": username,
                    "password": password,
                    "account_number": data.get("account_number", ""),
                    "id": data.get("id"),
                    "balance": data.get("balance"),
                },
                None,
            )
        if r.status_code == 409:
            return RESULT_SKIP, None, f"Exists: phone={phone} username={username}"
        err = f"HTTP {r.status_code}: {r.text[:200]}"
        return RESULT_FAIL, None, err
    except Exception as e:
        return RESULT_FAIL, None, str(e)


def register_v1(
    base_url: str, session: requests.Session, verify: bool = True, index: int = 0
) -> tuple[str, dict | None, str | None]:
    """Đăng ký qua API v1. Returns (status, data, error)."""
    url = f"{base_url.rstrip('/')}/api/auth/register"
    username = random_username(index=index)
    password = random_password()
    payload = {"username": username, "password": password}
    try:
        r = session.post(url, json=payload, timeout=15, verify=verify)
        if r.status_code == 200:
            data = r.json()
            return (
                RESULT_OK,
                {
                    "username": username,
                    "password": password,
                    "id": data.get("id"),
                    "balance": data.get("balance"),
                },
                None,
            )
        if r.status_code == 409:
            return RESULT_SKIP, None, f"Exists: username={username}"
        err = f"HTTP {r.status_code}: {r.text[:200]}"
        return RESULT_FAIL, None, err
    except Exception as e:
        return RESULT_FAIL, None, str(e)


def detect_api_version(base_url: str, verify: bool = True) -> str:
    """Thử v2 trước (phone), nếu 400/422 thì dùng v1."""
    url = f"{base_url.rstrip('/')}/api/auth/register"
    # v2: cần phone, username, password
    r = requests.post(
        url,
        json={"phone": "0900000000", "username": "test", "password": "Test123456"},
        timeout=5,
        verify=verify,
    )
    if r.status_code in (200, 409):  # 409 = phone exists
        return "v2"
    # v1: username, password
    r = requests.post(
        url,
        json={"username": "test_detect_xyz", "password": "Test123456"},
        timeout=5,
        verify=verify,
    )
    if r.status_code in (200, 409):
        return "v1"
    return "v1"  # fallback


def main():
    parser = argparse.ArgumentParser(description="Tạo users giả lập để test dịch vụ banking")
    parser.add_argument("--count", "-n", type=int, default=1000, help="Số users cần tạo")
    parser.add_argument(
        "--base-url",
        "-u",
        default="http://npd-banking.co",
        help="Base URL API (vd: http://npd-banking.co)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="File JSON lưu danh sách users (để dùng cho test login, transfer)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=20,
        help="Số luồng chạy song song",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Bỏ qua SSL verify (self-signed cert)",
    )
    parser.add_argument(
        "--api",
        choices=["v1", "v2", "auto"],
        default="auto",
        help="API version: v1 (username), v2 (phone+username), auto (tự phát hiện)",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=0,
        help="Seed offset cho phone/username (chạy nhiều lần không trùng)",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Chỉ gửi 1 request để test, in response đầy đủ",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    verify = not args.no_verify

    print("=== Seed Users (Python) ===")
    print(f"Count:    {args.count}")
    print(f"Base URL: {base_url}")
    print(f"Workers:  {args.workers}")
    print()

    # Phát hiện API version
    if args.api == "auto":
        print("Đang phát hiện API version...")
        api_version = detect_api_version(base_url, verify)
        print(f"API: {api_version}")
    else:
        api_version = args.api

    register_fn = register_v2 if api_version == "v2" else register_v1
    first_errors: list[str] = []

    def do_register(idx: int) -> tuple[str, dict | None, str | None]:
        with requests.Session() as s:
            return register_fn(base_url, s, verify, args.seed + idx)

    if args.test:
        print("Chạy 1 request test...")
        status, result, err = do_register(0)
        if result:
            print("OK:", json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"[{status}]:", err)
        return

    success = 0
    skipped = 0
    failed = 0
    users: list[dict] = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(do_register, i): i for i in range(args.count)}
        for i, future in enumerate(as_completed(futures)):
            status, result, err = future.result()
            if status == RESULT_OK:
                success += 1
                users.append(result)
            elif status == RESULT_SKIP:
                skipped += 1
            else:
                failed += 1
                if len(first_errors) < 5:
                    first_errors.append(err or "Unknown")
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{args.count}  (ok={success} skip={skipped} fail={failed})")

    if first_errors:
        print("\n--- Lỗi thật (mẫu) ---")
        for i, e in enumerate(first_errors[:5], 1):
            print(f"  {i}. {e}")
        if failed == args.count:
            print("\nGợi ý: Thử https và --no-verify nếu dùng self-signed cert:")
            print(f"  python seed_users.py -n 1 -u https://npd-banking.co --no-verify --test")

    print()
    print("=== Kết quả ===")
    print(f"Thành công: {success}")
    print(f"Bỏ qua:    {skipped}  (đã tồn tại)")
    print(f"Thất bại:   {failed}")
    print()

    if args.output and users:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        print(f"Đã lưu {len(users)} users vào {args.output}")
        print()
        print("Ví dụ dùng cho test:")
        print("  # Login với user đầu tiên")
        u = users[0]
        if "phone" in u:
            print(f'  curl -X POST {base_url}/api/auth/login -H "Content-Type: application/json" \\')
            print(f'    -d \'{{"phone":"{u["phone"]}","password":"{u["password"]}"}}\'')
        else:
            print(f'  curl -X POST {base_url}/api/auth/login -H "Content-Type: application/json" \\')
            print(f'    -d \'{{"username":"{u["username"]}","password":"{u["password"]}"}}\'')


if __name__ == "__main__":
    main()

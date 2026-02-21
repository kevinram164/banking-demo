# Scripts

## seed_users.py (Python — khuyến nghị)

Tạo users giả lập với **tên**, **số điện thoại**, **số tài khoản** (STK do backend sinh) để test dịch vụ.

Hỗ trợ API v1 (username) và v2 (phone + username). Tự phát hiện version.

```bash
pip install requests
python seed_users.py --count 1000 --base-url https://npd-banking.co

# Lưu danh sách users để dùng cho test login, transfer
python seed_users.py -n 500 -o users.json --no-verify

# Debug: gửi 1 request, in response/error đầy đủ
python seed_users.py -n 1 --test
python seed_users.py -n 1 -u https://npd-banking.co --no-verify --test

# Tùy chọn
python seed_users.py -n 1000 -u https://npd-banking.co -o users.json -w 30 --no-verify --api v2
```

**Dữ liệu tạo**:
- **Tên**: Ngẫu nhiên tiếng Việt (Nguyễn Văn An, Trần Thị Bình...)
- **SĐT**: 09xxxxxxxx (unique)
- **STK**: Backend sinh tự động (v2)
- **Password**: Random 12 ký tự

---

## seed-users.sh (Bash)

Tạo N users đơn giản qua API (username + password cố định).

```bash
chmod +x seed-users.sh
./seed-users.sh 1000
./seed-users.sh 500 https://npd-banking.co
CURL_OPTS="-s -k" ./seed-users.sh 1000
```

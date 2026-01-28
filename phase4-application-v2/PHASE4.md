# Giai đoạn 4: Application v2 (Phone login + Account number + UI)

Mục tiêu của v2 là nâng cấp **application layer** nhưng vẫn giữ **v1** nguyên trạng để so sánh.

## Tính năng mới (v2)

- **Tạo số tài khoản random** cho user khi đăng ký (`account_number`, unique).
- **Đăng ký/đăng nhập bằng số điện thoại** (`phone`, unique).
- **Chuyển tiền bằng số tài khoản** và **tự hiển thị tên người nhận** (UI gọi lookup).
- **UI đẹp hơn** (giữ React + Tailwind, cải thiện form/UX).

## Thay đổi API (v2)

- `POST /api/auth/register`: body `{ phone, username, password }` → trả về `account_number`
- `POST /api/auth/login`: body `{ phone, password }`
- `GET /api/account/lookup?account_number=...` → `{ account_number, username }`
- `POST /api/transfer/transfer`: body `{ to_account_number, amount }`

## Ghi chú DB

v2 vẫn dùng `Base.metadata.create_all()` để demo nhanh. Khi chạy trên DB đã có schema v1, bạn nên dùng DB mới hoặc migration (Alembic) để thêm cột `phone`, `account_number`.


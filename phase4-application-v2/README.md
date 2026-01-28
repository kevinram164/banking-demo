# Phase 4 — Application v2

Folder này là **version mới** để so sánh với code **v1** ở root.

## Tính năng chính

- Đăng ký/đăng nhập bằng **số điện thoại**
- Tự tạo **số tài khoản (account number) random** khi đăng ký
- Chuyển tiền theo **số tài khoản** + UI tự lookup **tên người nhận**
- UI được chỉnh lại đẹp/clear hơn (React + Tailwind)

## Chạy thử nhanh (dev)

Bạn có thể chạy theo cách cũ (Docker/K8s) nhưng trỏ image/build context sang `phase4-application-v2/`.

### Docker build (ví dụ)

Build từ repo root, nhưng Dockerfile nằm trong phase4:

```bash
docker build -f phase4-application-v2/services/auth-service/Dockerfile -t auth-service:v2 .
```

Lưu ý: v2 có thay đổi schema bảng `users` (thêm `phone`, `account_number`), nên nên dùng **database mới** hoặc migration.


# Giai đoạn 5: Security Hardening & Reliability

Giai đoạn 5 tập trung vào **bảo mật** (application + API gateway + secrets) và **độ tin cậy** (SLO, alert, smoke-test).

## Mục tiêu

- Cải thiện **auth/session** (chuẩn hoá JWT + refresh token).
- Bảo vệ **API Gateway (Kong)** bằng các plugin security cơ bản.
- Chuẩn hoá **quản lý secrets/config** trong CI/CD.
- Định nghĩa **SLO** đơn giản + ý tưởng alerting/chaos để demo “SRE mindset”.

## Cấu trúc thư mục

```text
phase5-security-reliability/
├── PHASE5.md                 # File này – overview + checklist
├── auth-hardening/
│   └── JWT-DESIGN.md         # Thiết kế JWT + refresh token + revoke
├── kong-security/
│   └── KONG-PLUGINS.md       # Thiết kế plugin rate-limit, size-limit, correlation-id
├── ci-security/
│   └── GHA-SECURITY.md       # Hardening CI: image scan, secrets
└── sre/
    └── SLO-ALERTING.md       # SLO, alert, chaos idea
```

## Lộ trình thực hiện (gợi ý)

1. **Auth hardening (JWT)** – đọc `auth-hardening/JWT-DESIGN.md`, nếu muốn có thể implement vào Phase 4.
2. **Kong security** – dùng `kong-security/KONG-PLUGINS.md` để chỉnh `values.yaml` Phase 2.
3. **CI security** – mở rộng `.github/workflows/ci.yml` theo `ci-security/GHA-SECURITY.md`.
4. **SRE** – nếu có thời gian, thêm alert rule vào Phase 3 Prometheus (theo `sre/SLO-ALERTING.md`).


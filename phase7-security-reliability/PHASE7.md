# Giai đoạn 7: Security Hardening & Reliability

Giai đoạn 7 tập trung vào **bảo mật** (application + API gateway + secrets) và **độ tin cậy** (SLO, alert, smoke-test). Nội dung này trước đây nằm trong Phase 5; Phase 5 đã chuyển sang **đổi kiến trúc** (tách namespace, tách Helm chart, Kong DB riêng).

## Mục tiêu

- Cải thiện **auth/session** (chuẩn hoá JWT + refresh token).
- Bảo vệ **API Gateway (Kong)** bằng các plugin security cơ bản.
- Chuẩn hoá **quản lý secrets/config** trong CI/CD.
- Định nghĩa **SLO** đơn giản + ý tưởng alerting/chaos để demo “SRE mindset”.

## Cấu trúc thư mục

```text
phase7-security-reliability/
├── PHASE7.md                 # File này – overview + checklist
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

1. **Auth hardening (JWT)** – đọc `auth-hardening/JWT-DESIGN.md`; có thể implement vào Phase 4.
2. **Kong security** – dùng `kong-security/KONG-PLUGINS.md` để chỉnh values Kong (Phase 2 hoặc chart Kong riêng sau Phase 5).
3. **CI security** – mở rộng `.github/workflows/ci.yml` theo `ci-security/GHA-SECURITY.md`.
4. **SRE** – thêm alert rule vào Phase 3 Prometheus (theo `sre/SLO-ALERTING.md`).

## Liên kết

- **Phase 5**: Kiến trúc (tách ns, tách chart, Kong DB) – `phase5-architecture-refactor/`.
- **Phase 2 / Phase 5**: Kong values hoặc chart Kong riêng khi áp dụng plugin.
- **Phase 3**: Prometheus + Grafana cho SLO/alert.

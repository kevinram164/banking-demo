# Giai đoạn 5: Đổi kiến trúc – Tách namespace & Helm chart (Kong, Redis, DB)

Giai đoạn 5 tập trung vào **đổi kiến trúc**: tách Kong, Redis, Postgres (DB) sang **các namespace riêng** và **Helm chart riêng**, không còn gộp chung trong chart banking-demo. Mục tiêu: dễ mở rộng tính năng mới và cho Kong có **DB riêng** để sử dụng (Kong DB mode).

## Mục tiêu

- **Tách namespace**: Kong → namespace riêng (ví dụ `kong` hoặc `api-gateway`), Redis → `redis`, Postgres (DB ứng dụng) → `postgres` hoặc `data`; ứng dụng banking giữ namespace `banking` và kết nối qua DNS cross-namespace.
- **Tách Helm chart**: Kong, Redis, Postgres mỗi thứ một chart (hoặc chart riêng cho từng nhóm), không còn nằm trong `phase2-helm-chart/banking-demo`. Chart banking-demo chỉ còn **ứng dụng** (frontend, auth-service, account-service, transfer-service, notification-service) + Ingress trỏ tới Kong.
- **Kong DB riêng**: Kong chuyển từ mode declarative file (`KONG_DATABASE: "off"`) sang **DB mode** (Postgres riêng cho Kong), giúp quản lý config/routes qua Admin API và scale Kong dễ hơn.
- **Mở rộng**: Kiến trúc tách giúp sau này thêm service mới, gateway mới, hoặc DB/Redis dùng chung cho nhiều app mà không ảnh hưởng chart banking.

## Cấu trúc thư mục

```text
phase5-architecture-refactor/
├── PHASE5.md                         # File này – overview Phase 5 (kiến trúc)
└── architecture/
    ├── NAMESPACE-SPLIT.md            # Tách namespace: banking, kong, redis, postgres; DNS, kết nối
    ├── KONG-DEDICATED-DB.md          # Kong DB riêng (DB mode), lợi ích, migration
    ├── HELM-CHART-SPLIT.md           # Tách Helm chart; dùng chart có sẵn (Kong, Bitnami Redis/Postgres)
    └── PHASE2-TO-PHASE5-MAPPING.md  # HA (Kong/Redis/Postgres), mapping config Phase 2 → Phase 5, Application có cần sửa không
```

**Security & Reliability** (JWT, Kong plugins, CI security, SLO/alert) đã chuyển sang **Phase 7**: `phase7-security-reliability/`.

## Lộ trình thực hiện (gợi ý)

1. **Namespace split** – đọc `architecture/NAMESPACE-SPLIT.md`. Triển khai: tạo namespace `kong`, `redis`, `postgres`; deploy Kong, Redis, Postgres vào từng ns; chỉnh banking app kết nối qua FQDN.
2. **Helm chart split** – đọc `architecture/HELM-CHART-SPLIT.md`. Kong, Redis, Postgres **dùng chart có sẵn** (Kong official, Bitnami Redis, Bitnami PostgreSQL); chart banking-demo chỉ còn app + Ingress trỏ tới Kong (cross-namespace).
3. **Kong DB riêng** – đọc `architecture/KONG-DEDICATED-DB.md`. Deploy Postgres riêng cho Kong; chuyển Kong sang DB mode; migrate config từ kong.yml sang Admin API hoặc db_import.
4. **Mapping Phase 2 → Phase 5** – đọc `architecture/PHASE2-TO-PHASE5-MAPPING.md`: Kong/Redis/Postgres HA, mapping config sang chart có sẵn, Application **không cần sửa code** (chỉ đổi connection string qua values/Secret).
5. **Security & Reliability** – xem **Phase 7** (`phase7-security-reliability/`).

## Điều kiện tiên quyết

- **Phase 2** Helm chart banking-demo đã chạy (hiện tại Kong, Redis, Postgres trong cùng chart/namespace `banking`).
- Hiểu cơ bản DNS Kubernetes (FQDN cross-namespace: `<svc>.<ns>.svc.cluster.local`).

## Liên kết

- **Phase 2**: `phase2-helm-chart/banking-demo` – chart hiện tại (sẽ thu gọn sau khi tách).
- **Phase 3**: Monitoring vẫn scrape cross-namespace (Prometheus có thể scrape Kong, Redis, Postgres ở ns khác).
- **Phase 6**: Deployment strategies (blue-green/canary) vẫn áp dụng cho app trong ns `banking`; Kong/Redis/DB có thể rollout độc lập.
- **Phase 7**: Security & Reliability – `phase7-security-reliability/`.

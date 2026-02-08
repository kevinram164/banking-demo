# Kong DB riêng (Phase 5)

**Chart Kong từ Helm (Kong official) không đi kèm Postgres.** Kong hỗ trợ hai chế độ:

1. **Declarative (không DB)** – mặc định: `KONG_DATABASE: "off"`, config từ file/ConfigMap. Phase 2 đang dùng kiểu này.
2. **DB mode** – `KONG_DATABASE: "postgres"`: Kong cần **một instance Postgres cài riêng** (ví dụ Bitnami PostgreSQL), rồi cấu hình Kong trỏ tới qua `KONG_PG_HOST`, `KONG_PG_*`.

Phase 5 nếu muốn Kong **DB mode**: cài Postgres riêng (ví dụ `helm install postgres-kong bitnami/postgresql -n kong ...`), tạo DB `kong`, rồi set env Kong trỏ tới Postgres đó. Lợi ích: quản lý config qua Admin API, dễ scale Kong replica.

## 1. Lợi ích Kong DB mode

- **Config tập trung**: Config lưu trong Postgres; nhiều replica Kong cùng đọc, đồng bộ.
- **Admin API**: Thêm/sửa routes, services, plugins qua API (hoặc Konga, deck) thay vì sửa file và rollout lại.
- **Scale Kong**: Tăng số replica Kong mà không phải replicate file config.
- **Tách biệt**: DB Kong tách với DB ứng dụng banking → bảo trì, backup, quyền riêng.

## 2. Kiến trúc

- **Postgres cho Kong**: Deploy Postgres riêng (có thể trong ns `kong` hoặc `postgres`). Tạo database ví dụ `kong`.
- **Kong env**: `KONG_DATABASE: "postgres"`, `KONG_PG_HOST`, `KONG_PG_PORT`, `KONG_PG_DATABASE`, `KONG_PG_USER`, `KONG_PG_PASSWORD` (hoặc dùng Secret).
- **Migration**: Lần đầu chạy Kong với DB mode, Kong tự tạo bảng; sau đó **import** config từ file declarative (nếu có) bằng `kong config db_import kong.yml` (Admin API hoặc job một lần).

## 3. Migration từ declarative (file) sang DB

1. Deploy Postgres cho Kong; tạo DB và user.
2. Deploy Kong với `KONG_DATABASE: "postgres"` và connection string tới Postgres Kong.
3. Chạy Kong một lần để Kong chạy migration (tạo bảng).
4. Import config cũ: dùng Admin API hoặc `deck sync` (Kong declarative config) / script import từ `kong.yml` sang Admin API (services, routes, plugins).
5. Tắt Kong cũ (mode off); traffic trỏ sang Kong mới (DB mode).

Công cụ gợi ý: **decK** (Kong) để sync file YAML ↔ Kong DB; hoặc viết script gọi Admin API từ nội dung `kong.yml`.

## 4. Chart và namespace

- **Chart Kong (Helm) không bundle Postgres.** Kong chạy DB mode thì bạn cài Postgres **bằng chart khác** (ví dụ Bitnami PostgreSQL), có thể cùng ns `kong` hoặc ns `postgres`. Sau đó values Kong: `env.KONG_DATABASE=postgres`, `env.KONG_PG_HOST=<postgres-service>.<ns>.svc.cluster.local`, `env.KONG_PG_DATABASE=kong`, …

## 5. Checklist

- [ ] Deploy Postgres riêng cho Kong (ns `kong` hoặc `postgres`); tạo DB `kong`.
- [ ] Chỉnh Kong: `KONG_DATABASE=postgres`, biến `KONG_PG_*` (hoặc Secret).
- [ ] Chạy Kong lần đầu để migration DB.
- [ ] Import config từ kong.yml (Admin API / decK / script).
- [ ] Kiểm tra routes, plugins hoạt động; chuyển traffic sang Kong DB mode.

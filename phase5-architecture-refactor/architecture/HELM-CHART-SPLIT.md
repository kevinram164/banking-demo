# Tách Helm chart (Phase 5)

Phase 2 hiện có **một chart** `banking-demo` gồm: namespace, secret, postgres, redis, kong, frontend, auth-service, account-service, transfer-service, notification-service, ingress. Phase 5 tách thành **nhiều chart** để Kong, Redis, Postgres không còn nằm chung chart với app.

**Kong, Redis, Postgres hoàn toàn có thể (và nên) dùng chart có sẵn** từ Helm repo – không cần tự viết chart. Xem mục 2 bên dưới.

## 1. Mục tiêu

- **Chart banking-demo (thu gọn)**: Chỉ còn namespace `banking`, secret (tham chiếu hoặc copy URL từ bên ngoài), frontend, các service app (auth, account, transfer, notification), Ingress (backend trỏ tới Kong ở ns khác). **Không** còn template postgres, redis, kong.
- **Kong**: Deploy bằng **chart có sẵn** (Kong official) hoặc chart wrapper; ns `kong`. Values: image, replicas, env (KONG_DATABASE, KONG_PG_* nếu DB mode), config/backends (ConfigMap hoặc Admin API).
- **Redis**: Deploy bằng **chart có sẵn** (Bitnami Redis) vào ns `redis`.
- **Postgres**: Deploy bằng **chart có sẵn** (Bitnami PostgreSQL hoặc CloudNative-PG) vào ns `postgres`; tạo DB `banking`, user, Secret connection string cho banking app.

## 2. Dùng chart có sẵn (Kong, Redis, Postgres)

**Được**, và khuyến nghị dùng chart có sẵn để giảm công bảo trì và tận dụng cấu hình chuẩn.

| Thành phần | Chart có sẵn | Repo / Ghi chú |
|------------|--------------|----------------|
| **Kong** | `kong` (Kong official) | `helm repo add kong https://charts.konghq.com`. **Chart Kong không đi kèm DB**: mặc định chạy **declarative** (không DB, config từ file/ConfigMap). Muốn Kong **DB mode** thì cài Postgres **riêng** (Bitnami hoặc khác) rồi set env `KONG_DATABASE=postgres`, `KONG_PG_*` trỏ tới Postgres đó. |
| **Redis** | `bitnami/redis` | `helm repo add bitnami https://charts.bitnami.com/bitnami` – có sẵn master/replica, auth, persistence. |
| **Postgres (app)** | `bitnami/postgresql` hoặc `cloudnative-pg` | Bitnami: đơn giản, tạo DB/user qua values. CloudNative-PG: operator, phù hợp production. |
| **Postgres (Kong DB)** | Cùng Bitnami PostgreSQL (cài riêng) | Chart Kong **không bundle** Postgres. Muốn Kong DB mode: cài thêm 1 release Bitnami PostgreSQL (ví dụ `postgres-kong`) trong ns `kong` hoặc `postgres`, tạo DB `kong`, rồi cấu hình Kong `KONG_PG_HOST`, `KONG_PG_*`. |

Ví dụ thêm repo và cài:

```bash
# Thêm repo
helm repo add kong https://charts.konghq.com
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Tạo namespace
kubectl create namespace postgres
kubectl create namespace redis
kubectl create namespace kong

# Postgres (DB ứng dụng banking) – Bitnami
helm install postgres bitnami/postgresql -n postgres \
  --set auth.database=banking \
  --set auth.username=banking \
  --set auth.password=bankingpass \
  --set primary.persistence.size=1Gi

# Redis – Bitnami
helm install redis bitnami/redis -n redis \
  --set auth.enabled=false \
  --set master.persistence.size=1Gi

# Kong – Kong official (mặc định: declarative, không DB; chart Kong không có Postgres đi kèm)
helm install kong kong/kong -n kong \
  -f values-kong.yaml

# (Tùy chọn) Kong DB mode: cài Postgres riêng cho Kong trước, rồi set env Kong:
# helm install postgres-kong bitnami/postgresql -n kong --set auth.database=kong ...
# Sau đó values Kong: env.KONG_DATABASE=postgres, env.KONG_PG_HOST=postgres-kong-postgresql.kong.svc.cluster.local, ...
```

Sau khi cài: lấy connection string từ Secret do chart tạo (Bitnami thường tạo secret `<release>-postgresql` / `<release>-redis`) rồi điền vào `global.databaseUrl`, `global.redisUrl` của banking-demo. Service name thường là `<release>-postgresql.postgres.svc.cluster.local`, `<release>-redis-master.redis.svc.cluster.local` (Bitnami Redis).

## 3. Thứ tự cài đặt

1. **Postgres (app)** – `helm install postgres bitnami/postgresql -n postgres ...` (xem mục 2). Tạo hoặc copy Secret connection string sang ns `banking` cho app.
2. **Redis** – `helm install redis bitnami/redis -n redis ...`.
3. **Kong** – `helm install kong kong/kong -n kong -f values-kong.yaml`. Values: backends trỏ tới `http://auth-service.banking.svc.cluster.local:8001`, …
4. **Banking app** – `helm install banking-demo ./banking-demo -n banking -f values.yaml`. Values: `global.databaseUrl`, `global.redisUrl` trỏ FQDN tới Postgres/Redis (ví dụ `postgres-postgresql.postgres.svc.cluster.local`, `redis-master.redis.svc.cluster.local`).

Ingress có thể nằm trong chart banking-demo (host/path trỏ backend tới Kong) hoặc chart ingress riêng; backend Kong cần trỏ tới Service Kong trong ns `kong` (cross-namespace nếu Ingress controller hỗ trợ).

## 4. Tham chiếu giữa chart

- **Banking app** cần biết địa chỉ Postgres, Redis: truyền qua values (ví dụ `global.databaseUrl`, `global.redisUrl`) hoặc Secret tạo bởi chart Postgres/Redis và copy/reference vào ns `banking`.
- **Kong** cần biết địa chỉ các backend (auth-service, …): hardcode FQDN `*.banking.svc.cluster.local` trong values Kong hoặc ConfigMap.
- **Ingress** backend: nếu dùng HAProxy/NGINX Ingress và backend phải cùng ns, có thể tạo Service kiểu ExternalName trong ns `banking` trỏ tới `kong.kong.svc.cluster.local`, rồi Ingress trỏ backend tới Service đó.

## 5. Cấu trúc thư mục gợi ý (Phase 5)

Không bắt buộc tạo chart riêng cho Kong/Redis/Postgres – **dùng chart có sẵn** (mục 2) là đủ. Nếu muốn override values cố định cho môi trường, có thể giữ file values trong repo:

```text
phase5-architecture-refactor/
├── PHASE5.md
├── architecture/
│   └── ...
├── values-kong.yaml      # (Tùy chọn) Override cho helm install kong/kong
├── values-postgres.yaml  # (Tùy chọn) Override cho bitnami/postgresql
└── values-redis.yaml     # (Tùy chọn) Override cho bitnami/redis
```

Chart banking-demo thu gọn nằm trong `phase2-helm-chart/banking-demo` với điều kiện: **disable** postgres, redis, kong (subchart hoặc template có `enabled: false`); values dùng URL từ bên ngoài.

**HA và mapping config Phase 2 → Phase 5**: xem `PHASE2-TO-PHASE5-MAPPING.md` – Kong/Redis/Postgres triển khai HA được (replica, Bitnami replication); mapping từng trường Phase 2 sang values chart có sẵn; Application không cần sửa code, chỉ cấu hình DATABASE_URL/REDIS_URL trỏ FQDN.

## 6. Checklist

- [ ] Thêm Helm repo: kong, bitnami; `helm repo update`.
- [ ] Cài Postgres (app) bằng `bitnami/postgresql` vào ns `postgres`; lấy connection string cho banking.
- [ ] Cài Redis bằng `bitnami/redis` vào ns `redis`.
- [ ] Cài Kong bằng `kong/kong` vào ns `kong`; cấu hình backends trỏ tới `*.banking.svc.cluster.local`.
- [ ] Thu gọn banking-demo: tắt postgres, redis, kong; cấu hình databaseUrl, redisUrl trỏ FQDN cross-ns.
- [ ] Ingress (banking hoặc riêng) trỏ /api tới Kong; kiểm tra end-to-end.

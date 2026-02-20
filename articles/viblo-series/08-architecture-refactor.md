# Banking Demo: Refactor kiến trúc — Tách namespace, Kong DB, Postgres/Redis HA

> **Series**: Banking Demo — Full DevOps với Microservices  
> **Bài 8/11**: Refactor kiến trúc — Phase 5

---

## Mở đầu

Xin chào mọi người, hôm nay là mùng 5 Tết, chúng ta cùng khai bút đầu xuân với bài tiếp theo trong series.

Khi mọi người làm đến Phase 4, tôi tin chắc là nhiều bạn cũng đã đặt chửi thầm tôi: *"Kiến trúc tệ thế? DB không HA? Kong không có DB, Redis single, rồi thì update function thì redis, pg đều bị restart lại. Vớ vẩn thật sự."*

Tôi biết chứ, nhưng đó là **chủ đích** của tôi.

Phase 1–4 cố ý giữ mọi thứ gọn, đơn giản: mọi thứ trong một namespace `banking`, một chart gồm cả app + Kong + Redis + Postgres, Kong chạy declarative (không DB), Redis/Postgres một replica. Mục đích là để bạn **chạy được nhanh**, hiểu flow, rồi đến lúc thấy đau chỗ nào thì mới sửa chỗ đó — thay vì ngay từ đầu nhồi nhét HA, DB mode, tách namespace, dễ rối.

Và tôi đã chuẩn bị bài hôm nay để **chỉnh sửa lại kiến trúc** của hệ thống này, cũng như áp dụng thêm một tí kiến thức của K8s: tách namespace, tách Helm chart, Kong DB mode, Postgres/Redis HA, và cách cutover an toàn.

---

## Vấn đề Phase 2–4 (những gì ta “chịu đựng” đến giờ)

| Vấn đề | Phase 2–4 | Hệ quả |
|--------|-----------|--------|
| **Một namespace** | `banking` chứa app + Kong + Redis + Postgres | Khó tách quyền, khó tái sử dụng DB/Redis cho app khác. |
| **Một chart** | `banking-demo` gồm hết | Update image app → ArgoCD sync → nếu không Selective Sync, Postgres/Redis cũng bị “đụng” (dù không đổi gì). |
| **Kong declarative** | Config từ file/ConfigMap, `KONG_DATABASE: off` | Sửa route phải sửa file, rollout lại Kong. Không dùng Admin API, scale Kong replica khó đồng bộ config. |
| **Postgres single** | 1 replica, không HA | Chết một cái là app chết theo. |
| **Redis single** | 1 replica | Giống Postgres — không failover. |
| **Ingress backend** | Trỏ `kong` cùng ns `banking` | Sau khi tách Kong sang ns khác phải chỉnh Ingress (cross-ns hoặc ExternalName). |

Đó là lý do nhiều bạn “chửi thầm” — và đúng là có lý. Phase 5 sẽ sửa từng cái một.

---

## Mục tiêu Phase 5

Phase 5 tập trung **đổi kiến trúc**, không thêm tính năng mới:

1. **Tách namespace**: Kong → `kong`, Redis → `redis`, Postgres (DB app) → `postgres`; app banking giữ `banking`. Kết nối qua **DNS cross-namespace** (FQDN).
2. **Tách Helm chart**: Kong, Redis, Postgres **dùng chart có sẵn** (Kong official, Bitnami Redis, Bitnami PostgreSQL); chart `banking-demo` **chỉ còn app** (frontend, auth, account, transfer, notification) + Ingress trỏ tới Kong.
3. **Kong DB mode**: Kong chuyển từ declarative file sang **DB mode** (Postgres riêng cho Kong) — quản lý config qua Admin API, scale Kong dễ hơn.
4. **Postgres HA, Redis HA**: Dùng chart Bitnami với primary + replica; migrate data từ single cũ sang cluster mới.

Kết quả: app banking **không sửa code**, chỉ đổi **connection string** (DATABASE_URL, REDIS_URL) qua values/Secret; Kong backends trỏ FQDN tới `*.banking.svc.cluster.local`; Ingress trỏ backend tới Kong ở ns `kong`.

---

## Kiến trúc sau khi refactor

```
Namespace banking:
  - frontend, auth-service, account-service, transfer-service, notification-service
  - Ingress (backend trỏ tới Kong ở ns kong)
  - Secret (DATABASE_URL, REDIS_URL → postgres.postgres, redis.redis)

Namespace kong:
  - Kong Deployment (DB mode) + Service
  - (Tùy chọn) Postgres riêng cho Kong

Namespace redis:
  - Redis (Bitnami: master + replica)

Namespace postgres:
  - Postgres (Bitnami: primary + replica, DB banking)
```

**DNS cross-namespace** (FQDN):

- Postgres app: `postgres-postgresql-primary.postgres.svc.cluster.local:5432`
- Redis: `redis-master.redis.svc.cluster.local:6379` (Bitnami Redis)
- Kong proxy: `kong-kong-proxy.kong.svc.cluster.local:8000`
- App từ Kong: `auth-service.banking.svc.cluster.local:8001`, …

---

## Các thay đổi chính

### 1. Tách namespace

Tạo 4 namespace: `banking`, `kong`, `redis`, `postgres`. App trong `banking` kết nối Postgres/Redis qua FQDN. Kong trong `kong` trỏ backend tới các service trong `banking` qua FQDN. Ingress (trong `banking` hoặc `ingress`) trỏ path `/api`, `/ws` sang Kong ở ns `kong` — nếu Ingress controller không hỗ trợ backend cross-namespace thì dùng **ExternalName Service** trong ns `banking` trỏ tới `kong-kong-proxy.kong.svc.cluster.local`.

### 2. Tách Helm chart — dùng chart có sẵn

**Không cần** tự viết chart cho Kong, Redis, Postgres. Dùng chart chuẩn:

| Thành phần | Chart | Repo |
|------------|-------|------|
| **Kong** | `kong/kong` | `helm repo add kong https://charts.konghq.com` |
| **Redis** | `bitnami/redis` | `helm repo add bitnami https://charts.bitnami.com/bitnami` |
| **Postgres (app)** | `bitnami/postgresql` | Bitnami |
| **Postgres (Kong DB)** | `bitnami/postgresql` (cài riêng) | Kong chart **không** đi kèm DB; muốn DB mode phải cài Postgres riêng. |

Chart `banking-demo` thu gọn: bỏ template postgres, redis, kong; chỉ còn app + Ingress + Secret; values dùng FQDN cho `DATABASE_URL`, `REDIS_URL`.

### 3. Kong DB mode

Phase 2 Kong chạy **declarative** (`KONG_DATABASE: off`) — config từ ConfigMap. Phase 5 chuyển sang **DB mode**:

- Cài Postgres riêng cho Kong (vd trong ns `kong`).
- Set Kong: `KONG_DATABASE: postgres`, `KONG_PG_HOST`, `KONG_PG_*`.
- Lần đầu Kong chạy sẽ tự tạo bảng; sau đó **import** config từ file `kong.yml` (services, routes, plugins) qua Admin API hoặc `kong config db_import`.

Lợi ích: sửa route qua Admin API, không cần rollout Kong; scale nhiều replica Kong dùng chung config trong DB.

### 4. Postgres HA, Redis HA

- **Postgres**: Bitnami PostgreSQL với primary + replica; tạo DB `banking`, user; migrate data từ DB cũ bằng Job (`pg_dump` → `pg_restore`).
- **Redis**: Bitnami Redis với master + replica; migrate session/presence từ Redis cũ bằng Job (COPY hoặc script sync) — nếu không migrate, user phải đăng nhập lại.

---

## Các bước triển khai chi tiết

Điều kiện: Phase 2 (banking-demo với Postgres, Redis, Kong trong ns `banking`) đã chạy ổn định.

---

### Bước 0: Chuẩn bị

```bash
# Tạo các namespace mới
kubectl create namespace postgres
kubectl create namespace redis
kubectl create namespace kong

# Thêm Helm repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add kong https://charts.konghq.com
helm repo update
```

---

### Bước 1: Deploy Postgres HA và migrate data

**1.1. Tạo file values** `phase5-architecture-refactor/postgres-ha/values-postgres-ha.yaml` (auth.database=banking, auth.username=banking, primary.persistence, readReplicas…). Xem mẫu trong repo.

**1.2. Deploy Postgres HA (trống):**

```bash
helm upgrade -i postgres-ha bitnami/postgresql \
  -n postgres \
  -f phase5-architecture-refactor/postgres-ha/values-postgres-ha.yaml

# Chờ primary Ready
kubectl -n postgres get pods -l app.kubernetes.io/name=postgresql -w
# Ctrl+C khi postgres-postgresql-primary-0 Running, Ready 1/1
```

**1.3. Migrate data từ DB cũ (ns banking) sang DB mới:**

```bash
kubectl apply -f phase5-architecture-refactor/postgres-ha/migrate-db-job.yaml -n postgres
kubectl -n postgres get jobs
kubectl -n postgres logs -f job/postgres-migrate-from-banking
```

*Lưu ý:* Sửa `migrate-db-job.yaml` nếu tên Service DB cũ khác (vd: `postgres.banking.svc.cluster.local`).

**1.4. Kiểm tra DB sau migrate:**

```bash
export POSTGRES_PASSWORD=$(kubectl get secret --namespace postgres postgres-postgresql -o jsonpath="{.data.password}" | base64 -d)

kubectl run postgres-check --rm -it --restart=Never -n postgres \
  --image=bitnami/postgresql:latest \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  -- psql -h postgres-postgresql-primary -U banking -d banking -c "\dt"
```

---

### Bước 2: Deploy Redis HA và migrate session/presence

**2.1. Deploy Redis HA:**

```bash
helm upgrade -i redis bitnami/redis -n redis \
  -f phase5-architecture-refactor/redis-ha/values-redis-ha.yaml

kubectl -n redis get pods -w
# Chờ redis-master-0, redis-replicas-* Ready
```

**2.2. Migrate session và presence từ Redis cũ:**

```bash
kubectl apply -f phase5-architecture-refactor/redis-ha/migrate-redis-job.yaml -n redis
kubectl -n redis logs -f job/redis-migrate-from-banking
```

*Lưu ý:* Sửa `OLD_HOST` trong Job nếu Phase 2 dùng tên khác (vd: `redis.banking.svc.cluster.local`). Không migrate thì user phải đăng nhập lại.

---

### Bước 3: Deploy Kong HA (DB mode)

**3.1. Tạo database Kong trên Postgres HA (đã có sẵn):**

```bash
kubectl apply -f phase5-architecture-refactor/kong-ha/kong-db-init-job.yaml -n postgres
kubectl -n postgres logs job/kong-db-init
# Đảm bảo COMPLETIONS 1/1
```

*Lưu ý:* Sửa `kong-db-init-job.yaml` nếu release Postgres khác (vd: `postgres-ha-postgresql-primary`).

**3.2. Deploy Kong:**

```bash
helm upgrade -i kong kong/kong -n kong \
  -f phase5-architecture-refactor/kong-ha/values-kong-ha.yaml

kubectl -n kong get pods -l app.kubernetes.io/name=kong -w
# Chờ Kong Running, migrations Completed
```

**3.3. Import config (services, routes, plugins) từ file declarative vào Kong DB:**

```bash
kubectl apply -f phase5-architecture-refactor/kong-ha/kong-import-job.yaml -n kong
kubectl -n kong logs -f job/kong-config-import
```

**3.4. Kiểm tra Kong:**

```bash
kubectl -n kong get svc
# Proxy: kong-kong-proxy:8000, Admin: kong-kong-admin:8001

kubectl run curl-test --rm -it --restart=Never --image=curlimages/curl -n kong -- \
  curl -s -o /dev/null -w "%{http_code}" http://kong-kong-proxy:8000/api/auth/health
# Kỳ vọng: 200
```

---

### Bước 4: Cutover — chuyển app sang hạ tầng mới

**4.1. Cập nhật Secret `banking-db-secret` trong ns `banking`:**

```bash
kubectl patch secret banking-db-secret -n banking -p '{
  "stringData": {
    "DATABASE_URL": "postgresql://banking:bankingpass@postgres-postgresql-primary.postgres.svc.cluster.local:5432/banking",
    "REDIS_URL": "redis://redis-master.redis.svc.cluster.local:6379/0"
  }
}'
```

*Sửa host* nếu release name khác: `postgres-ha-postgresql-primary`, `redis.redis`, v.v.

**4.2. Cập nhật Ingress — trỏ backend sang Kong mới (ns kong):**

Nếu Ingress hỗ trợ backend cross-namespace (vd HAProxy), sửa paths:

```yaml
paths:
  - path: /api
    pathType: Prefix
    backend:
      service:
        name: kong-kong-proxy
        namespace: kong
        port:
          number: 8000
  - path: /ws
    pathType: Prefix
    backend:
      service:
        name: kong-kong-proxy
        namespace: kong
        port:
          number: 8000
```

Nếu không hỗ trợ, tạo ExternalName Service trong ns `banking`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kong-proxy
  namespace: banking
spec:
  type: ExternalName
  externalName: kong-kong-proxy.kong.svc.cluster.local
```

Rồi Ingress trỏ `serviceName: kong-proxy`, `servicePort: 8000`. Một số controller cần thêm Endpoints — xem `APP-CUTOVER.md`.

**4.3. Tắt Postgres, Redis, Kong cũ trong chart banking-demo:**

Trong values (hoặc override):

```yaml
postgres:
  enabled: false
redis:
  enabled: false
kong:
  enabled: false
```

Áp dụng:

```bash
helm upgrade banking-demo ./phase2-helm-chart/banking-demo -n banking -f values.yaml
# Hoặc qua ArgoCD: cập nhật values, sync
```

**4.4. Restart các Deployment app** (để đọc Secret mới):

```bash
kubectl -n banking rollout restart deployment auth-service account-service transfer-service notification-service frontend
kubectl -n banking rollout status deployment auth-service account-service transfer-service notification-service frontend
```

**4.5. Kiểm tra end-to-end:**

```bash
# Pods
kubectl -n banking get pods

# Test login
curl -X POST https://<ingress-host>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Kiểm tra chuyển tiền, WebSocket thông báo
```

---

### Bước 5: Rollback (nếu lỗi)

1. Trả Ingress về `serviceName: kong` (Kong cũ trong ns banking).
2. Bật lại `postgres.enabled`, `redis.enabled`, `kong.enabled` trong values.
3. Patch Secret về URL cũ: `postgres.banking`, `redis.banking`.
4. Restart deployments app.

---

### Bảng tóm tắt connection string

| Thành phần | Phase 2 (cũ) | Phase 5 (mới) |
|------------|--------------|---------------|
| Postgres | `postgres.banking:5432` | `postgres-postgresql-primary.postgres:5432` |
| Redis | `redis.banking:6379` | `redis-master.redis:6379` |
| Kong (proxy) | `kong.banking:8000` | `kong-kong-proxy.kong:8000` |

---

## Cấu trúc repo Phase 5

```
phase5-architecture-refactor/
├── PHASE5.md
├── postgres-ha/          # Postgres HA + migrate Job
├── kong-ha/              # Kong DB mode + import Job
├── redis-ha/             # Redis HA + migrate Job
├── APP-CUTOVER.md        # Hướng dẫn cutover từng bước
└── architecture/
    ├── NAMESPACE-SPLIT.md
    ├── KONG-DEDICATED-DB.md
    ├── HELM-CHART-SPLIT.md
    └── PHASE2-TO-PHASE5-MAPPING.md
```

---

## Lưu ý

- **ArgoCD**: Nếu Phase 2 dùng per-service Applications, Phase 5 cần thêm Application cho Kong, Redis, Postgres (mỗi cái một chart, ns riêng); chart banking-demo bỏ các template postgres/redis/kong, chỉnh valueFiles.
- **Monitoring (Phase 3)**: Prometheus có thể scrape cross-namespace — chỉ cần cấu hình đúng FQDN và ServiceMonitor (nếu dùng).
- **CI/CD (Phase 4)**: Không đổi; vẫn build 5 service app, push image, cập nhật values; Postgres/Redis/Kong giờ nằm ngoài chart banking-demo nên không bị “đụng” khi sync app.

---

## Tóm tắt

Phase 5 **refactor kiến trúc** chứ không thêm tính năng: tách namespace (banking, kong, redis, postgres), tách Helm chart (Kong/Redis/Postgres dùng chart có sẵn, banking-demo chỉ còn app), Kong chuyển sang DB mode, Postgres/Redis HA. App banking không sửa code, chỉ đổi connection string; cutover cần migrate data và cập nhật Secret + Ingress. Kiến trúc cũ Phase 2–4 có chủ đích đơn giản để học; đến Phase 5 mới nâng cấp cho gần production hơn.

Bài tiếp theo: **Security & Reliability** (Phase 7) — JWT hardening, Kong plugins, SLO/alerting.

---

## Bài tiếp theo

**Bài 9**: *Security & Reliability (Phase 7)*

- Auth hardening (JWT design)
- Kong security plugins
- SLO và alerting (SRE)

---

*Tags: #architecture #refactor #kubernetes #helm #kong #postgres #redis #phase5*

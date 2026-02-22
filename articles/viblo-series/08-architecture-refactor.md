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

## Troubleshooting: Fix lỗi 502 khi Frontend gọi Kong

Sau khi cutover xong, mở trình duyệt gọi `https://npd-banking.co/api/auth/health` — **502 Bad Gateway**. Mở DevTools thấy Frontend gọi `/api/*` đều trả 502.

### Nguyên nhân

HAProxy Ingress Controller **không hỗ trợ backend cross-namespace**. Ingress nằm trong ns `banking`, nhưng Kong proxy giờ ở ns `kong`. Khi Ingress trỏ `serviceName: kong-kong-proxy` — HAProxy tìm Service đó trong ns `banking`, không thấy → 502.

### Giải pháp: ExternalName Service

Tạo một **ExternalName Service** trong ns `banking` làm cầu nối DNS:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kong-proxy-ext
  namespace: banking
spec:
  type: ExternalName
  externalName: kong-kong-proxy.kong.svc.cluster.local
  ports:
    - port: 8000
      protocol: TCP
```

Service `kong-proxy-ext` không có Pod nào — nó chỉ là DNS alias trỏ sang `kong-kong-proxy.kong.svc.cluster.local`. HAProxy resolve Service này trong cùng ns `banking`, rồi forward traffic qua DNS tới Kong ở ns `kong`.

Cập nhật Ingress:

```yaml
ingress:
  paths:
    - path: /
      serviceName: frontend
      servicePort: 80
    - path: /api
      serviceName: kong-proxy-ext      # ← thay kong-kong-proxy
      servicePort: 8000
    - path: /ws
      serviceName: kong-proxy-ext
      servicePort: 8000
```

Trong Helm chart, thêm vào `common/values.yaml`:

```yaml
kongExternalService:
  enabled: true
  name: kong-proxy-ext
  externalName: kong-kong-proxy.kong.svc.cluster.local
  port: 8000
```

Template `ingress.yaml` render cả Ingress lẫn ExternalName Service:

```yaml
{{- if and .Values.kongExternalService .Values.kongExternalService.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.kongExternalService.name }}
  namespace: {{ .Release.Namespace }}
spec:
  type: ExternalName
  externalName: {{ .Values.kongExternalService.externalName }}
  ports:
    - port: {{ .Values.kongExternalService.port }}
      protocol: TCP
{{- end }}
```

Sync lại ArgoCD → 502 biến mất. Flow sau khi fix:

```
Browser → HAProxy Ingress (ns banking)
  /       → frontend:80                              (cùng ns)
  /api/*  → kong-proxy-ext:8000                      (ExternalName, cùng ns)
          → kong-kong-proxy.kong.svc:8000             (DNS resolve sang ns kong)
          → auth-service.banking.svc:8001 (etc.)      (Kong route tới app)
  /ws     → tương tự qua Kong → notification-service
```

> **Bài học**: Khi tách namespace, đừng quên rằng nhiều Ingress Controller (HAProxy, nginx-ingress community) không cho phép backend ở namespace khác. ExternalName Service là cách đơn giản nhất để bridge, không cần sửa Ingress Controller.

---

## CI/CD: Tự động update image tag (GitOps)

Phase 4 đã có CI build + push image, nhưng sau khi push xong, phải **tay** sửa `tag` trong Helm values rồi commit. Phase 5 bổ sung thêm **Stage 5: Update Image Tags** trong CI — tự động cập nhật tag và commit lại repo, để ArgoCD tự detect và sync.

### Thêm stage `update-manifests` trong CI

```yaml
# Stage 5: Update image tags in Helm values (GitOps)
update-manifests:
  name: Update Image Tags
  runs-on: ubuntu-latest
  needs: [detect-changes, push-images]
  permissions:
    contents: write
  if: |
    always() &&
    needs.push-images.result == 'success' &&
    github.ref == 'refs/heads/main'
  steps:
    - uses: actions/checkout@v4
      with:
        ref: main
        fetch-depth: 0

    - name: Compute image tag
      id: tag
      run: echo "sha=$(git rev-parse --short=7 HEAD)" >> $GITHUB_OUTPUT

    - name: Update Helm values
      run: |
        SERVICES="${{ needs.detect-changes.outputs.services-list }}"
        TAG="${{ steps.tag.outputs.sha }}"
        CHART_DIR="phase2-helm-chart/banking-demo/charts"

        should_update() {
          [ "$SERVICES" == "all" ] && return 0
          echo "$SERVICES" | grep -q "$1" && return 0
          return 1
        }

        update_tag() {
          local svc="$1"
          local file="$CHART_DIR/$svc/values.yaml"
          if [ -f "$file" ]; then
            sed -i "s|tag: .*|tag: $TAG|" "$file"
            echo "Updated $svc → $TAG"
          fi
        }

        for svc in auth-service account-service transfer-service \
                    notification-service frontend; do
          if should_update "$svc"; then
            update_tag "$svc"
          fi
        done

    - name: Commit and push
      run: |
        git config user.name "github-actions[bot]"
        git config user.email "github-actions[bot]@users.noreply.github.com"
        git add phase2-helm-chart/banking-demo/charts/*/values.yaml

        if git diff --cached --quiet; then
          echo "No tag changes, skipping commit"
          exit 0
        fi

        TAG="${{ steps.tag.outputs.sha }}"
        SERVICES="${{ needs.detect-changes.outputs.services-list }}"
        git commit -m "ci: update image tags to ${TAG} [${SERVICES}] [skip ci]"
        git push origin main
```

### Cách hoạt động

1. CI build image, tag bằng **short SHA** (7 ký tự, ví dụ `927432e`).
2. Push image lên GitLab Container Registry.
3. Stage `update-manifests` chạy:
   - Chỉ update **service nào thay đổi** (nhờ `detect-changes` ở đầu pipeline).
   - Dùng `sed` sửa `tag: ...` trong `charts/<service>/values.yaml`.
   - Commit với message `ci: update image tags to 927432e [auth-service,frontend] [skip ci]`.
   - `[skip ci]` để tránh trigger lại chính nó.
4. ArgoCD detect commit mới → tự sync → rollout Deployment mới.

Kết quả: push code → CI tự build, push, update tag → ArgoCD tự deploy. Không cần đụng tay.

---

## Cập nhật Log Level cho các service

Phase 4 đã thêm structured logging (JSON) qua `logging_utils.py`, nhưng log level mặc định cứng `INFO`. Phase 5 bổ sung khả năng **điều chỉnh log level qua environment variable** — hữu ích khi cần debug production mà không build lại image.

### `logging_utils.py` — đọc `LOG_LEVEL` từ env

```python
def get_json_logger(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    return logger
```

Mặc định `INFO`. Muốn bật `DEBUG` cho service nào, thêm env vào Helm values:

```yaml
auth-service:
  extraEnv:
    LOG_LEVEL: "DEBUG"
    OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector-..."
```

Hoặc patch nhanh bằng kubectl:

```bash
kubectl -n banking set env deployment/auth-service LOG_LEVEL=DEBUG
```

Khi debug xong, đổi lại `INFO` hoặc xoá env để về default. Không cần rebuild image, không cần sửa code.

### Logging flow

Mỗi service đều dùng chung pattern:

```python
logger = get_json_logger("auth-service")
app.add_middleware(RequestLogMiddleware, logger=logger, service_name="auth-service")
```

- **RequestLogMiddleware**: tự động log mọi HTTP request (trừ `/health`, `/metrics`) dạng JSON — method, path, status, duration_ms, request_id.
- **log_event()**: log sự kiện business — `login_success`, `transfer_failed`, `ws_connected`, …

Output mỗi dòng là JSON, dễ parse bằng Loki/Promtail hoặc Elasticsearch:

```json
{"ts":"2025-02-07T10:30:15","event":"http_request","service":"auth-service","method":"POST","path":"/login","status":200,"duration_ms":45.12,"request_id":"abc-123"}
{"ts":"2025-02-07T10:30:15","event":"login_success","user_id":42}
```

---

## Admin Portal — Trang quản trị NPD Banking

Phase 4 v2 thêm **Admin Panel** cho ứng dụng Banking — một trang quản trị để xem tổng quan hệ thống, danh sách users, chi tiết giao dịch. Sau khi refactor Phase 5, Admin Portal vẫn hoạt động bình thường vì không phụ thuộc vào kiến trúc hạ tầng — chỉ gọi API qua Kong như mọi request khác.

### Kiến trúc

Admin Portal gồm 2 phần:

**Backend** — 3 endpoint trong `account-service`, bảo vệ bằng header `X-Admin-Secret`:

```python
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "banking-admin-2025")

def verify_admin(x_admin_secret: str | None = Header(default=None)):
    if not x_admin_secret or x_admin_secret != ADMIN_SECRET:
        raise HTTPException(403, "Forbidden")
```

| Endpoint | Mô tả |
|----------|-------|
| `GET /admin/stats` | Tổng users, tổng balance, tổng giao dịch, tổng giá trị chuyển khoản, tổng thông báo |
| `GET /admin/users?page=&size=&search=` | Danh sách users phân trang, tìm kiếm theo tên/phone/số tài khoản |
| `GET /admin/users/{user_id}` | Chi tiết 1 user + 20 giao dịch gần nhất (in/out) |

Secret mặc định: `banking-admin-2025`. Override qua env `ADMIN_SECRET` trong Helm values nếu cần.

**Frontend** — trang `Admin.js` gồm:

- **AdminLogin**: nhập admin secret, validate bằng cách gọi `/admin/stats`, lưu vào `localStorage`.
- **StatsCards**: 5 thẻ KPI — Total Users, Total Balance, Total Transfers, Transfer Volume, Notifications.
- **User Table**: bảng phân trang (20/trang), có search bar tìm kiếm.
- **UserDetailModal**: popup xem chi tiết user + lịch sử giao dịch (in/out, thời gian, số tiền).

### Cách truy cập

1. Mở `https://npd-banking.co` → trang Login.
2. Click **"Admin"** ở footer hoặc vào Dashboard → sidebar → **"Admin Panel"**.
3. Nhập admin secret (`banking-admin-2025`) → vào trang quản trị.

### Luồng API

```
Browser → Ingress → Kong → account-service
  GET /api/account/admin/stats          (Header: X-Admin-Secret)
  GET /api/account/admin/users?page=1   (Header: X-Admin-Secret)
  GET /api/account/admin/users/42       (Header: X-Admin-Secret)
```

Kong route `/api/account` trỏ tới `account-service` với `strip_path: true`, nên request đến account-service là `/admin/stats`, `/admin/users`, …

---

## Test tải với `seed_users.py`

Sau khi refactor, cần verify hệ thống chịu tải. Script `scripts/seed_users.py` tạo hàng trăm/nghìn users giả lập với tên tiếng Việt, gọi API đăng ký song song qua nhiều luồng — vừa là load test, vừa tạo dữ liệu để Admin Portal có gì mà xem.

### Cách chạy

```bash
cd scripts
pip install requests

# Tạo 500 users, 20 luồng song song
python seed_users.py --count 500 --base-url http://npd-banking.co

# Tạo 1000 users, lưu ra file JSON để dùng tiếp
python seed_users.py -n 1000 -u http://npd-banking.co -o users.json

# Self-signed cert? Thêm --no-verify
python seed_users.py -n 500 -u https://npd-banking.co --no-verify

# Test 1 request trước
python seed_users.py --test -u http://npd-banking.co
```

### Tính năng chính

- **Auto-detect API version**: tự phát hiện v1 (username) hay v2 (phone + username). Phase 4 v2 dùng v2 — script gửi `phone`, `username`, `password`.
- **Tên tiếng Việt**: tổ hợp ngẫu nhiên từ Họ (Nguyễn, Trần, Lê…), Tên đệm (Văn, Thị, Minh…), Tên (An, Bình, Chi…) + số index để không trùng.
- **Phone unique**: `09xxxxxxxx` — mỗi index một số phone khác nhau.
- **Concurrent**: dùng `ThreadPoolExecutor` với `--workers` (mặc định 20 luồng).
- **Seed offset**: `--seed 1000` để chạy batch 2 không trùng batch 1.
- **Output JSON**: `--output users.json` lưu danh sách users đã tạo (phone, username, password, account_number) — dùng cho test login/transfer sau.

### Kết quả mẫu

```
=== Seed Users (Python) ===
Count:    500
Base URL: http://npd-banking.co
Workers:  20

Đang phát hiện API version...
API: v2
  Progress: 100/500  (ok=98 skip=2 fail=0)
  Progress: 200/500  (ok=198 skip=2 fail=0)
  Progress: 300/500  (ok=298 skip=2 fail=0)
  Progress: 400/500  (ok=398 skip=2 fail=0)
  Progress: 500/500  (ok=498 skip=2 fail=0)

=== Kết quả ===
Thành công: 498
Bỏ qua:    2  (đã tồn tại)
Thất bại:   0
```

### Kết hợp Admin Portal

Sau khi seed xong, mở Admin Portal → thấy:

- **Total Users** tăng lên (vd: 498 users mới).
- **User Table** có hàng trăm users với tên tiếng Việt, phone, account number.
- Search thử `"Nguyễn"` → lọc ra tất cả users họ Nguyễn.
- Click **Detail** trên 1 user → xem balance (mặc định 10,000₫) và chưa có giao dịch.

Đây là cách nhanh nhất để có dữ liệu test thực tế cho Admin Portal, đồng thời verify rằng auth-service + account-service chịu được burst 500 requests đăng ký đồng thời sau khi refactor hạ tầng.

---

## Tóm tắt

Phase 5 **refactor kiến trúc** chứ không thêm tính năng: tách namespace (banking, kong, redis, postgres), tách Helm chart (Kong/Redis/Postgres dùng chart có sẵn, banking-demo chỉ còn app), Kong chuyển sang DB mode, Postgres/Redis HA. App banking không sửa code, chỉ đổi connection string; cutover cần migrate data và cập nhật Secret + Ingress.

Ngoài ra, bài này cũng cover:

- **Fix 502**: HAProxy Ingress không hỗ trợ cross-namespace backend → dùng ExternalName Service làm cầu nối.
- **CI auto-update tag**: Thêm stage `update-manifests` trong GitHub Actions — tự sửa image tag trong Helm values và commit, để ArgoCD tự sync.
- **Log level runtime**: Tất cả service đọc `LOG_LEVEL` từ env, mặc định `INFO`, có thể chuyển `DEBUG` mà không cần rebuild.
- **Admin Portal**: Trang quản trị NPD Banking — xem stats, danh sách users phân trang, chi tiết giao dịch, bảo vệ bằng `X-Admin-Secret`.
- **Load test `seed_users.py`**: Script Python tạo hàng trăm/nghìn users giả lập (tên Việt, phone unique) song song 20 luồng — vừa test tải, vừa tạo dữ liệu cho Admin Portal.

Kiến trúc cũ Phase 2–4 có chủ đích đơn giản để học; đến Phase 5 mới nâng cấp cho gần production hơn.

---

## Bài tiếp theo

**Bài 9**: *Security & Reliability (Phase 7)*

- Auth hardening (JWT design)
- Kong security plugins
- SLO và alerting (SRE)

---

*Tags: #architecture #refactor #kubernetes #helm #kong #postgres #redis #phase5 #cicd #troubleshooting #admin-portal #load-test #seed-users*

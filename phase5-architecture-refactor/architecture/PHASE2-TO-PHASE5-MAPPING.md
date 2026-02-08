# Phase 2 → Phase 5: HA, mapping config, và thay đổi Application

Tài liệu này trả lời: (1) Kong, Redis, Postgres có triển khai HA được không; (2) mapping config Phase 2 sang Phase 5 (chart có sẵn); (3) Application có cần sửa gì không.

---

## 1. Kong, Redis, Postgres có triển khai HA được không?

**Có.** Cả ba đều có thể chạy kiểu HA khi dùng chart có sẵn (và đúng mode).

### 1.1. Kong HA

- **Declarative mode (Phase 2 hiện tại)**: Nhiều replica Kong cùng đọc 1 file config (ConfigMap). Chỉ cần `replicas: 2` trở lên; Service load-balance giữa các pod. **Đã HA** về mặt nhiều instance.
- **DB mode (Phase 5 gợi ý)**: Kong dùng Postgres làm nguồn sự thật; nhiều replica Kong cùng kết nối DB. Chart Kong official hỗ trợ `replicaCount: 2+`. Cần Postgres Kong chạy HA nếu muốn Kong không single point of failure (xem Postgres HA bên dưới).

Chart Kong (Kong official): set `replicaCount: 2` (hoặc hơn) trong values. Không cần sửa code app.

### 1.2. Redis HA

- **Bitnami Redis**: Có sẵn chế độ **master + replica(s)**. Bật HA bằng cách set `architecture: replication`, `master.replicaCount: 1`, `replica.replicaCount: 1` (hoặc 2+). Client kết nối qua Service master; chart tạo `redis-master`, `redis-replicas`. App vẫn trỏ **một endpoint** (redis-master) – Redis tự xử lý failover (Bitnami có sentinel/script tùy phiên bản).
- **Lưu ý**: Ứng dụng banking hiện dùng Redis cho session; client kết nối 1 URL. Với Bitnami Redis HA, URL vẫn là `redis://redis-master.redis.svc.cluster.local:6379/0` (hoặc tên Service do chart tạo). Không cần sửa code app nếu vẫn dùng một endpoint.

Ví dụ Bitnami Redis HA:

```yaml
# values-redis.yaml (Phase 5)
architecture: replication
auth:
  enabled: false
master:
  replicaCount: 1
  persistence:
    size: 256Mi
replica:
  replicaCount: 2
  persistence:
    size: 256Mi
```

### 1.3. Postgres HA

- **Bitnami PostgreSQL**: Có **primary + read replicas**. Set `architecture: replication`, `primary.replicaCount: 1`, `readReplicas.replicaCount: 1` (hoặc 2+). App **ghi** vào primary, **đọc** có thể trỏ read replica (nếu app hỗ trợ 2 connection string). Banking demo hiện chỉ dùng 1 connection string (ghi + đọc) → trỏ vào **primary** là đủ; primary có 1 replica để failover.
- **CloudNative-PG**: Operator quản lý cluster Postgres HA (primary + replicas, failover tự động). App trỏ vào Service primary (hoặc read-only service nếu tách).

Ví dụ Bitnami Postgres HA (primary + 1 replica):

```yaml
# values-postgres.yaml (Phase 5)
architecture: replication
auth:
  database: banking
  username: banking
  password: bankingpass
primary:
  replicaCount: 1
  persistence:
    size: 1Gi
readReplicas:
  replicaCount: 1
  persistence:
    size: 1Gi
```

Application chỉ cần **một** connection string trỏ tới primary (ví dụ `postgres-postgresql.postgres.svc.cluster.local:5432`). **Không cần sửa code** nếu vẫn dùng một URL cho cả đọc/ghi.

**Tóm tắt HA**: Kong = tăng replicaCount; Redis = Bitnami replication; Postgres = Bitnami replication hoặc CloudNative-PG. App chỉ cần trỏ đúng FQDN/URL (và nếu Postgres HA thì trỏ primary).

---

## 2. Mapping config Phase 2 → Phase 5

Config Phase 2 nằm trong `phase2-helm-chart/banking-demo/charts/{kong,redis,postgres,common}/values.yaml`. Sang Phase 5 (chart có sẵn), mapping như sau.

### 2.1. Postgres (Phase 2 → Bitnami PostgreSQL)

| Phase 2 (charts/postgres + common) | Phase 5 (bitnami/postgresql) |
|-----------------------------------|-----------------------------|
| `postgres.fullnameOverride: postgres` | Release name ví dụ `postgres` → Service `postgres-postgresql` (Bitnami mặc định) |
| `secretRef.name: banking-db-secret`, `keys: user/password/db` | Bitnami tạo secret `postgres-postgresql`; keys `postgres-password`, `user`, `database`. Dùng values: `auth.username`, `auth.password`, `auth.database` |
| `postgresUser: banking`, `postgresPassword: bankingpass`, `postgresDb: banking` (trong common) | `--set auth.username=banking` (hoặc `auth.postgresPassword` tùy chart), `auth.database=banking`, `auth.password=bankingpass` |
| `service.port: 5432` | Bitnami mặc định 5432 |
| `storage.size: 1Gi`, `storageClassName: nfs-client` | `primary.persistence.size=1Gi`, `primary.persistence.storageClass=nfs-client` (nếu giữ NFS) |
| `image.tag: "16"` | Bitnami: `image.tag` tương ứng bản 16 |

Connection string app (Phase 2): `postgresql://banking:bankingpass@postgres:5432/banking`.  
Phase 5 (cross-ns): `postgresql://banking:bankingpass@postgres-postgresql.postgres.svc.cluster.local:5432/banking` (hoặc tên Service thực tế do Bitnami tạo, ví dụ `<release>-postgresql`).

### 2.2. Redis (Phase 2 → Bitnami Redis)

| Phase 2 (charts/redis) | Phase 5 (bitnami/redis) |
|------------------------|-------------------------|
| `fullnameOverride: redis`, `service.port: 6379` | Release name `redis` → Service `redis-master` (Bitnami); port 6379 |
| Không auth (`redis://redis:6379/0`) | `auth.enabled: false` |
| `storage.size: 256Mi`, `storageClassName: nfs-client` | `master.persistence.size=256Mi`, `master.persistence.storageClass=nfs-client` |
| `image.tag: 7-alpine` | Bitnami: `image.tag` tương ứng 7 |

Connection string app (Phase 2): `redis://redis:6379/0`.  
Phase 5: `redis://redis-master.redis.svc.cluster.local:6379/0` (Bitnami Redis không HA dùng `redis-master`; nếu bật HA vẫn thường trỏ `redis-master`).

### 2.3. Kong (Phase 2 → Kong official chart)

| Phase 2 (charts/kong) | Phase 5 (kong/kong) |
|----------------------|---------------------|
| `image.repository: kong`, `tag: "3.4"` | Chart Kong: `image.repository`, `image.tag` (ví dụ 3.4) |
| `replicas: 1` | `replicaCount: 2` (HA) hoặc 1 |
| `proxyPort: 8000`, `adminPort: 8001` | Chart Kong dùng port 8000 (proxy), 8001 (admin) mặc định |
| `env.KONG_DATABASE: "off"`, `KONG_DECLARATIVE_CONFIG: "/kong/kong.yml"` | Giữ nguyên nếu vẫn declarative; chart Kong hỗ trợ mount ConfigMap và env |
| `backends` (auth-service, account-service, …) với `url: "http://auth-service:8001"` | Phase 5 Kong ở ns khác → URL phải FQDN: `http://auth-service.banking.svc.cluster.local:8001`, `http://account-service.banking.svc.cluster.local:8002`, … |
| `corsOrigins`, `corsCredentials`, `corsMethods`, `corsHeaders` | Giữ trong ConfigMap/values khi tạo kong.yml (declarative) hoặc cấu hình qua Admin API |
| `globalPlugins: [prometheus]`, `extraPlugins: []` | Cấu hình tương ứng trong declarative config hoặc Admin API |
| `readinessProbe`, `resources`, `securityContext` | Map sang values chart Kong (pod annotations, resources, securityContext) |

Quan trọng: **backends** trong Phase 2 dùng tên Service ngắn (`auth-service:8001`) vì cùng namespace. Phase 5 Kong ở ns `kong`, app ở ns `banking` → phải dùng FQDN:

- `http://auth-service.banking.svc.cluster.local:8001`
- `http://account-service.banking.svc.cluster.local:8002`
- `http://transfer-service.banking.svc.cluster.local:8003`
- `http://notification-service.banking.svc.cluster.local:8004`

Chart Kong official có thể dùng declarative config qua ConfigMap; bạn tạo 1 ConfigMap chứa nội dung kong.yml (giống Phase 2 nhưng url backend = FQDN trên) rồi mount vào Kong.

### 2.4. Common / Ingress (Phase 2 → Phase 5)

| Phase 2 (common) | Phase 5 |
|------------------|--------|
| `global.namespace: banking` | Giữ; app vẫn deploy trong `banking` |
| `secret.databaseUrl`, `secret.redisUrl` | Thay bằng URL trỏ FQDN Postgres/Redis (xem 2.1, 2.2). Secret `banking-db-secret` trong ns `banking` chứa `DATABASE_URL`, `REDIS_URL` mới. |
| `ingress.paths` trỏ `serviceName: kong`, `servicePort: 8000` | Ingress vẫn trỏ tới Kong; backend có thể là `kong-proxy.kong.svc.cluster.local:8000` (tên Service do chart Kong tạo) hoặc ExternalName Service trong ns `banking` trỏ tới đó. |

---

## 3. Application có cần sửa gì không?

**Không cần sửa code** nếu ứng dụng đọc **DATABASE_URL** và **REDIS_URL** từ biến môi trường (hoặc Secret inject vào env). Phase 2 đã làm vậy (Secret `banking-db-secret` → env của từng service).

Thay đổi duy nhất: **giá trị** hai URL đó:

- **Phase 2**: `postgresql://banking:bankingpass@postgres:5432/banking`, `redis://redis:6379/0` (host = tên Service trong cùng ns `banking`).
- **Phase 5**: `postgresql://banking:bankingpass@postgres-postgresql.postgres.svc.cluster.local:5432/banking`, `redis://redis-master.redis.svc.cluster.local:6379/0` (FQDN cross-namespace).

Cách làm:

1. **Chart banking-demo (thu gọn)**: Trong values (common hoặc global), set `databaseUrl` và `redisUrl` (hoặc secretRef) trỏ đúng FQDN. Template Secret/Deployment của app vẫn dùng hai biến này → không đổi template (chỉ đổi values).
2. **Hoặc**: Tạo Secret `banking-db-secret` trong ns `banking` thủ công (hoặc từ CI) với `DATABASE_URL` và `REDIS_URL` = chuỗi Phase 5; chart banking-demo chỉ cần tham chiếu secret này, không tạo từ values. App không đổi.

Kết luận: **Application không cần sửa code**; chỉ cần cấu hình (values hoặc Secret) cung cấp đúng connection string cho Postgres và Redis (và nếu có CORS/origin thì vẫn giữ như Phase 2). Kong không do app gọi trực tiếp (client → Ingress → Kong → app) nên app không cần biết địa chỉ Kong.

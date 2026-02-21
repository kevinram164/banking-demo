# Chuyển app Banking sang dùng Redis, Kong, Postgres mới (Phase 5)

Hướng dẫn cutover: migrate data, cập nhật connection string, chuyển Ingress sang Kong mới, tắt các service cũ.

---

## Điều kiện tiên quyết

- **Postgres HA** đã deploy trong ns `postgres`, DB `banking` đã migrate (xem `postgres-ha/README.md`)
- **Redis HA** đã deploy trong ns `redis` (xem `redis-ha/` – Bitnami Redis)
- **Kong HA** đã deploy trong ns `kong`, config đã import (xem `kong-ha/README.md`)

---

## Tổng quan thứ tự

1. Migrate Postgres (nếu chưa)
2. Migrate Redis (session, presence)
3. Cập nhật Secret `banking-db-secret` – `DATABASE_URL`, `REDIS_URL`
4. Cập nhật Ingress – trỏ `/api`, `/ws` sang Kong mới
5. Tắt Postgres, Redis, Kong cũ trong chart banking-demo
6. Restart các deployment app
7. Kiểm tra end-to-end

---

## Bước 1: Migrate Postgres (nếu chưa)

```bash
kubectl apply -f postgres-ha/migrate-db-job.yaml -n postgres
kubectl -n postgres logs -f job/postgres-migrate-from-banking
```

---

## Bước 2: Migrate Redis

Redis cũ lưu: `session:{sid}`, `presence:{user_id}`. Migrate để user không bị logout.

```bash
kubectl apply -f redis-ha/migrate-redis-job.yaml -n redis
kubectl -n redis logs -f job/redis-migrate-from-banking
```

**Lưu ý**: Sửa `OLD_HOST` / `NEW_HOST` trong Job nếu Phase 2 dùng tên Service khác:
- Phase 2 Redis: `redis.banking.svc.cluster.local` (hoặc `redis` nếu cùng ns)
- Phase 5 Redis: `redis-master.redis.svc.cluster.local`

**Nếu không migrate Redis**: User sẽ cần đăng nhập lại sau cutover.

---

## Bước 3: Cập nhật Secret cho app

Tạo/cập nhật Secret `banking-db-secret` trong ns `banking` với URL mới.

**Quan trọng**: Bitnami Redis Phase 5 bật `auth.enabled: true` → **REDIS_URL phải có password**. Nếu thiếu, app trả 503 trên `/health` (Readiness probe failed).

```bash
# Lấy Redis password (Bitnami: redis-password hoặc password)
REDIS_PASS=$(kubectl get secret -n redis redis -o jsonpath='{.data.redis-password}' 2>/dev/null | base64 -d)
[ -z "$REDIS_PASS" ] && REDIS_PASS=$(kubectl get secret -n redis redis -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)

# Patch Secret — cú pháp redis://:password@host (dấu : trước password)
kubectl patch secret banking-db-secret -n banking -p "{
  \"stringData\": {
    \"DATABASE_URL\": \"postgresql://banking:bankingpass@postgres-postgresql-primary.postgres.svc.cluster.local:5432/banking\",
    \"REDIS_URL\": \"redis://:${REDIS_PASS}@redis.redis.svc.cluster.local:6379/0\"
  }
}"
```

**Hoặc tạo mới** (nếu Secret chưa tồn tại):

```bash
REDIS_PASS=$(kubectl get secret -n redis redis -o jsonpath='{.data.redis-password}' 2>/dev/null | base64 -d)
kubectl create secret generic banking-db-secret -n banking \
  --from-literal=DATABASE_URL='postgresql://banking:bankingpass@postgres-postgresql-primary.postgres.svc.cluster.local:5432/banking' \
  --from-literal=REDIS_URL="redis://:${REDIS_PASS}@redis.redis.svc.cluster.local:6379/0"
```

**Sửa host** nếu release name khác:
- Postgres: `postgres-ha-postgresql-primary` nếu release = `postgres-ha`
- Redis: `redis` hoặc `redis-master` (tùy chart)

---

## Bước 4: Cập nhật Ingress – trỏ sang Kong mới

Ingress hiện trỏ `serviceName: kong` (trong ns banking). Kong mới ở ns `kong`, Service `kong-kong-proxy:8000`.

**Cách 1: Ingress backend cross-namespace**

Nếu HAProxy/Ingress hỗ trợ backend khác namespace, sửa Ingress:

```yaml
# Trong Ingress banking (hoặc ArgoCD application ingress)
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

**Cách 2: ExternalName Service (HAProxy Ingress mặc định không hỗ trợ cross-ns)**

Chart `banking-demo` đã cấu hình `ingress.kongExternalService: true` trong `charts/common/values.yaml` — tạo Service `kong-proxy` (ExternalName) trong ns `banking` trỏ tới `kong-kong-proxy.kong.svc.cluster.local`. Ingress reference `kong-proxy` (cùng namespace).

**Cách 3: Bật --allow-cross-namespace trên HAProxy Ingress**

```bash
kubectl get deployment -A -l app.kubernetes.io/name=haproxy-ingress
kubectl edit deployment <tên> -n <namespace>
# Thêm vào args: --allow-cross-namespace=true
```

---

## Bước 5: Tắt Postgres, Redis, Kong cũ

Trong `banking-demo` chart (Phase 2), set:

```yaml
# values hoặc values override
postgres:
  enabled: false
redis:
  enabled: false
kong:
  enabled: false
```

Upgrade release:

```bash
helm upgrade banking-demo ./banking-demo -n banking -f values.yaml
# Hoặc qua ArgoCD: cập nhật values, sync
```

---

## Bước 6: Restart app deployments

Để app đọc Secret mới:

```bash
kubectl -n banking rollout restart deployment auth-service account-service transfer-service notification-service
kubectl -n banking rollout status deployment auth-service account-service transfer-service notification-service
```

---

## Bước 7: Kiểm tra

```bash
# Pods app
kubectl -n banking get pods

# Test login, chuyển tiền, thông báo
curl -X POST https://npd-banking.co/api/auth/login -H "Content-Type: application/json" -d '{"username":"...","password":"..."}'
```

---

## Rollback (nếu lỗi)

1. Trả Ingress về `serviceName: kong` (Kong cũ)
2. Bật lại `postgres.enabled`, `redis.enabled`, `kong.enabled`
3. Restore Secret về URL cũ (postgres.banking, redis.banking)
4. Restart deployments

---

## Tóm tắt connection string

| Thành phần | Phase 2 (cũ) | Phase 5 (mới) |
|------------|--------------|---------------|
| Postgres | `postgres.banking:5432` | `postgres-postgresql-primary.postgres:5432` |
| Redis | `redis.banking:6379` (no auth) | `redis.redis:6379` — **cần password**: `redis://:PASSWORD@redis.redis...` |
| Kong (proxy) | `kong.banking:8000` | `kong-kong-proxy.kong:8000` |

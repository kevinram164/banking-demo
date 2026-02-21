# Chuyển sang Per-Service Applications (Phase 5)

Mỗi service một Application riêng. **Postgres, Redis, Kong** đã tách sang Phase 5 (ns riêng) — không deploy qua banking-demo.

---

## Điều kiện tiên quyết

- **ArgoCD Project** `banking-demo` đã apply: `kubectl apply -f project.yaml -n argocd`
- **Postgres HA** đã deploy trong ns `postgres`, DB `banking` đã migrate
- **Redis HA** đã deploy trong ns `redis` (Bitnami Redis — **có password**)
- **Kong HA** đã deploy trong ns `kong`

---

## Migration (từ Application đơn `banking-demo`)

### Bước 0: Cấu hình ArgoCD CLI (nếu dùng sync qua CLI)

```bash
# Login ArgoCD server (thay URL nếu khác)
argocd login https://npd-argocd.co --insecure

# Nếu lỗi "Argo CD server address unspecified" → chưa login
# Nếu lỗi proxy "lookup tcp///..." → unset proxy:
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
```

**Lưu ý**: Cần thêm `accounts.admin: apiKey, login` vào ConfigMap `argocd-cm` để tạo token từ UI (Settings > Accounts > admin > Generate New).

---

### Bước 1: Xóa Application đơn (bắt buộc — trước khi apply per-service)

**Quan trọng**: Phải xóa `banking-demo` trước, nếu không sẽ gặp:
- **SharedResourceWarning**: Deployment được quản lý bởi 2 Application (banking-demo và banking-demo-account-service)
- **SyncError**: `spec.selector: Invalid value: ... field is immutable` — hai app có selector khác nhau, patch Deployment thất bại

```bash
kubectl delete application banking-demo -n argocd
```

Nếu đã apply per-service trước khi xóa và gặp lỗi `spec.selector immutable`, xóa Deployment rồi để ArgoCD tạo lại:

```bash
kubectl delete deployment account-service -n banking
# Sau đó sync lại banking-demo-account-service
```

---

### Bước 2: Apply per-service Applications

```bash
cd phase2-helm-chart/argocd
kubectl apply -f applications/ -n argocd
```

---

### Bước 3: Patch Secret với Redis password (bắt buộc nếu Redis có auth)

Chart `banking-demo` tạo Secret từ `charts/common/values.yaml` với `redisUrl` mặc định **không có password**. Bitnami Redis Phase 5 bật `auth.enabled: true` → app sẽ trả **503** trên `/health` (Readiness probe failed).

Lấy password và patch:

```bash
# Lấy Redis password (Bitnami: redis-password hoặc password)
REDIS_PASS=$(kubectl get secret -n redis redis -o jsonpath='{.data.redis-password}' 2>/dev/null | base64 -d)
[ -z "$REDIS_PASS" ] && REDIS_PASS=$(kubectl get secret -n redis redis -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)

# Patch Secret — cú pháp redis://:password@host (dấu : trước password)
kubectl patch secret banking-db-secret -n banking -p "{\"stringData\": {\"REDIS_URL\": \"redis://:${REDIS_PASS}@redis.redis.svc.cluster.local:6379/0\"}}"
```

**Kiểm tra**:

```bash
kubectl run -n banking redis-test --rm -it --restart=Never --image=redis:7 -- \
  redis-cli -h redis.redis.svc.cluster.local -a "$REDIS_PASS" ping
# Kỳ vọng: PONG
```

---

### Bước 4: Sync theo thứ tự (lần đầu)

```bash
argocd app sync banking-demo-namespace
argocd app sync banking-demo-auth-service
argocd app sync banking-demo-account-service
argocd app sync banking-demo-transfer-service
argocd app sync banking-demo-notification-service
argocd app sync banking-demo-frontend
argocd app sync banking-demo-ingress
```

Hoặc sync tất cả (ArgoCD dùng sync-wave để thứ tự đúng):

```bash
argocd app sync -l app.kubernetes.io/name=banking-demo
```

---

### Bước 5: Restart deployments (sau khi patch Secret)

Để app đọc Secret mới (REDIS_URL có password):

```bash
kubectl rollout restart deployment -n banking auth-service account-service transfer-service notification-service
kubectl rollout status deployment -n banking auth-service account-service transfer-service notification-service
```

---

## Xử lý sự cố thường gặp

| Sự cố | Nguyên nhân | Cách xử lý |
|-------|-------------|------------|
| `Argo CD server address unspecified` | Chưa login ArgoCD | `argocd login https://npd-argocd.co --insecure` |
| `lookup tcp///npd-argocd.co: unknown port` | Proxy env sai | `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY` |
| `account 'admin' does not have apiKey capability` | Admin chưa có quyền tạo token | Thêm `accounts.admin: apiKey, login` vào `argocd-cm`, restart argocd-server |
| **SharedResourceWarning** (Deployment part of 2 apps) | Cả banking-demo và per-service cùng quản lý | Xóa `kubectl delete application banking-demo -n argocd` |
| **SyncError** `spec.selector: field is immutable` | Hai app có selector khác nhau | Xóa banking-demo; nếu vẫn lỗi: `kubectl delete deployment <name> -n banking` rồi sync lại |
| **OrphanedResourceWarning** (50 orphaned) | Resource cũ từ app tập trung | Xóa banking-demo; xem danh sách orphaned trong UI, xóa thủ công nếu cần |
| **Readiness probe 503** | App không kết nối được Postgres/Redis | Xem mục dưới |

---

### Readiness probe 503 — Health check failed

`/health` trả 503 khi **không kết nối được Postgres hoặc Redis**.

**Kiểm tra**:

```bash
# 1. Test Postgres
kubectl run -n banking psql-test --rm -it --restart=Never --image=postgres:15 -- \
  psql "postgresql://banking:bankingpass@postgres-postgresql-primary.postgres.svc.cluster.local:5432/banking" -c "SELECT 1"

# 2. Test Redis (không password → NOAUTH)
kubectl run -n banking redis-test --rm -it --restart=Never --image=redis:7 -- \
  redis-cli -h redis.redis.svc.cluster.local ping
# Nếu (error) NOAUTH Authentication required → cần patch REDIS_URL có password (Bước 3)
```

**Sửa**: Patch `banking-db-secret` với `REDIS_URL` có password (Bước 3), rồi restart deployments (Bước 5).

---

## Phase 5: Không còn postgres, redis, kong Applications

- **Postgres**: Deploy bằng `phase5-architecture-refactor/postgres-ha/` (Helm riêng)
- **Redis**: Deploy bằng `phase5-architecture-refactor/redis-ha/` (Helm riêng)
- **Kong**: Deploy bằng `phase5-architecture-refactor/kong-ha/` (Helm riêng)

Chart banking-demo chỉ deploy: namespace, secret, auth, account, transfer, notification, frontend, ingress.

---

## Tóm tắt thứ tự thực hiện

1. Xóa `banking-demo` (tránh SharedResource + SyncError)
2. Apply per-service Applications
3. **Patch Secret** với Redis password (tránh 503)
4. Sync Applications
5. Restart deployments (đọc Secret mới)

---

## Lợi ích

- Mỗi service quản lý độc lập trong ArgoCD
- Đổi image auth-service → chỉ `banking-demo-auth-service` sync
- Ingress backend trỏ Kong mới (ns kong) cross-namespace

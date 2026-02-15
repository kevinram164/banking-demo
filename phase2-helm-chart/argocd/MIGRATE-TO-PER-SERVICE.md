# Chuyển sang Per-Service Applications

Dùng các Application riêng trong `applications/` để **tránh restart postgres/redis và services khác** khi chỉ đổi Kong hoặc 1 service.

---

## Migration (từ Application đơn `banking-demo`)

### Bước 1: Xóa Application đơn

```bash
kubectl delete application banking-demo -n argocd
```

Resources trong cluster **không bị xóa** (ArgoCD orphan mặc định). Các per-service Applications sẽ adopt lại.

### Bước 2: Apply per-service Applications

```bash
kubectl apply -f applications/ -n argocd
```

### Bước 3: Sync theo thứ tự (lần đầu)

```bash
# 1. Namespace + Secret
argocd app sync banking-demo-namespace

# 2. Infra (postgres, redis)
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis

# 3. Kong
argocd app sync banking-demo-kong

# 4. App services
argocd app sync banking-demo-auth-service
argocd app sync banking-demo-account-service
argocd app sync banking-demo-transfer-service
argocd app sync banking-demo-notification-service

# 5. Frontend + Ingress
argocd app sync banking-demo-frontend
argocd app sync banking-demo-ingress
```

Hoặc sync tất cả cùng lúc — ArgoCD dùng sync waves để deploy đúng thứ tự.

---

## Sync policy

| Application | selfHeal | Ghi chú |
|-------------|----------|---------|
| **namespace, postgres, redis** | `false` | Sync thủ công — tránh restart DB |
| **kong, auth, account, transfer, notification, frontend, ingress** | `true` | Auto sync — đổi Kong chỉ rollout Kong |

---

## Lợi ích

- Commit Kong config → chỉ `banking-demo-kong` sync → không động postgres/redis/services khác
- Bump image auth-service → chỉ `banking-demo-auth-service` sync
- Mỗi service quản lý độc lập trong ArgoCD UI

# Chuyển sang Per-Service Applications (Phase 5)

Mỗi service một Application riêng. **Postgres, Redis, Kong** đã tách sang Phase 5 (ns riêng) — không deploy qua banking-demo.

---

## Migration (từ Application đơn `banking-demo`)

### Bước 1: Xóa Application đơn (nếu đang dùng)

```bash
kubectl delete application banking-demo -n argocd
```

### Bước 2: Apply per-service Applications

```bash
kubectl apply -f applications/ -n argocd
```

### Bước 3: Sync theo thứ tự (lần đầu)

```bash
argocd app sync banking-demo-namespace
argocd app sync banking-demo-auth-service
argocd app sync banking-demo-account-service
argocd app sync banking-demo-transfer-service
argocd app sync banking-demo-notification-service
argocd app sync banking-demo-frontend
argocd app sync banking-demo-ingress
```

---

## Phase 5: Không còn postgres, redis, kong Applications

- **Postgres**: Deploy bằng `phase5-architecture-refactor/postgres-ha/` (Helm riêng)
- **Redis**: Deploy bằng `phase5-architecture-refactor/redis-ha/` (Helm riêng)
- **Kong**: Deploy bằng `phase5-architecture-refactor/kong-ha/` (Helm riêng)

Chart banking-demo chỉ deploy: namespace, secret, auth, account, transfer, notification, frontend, ingress.

---

## Lợi ích

- Mỗi service quản lý độc lập trong ArgoCD
- Đổi image auth-service → chỉ `banking-demo-auth-service` sync
- Ingress backend trỏ Kong mới (ns kong) cross-namespace

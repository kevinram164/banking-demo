# Cleanup Phase 2 - Xóa các file không cần thiết

## Vấn đề hiện tại

1. Namespace "banking" cứ tạo ra là mất
2. Application không deploy được
3. Có nhiều file gây conflict

## Các file cần XÓA

### 1. `application.yaml` ❌
- **Lý do:** Application deploy tất cả services cùng lúc, conflict với per-service Applications
- **Thay thế:** Đã có per-service Applications trong `applications/`

### 2. `application-set.yaml` ❌
- **Lý do:** ApplicationSet cũ cho multi-env, có `prune: true` và `selfHeal: true` → có thể xóa namespace
- **Thay thế:** Không cần vì đã có per-service Applications

### 3. `application-set-all-services.yaml` ⚠️ (Tùy chọn)
- **Lý do:** ApplicationSet mới, có thể dùng nhưng không bắt buộc
- **Quyết định:** Có thể giữ để tự động tạo Applications, hoặc xóa nếu muốn quản lý thủ công

## Các file CẦN GIỮ

### Core files:
- ✅ `project.yaml` - ArgoCD Project (bắt buộc)
- ✅ `ARGOCD.md` - Documentation

### Per-service Applications:
- ✅ `applications/namespace.yaml` - Tạo namespace và secret (wave -1)
- ✅ `applications/postgres.yaml` - PostgreSQL (wave 0)
- ✅ `applications/redis.yaml` - Redis (wave 0)
- ✅ `applications/kong.yaml` - Kong API Gateway (wave 1)
- ✅ `applications/auth-service.yaml` - Auth Service (wave 2)
- ✅ `applications/account-service.yaml` - Account Service (wave 2)
- ✅ `applications/transfer-service.yaml` - Transfer Service (wave 2)
- ✅ `applications/notification-service.yaml` - Notification Service (wave 2)
- ✅ `applications/frontend.yaml` - Frontend (wave 3)
- ✅ `applications/ingress.yaml` - Ingress (wave 4)

### Scripts (hữu ích):
- ✅ `deploy-all.sh` / `deploy-all.ps1` - Deploy tất cả Applications
- ✅ `fix-namespace-pending-deletion.sh` / `.ps1` - Fix namespace pending deletion
- ✅ `fix-secret-finalizers.sh` / `.ps1` - Fix secret finalizers
- ✅ `check-postgres-redis-resources.sh` / `.ps1` - Kiểm tra resources
- ✅ `delete-application-large-payload.sh` / `.ps1` - Xóa Application payload lớn

### Documentation:
- ✅ `fix-postgres-redis-no-resources.md` - Troubleshooting guide

## Lệnh cleanup

```bash
cd phase2-helm-chart/argocd

# Xóa các file không cần thiết
rm -f application.yaml
rm -f application-set.yaml
# rm -f application-set-all-services.yaml  # Tùy chọn

# Xóa Application banking-demo nếu đã apply
kubectl delete application banking-demo -n argocd --cascade=false 2>/dev/null || true

# Xóa ApplicationSet cũ nếu đã apply
kubectl delete applicationset banking-demo-envs -n argocd 2>/dev/null || true
```

## Sau khi cleanup

1. **Deploy lại với per-service Applications:**
   ```bash
   kubectl apply -f project.yaml -n argocd
   kubectl apply -f applications/ -n argocd
   ```

2. **Sync theo thứ tự:**
   ```bash
   argocd app sync banking-demo-namespace
   argocd app sync banking-demo-postgres
   argocd app sync banking-demo-redis
   # ... tiếp tục với các services khác
   ```

3. **Hoặc sync tất cả cùng lúc (ArgoCD sẽ tự động deploy theo sync waves):**
   ```bash
   argocd app sync -l app.kubernetes.io/name=banking-demo
   ```

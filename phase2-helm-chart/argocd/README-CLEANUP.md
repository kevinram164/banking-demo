# ✅ Cleanup Phase 2 - Đã hoàn tất

## Các file đã XÓA

1. ✅ `application.yaml` - Application deploy tất cả services cùng lúc → **ĐÃ XÓA**
   - **Lý do:** Conflict với per-service Applications
   - **Thay thế:** Dùng per-service Applications trong `applications/`

2. ✅ `application-set.yaml` - ApplicationSet cũ cho multi-env → **ĐÃ XÓA**
   - **Lý do:** Có `prune: true` và `selfHeal: true` → có thể xóa namespace
   - **Thay thế:** Không cần vì đã có per-service Applications

## Các file CẦN GIỮ

### Core files:
- ✅ `project.yaml` - ArgoCD Project (bắt buộc)
- ✅ `ARGOCD.md` - Documentation chính

### Per-service Applications (trong `applications/`):
- ✅ `namespace.yaml` - Tạo namespace và secret (wave -1)
- ✅ `postgres.yaml` - PostgreSQL (wave 0)
- ✅ `redis.yaml` - Redis (wave 0)
- ✅ `kong.yaml` - Kong API Gateway (wave 1)
- ✅ `auth-service.yaml` - Auth Service (wave 2)
- ✅ `account-service.yaml` - Account Service (wave 2)
- ✅ `transfer-service.yaml` - Transfer Service (wave 2)
- ✅ `notification-service.yaml` - Notification Service (wave 2)
- ✅ `frontend.yaml` - Frontend (wave 3)
- ✅ `ingress.yaml` - Ingress (wave 4)

### Scripts hỗ trợ:
- ✅ `cleanup-and-fix.sh` / `.ps1` - Cleanup và fix toàn bộ phase 2
- ✅ `deploy-all.sh` / `.ps1` - Deploy tất cả Applications
- ✅ `fix-namespace-pending-deletion.sh` / `.ps1` - Fix namespace pending deletion
- ✅ `fix-secret-finalizers.sh` / `.ps1` - Fix secret finalizers
- ✅ `check-postgres-redis-resources.sh` / `.ps1` - Kiểm tra resources
- ✅ `delete-application-large-payload.sh` / `.ps1` - Xóa Application payload lớn

### Tùy chọn:
- ⚠️ `application-set-all-services.yaml` - ApplicationSet tự động tạo Applications (có thể giữ hoặc xóa)

## Các thay đổi quan trọng

### 1. Namespace template - Bỏ Helm hooks
**File:** `banking-demo/templates/namespace.yaml`
- **Đã bỏ:** Helm hooks `pre-install,pre-upgrade`
- **Lý do:** Helm hooks có thể gây conflict với ArgoCD `CreateNamespace=true`
- **Kết quả:** Namespace chỉ được tạo bởi ArgoCD, không bị xóa khi Helm upgrade

### 2. Chỉ `namespace.yaml` tạo namespace
- **Chỉ Application `banking-demo-namespace`** có `CreateNamespace=true`
- **Tất cả Applications khác** đã bỏ `CreateNamespace=true`
- **Kết quả:** Không còn conflict khi nhiều Applications cùng tạo namespace

## Cách deploy sau cleanup

### Cách 1: Dùng script cleanup tự động (khuyến nghị)

```bash
# Linux/Mac
chmod +x cleanup-and-fix.sh
./cleanup-and-fix.sh

# Windows PowerShell
.\cleanup-and-fix.ps1
```

### Cách 2: Deploy thủ công

```bash
# Bước 1: Xóa Application cũ (nếu có)
kubectl delete application banking-demo -n argocd --cascade=false 2>/dev/null || true

# Bước 2: Xóa namespace stuck (nếu có)
kubectl delete namespace banking --force --grace-period=0 2>/dev/null || true

# Bước 3: Deploy Project
kubectl apply -f project.yaml -n argocd

# Bước 4: Deploy Applications
kubectl apply -f applications/ -n argocd

# Bước 5: Sync tất cả (ArgoCD sẽ tự động deploy theo sync waves)
argocd app sync -l app.kubernetes.io/name=banking-demo
```

## Kiểm tra sau khi deploy

```bash
# Kiểm tra Applications
kubectl get applications -n argocd -l app.kubernetes.io/name=banking-demo

# Kiểm tra namespace
kubectl get namespace banking

# Kiểm tra pods
kubectl get pods -n banking

# Kiểm tra không còn conflict
# Vào ArgoCD UI → Application conditions → không còn SharedResourceWarning
```

## Troubleshooting

Nếu namespace vẫn cứ tạo ra là mất:

1. **Kiểm tra Application cũ còn tồn tại không:**
   ```bash
   kubectl get applications -n argocd | grep banking-demo
   ```

2. **Xóa tất cả Applications cũ:**
   ```bash
   kubectl delete applications -n argocd -l app.kubernetes.io/name=banking-demo --cascade=false
   ```

3. **Xóa namespace và deploy lại:**
   ```bash
   ./cleanup-and-fix.sh
   ```

## Lưu ý quan trọng

- ✅ **Chỉ `namespace.yaml`** tạo namespace và secret
- ✅ **Tất cả Applications khác** không tạo namespace/secret
- ✅ **Không có Application nào** có `prune: true` hoặc `selfHeal: true`
- ✅ **Namespace template** không có Helm hooks để tránh conflict

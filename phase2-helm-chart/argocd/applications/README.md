# Deploy riêng từng service — mỗi service một Application riêng

Thư mục này chứa các Application riêng cho từng service để dễ quản lý trong ArgoCD dashboard.

## Cấu trúc

Mỗi service có một file Application riêng:
- `infra.yaml` - Infrastructure: namespace, secret, postgres, redis
- `kong.yaml` - Kong API Gateway
- `auth-service.yaml` - Auth Service
- `account-service.yaml` - Account Service
- `transfer-service.yaml` - Transfer Service
- `notification-service.yaml` - Notification Service
- `frontend.yaml` - Frontend (React)
- `ingress.yaml` - Ingress (HAProxy)

## Cách deploy

**Thứ tự deploy đề xuất:**
1. `infra.yaml` (namespace, secret, postgres, redis)
2. `kong.yaml` (API Gateway)
3. `auth-service.yaml`
4. `account-service.yaml`
5. `transfer-service.yaml`
6. `notification-service.yaml`
7. `frontend.yaml`
8. `ingress.yaml`

**Áp dụng tất cả:**
```bash
kubectl apply -f applications/ -n argocd
```

**Hoặc từng cái:**
```bash
kubectl apply -f applications/infra.yaml -n argocd
kubectl apply -f applications/kong.yaml -n argocd
# ... tiếp tục với các service khác
```

## Sync policy

Tất cả Application đều có:
- `automated.prune: false` - Không tự động xóa resources
- `automated.selfHeal: false` - Không tự động sửa drift
- Sync thủ công qua UI hoặc CLI: `argocd app sync <app-name>`

Điều này tránh việc tự động xóa/tạo lại khi push commit mới.

## Quản lý

Mỗi service sẽ xuất hiện như một Application riêng trong ArgoCD dashboard, giúp:
- Dễ theo dõi status từng service
- Sync/rollback riêng từng service
- Quản lý độc lập không ảnh hưởng service khác

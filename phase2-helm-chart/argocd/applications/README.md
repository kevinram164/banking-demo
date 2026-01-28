# Deploy riêng từng service — mỗi service một Application riêng

Thư mục này chứa các Application riêng cho từng service để dễ quản lý trong ArgoCD dashboard.

## Cấu trúc

Mỗi service có một file Application riêng:
- `namespace.yaml` - Namespace và Secret (deploy đầu tiên nhất)
- `postgres.yaml` - PostgreSQL Database
- `redis.yaml` - Redis Cache
- `kong.yaml` - Kong API Gateway
- `auth-service.yaml` - Auth Service
- `account-service.yaml` - Account Service
- `transfer-service.yaml` - Transfer Service
- `notification-service.yaml` - Notification Service
- `frontend.yaml` - Frontend (React)
- `ingress.yaml` - Ingress (HAProxy)

## Cách deploy

**Thứ tự deploy đề xuất:**
1. `namespace.yaml` (namespace và secret) - Wave -1
2. `postgres.yaml`, `redis.yaml` (infrastructure) - Wave 0
3. `kong.yaml` (API Gateway) - Wave 1
4. `auth-service.yaml`, `account-service.yaml`, `transfer-service.yaml`, `notification-service.yaml` (microservices) - Wave 2
5. `frontend.yaml` - Wave 3
6. `ingress.yaml` - Wave 4

**Lưu ý:** ArgoCD sẽ tự động deploy theo sync waves khi sync tất cả cùng lúc.

**Áp dụng tất cả:**
```bash
kubectl apply -f applications/ -n argocd
```

**Hoặc từng cái:**
```bash
kubectl apply -f applications/namespace.yaml -n argocd
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd
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

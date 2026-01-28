# Fix: Postgres và Redis không hiển thị resources trong ArgoCD

## Vấn đề

Application `banking-demo-postgres` và `banking-demo-redis` hiển thị "Healthy" và "Synced" trong ArgoCD nhưng không có Kubernetes resources (Pod, StatefulSet, Service) được tạo ra.

## Nguyên nhân

Có thể do:
1. ArgoCD không render Helm templates đúng cách
2. Values không được merge đúng giữa valueFiles và parameters
3. Application cần được hard refresh để reload templates

## Giải pháp

### Cách 1: Hard refresh và sync lại (thử trước)

```bash
# Hard refresh Application để reload templates
argocd app get banking-demo-postgres --refresh
argocd app get banking-demo-redis --refresh

# Sync lại
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis
```

### Cách 2: Kiểm tra rendered templates

```bash
# Xem templates được render như thế nào
argocd app manifests banking-demo-postgres

# Hoặc dùng helm template để test local
cd phase2-helm-chart/banking-demo
helm template test . \
  --values charts/common/values.yaml \
  --values charts/postgres/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set redis.enabled=false \
  --set kong.enabled=false \
  --set auth-service.enabled=false \
  --set account-service.enabled=false \
  --set transfer-service.enabled=false \
  --set notification-service.enabled=false \
  --set frontend.enabled=false \
  --set ingress.enabled=false
```

### Cách 3: Xóa và tạo lại Application

```bash
# Xóa Application cũ
kubectl delete application banking-demo-postgres -n argocd --cascade=false
kubectl delete application banking-demo-redis -n argocd --cascade=false

# Apply lại
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd

# Sync
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis
```

### Cách 4: Kiểm tra values được merge

Trong ArgoCD UI:
1. Vào Application `banking-demo-postgres`
2. Click tab **MANIFESTS** hoặc **PARAMETERS**
3. Kiểm tra xem `postgres.enabled` có được set đúng không

Hoặc qua CLI:
```bash
# Xem values được merge
argocd app get banking-demo-postgres -o yaml | grep -A 20 "helm:"
```

## Kiểm tra sau khi fix

```bash
# Kiểm tra pods
kubectl get pods -n banking | grep -E "postgres|redis"

# Kiểm tra statefulsets
kubectl get statefulsets -n banking

# Kiểm tra services
kubectl get services -n banking | grep -E "postgres|redis"
```

## Lưu ý

- Đảm bảo namespace "banking" đã được tạo trước (bởi `namespace.yaml`)
- Đảm bảo secret "banking-db-secret" đã được tạo trước (bởi `namespace.yaml`)
- StorageClass "nfs-client" phải tồn tại trong cluster

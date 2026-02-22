# Bật --allow-cross-namespace cho HAProxy Ingress

Ingress `banking-ingress` (ns banking) cần trỏ backend `/api`, `/ws` tới Kong (ns kong). HAProxy Ingress mặc định **không cho phép** backend cross-namespace → lỗi `services "kong-kong-proxy" not found` hoặc 502.

## Cách sửa

### 1. Tìm HAProxy Ingress deployment

```bash
kubectl get deployment -A | grep -i haproxy
# hoặc
kubectl get pods -A | grep -i haproxy
```

### 2. Sửa deployment, thêm args

```bash
kubectl edit deployment -n <namespace> <haproxy-deployment-name>
```

Trong `spec.template.spec.containers[0]`, thêm hoặc sửa `args`:

```yaml
containers:
  - name: controller
    args:
      - --allow-cross-namespace=true
      # ... các args khác nếu có
```

**Nếu dùng Helm** (haproxy-ingress chart):

```bash
helm upgrade haproxy-ingress haproxy-ingress/haproxy-ingress -n <namespace> \
  --set controller.extraArgs[0]=--allow-cross-namespace=true
```

### 3. Đảm bảo values dùng cross-namespace

Trong `charts/common/values.yaml`:

```yaml
ingress:
  kongExternalService: false
  paths:
    - path: /api
      serviceName: kong-kong-proxy
      serviceNamespace: kong
      servicePort: 8000
```

### 4. Sync Ingress

```bash
argocd app sync banking-demo-ingress
# hoặc
kubectl delete svc kong-proxy -n banking  # Xóa ExternalName nếu không dùng
```

### 5. Kiểm tra

```bash
kubectl describe ingress -n banking banking-ingress
# Backends /api, /ws phải hiển thị kong-kong-proxy:8000 (không còn "not found")

curl -X POST http://npd-banking.co/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"Test123456"}'
```

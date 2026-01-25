# Deploy Banking Demo lên Kubernetes

Hướng dẫn deploy ứng dụng banking-demo (đã chạy Docker Compose) lên Kubernetes.

## Cấu trúc thư mục `k8s/`

| File | Mô tả |
|------|--------|
| `namespace.yaml` | Namespace `banking` |
| `secret.yaml` | Secret cho DB (user, password, `DATABASE_URL`, `REDIS_URL`) |
| `postgres.yaml` | PVC, Deployment, Service PostgreSQL |
| `redis.yaml` | Deployment, Service Redis |
| `kong-configmap.yaml` | ConfigMap chứa `kong.yml` |
| `kong.yaml` | Deployment, Service Kong API Gateway |
| `auth-service.yaml` | Deployment, Service Auth |
| `account-service.yaml` | Deployment, Service Account |
| `transfer-service.yaml` | Deployment, Service Transfer |
| `notification-service.yaml` | Deployment, Service Notification |
| `frontend.yaml` | Deployment, Service Frontend (React + nginx) |
| `ingress.yaml` | Ingress (theo host, ví dụ `banking.local`) |
| `ingress-minikube.yaml` | Ingress không host (phù hợp Minikube) |

## Yêu cầu

- `kubectl` đã cài và trỏ tới cluster (Minikube, Kind, hoặc cluster thật).
- Ingress Controller (ví dụ **nginx-ingress**) nếu dùng Ingress.
- Đã build và có sẵn image cho các service (xem bước 1–2).

---

## Bước 1: Build image (từ thư mục gốc project)

Build từ **context gốc** (`banking-demo/`) vì các Dockerfile cần thư mục `common/`:

```bash
cd banking-demo

# Auth
docker build -t banking-demo/auth-service:latest -f services/auth-service/Dockerfile .

# Account
docker build -t banking-demo/account-service:latest -f services/account-service/Dockerfile .

# Transfer
docker build -t banking-demo/transfer-service:latest -f services/transfer-service/Dockerfile .

# Notification
docker build -t banking-demo/notification-service:latest -f services/notification-service/Dockerfile .

# Frontend
docker build -t banking-demo/frontend:latest ./frontend
```

---

## Bước 2: Đưa image vào cluster

### Cách A: Minikube (dùng Docker của Minikube)

```bash
eval $(minikube docker-env)
# Rồi chạy lại toàn bộ lệnh build ở Bước 1 trong cùng shell
```

### Cách B: Kind

```bash
# Sau khi build xong (Bước 1), load vào kind
kind load docker-image banking-demo/auth-service:latest --name <tên-cluster>
kind load docker-image banking-demo/account-service:latest --name <tên-cluster>
kind load docker-image banking-demo/transfer-service:latest --name <tên-cluster>
kind load docker-image banking-demo/notification-service:latest --name <tên-cluster>
kind load docker-image banking-demo/frontend:latest --name <tên-cluster>
```

### Cách C: Cluster thật / registry

Push image lên registry rồi trong từng file Deployment đổi:

- `image: banking-demo/auth-service:latest` → `image: <registry>/banking-demo/auth-service:latest`
- Đặt `imagePullPolicy: Always` (hoặc bỏ, mặc định là Always khi tag là `latest`).
- Tạo Secret `kubernetes.io/dockerconfigjson` nếu registry private.

---

## Bước 3: Apply manifests (đúng thứ tự)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# Đợi Postgres sẵn sàng (tuỳ chọn)
kubectl -n banking wait --for=condition=ready pod -l app=postgres --timeout=120s

kubectl apply -f k8s/kong-configmap.yaml
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/account-service.yaml
kubectl apply -f k8s/transfer-service.yaml
kubectl apply -f k8s/notification-service.yaml
kubectl apply -f k8s/kong.yaml
kubectl apply -f k8s/frontend.yaml
```

Apply tất cả một lần (nếu đã có đủ file):

```bash
kubectl apply -f k8s/
```

---

## Bước 4: Expose ra ngoài (chọn một)

### Option 1: Ingress (nên dùng)

- **Minikube (không dùng host):**  
  ```bash
  minikube addons enable ingress
  kubectl apply -f k8s/ingress-minikube.yaml
  ```
  Truy cập: `http://<minikube-ip>` (xem IP: `minikube ip`).  
  Có thể cần thêm host: `echo "$(minikube ip) banking.local" | sudo tee -a /etc/hosts` rồi dùng `ingress.yaml` với host `banking.local` nếu bạn đổi sang dùng file đó.

- **Cluster có Ingress (ví dụ nginx-ingress):**  
  ```bash
  kubectl apply -f k8s/ingress.yaml
  ```
  Thêm DNS hoặc `/etc/hosts`: `banking.local` → IP Ingress.  
  Mở app: `http://banking.local`.

### Option 2: NodePort (không cần Ingress)

```bash
kubectl -n banking patch svc frontend -p '{"spec":{"type":"NodePort"}}'
kubectl -n banking get svc frontend
# Truy cập: http://<node-ip>:<nodeport>
```

Lưu ý: Frontend gọi API qua relative path (`/api/`, `/ws`). Nếu user vào bằng `http://<node-ip>:30080` thì API cũng phải trên cùng host/port; trong setup hiện tại **frontend nginx proxy `/api` và `/ws` tới Kong**, nên user chỉ cần mở **một URL** (frontend). Nếu bạn expose riêng Kong bằng NodePort thì frontend vẫn proxy tới `kong:8000` **trong cluster**, không ảnh hưởng URL trên trình duyệt.

### Option 3: Port-forward (chỉ để test nhanh)

```bash
kubectl -n banking port-forward svc/frontend 3000:80
# Mở http://localhost:3000
```

---

## CORS khi deploy K8s

Trong Kong (ConfigMap `kong-config`) đang cấu hình CORS origin `http://localhost:3000`. Nếu bạn truy cập app qua URL khác (ví dụ `http://banking.local` hoặc `http://<minikube-ip>`), cần thêm origin đó vào ConfigMap `k8s/kong-configmap.yaml` (phần `origins` của từng service), rồi:

```bash
kubectl apply -f k8s/kong-configmap.yaml
kubectl -n banking rollout restart deployment/kong
```

---

## Kiểm tra

```bash
kubectl -n banking get pods
kubectl -n banking get svc
kubectl -n banking logs -l app=auth-service --tail=50
```

---

## Xoá deployment

```bash
kubectl delete -f k8s/
# Hoặc xoá namespace (sẽ xoá toàn bộ tài nguyên trong namespace banking)
kubectl delete namespace banking
```

---

## Tóm tắt luồng request trên K8s

1. User mở **Frontend** (qua Ingress/NodePort/port-forward).
2. Frontend (nginx) proxy `/api/*` và `/ws` tới **Kong** (Service `kong:8000` trong namespace `banking`).
3. Kong định tuyến theo path tới **auth-service**, **account-service**, **transfer-service**, **notification-service** (các Service tương ứng).
4. Các service kết nối **PostgreSQL** (`postgres:5432`) và **Redis** (`redis:6379`) trong cùng namespace.

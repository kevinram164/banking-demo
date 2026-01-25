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

Build từ **context gốc** (`banking-demo/`) vì các Dockerfile cần thư mục `common/`.

**Dùng GitLab Registry (khuyến nghị khi deploy K8s cluster thật):** xem **[GITLAB_REGISTRY.md](GITLAB_REGISTRY.md)** — có script build + push từng service lên `registry.gitlab.com/kiettt164/banking-demo-payment/<service>:<tag>`.

**Build local (Minikube/Kind):**

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

### Cách C: GitLab Container Registry (cluster thật)

Image đã cấu hình sẵn cho **registry.gitlab.com/kiettt164/banking-demo-payment** (mỗi service một image). Xem chi tiết build/push trong **[GITLAB_REGISTRY.md](GITLAB_REGISTRY.md)**.

Sau khi push image lên GitLab, nếu repo **private** thì tạo Secret trong namespace `banking` trước khi apply:

```bash
kubectl create secret docker-registry gitlab-registry \
  --namespace=banking \
  --docker-server=registry.gitlab.com \
  --docker-username=<USERNAME> \
  --docker-password=<TOKEN>
```

Nếu repo **public** và không dùng secret: xóa đoạn `imagePullSecrets` trong từng file Deployment (auth-service, account-service, transfer-service, notification-service, frontend).

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

## Bước 4: Expose ra ngoài qua Ingress

Dùng **một Ingress** cho app (banking) và **một Ingress** cho monitoring (Grafana, Jaeger, Prometheus). Cả web app và các UI monitoring đều truy cập qua Ingress.

### Bật Ingress (Minikube)

```bash
minikube addons enable ingress
```

### Apply Ingress

**App (frontend + API):**
```bash
# Có host (banking.local)
kubectl apply -f k8s/ingress.yaml

# Hoặc Minikube không host: dùng IP trực tiếp
kubectl apply -f k8s/ingress-minikube.yaml
```

**Monitoring (Grafana, Jaeger, Prometheus):**
```bash
kubectl apply -f k8s/monitoring/ingress.yaml
```

### Trỏ host về Ingress

Thêm vào **/etc/hosts** (Linux/macOS) hoặc **C:\Windows\System32\drivers\etc\hosts** (Windows). Thay `<INGRESS_IP>` bằng IP Ingress (Minikube: `minikube ip`):

```
<INGRESS_IP> banking.local grafana.banking.local jaeger.banking.local prometheus.banking.local
```

Ví dụ Minikube:
```bash
echo "$(minikube ip) banking.local grafana.banking.local jaeger.banking.local prometheus.banking.local" | sudo tee -a /etc/hosts
```

### Truy cập (đều qua Ingress)

| Mục đích    | URL |
|------------|-----|
| Web app    | http://banking.local |
| Grafana    | http://grafana.banking.local (admin / admin) |
| Jaeger     | http://jaeger.banking.local |
| Prometheus | http://prometheus.banking.local |

Nếu dùng **ingress-minikube** (không host) thì chỉ có app qua `http://<minikube-ip>`; Grafana/Jaeger/Prometheus vẫn dùng host như trên (cần thêm 3 host vào /etc/hosts trỏ về cùng IP).

### NodePort / port-forward (tuỳ chọn)

Nếu không dùng Ingress: NodePort cho frontend hoặc `kubectl port-forward svc/frontend 3000:80` (chỉ test nhanh).

---

## CORS khi deploy K8s

Trong Kong (ConfigMap `kong-config`) đang cấu hình CORS origin `http://localhost:3000`. Nếu bạn truy cập app qua URL khác (ví dụ `http://banking.local` hoặc `http://<minikube-ip>`), cần thêm origin đó vào ConfigMap `k8s/kong-configmap.yaml` (phần `origins` của từng service), rồi:

```bash
kubectl apply -f k8s/kong-configmap.yaml
kubectl -n banking rollout restart deployment/kong
```

---

## Resources và Security

Tất cả Deployment đã cấu hình **resources** (requests/limits) và **securityContext**:

**Resources (demo):**

| Thành phần | Requests | Limits |
|------------|----------|--------|
| postgres | 256Mi, 100m CPU | 512Mi, 500m |
| redis | 64Mi, 50m | 128Mi, 200m |
| kong | 128Mi, 100m | 256Mi, 300m |
| auth/account/transfer/notification | 128Mi, 100m | 256Mi, 300m |
| frontend | 64Mi, 50m | 128Mi, 200m |
| prometheus/grafana/jaeger/otel-collector | 128Mi, 50–100m | 256–512Mi, 200–500m |

**Security (pod + container):**

- **Pod:** `seccompProfile: type: RuntimeDefault`
- **Container:** `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`

Có thể chỉnh `resources` trong từng file Deployment khi cần tăng/giảm tải. Nếu cluster bật **Pod Security Admission** (restricted), có thể cần chỉnh thêm (ví dụ `runAsNonRoot`, `runAsUser`) tùy image.

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

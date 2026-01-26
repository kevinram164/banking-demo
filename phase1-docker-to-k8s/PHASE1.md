# Giai đoạn 1: Migrate Docker sang Kubernetes

Giai đoạn 1 tập trung **chuyển toàn bộ stack từ Docker Compose sang Kubernetes** với manifest files trong folder này. Các giai đoạn sau (monitoring, CI/CD, v.v.) sẽ có folder và tài liệu riêng để không lẫn lộn.

- **Sơ đồ kiến trúc:** xem [ARCHITECTURE.md](./ARCHITECTURE.md) (luồng traffic, thành phần, Mermaid diagram).

---

## Mục tiêu

- **Postgres**, **Redis**: chạy dưới **StatefulSet** (database/cache có state, cần identity và storage ổn định).
- **Kong**: API Gateway (Deployment + ConfigMap).
- **Các service ứng dụng**: auth-service, account-service, transfer-service, notification-service (Deployment + Service).
- **Frontend**: Deployment + Service.
- **Ingress**: path-based qua **HAProxy Ingress** (cluster đã cài HAProxy Ingress).
- **Storage**: PVC dùng **StorageClass `nfs-client`** (NFS server + NFS subdir provisioner).

---

## Cấu trúc manifest trong folder này

| File | Mô tả |
|------|--------|
| `namespace.yaml` | Namespace `banking` |
| `secret.yaml` | Secret DB (Postgres user/pass, DATABASE_URL, REDIS_URL) |
| `postgres.yaml` | **StatefulSet** + Headless Service (volumeClaimTemplate cho `/var/lib/postgresql/data`) |
| `redis.yaml` | **StatefulSet** + Headless Service (volumeClaimTemplate cho `/data`) |
| `kong-configmap.yaml` | Config Kong (routes `/api/auth`, `/api/account`, `/api/transfer`, `/api/notifications`, `/ws`) |
| `kong.yaml` | Deployment Kong (proxy 8000, admin 8001) |
| `kong-service.yaml` | Service Kong |
| `auth-service.yaml` | Deployment + Service auth-service (8001) |
| `account-service.yaml` | Deployment + Service account-service (8002) |
| `transfer-service.yaml` | Deployment + Service transfer-service (8003) |
| `notification-service.yaml` | Deployment + Service notification-service (8004) |
| `frontend.yaml` | Deployment + Service frontend (80) |
| `ingress.yaml` | Ingress HAProxy (/) → frontend, (/api, /ws) → kong |

---

## Thứ tự triển khai (kubectl apply)

Áp dụng đúng thứ tự để đảm bảo dependency (DB/Redis trước, sau đó Kong, rồi các service, cuối cùng Ingress).

```bash
# 1. Namespace + Secret
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml

# 2. Database & cache (StatefulSet)
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml

# Đợi Postgres và Redis ready (tùy cluster)
kubectl -n banking rollout status statefulset/postgres
kubectl -n banking rollout status statefulset/redis

# 3. Kong (cần ConfigMap trước)
kubectl apply -f kong-configmap.yaml
kubectl apply -f kong.yaml -f kong-service.yaml

# 4. Ứng dụng
kubectl apply -f auth-service.yaml
kubectl apply -f account-service.yaml
kubectl apply -f transfer-service.yaml
kubectl apply -f notification-service.yaml
kubectl apply -f frontend.yaml

# 5. Ingress (cluster đã có HAProxy Ingress)
kubectl apply -f ingress.yaml
```

**Một lệnh (áp dụng toàn bộ folder):**

```bash
kubectl apply -f namespace.yaml -f secret.yaml
kubectl apply -f postgres.yaml -f redis.yaml
kubectl apply -f kong-configmap.yaml -f kong.yaml -f kong-service.yaml
kubectl apply -f auth-service.yaml -f account-service.yaml -f transfer-service.yaml -f notification-service.yaml -f frontend.yaml
kubectl apply -f ingress.yaml
```

---

## Lưu ý

### StatefulSet cho Postgres và Redis

- **Postgres**: `volumeClaimTemplates` tạo PVC `pgdata-postgres-0`, mount tại `/var/lib/postgresql/data`. Pod có tên cố định `postgres-0`, Service headless `postgres` (clusterIP: None). **StorageClass: `nfs-client`** (NFS subdir provisioner).
- **Redis**: `volumeClaimTemplates` tạo PVC `redis-data-redis-0` (256Mi), mount tại `/data` cho RDB/AOF nếu cần. Service headless `redis`. **StorageClass: `nfs-client`**.

### Storage (NFS)

- Cluster dùng **NFS server** và **NFS subdir provisioner**, StorageClass tên **`nfs-client`**. Các PVC của Postgres và Redis đều chỉ định `storageClassName: nfs-client` để lưu trên NFS.

### Image và Registry

- Các manifest mặc định dùng **image từ GitLab Registry** và **imagePullSecrets: gitlab-registry**. Cần tạo Secret `gitlab-registry` trong namespace `banking` nếu dùng registry riêng:

  ```bash
  kubectl -n banking create secret docker-registry gitlab-registry \
    --docker-server=registry.gitlab.com \
    --docker-username=<user> \
    --docker-password=<token>
  ```

- **Docker Hub rate limit (429 / ImagePullBackOff):** Image **postgres**, **redis**, **kong** lấy từ Docker Hub. Nếu cluster bị giới hạn pull (lỗi `429 Too Many Requests` / `toomanyrequests`), cần tạo secret đăng nhập Docker Hub và khai báo `imagePullSecrets` để tăng rate limit:

  ```bash
  kubectl -n banking create secret docker-registry dockerhub-registry \
    --docker-server=https://index.docker.io/v1/ \
    --docker-username=kiettran164 \
    --docker-password=Tech@1604
  ```

  Các file `postgres.yaml`, `redis.yaml`, `kong.yaml` đã khai báo `imagePullSecrets: - name: dockerhub-registry`. Sau khi tạo secret, xóa pod để kéo image lại (ví dụ: `kubectl delete pod redis-0 postgres-0 -n banking`, redeploy kong nếu cần).

- **Chạy với image build tại chỗ:** sửa manifest: xóa `imagePullSecrets`, đặt `imagePullPolicy: Never` và `image: <tên-image-local>`.

### Ingress (HAProxy)

- Cluster đã cài **HAProxy Ingress**. Ingress dùng `ingressClassName: haproxy`, path-based: `/` → frontend, `/api` và `/ws` → Kong. Truy cập qua host/IP do HAProxy Ingress cấu hình (ví dụ LoadBalancer IP hoặc hostname).

### Giai đoạn sau

- Giai đoạn 1 **không** gồm monitoring (Prometheus, Grafana, Jaeger, Otel). Các file trong `k8s/monitoring/` và biến OTEL trong service thuộc giai đoạn sau. Folder `k8s/` ở root có thể dùng cho giai đoạn chung hoặc tham chiếu; mọi thứ cần cho **chỉ migration Docker → K8s** nằm trong folder **phase1-docker-to-k8s** và file **PHASE1.md** này.

---

## So sánh nhanh với Docker Compose

| Docker Compose | Giai đoạn 1 (K8s) |
|----------------|-------------------|
| `postgres` (volume pgdata) | StatefulSet `postgres` + volumeClaimTemplate |
| `redis` | StatefulSet `redis` + volumeClaimTemplate |
| `kong` + volume kong.yml | Deployment Kong + ConfigMap `kong-config` |
| `auth-service`, `account-service`, … | Deployment + Service từng service |
| `frontend` | Deployment + Service frontend |
| Port mapping local | Ingress (path /, /api, /ws) |

Sau khi apply xong, ứng dụng banking có thể dùng qua Ingress tương đương cách dùng qua Docker Compose (frontend + API qua Kong).

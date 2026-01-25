# Push image lên GitLab Container Registry

Repo registry: **registry.gitlab.com/kiettt164/banking-demo-payment**

Mỗi service được push thành **một image riêng** trong cùng project:

| Service              | Image đầy đủ                                                       |
|----------------------|--------------------------------------------------------------------|
| auth-service         | `registry.gitlab.com/kiettt164/banking-demo-payment/auth-service`  |
| account-service      | `registry.gitlab.com/kiettt164/banking-demo-payment/account-service` |
| transfer-service     | `registry.gitlab.com/kiettt164/banking-demo-payment/transfer-service` |
| notification-service | `registry.gitlab.com/kiettt164/banking-demo-payment/notification-service` |
| frontend             | `registry.gitlab.com/kiettt164/banking-demo-payment/frontend`    |

---

## 1. Đăng nhập GitLab Registry

- **Username:** GitLab username của bạn (hoặc `gitlab-ci-token` khi dùng trong CI).
- **Password:** Personal Access Token (Scope: `read_registry`, `write_registry`) hoặc Deploy Token.

```bash
docker login registry.gitlab.com
# Nhập username và token khi được hỏi
```

Tạo token: GitLab → Settings → Access Tokens (hoặc project Settings → Repository → Deploy tokens).

---

## 2. Build và push (mỗi service một image)

### Cách A: Script (khuyến nghị)

Từ **thư mục gốc** project (`banking-demo/`):

**Linux / macOS / Git Bash:**
```bash
chmod +x scripts/push-gitlab.sh
./scripts/push-gitlab.sh           # tag mặc định: latest
./scripts/push-gitlab.sh v1.0.0    # tag tùy chỉnh
```

**Windows PowerShell:**
```powershell
.\scripts\push-gitlab.ps1
.\scripts\push-gitlab.ps1 -Tag v1.0.0
```

### Cách B: Lệnh tay

Chạy ở thư mục gốc project. Thay `latest` bằng tag bạn muốn.

```bash
REGISTRY=registry.gitlab.com/kiettt164/banking-demo-payment
TAG=latest

docker build -t $REGISTRY/auth-service:$TAG -f services/auth-service/Dockerfile .
docker push $REGISTRY/auth-service:$TAG

docker build -t $REGISTRY/account-service:$TAG -f services/account-service/Dockerfile .
docker push $REGISTRY/account-service:$TAG

docker build -t $REGISTRY/transfer-service:$TAG -f services/transfer-service/Dockerfile .
docker push $REGISTRY/transfer-service:$TAG

docker build -t $REGISTRY/notification-service:$TAG -f services/notification-service/Dockerfile .
docker push $REGISTRY/notification-service:$TAG

docker build -t $REGISTRY/frontend:$TAG ./frontend
docker push $REGISTRY/frontend:$TAG
```

---

## 3. Kubernetes dùng image từ GitLab

Manifest trong `k8s/` đã dùng sẵn image GitLab, ví dụ:

- `registry.gitlab.com/kiettt164/banking-demo-payment/auth-service:latest`
- Tương tự cho account-service, transfer-service, notification-service, frontend.

Nếu **repo private**, cần tạo Secret để K8s kéo image:

```bash
kubectl create secret docker-registry gitlab-registry \
  --namespace=banking \
  --docker-server=registry.gitlab.com \
  --docker-username=<USERNAME> \
  --docker-password=<TOKEN>
```

Các Deployment đã khai báo `imagePullSecrets: - name: gitlab-registry`. Nếu repo **public** và không muốn dùng secret, xóa đoạn `imagePullSecrets` trong từng file deployment.

---

## 4. Tag khác `latest`

Nếu push với tag khác (ví dụ `v1.0.0`), chỉnh trong file K8s tương ứng, ví dụ:

```yaml
image: registry.gitlab.com/kiettt164/banking-demo-payment/auth-service:v1.0.0
```

Hoặc dùng Kustomize/Helm để set tag một lần cho tất cả.

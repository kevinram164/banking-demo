# Hướng dẫn k3d + WSL2 + Nginx LB + ArgoCD (domain)

Tài liệu tổng hợp các bước đã triển khai và **các lỗi đã fix** khi chạy GitOps lab trên:

- **Windows** + **WSL2 Ubuntu**
- **Docker Desktop**
- **k3d** cluster `npd`
- **Nginx** làm LB/reverse proxy trên WSL2
- **Traefik** (Ingress controller mặc định k3s/k3d)
- **ArgoCD** truy cập qua domain `argocd-npd.co`

---

## 1. Kiến trúc (Mô hình SSL 1 — khuyến nghị)

User vẫn dùng **HTTPS**; TLS terminate tại **Nginx**. Trong cluster dùng HTTP (đơn giản, ổn định trên k3d).

```text
Browser (Windows)
  │  https://argocd-npd.co
  ▼
Windows hosts → 127.0.0.1 hoặc IP WSL2
  ▼
Nginx (WSL2 :443, cert self-signed)
  │  HTTP + Host: argocd-npd.co
  ▼
k3d LoadBalancer 127.0.0.1:9080  (map 9080→Traefik:80)
  ▼
Traefik Ingress (host argocd-npd.co, không tls)
  ▼
argocd-server:80  (server.insecure=true)
```

| Tầng | SSL | Ghi chú |
|------|-----|---------|
| Browser ↔ Nginx | HTTPS | Cert `/home/kevin/argocd-self-signed/` |
| Nginx ↔ Traefik | HTTP | Port **9080**, không dùng 9443 với `proxy_pass http://` |
| Traefik ↔ ArgoCD | HTTP | Service port **80** |

---

## 2. Điều kiện tiên quyết

- WSL2 Ubuntu, RAM khuyến nghị 16–24 GB cho full stack
- Docker Desktop **Running**
- `kubectl`, `k3d`, `nginx` trên WSL2

```bash
# Kiểm tra
docker version
k3d version
kubectl version --client
nginx -v
```

---

## 3. Tạo cluster k3d (quan trọng — port map)

Cluster **phải** publish port HTTP/HTTPS ra host. Nếu thiếu, Nginx không vào được Traefik.

```bash
k3d cluster create npd \
  --agents 5 \
  -p "9080:80@loadbalancer" \
  -p "9443:443@loadbalancer"
```

Kiểm tra sau khi tạo:

```bash
k3d cluster list
docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep serverlb
```

Kỳ vọng:

```text
k3d-npd-serverlb   0.0.0.0:9080->80/tcp, 0.0.0.0:9443->443/tcp, ...
```

> **Lỗi đã gặp:** Chỉ map `6443` → mọi `curl 127.0.0.1:80` trúng **Nginx**, không phải Traefik → **502 Bad Gateway**.

---

## 4. kubectl không cần sudo

**Triệu chứng:** `kubectl get nodes` báo `localhost:8080 connection refused`, `sudo kubectl` mới chạy.

**Fix:**

```bash
mkdir -p ~/.kube
k3d kubeconfig merge npd --kubeconfig-merge-default
# hoặc
k3d kubeconfig get npd > ~/.kube/config
chmod 600 ~/.kube/config

kubectl get nodes
```

Thêm vào `~/.bashrc` (tùy chọn):

```bash
export KUBECONFIG="$HOME/.kube/config"
```

---

## 5. Cài ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.4/manifests/install.yaml

kubectl wait -n argocd --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server --timeout=300s
kubectl get pods -n argocd
```

### ApplicationSet controller lỗi CRD (tùy chọn)

Log: `no matches for kind "ApplicationSet"`.

- **Cách 1:** Scale 0 nếu không dùng ApplicationSet (App of Apps vẫn OK):

```bash
kubectl scale deployment argocd-applicationset-controller -n argocd --replicas=0
```

- **Cách 2:** Cài CRD bằng server-side apply (không dùng `kubectl apply -k` client-side):

```bash
curl -fsSL -o /tmp/applicationsets-crd.yaml \
  https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.4/manifests/crds/argoproj.io_applicationsets.yaml
kubectl apply --server-side --force-conflicts -f /tmp/applicationsets-crd.yaml
```

---

## 6. Cấu hình ArgoCD phía sau reverse proxy

```bash
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'

kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"url":"https://argocd-npd.co"}}'

kubectl rollout restart deployment argocd-server -n argocd
kubectl rollout status deployment argocd-server -n argocd
```

- `server.insecure`: ArgoCD nhận HTTP từ Traefik (user vẫn HTTPS ở Nginx).
- `url`: UI/CLI biết public URL.

---

## 7. Ingress Traefik cho ArgoCD

File mẫu: [`argocd-ingress.yaml`](./argocd-ingress.yaml)

```bash
kubectl apply -f phase9-gitops-platform/k3d/argocd-ingress.yaml
kubectl describe ingress argocd-npd -n argocd
```

Kỳ vọng:

```text
Rules:
  Host            Path  Backends
  argocd-npd.co   /     argocd-server:80
```

> **Lỗi đã gặp:**
> - Host `npd-argocd.co` ≠ browser `argocd-npd.co` → 502/404
> - Backend `:443` trong khi dùng mô hình 1 → nên dùng **:80**
> - Ingress `tls:` + Nginx SSL → trùng TLS, dễ lỗi (mô hình 1 **không** cần `tls` trên Ingress)

---

## 8. Nginx LB trên WSL2

Cài và bật:

```bash
sudo apt update && sudo apt install -y nginx
sudo systemctl enable nginx
```

File mẫu: [`nginx-argocd-npd.co.conf`](./nginx-argocd-npd.co.conf)

```bash
sudo cp phase9-gitops-platform/k3d/nginx-argocd-npd.co.conf /etc/nginx/conf.d/
sudo nginx -t && sudo systemctl reload nginx
```

### Cert self-signed (lab)

```bash
mkdir -p ~/argocd-self-signed
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/argocd-self-signed/tls.key \
  -out ~/argocd-self-signed/tls.crt \
  -subj "/CN=argocd-npd.co"
```

### Điểm quan trọng trong Nginx

| Cấu hình | Giá trị | Lý do |
|----------|---------|-------|
| `upstream` | `127.0.0.1:9080` | Map k3d HTTP → Traefik |
| **Không** dùng | `127.0.0.1:80` | Port 80 là **chính Nginx** → loop → 502 |
| **Không** dùng | `proxy_pass http://...:9443` | 9443 là HTTPS → 404 |
| `large_client_header_buffers` | `8 64k` | Fix **400 Header/Cookie Too Large** |
| `X-Forwarded-Proto` | `https` (block 443) | ArgoCD biết user dùng HTTPS |

---

## 9. Windows hosts

Sửa `C:\Windows\System32\drivers\etc\hosts` (**Run as Administrator**):

### Cách A — localhost (khuyến nghị nếu WSL forward port)

```text
127.0.0.1   argocd-npd.co
```

### Cách B — IP WSL2 (IP có thể đổi sau reboot)

```bash
# Trong WSL2
hostname -I | awk '{print $1}'
```

```text
172.31.0.59   argocd-npd.co
```

> **Lỗi đã gặp:** Ping/telnet `172.31.0.58` fail vì IP WSL thực tế là `.59`. SSH port 22 không cần mở cho truy cập web.

---

## 10. Đăng nhập ArgoCD

| | |
|--|--|
| URL | `https://argocd-npd.co` |
| User | `admin` |
| Password | |

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

Browser báo "Not secure" do cert self-signed — chấp nhận để test (Advanced → Proceed).

---

## 11. Kiểm tra từng tầng (debug)

```bash
# 1) Traefik + Ingress (bỏ Nginx)
curl -sI -H "Host: argocd-npd.co" http://127.0.0.1:9080/

# 2) Qua Nginx HTTPS
curl -skI https://argocd-npd.co/

# 3) Trong cluster
kubectl run curl-test --rm -it --restart=Never --image=curlimages/curl -- \
  curl -sI -H "Host: argocd-npd.co" http://traefik.kube-system.svc.cluster.local/
```

| Kết quả bước 1 | Kết quả bước 2 | Nguyên nhân |
|----------------|----------------|-------------|
| OK | Fail | Lỗi Nginx / hosts / cert |
| Fail | Fail | Ingress / ArgoCD / port map |
| 404 | 404 | Sai Host hoặc HTTP vào port 9443 |
| 502 | 502 | Upstream `127.0.0.1:80` (loop) hoặc chưa map 9080 |
| 400 | 400 | Cookie/header lớn → tăng buffer + xóa cookie browser |

---

## 12. Tắt / bật máy — cluster có mất không?

| Hành động | Cluster / App | Pod |
|-----------|---------------|-----|
| Tắt máy, bật lại | **Giữ** | Restart, Deployment tạo lại |
| `k3d cluster stop npd` / `start npd` | **Giữ** | Tương tự |
| `k3d cluster delete npd` | **Mất** | Mất |

Sau bật máy:

```bash
# Docker Desktop Running
k3d cluster list
kubectl get nodes
kubectl get pods -n argocd
docker ps | grep serverlb   # 9080, 9443 còn không
sudo systemctl start nginx
```

**Giữ nguyên:** Deployment, Service, Ingress, Secret, ArgoCD config, port map `9080`/`9443`.  
**Có thể đổi:** IP WSL2 nếu hosts trỏ IP thay vì `127.0.0.1`.  
**Mất:** `kubectl port-forward` (nếu có dùng).

---

## 13. Bảng lỗi thường gặp (tóm tắt fix)

| Lỗi | Nguyên nhân | Fix |
|-----|-------------|-----|
| `localhost:8080 refused` (kubectl) | Sai kubeconfig user | `k3d kubeconfig merge npd` |
| `502 Bad Gateway` (nginx) | Upstream `127.0.0.1:80` hoặc chưa map port k3d | Upstream `127.0.0.1:9080`, tạo cluster với `-p 9080:80@loadbalancer` |
| `404 page not found` | HTTP → port 9443 (HTTPS) hoặc sai Host Ingress | Upstream 9080; Ingress host `argocd-npd.co` |
| `400 Header/Cookie Too Large` | Buffer Nginx nhỏ + cookie cũ | `large_client_header_buffers`; Incognito |
| `ApplicationSet` CRD error | CRD chưa cài | Scale 0 controller hoặc server-side apply CRD |
| `curl :30468` refused | NodePort không publish ra host WSL | Dùng `9080` (LB map), không NodePort từ host |
| `curl 10.43.x` timeout | ClusterIP không route từ host | Chỉ dùng từ pod hoặc port map |

---

## 14. Bước tiếp theo (Phase 9 GitOps — nhánh `dev-k3d`)

Sau khi ArgoCD UI chạy ổn, làm việc trên nhánh **`dev-k3d`**:

```bash
git checkout dev-k3d
kubectl apply -f phase9-gitops-platform/gitops-platform/project.yaml -n argocd
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/app-of-apps.yaml -n argocd
```

Luồng CI/CD Jenkins (không GitHub Actions): [DEV-K3D-WORKFLOW.md](./DEV-K3D-WORKFLOW.md)

Xem thêm: [phase9-gitops-platform/README.md](../phase9-gitops-platform/README.md)

---

## 15. File tham chiếu trong repo

| File | Mô tả |
|------|--------|
| [`argocd-ingress.yaml`](./argocd-ingress.yaml) | Ingress Traefik Mô hình 1 |
| [`nginx-argocd-npd.co.conf`](./nginx-argocd-npd.co.conf) | Nginx reverse proxy ArgoCD |
| [`nginx-banking-npd.co.conf`](./nginx-banking-npd.co.conf) | Nginx reverse proxy Banking app |
| [`cluster-create.sh`](./cluster-create.sh) | Script tạo cluster k3d |

---

## 16. Lệnh tạo lại cluster (disaster recovery)

Chỉ khi cluster bị xóa nhầm:

```bash
k3d cluster delete npd
k3d cluster create npd --agents 5 \
  -p "9080:80@loadbalancer" \
  -p "9443:443@loadbalancer"

k3d kubeconfig merge npd --kubeconfig-merge-default
# Cài lại ArgoCD, Ingress, Nginx như các mục trên
```

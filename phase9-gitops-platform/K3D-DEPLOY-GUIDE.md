# Phase 9 — Triển khai từ đầu trên k3d (cluster mới)

Hướng dẫn **end-to-end** cho cụm **k3d trống** trên **WSL2 + Docker Desktop**, nhánh Git **`dev-k3d`**.

- **CI:** Jenkins + Kaniko → Harbor (không GitHub Actions)
- **CD:** ArgoCD GitOps (App of Apps)
- **App:** Phase 8 code + Phase 5 namespace/infra
- **Secret:** thủ công lúc đầu → Vault + External Secrets (sau khi Vault chạy)

Tài liệu liên quan:

- [k3d/WSL2-K3D-ARGOCD-GUIDE.md](../k3d/WSL2-K3D-ARGOCD-GUIDE.md) — Nginx, Ingress, lỗi 502/404/400
- [k3d/DEV-K3D-WORKFLOW.md](../k3d/DEV-K3D-WORKFLOW.md) — Luồng nhánh dev-k3d
- [PHASE9.md](./PHASE9.md) — Tổng quan kiến trúc
- [bootstrap/BOOTSTRAP.md](./bootstrap/BOOTSTRAP.md) — Thứ tự bootstrap platform

---

## Quan trọng — Thứ tự triển khai (4 giai đoạn)

**ArgoCD chỉ deploy banking app ở giai đoạn cuối**, sau khi platform + infra + CI/CD đã sẵn sàng.

| Giai đoạn | Việc cần làm | ArgoCD deploy app? |
|-----------|--------------|-------------------|
| **1** | k3d cluster + ArgoCD bootstrap + Nginx/Ingress | Không |
| **2** | **Platform:** Harbor, Vault, ESO, Jenkins | Không |
| **2b** | **Observability:** Coroot, OTEL, Linkerd mesh | Không |
| **3** | **Infra:** Postgres, Redis, RabbitMQ, Kong + secret | Không |
| **4** | **CI/CD:** Jenkins build → Harbor → commit `values-images.yaml` | Không (chỉ push image) |
| **5** | **ArgoCD sync banking app** → rollout Phase 8 | **Có** |

```text
Giai đoạn 1–3          Giai đoạn 4              Giai đoạn 5
─────────────────      ─────────────            ─────────────
ArgoCD (bootstrap)     git push dev-k3d    →    ArgoCD sync
Harbor, Vault, ESO     Jenkins + Kaniko         banking-app-of-apps
Jenkins                push Harbor              pods Running + Linkerd sidecar
Coroot, OTEL, Linkerd  commit values-images     traces → Coroot UI
Postgres, Redis        verify pipeline green    https://banking-npd.co
RabbitMQ, Kong
```

> **Không** apply `banking-app-of-apps` hoặc root `app-of-apps` cho đến khi Giai đoạn 4 hoàn tất.

---

## 0. Kiến trúc sau khi hoàn tất

```text
Windows hosts (127.0.0.1)
    │
    ▼
Nginx WSL2 (:443 SSL terminate)
    │
    ├── argocd-npd.co  ──► k3d LB :9080 ──► Traefik ──► ArgoCD
    ├── harbor-npd.co  ──► k3d LB :9080 ──► Traefik ──► Harbor UI
    ├── jenkins-npd.co ──► k3d LB :9080 ──► Traefik ──► Jenkins UI
    ├── vault-npd.co   ──► k3d LB :9080 ──► Traefik ──► Vault UI
    ├── coroot-npd.co  ──► k3d LB :9080 ──► Traefik ──► Coroot (metrics/logs/traces)
    ├── linkerd-npd.co ──► k3d LB :9080 ──► Traefik ──► Linkerd Viz (service mesh)
    └── banking-npd.co ──► k3d LB :9080 ──► Traefik ──► Kong ──► App Phase 8 (Linkerd mTLS)

Banking pods ──OTLP──► OTEL Collector ──OTLP──► Coroot (ClickHouse)
              └── Linkerd sidecar (mTLS mesh)

GitHub (dev-k3d) ──webhook──► Jenkins ──Kaniko──► Harbor
         ▲                           │
         └── commit values-images.yaml ◄┘
                    │
                    ▼
              ArgoCD sync ──► ns banking   ← CHỈ sau Giai đoạn 4
```

| Namespace | Thành phần | Domain UI | Giai đoạn |
|-----------|------------|-----------|-----------|
| `argocd` | ArgoCD | `argocd-npd.co` | 1 |
| `platform` | Jenkins, Harbor | `jenkins-npd.co`, `harbor-npd.co` | 2 |
| `vault` | Vault | `vault-npd.co` | 2 |
| `external-secrets` | ESO | — | 2 |
| `observability` | Coroot, OTEL Collector | `coroot-npd.co` | 2b |
| `linkerd` / `linkerd-viz` | Linkerd mesh + Viz | `linkerd-npd.co` | 2b |
| `postgres` | Postgres (Phase 5) | 3 |
| `redis` | Redis (Phase 5) | 3 |
| `kong` | Kong HA (Phase 5) | 3 |
| `rabbit` | RabbitMQ (Phase 8) | 3 |
| `banking` | App Phase 8 | **5** |

---

## 1. Điều kiện tiên quyết

### Phần cứng / OS

| | Khuyến nghị |
|--|-------------|
| RAM WSL2 | ≥ 24 GB (Coroot + ClickHouse + Linkerd + full platform) |
| Docker Desktop | Running, WSL integration bật |
| OS | WSL2 Ubuntu |

### Cài trên WSL2

```bash
sudo apt update
sudo apt install -y curl git nginx openssl

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# helm (tùy chọn — debug)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Kiểm tra:

```bash
docker version
kubectl version --client
k3d version
nginx -v
```

---

## 2. Clone repo và nhánh `dev-k3d`

```bash
cd ~
git clone https://github.com/kevinram164/banking-demo.git
cd banking-demo
git checkout dev-k3d
git pull
```

Repo: **`https://github.com/kevinram164/banking-demo.git`** — đã cấu hình trong ArgoCD manifests và `Jenkinsfile`.

### Biến môi trường (dùng xuyên suốt doc)

```bash
export REPO_ROOT=~/banking-demo   # chỉnh path thật
export GIT_BRANCH=dev-k3d
export CLUSTER=npd
```

---

## 3. Giai đoạn 1 — Cluster k3d + ArgoCD bootstrap

### 3.1 Tạo cluster k3d

```bash
cd "$REPO_ROOT/k3d"
chmod +x cluster-create.sh
./cluster-create.sh
```

Hoặc thủ công:

```bash
k3d cluster create npd \
  --agents 2 \
  -p "9080:80@loadbalancer" \
  -p "9443:443@loadbalancer"

k3d kubeconfig merge npd --kubeconfig-merge-default
chmod 600 ~/.kube/config
```

Kiểm tra:

```bash
kubectl get nodes
docker ps | grep serverlb
# Kỳ vọng: 9080->80, 9443->443
```

StorageClass mặc định k3d: **`local-path`** (sẽ chỉnh values infra ở Giai đoạn 3).

### 3.2 Cài ArgoCD (bootstrap — không qua GitOps)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.4/manifests/install.yaml

kubectl wait -n argocd --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server --timeout=600s
kubectl get pods -n argocd
```

(Tùy chọn) Tắt ApplicationSet controller nếu log lỗi CRD:

```bash
kubectl scale deployment argocd-applicationset-controller -n argocd --replicas=0
```

### 3.3 Cấu hình ArgoCD phía sau Nginx (Mô hình SSL 1)

```bash
kubectl patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'

kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"url":"https://argocd-npd.co"}}'

kubectl rollout restart deployment argocd-server -n argocd
```

### 3.4 Ingress Traefik + Nginx LB

```bash
kubectl apply -f "$REPO_ROOT/k3d/argocd-ingress.yaml"

mkdir -p ~/argocd-self-signed
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/argocd-self-signed/tls.key \
  -out ~/argocd-self-signed/tls.crt \
  -subj "/CN=argocd-npd.co"

sudo cp "$REPO_ROOT/k3d/nginx-argocd-npd.co.conf" /etc/nginx/conf.d/
sudo cp "$REPO_ROOT/k3d/nginx-harbor-npd.co.conf" /etc/nginx/conf.d/
sudo cp "$REPO_ROOT/k3d/nginx-jenkins-npd.co.conf" /etc/nginx/conf.d/
sudo cp "$REPO_ROOT/k3d/nginx-vault-npd.co.conf" /etc/nginx/conf.d/
sudo cp "$REPO_ROOT/k3d/nginx-coroot-npd.co.conf" /etc/nginx/conf.d/
sudo cp "$REPO_ROOT/k3d/nginx-linkerd-npd.co.conf" /etc/nginx/conf.d/
sudo cp "$REPO_ROOT/k3d/nginx-banking-npd.co.conf" /etc/nginx/conf.d/
sudo nginx -t && sudo systemctl enable nginx && sudo systemctl reload nginx
```

Windows `hosts` (Admin):

```text
127.0.0.1   argocd-npd.co
127.0.0.1   harbor-npd.co
127.0.0.1   jenkins-npd.co
127.0.0.1   vault-npd.co
127.0.0.1   coroot-npd.co
127.0.0.1   linkerd-npd.co
127.0.0.1   banking-npd.co
```

Lấy password admin:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

Mở **https://argocd-npd.co** → user **`admin`**.

### 3.5 Kết nối GitHub repo trong ArgoCD

1. ArgoCD UI → **Settings → Repositories → Connect repo**
2. URL: `https://github.com/kevinram164/banking-demo.git`
3. Nếu private: username + PAT (scope `repo`)

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/argocd/project.yaml" -n argocd
```

Chi tiết lỗi Nginx: [WSL2-K3D-ARGOCD-GUIDE.md](../k3d/WSL2-K3D-ARGOCD-GUIDE.md).

---

## 4. Giai đoạn 2 — Platform (Harbor, Vault, ESO, Jenkins)

ArgoCD quản lý platform; **chưa deploy banking app**.

### 4.1 Apply platform App of Apps

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/platform-app-of-apps.yaml" -n argocd
```

ArgoCD UI → **`platform-app-of-apps-dev-k3d`** → **Sync**.

Thứ tự sync wave trong platform:

| Wave | App | Ghi chú |
|------|-----|---------|
| 0 | Harbor, Vault, External Secrets (controller) | Chờ pod Running |
| 1 | External Secrets config, Jenkins | Sau Vault + Harbor cơ bản |

Theo dõi:

```bash
kubectl get pods -n platform
kubectl get pods -n vault
kubectl get pods -n external-secrets
```

### 4.2 Harbor

1. Ingress đã cấu hình trong Helm (`harbor-npd.co`, Traefik) — Nginx LB ở mục 3.4
2. UI: **https://harbor-npd.co** — đổi admin password
3. Tạo project **`banking-demo`**
4. Robot accounts: **`ci-push`** (Jenkins push), **`k8s-pull`** (cluster pull)

Pull secret (dùng ở Giai đoạn 5):

```bash
kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor-npd.co \
  --docker-username='robot$k8s-pull' \
  --docker-password='ROBOT_TOKEN' \
  -n banking --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor-npd.co \
  --docker-username='robot$k8s-pull' \
  --docker-password='ROBOT_TOKEN' \
  -n platform
```

Cập nhật `phase9-gitops-platform/gitops/values-images.yaml` → registry `harbor-npd.co/banking-demo/...`

### 4.3 Vault + External Secrets

1. Sync `platform-vault` → dev mode: token **`root`**, UI **https://vault-npd.co**
2. Seed secret paths — xem [vault/README.md](./vault/README.md)
3. Sync `platform-external-secrets` + `platform-external-secrets-config`
4. Tạo secret `vault-token` trong `external-secrets` nếu dùng token auth lab

Sau ESO sync → secret K8s được tạo tự động (thay `kubectl create secret` thủ công nếu đã cấu hình ExternalSecret).

### 4.4 Jenkins

1. Sync `platform-jenkins` → pod Running
2. UI: **https://jenkins-npd.co** — user `admin`, password trong values hoặc:
   ```bash
   kubectl exec -n platform deploy/jenkins -c jenkins -- cat /run/secrets/additional/chart-admin-password 2>/dev/null || true
   ```
3. **Manage Jenkins → Global Pipeline Libraries** → name `banking-demo`, repo + branch `dev-k3d`, path `phase9-gitops-platform/jenkins-shared-library`
4. Tạo **Multibranch Pipeline** → branch `dev-k3d`, script path `Jenkinsfile`
5. Credentials Jenkins:
   - `harbor-ci-push` — robot Harbor push
   - `github-gitops-push` — PAT commit `values-images.yaml`
6. GitHub webhook → Jenkins (push `dev-k3d`)

Chi tiết: [jenkins-shared-library/README.md](./jenkins-shared-library/README.md)

**Checkpoint Giai đoạn 2:** Harbor UI OK, Vault unsealed, Jenkins login OK, Shared Library loaded.

---

## 4b. Giai đoạn 2b — Observability (Coroot + OpenTelemetry + Linkerd)

Metrics + logs + traces qua **Coroot**; **OpenTelemetry Collector** làm gateway; **Linkerd** làm service mesh (mTLS).

Chi tiết: [observability/README.md](./observability/README.md)

### 4b.1 Linkerd certificates (một lần)

```bash
chmod +x "$REPO_ROOT/phase9-gitops-platform/observability/scripts/generate-linkerd-certs.sh"
"$REPO_ROOT/phase9-gitops-platform/observability/scripts/generate-linkerd-certs.sh"
# Tạo: secret linkerd-identity-issuer + configmap linkerd-identity-trust-roots (ns linkerd)
```

### 4b.2 Apply observability App of Apps

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/observability-app-of-apps.yaml" -n argocd
```

ArgoCD UI → **`observability-app-of-apps-dev-k3d`** → **Sync**.

| Wave | App |
|------|-----|
| 0 | coroot-operator, linkerd-crds |
| 1 | coroot-ce, otel-collector, linkerd-control-plane |
| 2 | linkerd-viz |

Theo dõi:

```bash
kubectl get pods -n observability
kubectl get pods -n linkerd
kubectl get pods -n linkerd-viz
linkerd check
```

### 4b.3 Ingress + Nginx

```bash
kubectl apply -f "$REPO_ROOT/k3d/linkerd-viz-ingress.yaml"
sudo nginx -t && sudo systemctl reload nginx
```

- **Coroot UI:** https://coroot-npd.co (metrics, logs, traces, service map eBPF)
- **Linkerd Viz:** https://linkerd-npd.co (mesh topology, success rate, latency)

### 4b.4 Sau khi banking app deploy (Giai đoạn 5)

Banking pods tự gửi OTLP qua `gitops/values-observability.yaml`. Restart để inject Linkerd:

```bash
kubectl rollout restart deployment -n banking
linkerd viz stat deploy -n banking
```

**Checkpoint Giai đoạn 2b:** Coroot UI mở được; `linkerd check` pass; OTEL collector Running.

---

## 5. Giai đoạn 3 — Infra (Postgres, Redis, RabbitMQ, Kong)

### StorageClass trên k3d

k3d **không có** `nfs-client` / `pg-client`. Dùng **`local-path`** cho mọi StatefulSet/PVC:

| Thành phần | File cấu hình | StorageClass k3d |
|------------|---------------|------------------|
| Harbor, Jenkins | `argocd/applications/platform/*.yaml` | `local-path` (đã sửa) |
| Postgres | `phase5-architecture-refactor/postgres-ha/values-postgres-ha.yaml` | đổi `pg-client` → `local-path` |
| Redis | `phase5-architecture-refactor/redis-ha/values-redis-ha.yaml` | đổi `nfs-client` → `local-path` |
| RabbitMQ | `phase8-application-v3/rabbitmq/k8s-rabbitmq-standalone.yaml` | đổi → `local-path` |

### 5.1 Chỉnh StorageClass cho k3d (trước khi sync infra)

Sửa trên nhánh `dev-k3d`, commit push:

**Postgres** — `phase5-architecture-refactor/postgres-ha/values-postgres-ha.yaml`:

```yaml
primary:
  persistence:
    storageClass: local-path
```

**Redis** — `phase5-architecture-refactor/redis-ha/values-redis-ha.yaml`:

```yaml
master:
  persistence:
    storageClass: local-path
```

**RabbitMQ** — `phase8-application-v3/rabbitmq/k8s-rabbitmq-standalone.yaml`:

```yaml
storageClassName: local-path
```

### 5.2 Apply infra App of Apps

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/infra-app-of-apps.yaml" -n argocd
```

ArgoCD UI → **`infra-app-of-apps-dev-k3d`** → **Sync**.

Thứ tự sync wave:

| Wave | App | Ghi chú |
|------|-----|---------|
| 0 | Postgres, Redis | Chờ PVC Bound + pod Running |
| 1 | RabbitMQ, Kong | Sau postgres/redis |

Theo dõi:

```bash
kubectl get pods -n postgres
kubectl get pods -n redis
kubectl get pods -n rabbit
kubectl get pods -n kong
```

### 5.3 Secret (nếu chưa dùng Vault/ESO)

Tạo namespace:

```bash
kubectl create namespace banking --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace rabbit --dry-run=client -o yaml | kubectl apply -f -
```

**RabbitMQ** (ns `rabbit`):

```bash
export RABBIT_PASS='bankingpass-change-me'

kubectl create secret generic rabbitmq-secret \
  --from-literal=rabbitmq-username=banking \
  --from-literal=rabbitmq-password="$RABBIT_PASS" \
  -n rabbit
```

**Banking DB + Redis** (ns `banking`) — sau Postgres + Redis Running:

```bash
kubectl create secret generic banking-db-secret \
  --from-literal=DATABASE_URL='postgresql://banking:bankingpass@postgres-ha-postgresql.postgres.svc.cluster.local:5432/banking' \
  --from-literal=REDIS_URL='redis://redis-ha-redis-master.redis.svc.cluster.local:6379/0' \
  -n banking
```

**RabbitMQ connection** (ns `banking`):

```bash
kubectl create secret generic rabbitmq-connection-secret \
  --from-literal=RABBITMQ_URL="amqp://banking:${RABBIT_PASS}@rabbitmq.rabbit.svc.cluster.local:5672/" \
  -n banking
```

> Hostname Postgres/Redis phụ thuộc Helm release — kiểm tra `kubectl get svc -n postgres` và `-n redis`.

**Checkpoint Giai đoạn 3:** Tất cả pod infra Running; secret banking/rabbit có sẵn.

---

## 6. Giai đoạn 4 — Tích hợp CI/CD (Jenkins → Harbor → Git)

Mục tiêu: pipeline build image và commit tag vào Git **trước khi** ArgoCD deploy app.

### 6.1 Chạy pipeline lần đầu

```bash
# Sửa code Phase 8 (hoặc trigger build thủ công trên Jenkins)
vim phase8-application-v3/services/auth-service/main.py

git add phase8-application-v3/
git commit -m "feat: first CI build on dev-k3d"
git push origin dev-k3d
```

Jenkins pipeline kỳ vọng:

1. Kaniko build image từ Dockerfile Phase 8
2. Push `harbor-npd.co/banking-demo/<service>:<short-sha>`
3. Commit + push `phase9-gitops-platform/gitops/values-images.yaml`

Verify:

```bash
# Harbor UI — project banking-demo có image
# GitHub — commit mới trên values-images.yaml
git log -1 --oneline -- phase9-gitops-platform/gitops/values-images.yaml
```

### 6.2 Jenkins credentials & webhook checklist

- [ ] `harbor-ci-push` — push image OK
- [ ] `github-gitops-push` — commit GitOps OK
- [ ] Webhook GitHub → Jenkins trigger trên push `dev-k3d`
- [ ] Pipeline green end-to-end

**Checkpoint Giai đoạn 4:** Harbor có image mới; `values-images.yaml` đã commit; Jenkins pipeline green.

---

## 7. Giai đoạn 5 — ArgoCD deploy banking app

**Chỉ thực hiện sau Giai đoạn 4.**

### 7.1 Apply banking App of Apps

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/banking-app-of-apps.yaml" -n argocd
```

ArgoCD UI → **`banking-app-of-apps-dev-k3d`** → **Sync** (lần đầu sync thủ công).

Apps được tạo:

- `banking-namespace`
- `banking-api-producer`, auth, account, transfer, notification
- `banking-frontend`, `banking-ingress`

```bash
kubectl get applications -n argocd | grep banking
kubectl get pods -n banking
```

Nếu `ImagePullBackOff` → kiểm tra Harbor pull secret (mục 4.2) và tag trong `values-images.yaml`.

### 7.2 (Tùy chọn) Apply root App of Apps — quản lý tập trung

Sau khi mọi thứ ổn:

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/app-of-apps.yaml" -n argocd
```

Root adopt 3 nhóm app-of-apps đã apply trước đó.

### 7.3 Kong Phase 8 routes

Sau Kong infra + banking pods Running:

```bash
kubectl apply -f "$REPO_ROOT/phase8-application-v3/kong-ha/kong-import-job.yaml"
kubectl wait -n kong --for=condition=complete job/kong-import-phase8 --timeout=300s
kubectl rollout restart deployment -n kong -l app.kubernetes.io/name=kong
```

Verify:

```bash
curl -sk -H "Host: banking-npd.co" https://127.0.0.1:9080/ | head
# hoặc: https://banking-npd.co
```

---

## 8. Luồng phát triển hàng ngày (sau bootstrap)

```text
git push dev-k3d  →  Jenkins build  →  Harbor  →  commit values-images.yaml
                                                          ↓
                                              ArgoCD auto-sync banking apps
                                                          ↓
                                              rollout pods ns banking
```

```bash
git push origin dev-k3d
kubectl get applications -n argocd -w
kubectl get pods -n banking
```

---

## 9. Checklist hoàn tất

### Giai đoạn 1
- [ ] `kubectl get nodes` — All Ready
- [ ] `https://argocd-npd.co` — login OK
- [ ] ArgoCD repo connected, branch `dev-k3d`

### Giai đoạn 2 — Platform
- [ ] Harbor UI + project `banking-demo` + robot accounts
- [ ] Vault unsealed (hoặc dev mode)
- [ ] ESO controller Running
- [ ] Jenkins + Shared Library + Multibranch job

### Giai đoạn 3 — Infra
- [ ] Postgres, Redis, RabbitMQ, Kong pods Running
- [ ] Secret `banking`, `rabbit` (ESO hoặc thủ công)

### Giai đoạn 4 — CI/CD
- [ ] Push code → Jenkins green
- [ ] Image trên Harbor
- [ ] `values-images.yaml` committed

### Giai đoạn 5 — App
- [ ] Banking pods Running trong `banking`
- [ ] Kong routes imported
- [ ] `https://banking-npd.co` — Banking Demo UI

---

## 10. Tắt / bật máy

Cluster **không mất** khi reboot (không `k3d cluster delete`):

```bash
docker ps | grep serverlb    # 9080, 9443
kubectl get nodes
sudo systemctl start nginx
```

Chi tiết: [WSL2-K3D-ARGOCD-GUIDE.md](../k3d/WSL2-K3D-ARGOCD-GUIDE.md).

---

## 11. Xử lý lỗi nhanh

| Triệu chứng | Xem |
|-------------|-----|
| 502 / 404 ArgoCD | Upstream Nginx phải `127.0.0.1:9080`, Ingress host đúng |
| 400 Header Too Large | `large_client_header_buffers` + xóa cookie |
| kubectl localhost:8080 | `k3d kubeconfig merge npd` |
| ImagePullBackOff | Harbor secret + robot account; CI đã push image? |
| Banking sync quá sớm | Quay lại Giai đoạn 4 — cần image trên Harbor trước |
| ArgoCD OutOfSync lâu | Sync từng app; kiểm tra repo branch `dev-k3d` |
| PVC Pending | Đổi `storageClass: local-path` |

---

## 12. Lệnh tham chiếu nhanh

```bash
# Trạng thái tổng
kubectl get pods -A | grep -v Running
kubectl get applications -n argocd

# Apply theo giai đoạn (dev-k3d)
kubectl apply -f phase9-gitops-platform/argocd/project.yaml -n argocd
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/platform-app-of-apps.yaml -n argocd
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/observability-app-of-apps.yaml -n argocd
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/infra-app-of-apps.yaml -n argocd
# ... CI/CD ...
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/banking-app-of-apps.yaml -n argocd

# Logs app
kubectl logs -n banking -l app=auth-service --tail=50
```

---

## 13. Tài liệu theo phase trong repo

| Phase | Thư mục |
|-------|---------|
| 5 — Namespace/HA | `phase5-architecture-refactor/` |
| 8 — Code + RabbitMQ | `phase8-application-v3/` |
| 2 — Helm chart | `phase2-helm-chart/banking-demo/` |
| 9 — GitOps platform | `phase9-gitops-platform/` |

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
export REPO_ROOT=/home/kevin/banking-demo  # chỉnh path thật
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
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/gitops-platform/project.yaml" -n argocd
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
| 1 | External Secrets config (gồm `jenkins-platform-credentials`) | Seed Vault `secret/platform/jenkins` trước |
| 2 | Jenkins | JCasC đọc credential từ K8s secret (Vault) |

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
# ns banking — tên harbor-registry (khớp values-images.yaml)
kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor-npd.co \
  --docker-username='robot$k8s-pull' \
  --docker-password='ROBOT_TOKEN' \
  -n banking --dry-run=client -o yaml | kubectl apply -f -

# ns platform — KHÔNG dùng tên harbor-registry (Harbor Helm chart chiếm tên đó)
kubectl delete secret harbor-pull-creds -n platform 2>/dev/null || true
kubectl create secret docker-registry harbor-pull-creds \
  --docker-server=harbor-npd.co \
  --docker-username='robot$k8s-pull' \
  --docker-password='ROBOT_TOKEN' \
  -n platform
```

**Kubelet pull qua TLS (x509):** Node k3d pull `harbor-npd.co` trực tiếp sẽ gặp cert self-signed từ Nginx WSL2 (khác Kaniko `--skip-tls-verify`). Cấu hình mirror HTTP nội bộ:

```bash
chmod +x "$REPO_ROOT/k3d/configure-harbor-registry-k3d.sh"
"$REPO_ROOT/k3d/configure-harbor-registry-k3d.sh"
```

Cluster mới: `k3d/cluster-create.sh` đã mount `k3d/registries.yaml` (mirror → `harbor.platform.svc.cluster.local:80`).

Cập nhật `phase9-gitops-platform/gitops/values-images.yaml` → registry `harbor-npd.co/banking-demo/...`

### 4.3 Vault + External Secrets

Chi tiết CLI: [vault/README.md](./vault/README.md). **Thứ tự bắt buộc** — đảo bước sẽ lỗi `InvalidProviderConfig` / `SecretSyncedError`.

#### Bước 1 — Sync Vault, seed KV trong pod

```bash
kubectl get pods -n vault   # vault-0 Running

kubectl exec -it vault-0 -n vault -- sh
```

Trong pod:

```sh
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

vault kv put secret/banking/db \
  DATABASE_URL='postgresql://banking:bankingpass@postgres.postgres.svc.cluster.local:5432/banking' \
  REDIS_URL='redis://redis.redis.svc.cluster.local:6379/0'

vault kv put secret/banking/rabbitmq \
  RABBITMQ_URL='amqp://banking:bankingpass@rabbitmq.rabbit.svc.cluster.local:5672/'

vault kv put secret/rabbitmq/admin \
  username='banking' \
  password='bankingpass'
```

UI lab (tùy chọn): **https://vault-npd.co**, token **`root`**.

#### Bước 2 — Sync ESO controller

ArgoCD: `platform-external-secrets` → Synced / Healthy.

```bash
kubectl get pods -n external-secrets
```

#### Bước 3 — Tạo `vault-token` **trước** ClusterSecretStore

```bash
kubectl create secret generic vault-token \
  --from-literal=token=root \
  -n external-secrets
```

> Nếu apply `ClusterSecretStore` khi chưa có `vault-token` → ArgoCD Events:  
> `InvalidProviderConfig: cannot get Kubernetes secret "vault-token": secrets "vault-token" not found`.

#### Bước 4 — Namespace + sync ExternalSecret manifest

```bash
kubectl create ns banking --dry-run=client -o yaml | kubectl apply -f -
kubectl create ns rabbit --dry-run=client -o yaml | kubectl apply -f -
```

ArgoCD: `platform-external-secrets-config`  
Hoặc thủ công: `kubectl apply -f phase9-gitops-platform/vault/external-secrets/`

#### Bước 5 — Kiểm tra sync

```bash
kubectl get clustersecretstore vault-backend          # STATUS Valid
kubectl get externalsecret -A                         # SecretSynced, READY True
kubectl get secret banking-db-secret -n banking
```

Nếu vừa tạo `vault-token` hoặc vừa seed Vault — force reconcile:

```bash
kubectl annotate clustersecretstore vault-backend force-sync=$(date +%s) --overwrite
kubectl annotate externalsecret banking-db-secret -n banking force-sync=$(date +%s) --overwrite
kubectl annotate externalsecret rabbitmq-connection-secret -n banking force-sync=$(date +%s) --overwrite
kubectl annotate externalsecret rabbitmq-secret -n rabbit force-sync=$(date +%s) --overwrite
```

#### Xử lý lỗi nhanh

| Triệu chứng | Cách sửa |
|-------------|----------|
| `vault-token` not found | Bước 3 → annotate `clustersecretstore` |
| `SecretSyncedError` | Seed Vault (bước 1) → annotate `externalsecret` |
| `namespaces "rabbit" not found` | `kubectl create ns rabbit` → apply lại manifest |
| `banking-db-secret` not found | `kubectl describe externalsecret banking-db-secret -n banking` |

Test Vault đã có data:

```bash
kubectl exec -n vault vault-0 -- sh -c \
  'export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root && vault kv get secret/banking/db'
```

Sau ESO sync → secret K8s được tạo tự động (thay `kubectl create secret` thủ công).

### 4.4 Jenkins — cấu hình CI (từng bước)

**Mục tiêu:** push code nhánh `dev-k3d` → Jenkins build image Kaniko → push Harbor → commit `values-images.yaml`.

**Cần làm trước:** Harbor đã chạy (mục 4.2), đã tạo project `banking-demo` và robot account `ci-push`.

---

#### Bước 1 — Đợi Jenkins chạy

```bash
kubectl get pods -n platform -l app.kubernetes.io/component=jenkins-controller
# jenkins-0 → 2/2 Running
```

ArgoCD: app `platform-jenkins` → **Synced / Healthy**.

---

#### Bước 2 — Đăng nhập Jenkins

| | |
|---|---|
| URL | https://jenkins-npd.co |
| User | `admin` |
| Password | `ChangeMe-Jenkins` (trong `jenkins.yaml`) |

Lấy password từ cluster (nếu đổi sau lần deploy đầu):

```bash
kubectl get secret jenkins -n platform \
  -o jsonpath='{.data.jenkins-admin-password}' | base64 -d; echo
```

---

#### Bước 3 — Shared Library (tự động qua GitOps)

Manifest `jenkins.yaml` đã khai báo **JCasC** — không cần cấu hình thủ công trên UI.

| Tham số | Giá trị |
|---------|---------|
| Tên library | `banking-demo` |
| Branch mặc định | `dev-k3d` |
| Repo | `https://github.com/kevinram164/banking-demo.git` |
| Thư mục library | `phase9-gitops-platform/jenkins-shared-library` |

Sau khi sync `platform-jenkins`, kiểm tra:

```bash
# ConfigMap JCasC có chứa banking-demo
kubectl get configmap -n platform -l jenkins-jenkins-config=true -o name | head -1 | \
  xargs kubectl get -n platform -o yaml | grep -A2 'name: "banking-demo"' || true
```

Nếu chưa thấy → sync lại app và restart pod:

```bash
argocd app sync platform-jenkins --force
kubectl delete pod jenkins-0 -n platform
```

> **Lưu ý UI:** Trên Jenkins mới, mục cấu hình library (nếu tự làm tay) nằm ở **Manage Jenkins → System** (`/configure`), tìm **Global Trusted Pipeline Libraries** — không có trên trang Manage Jenkins chính.

---

#### Bước 4 — Credential Jenkins qua Vault (không tạo trên UI)

Toàn bộ credential Jenkins lưu tại **`secret/platform/jenkins`** → ESO → JCasC (ID giữ nguyên: `harbor-ci-push`, `github-gitops-push`).

**4a. Seed Vault** (trong pod `vault-0`, xem [vault/README.md](./vault/README.md)):

```bash
vault kv put secret/platform/jenkins \
  admin_username='admin' \
  admin_password='YOUR_JENKINS_ADMIN_PASSWORD' \
  harbor_username='robot$banking-demo+ci-push' \
  harbor_password='HARBOR_ROBOT_TOKEN' \
  github_username='kevinram164' \
  github_pat='github_pat_xxxx'
```

**4b. Kiểm tra ESO sync** (sau `platform-external-secrets-config`):

```bash
kubectl get externalsecret jenkins-platform-credentials -n platform
kubectl get secret jenkins-platform-credentials -n platform
```

**4c. Sync Jenkins** (wave 2 — sau khi secret đã có):

ArgoCD → `platform-jenkins` → Sync. Hoặc:

```bash
kubectl delete pod jenkins-0 -n platform   # reload JCasC + admin password
```

**4d. Xác nhận trên Jenkins UI**

Manage Jenkins → Credentials → (global) phải có `harbor-ci-push`, `github-gitops-push` (do JCasC, không cần Add thủ công).

**GitHub PAT:** Fine-grained → repo `banking-demo` → **Contents: Read and write**. Kiểm tra:

```bash
curl -s -H "Authorization: Bearer github_pat_xxx" \
  https://api.github.com/repos/kevinram164/banking-demo | grep -E '"push"|"admin"'
```

> **Rotate:** `vault kv patch secret/platform/jenkins github_pat='...'` → annotate ExternalSecret → restart `jenkins-0`.

---

#### Bước 5 — ServiceAccount cho Kaniko (một lần)

Pipeline chạy pod Kaniko với SA `jenkins-kaniko`:

```bash
kubectl create serviceaccount jenkins-kaniko -n platform --dry-run=client -o yaml | kubectl apply -f -
```

---

#### Bước 6 — Tạo job Multibranch Pipeline

1. Jenkins home → **New Item**
2. Tên: `banking-demo` (tùy chọn)
3. Chọn **Multibranch Pipeline** → OK
4. Tab **Branch Sources** → **Add source** → **Git**
   - Repository URL: `https://github.com/kevinram164/banking-demo.git`
   - Credentials: không cần (repo public) hoặc thêm nếu private
5. **Behaviours** → **Filter by name (with wildcards)**
   - Include: `dev-k3d`
   - Exclude: (để trống)
6. Tab **Build Configuration**
   - Mode: **by Jenkinsfile**
   - Script Path: `Jenkinsfile` (file ở root repo — đã cấu hình sẵn `harbor-npd.co`, branch `dev-k3d`)
7. **Save**

Jenkins quét nhánh `dev-k3d` và tạo job con. Bấm job con → **Build Now** để thử.

---

#### Bước 7 — (Tùy chọn) Webhook GitHub tự động build

1. Job `banking-demo` → **Configure** → **Scan Multibranch Pipeline Triggers**
2. Bật **Periodically if not otherwise run** (vd. mỗi 5 phút) — hoặc cấu hình webhook:
3. GitHub repo → **Settings → Webhooks → Add**
   - Payload URL: `https://jenkins-npd.co/github-webhook/`
   - Content type: `application/json`
   - Events: **Just the push event**
   - Branch: `dev-k3d`

---

#### Bước 8 — Kiểm tra pipeline chạy OK

```bash
# Sửa code Phase 8 rồi push
git add phase8-application-v3/
git commit -m "test: trigger Jenkins CI"
git push origin dev-k3d
```

Kỳ vọng trên Jenkins UI:

1. Stage **Checkout** — OK
2. Stage **Build & Push** — image lên `harbor-npd.co/banking-demo/<service>:<sha7>`
3. Stage **Update GitOps** — commit mới trên `values-images.yaml`

Verify:

```bash
# Harbor UI — project banking-demo có image
git pull origin dev-k3d
git log -1 --oneline -- phase9-gitops-platform/gitops/values-images.yaml
```

---

#### Lỗi thường gặp

| Triệu chứng | Cách sửa |
|-------------|----------|
| `library banking-demo not found` | Sync `platform-jenkins`, restart `jenkins-0`, đợi plugin + JCasC load |
| `credentials harbor-ci-push not found` | Seed Vault `secret/platform/jenkins` → ESO sync → restart `jenkins-0` |
| Kaniko push 401 | Robot Harbor sai user/token; user phải là `robot$ci-push` |
| Kaniko `x509: certificate is not valid` / TLS verify | Harbor lab self-signed → `kanikoSkipTlsVerify: true` trong Jenkinsfile |
| Git push 403 Permission denied | PAT thiếu **Contents: Read and write** / scope `repo`; Password trong Jenkins phải là PAT (`ghp_` / `github_pat_`) |
| Pod Kaniko pending | Tạo SA `jenkins-kaniko` (Bước 5) |
| Kaniko `stat /busybox/cat: no such file` | Image phải là `executor:*-debug` (có busybox); không dùng `executor` thường |
| Kaniko `mkdir: cannot create directory '/kaniko': Permission denied` | Lệnh build phải chạy trong `container('kaniko')`, không phải container `jnlp` |

Chi tiết library: [jenkins-shared-library/README.md](./jenkins-shared-library/README.md)

**Checkpoint Giai đoạn 2:** Harbor UI OK, Vault seeded, Jenkins login OK, job Multibranch tạo xong, credentials 2 ID đã có.

---

## 4b. Giai đoạn 2b — Observability (Coroot + OpenTelemetry + Linkerd)

Metrics + logs + traces qua **Coroot**; **OpenTelemetry Collector** làm gateway; **Linkerd** làm service mesh (mTLS).

Chi tiết: [observability/README.md](./observability/README.md)

### 4b.1 Linkerd certificates

Linkerd: **wave 0** app `linkerd-identity-bootstrap` (Kustomize → secret + configmap) → **wave 1** Helm `externalCA: true`.

Nếu Linkerd lỗi / CreateContainerConfigError:

```bash
chmod +x "$REPO_ROOT/phase9-gitops-platform/observability/scripts/reset-linkerd-control-plane-k3d.sh"
"$REPO_ROOT/phase9-gitops-platform/observability/scripts/reset-linkerd-control-plane-k3d.sh"
# ArgoCD: sync linkerd-identity-bootstrap → rồi linkerd-control-plane (Replace)
argocd app sync observability-linkerd-identity-bootstrap --grpc-web
argocd app sync observability-linkerd-control-plane --force --replace --grpc-web
kubectl get pods -n linkerd -w
```

Phải có **cả** `linkerd-identity-issuer` (secret) và `linkerd-config` (configmap) trước khi pod Running.

### 4b.2 Apply observability App of Apps

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/observability-app-of-apps.yaml" -n argocd
```

ArgoCD UI → **`observability-app-of-apps-dev-k3d`** → **Sync**.

| Wave | App |
|------|-----|
| 0 | coroot-operator, linkerd-crds, **linkerd-identity-bootstrap** |
| 1 | otel-collector, linkerd-control-plane |
| 2 | coroot-ce, linkerd-viz |

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
| Harbor, Jenkins | `gitops-platform/applications/platform/*.yaml` | `local-path` (đã sửa) |
| Postgres | `phase5-architecture-refactor/postgres-ha/values-postgres-ha.yaml` | mặc định `local-path` (k3d) |
| Redis | `phase5-architecture-refactor/redis-ha/values-redis-ha.yaml` | mặc định `local-path` (k3d) |
| RabbitMQ | `phase8-application-v3/rabbitmq/k8s-rabbitmq-standalone.yaml` | đổi → `local-path` |

### 5.1 StorageClass (k3d)

Values Postgres/Redis/RabbitMQ đã mặc định **`local-path`** cho lab k3d. Cluster production có NFS → sửa lại `pg-client` / `nfs-client` trong các file values tương ứng.

Nếu PVC cũ đã tạo với StorageClass sai, **xóa StatefulSet trước** (volumeClaimTemplates không đổi được), rồi sync lại ArgoCD:

```bash
# Redis (sentinel → StatefulSet tên redis-ha-node)
kubectl delete sts -n redis redis-ha-node --cascade=orphan
kubectl delete pvc -n redis --all

# Postgres
kubectl delete sts -n postgres postgres-ha-postgresql-primary postgres-ha-postgresql-read --cascade=orphan
kubectl delete pvc -n postgres --all
# Chỉ khi chưa có data quan trọng
```

Kiểm tra ArgoCD đọc đúng nhánh values:

```bash
kubectl get application infra-redis -n argocd -o jsonpath='{range .spec.sources[*]}{.ref}{.targetRevision}{"\n"}{end}'
# phải thấy values + dev-k3d
```

ArgoCD → **Hard Refresh** (Clear cache) → Sync `infra-postgres`, `infra-redis`.

### 5.2 Apply infra App of Apps

```bash
kubectl apply -f "$REPO_ROOT/phase9-gitops-platform/environments/dev-k3d/argocd/applications/infra-app-of-apps.yaml" -n argocd
```

ArgoCD UI → **`infra-app-of-apps-dev-k3d`** → **Sync**.

> **Lỗi Bitnami OCI 401:** Nếu `infra-postgres` / `infra-redis` báo  
> `HEAD ... bitnamicharts/manifests/... 401 Unauthorized` — Docker Hub chặn pull OCI anonymous.  
> Application phải dùng Helm repo `https://charts.bitnami.com/bitnami` (không dùng `oci://registry-1.docker.io/bitnamicharts`).  
> Sau khi sửa manifest, **Refresh** + **Sync** lại app trong ArgoCD.

> **Lỗi Bitnami ImagePullBackOff (`not found`):** Chart pin image `docker.io/bitnami/*` — nhiều tag đã gỡ khỏi Docker Hub.  
> Values Postgres/Redis dùng `bitnamilegacy/*` + `global.security.allowInsecureImages: true`.  
> Push → Hard Refresh → Sync → `kubectl delete pod -n postgres -l app.kubernetes.io/name=postgresql` (và tương tự redis).

Thứ tự sync wave:

| Wave | App | Ghi chú |
|------|-----|---------|
| 0 | Postgres, Redis | Chờ PVC Bound + pod Running |
| 1 | RabbitMQ | Sau postgres/redis (sync-wave) |
| 2 | **Kong** | Sau Postgres — PreSync hook chờ PG Ready + tạo DB `kong` rồi mới deploy chart |

**Kong phụ thuộc Postgres:** `infra-kong` dùng ArgoCD **PreSync hooks** (`manifests/kong-prereq/`):

1. Job `kong-wait-postgres` — poll `pg_isready` tới primary PG
2. Job `kong-db-init` — tạo database/user `kong`
3. Sau hooks thành công → Helm chart Kong mới apply

`sync-wave: "2"` trên Application Kong giúp app-of-apps tạo/sync Kong **sau** Postgres/Redis (wave 0). Hooks đảm bảo PG **Running** trước khi Kong pod start.

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

- [ ] Vault `secret/platform/jenkins` seeded → `jenkins-platform-credentials` Bound
- [ ] JCasC credentials `harbor-ci-push`, `github-gitops-push` (không cần UI)
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

Nếu `ImagePullBackOff` → kiểm tra Harbor pull secret (mục 4.2), tag trong `values-images.yaml`, và registry mirror (mục 4.2 — lỗi `x509: certificate is not valid for any names`).

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
kubectl wait -n kong --for=condition=complete job/kong-config-import-phase8 --timeout=300s
kubectl logs -n kong job/kong-config-import-phase8 --tail=20
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
| ImagePullBackOff | Harbor secret + robot account; CI đã push image? Lỗi **x509 harbor-npd.co** → chạy `k3d/configure-harbor-registry-k3d.sh` |
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
kubectl apply -f phase9-gitops-platform/gitops-platform/project.yaml -n argocd
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

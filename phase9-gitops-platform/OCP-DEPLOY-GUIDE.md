# Phase 9 — Triển khai GitOps trên OpenShift (nhánh `dev-ocp`)

Hướng dẫn **end-to-end** cho **OpenShift Container Platform (OCP)** đã có sẵn — nhánh Git **`dev-ocp`**.

- **CI:** Jenkins + Kaniko → Harbor (in-cluster)
- **CD:** ArgoCD upstream (App of Apps)
- **App:** Phase 8 + infra Phase 5
- **Secret:** Vault + External Secrets Operator (ESO)
- **Expose:** OpenShift **Route** (không Traefik / Nginx)
- **Storage:** NFS CSI (`nfs-csi`)

Tài liệu liên quan:

- [OCP-ARCHITECTURE.md](./OCP-ARCHITECTURE.md) — kiến trúc Route, luồng CI/CD
- [PHASE9.md](./PHASE9.md) — tổng quan Phase 9
- [environments/dev-ocp/README.md](./environments/dev-ocp/README.md) — URL và thứ tự apply
- [environments/dev-ocp/INSTALL-NFS-CSI.md](./environments/dev-ocp/INSTALL-NFS-CSI.md) — NFS storage
- [environments/dev-ocp/INSTALL-ARGOCD-UPSTREAM.md](./environments/dev-ocp/INSTALL-ARGOCD-UPSTREAM.md) — cài ArgoCD + SCC

---

## Quan trọng — Thứ tự triển khai (5 giai đoạn)

**ArgoCD chỉ deploy banking app ở giai đoạn cuối**, sau khi platform + infra + CI/CD đã sẵn sàng.

| Giai đoạn | Việc cần làm | ArgoCD deploy app? |
|-----------|--------------|-------------------|
| **0** | NFS CSI driver + StorageClass `nfs-csi` | Không |
| **1** | ArgoCD upstream + SCC + Route + kết nối GitHub | Không |
| **2** | **Platform:** Harbor, Vault, ESO, Jenkins + **Routes** | Không |
| **2b** | **Observability** (tùy chọn): Coroot, OTEL, Linkerd | Không |
| **3** | **Infra:** Postgres, Redis, RabbitMQ, Kong + secret | Không |
| **4** | **CI/CD:** Jenkins build → Harbor → commit `values-images.yaml` | Không |
| **5** | **ArgoCD sync banking app** → rollout Phase 8 | **Có** |

```text
Giai đoạn 0–3              Giai đoạn 4              Giai đoạn 5
─────────────────          ─────────────            ─────────────
NFS CSI + ArgoCD           git push dev-ocp    →    ArgoCD sync
Harbor, Vault, ESO         Jenkins + Kaniko         banking-app-of-apps
Jenkins + Routes           push Harbor              pods Running
Postgres, Redis            commit values-images     https://npd-banking.co
RabbitMQ, Kong             verify pipeline green
```

> **Không** apply `banking-app-of-apps` cho đến khi Giai đoạn 4 hoàn tất (Harbor đã có image).

---

## 0. Kiến trúc sau khi hoàn tất

```text
Browser / oc
    │
    ▼
OpenShift Router (HAProxy) — TLS edge
    │
    ├── argocd-server-argocd.apps.ocp01.npd.co   → ArgoCD (ns argocd)
    ├── harbor-platform.apps.ocp01.npd.co         → Harbor (ns platform)
    ├── jenkins-platform.apps.ocp01.npd.co       → Jenkins (ns platform)
    ├── vault-platform.apps.ocp01.npd.co          → Vault (ns vault)
    ├── kong.apps.ocp01.npd.co                   → Kong proxy (ns kong)
    └── npd-banking.co (/ , /api , /ws)          → frontend + Kong (ns banking)

GitHub (dev-ocp) ──webhook──► Jenkins ──Kaniko──► Harbor
         ▲                           │
         └── commit values-images.yaml ◄┘
                    │
                    ▼
              ArgoCD sync ──► ns banking   ← CHỈ sau Giai đoạn 4
```

| Namespace | Thành phần | URL | Giai đoạn |
|-----------|------------|-----|-----------|
| `argocd` | ArgoCD upstream | `argocd-server-argocd.apps.<domain>` | 1 |
| `platform` | Jenkins, Harbor | `jenkins-platform...`, `harbor-platform...` | 2 |
| `vault` | Vault | `vault-banking...` | 2 |
| `external-secrets` | ESO | — | 2 |
| `observability` | Coroot, OTEL | (tùy chọn — `oc expose` hoặc Route) | 2b |
| `linkerd` / `linkerd-viz` | Linkerd mesh | (tùy chọn) | 2b |
| `postgres` | Postgres HA | 3 |
| `redis` | Redis HA | 3 |
| `kong` | Kong HA | `kong.apps.<domain>` | 3 |
| `rabbit` | RabbitMQ | 3 |
| `banking` | App Phase 8 | **`https://npd-banking.co`** | **5** |

Chi tiết sơ đồ: [OCP-ARCHITECTURE.md](./OCP-ARCHITECTURE.md)

---

## 1. Điều kiện tiên quyết

### Cluster OpenShift

| | Khuyến nghị |
|--|-------------|
| Quyền | `cluster-admin` (cài NFS CSI, SCC, ArgoCD) |
| RAM worker | ≥ 32 GB cho full stack (Harbor + Coroot + Linkerd) |
| CLI | `oc` đã login |
| NFS | Server `10.100.1.180` reachable từ worker (subnet `10.100.1.0/24`) |

### Công cụ trên bastion

```bash
oc version
git --version
helm version   # cài NFS CSI driver
```

### Login cluster

```bash
oc login --token=<TOKEN> --server=https://api.<cluster>:6443
oc get nodes
export CLUSTER_DOMAIN=$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}')
echo "Cluster domain: $CLUSTER_DOMAIN"
# Lab NPD: ocp01.npd.co → route pattern *.apps.ocp01.npd.co
```

### Biến môi trường (dùng xuyên suốt doc)

```bash
export REPO_ROOT=/path/to/banking-demo   # chỉnh path thật
export GIT_BRANCH=dev-ocp
export ARGOCD_NS=argocd
export CLUSTER_DOMAIN=ocp01.npd.co       # hoặc lấy từ oc ở trên
```

---

## 2. Clone repo — nhánh `dev-ocp`

```bash
git clone https://github.com/kevinram164/banking-demo.git
cd banking-demo
git checkout dev-ocp
git pull
```

Repo: **`https://github.com/kevinram164/banking-demo.git`**

Cấu hình môi trường: [`environments/dev-ocp/gitops-env.yaml`](./environments/dev-ocp/gitops-env.yaml)

### Tùy chỉnh cluster domain (nếu khác `ocp01.npd.co`)

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/customize-cluster-domain.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/customize-cluster-domain.sh "$CLUSTER_DOMAIN"
git diff phase9-gitops-platform/environments/dev-ocp
# commit + push nếu đổi domain
```

---

## 3. Giai đoạn 0 — NFS CSI Storage

Mọi PVC (Harbor, Jenkins, Postgres, Redis, RabbitMQ, Coroot…) dùng StorageClass **`nfs-csi`**.

Hướng dẫn đầy đủ: [INSTALL-NFS-CSI.md](./environments/dev-ocp/INSTALL-NFS-CSI.md)

```bash
# Namespace + PodSecurity privileged
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/00-namespace.yaml

# Helm install csi-driver-nfs (xem INSTALL-NFS-CSI.md §3)
helm repo add csi-driver-nfs https://raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs/master/charts
helm install csi-driver-nfs csi-driver-nfs/csi-driver-nfs -n csi-driver-nfs --version v4.11.0

# SCC cho CSI pods
chmod +x phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/scc.sh
./phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/scc.sh

# StorageClass
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/storageclass.yaml

# Test PVC
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/test-pvc.yaml
oc get pvc -n nfs-test
```

Kiểm tra:

```bash
oc get sc nfs-csi
oc get pods -n csi-driver-nfs
```

**Checkpoint Giai đoạn 0:** `nfs-csi` là default SC (hoặc chỉ định rõ trong values); PVC test `Bound`.

---

## 4. Giai đoạn 1 — ArgoCD bootstrap

ArgoCD cài **ngoài GitOps** lần đầu (bootstrap). Chi tiết: [INSTALL-ARGOCD-UPSTREAM.md](./environments/dev-ocp/INSTALL-ARGOCD-UPSTREAM.md)

### 4.1 Cài ArgoCD upstream

```bash
oc create namespace argocd
oc apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.4/manifests/install.yaml

oc wait -n argocd --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server --timeout=600s
```

### 4.2 SCC — theo namespace (khuyến nghị)

Sau khi pod ArgoCD cài xong, patch UID vào dải namespace + gán `nonroot`:

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh argocd
```

Chi tiết: [INSTALL-SCC-HARDENED.md](./environments/dev-ocp/INSTALL-SCC-HARDENED.md)

(Tùy chọn) Tắt Dex nếu không dùng SSO — script trên đã scale 0 mặc định.

### 4.3 Route + insecure mode

```bash
oc patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'
oc patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"url":"https://argocd-server-argocd.apps.'"$CLUSTER_DOMAIN"'"}}'
oc rollout restart deployment argocd-server -n argocd

oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/argocd-route.yaml
```

Lấy password admin:

```bash
oc get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d; echo
# user: admin
```

Mở **https://argocd-server-argocd.apps.ocp01.npd.co** (đổi domain nếu cần).

### 4.4 Kết nối GitHub + AppProject

1. ArgoCD UI → **Settings → Repositories → Connect repo**
2. URL: `https://github.com/kevinram164/banking-demo.git`
3. Nếu private: username + PAT (scope `repo`)

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
```

**Checkpoint Giai đoạn 1:** ArgoCD UI login OK; repo connected; AppProject `banking-platform` tồn tại.

---

## 5. Giai đoạn 2 — Platform (Harbor, Vault, ESO, Jenkins)

ArgoCD quản lý platform; **chưa deploy banking app**.

### 5.1 Apply platform App of Apps

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-app-of-apps.yaml -n argocd
```

ArgoCD UI → **`platform-app-of-apps-dev-ocp`** → **Sync**.

Thứ tự sync wave:

| Wave | App | Ghi chú |
|------|-----|---------|
| 0 | Harbor, Vault, External Secrets (controller) | Chờ pod Running |
| 1 | External Secrets config (`jenkins-platform-credentials`) | Seed Vault `secret/platform/jenkins` trước |
| 2 | Jenkins | JCasC đọc credential từ K8s secret (Vault) |

Theo dõi:

```bash
oc get pods -n platform
oc get pods -n vault
oc get pods -n external-secrets
```

### 5.2 SCC cho platform

Sau khi Harbor/Jenkins sync xong:

```bash
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh platform
```

### 5.3 Routes — expose UI platform

Sau khi Harbor, Jenkins, Vault **Running**:

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-routes-app-of-apps.yaml -n argocd
# ArgoCD UI → Sync platform-routes-dev-ocp
```

| Route | Host | Backend |
|-------|------|---------|
| Harbor | `harbor-platform.apps.ocp01.npd.co` | `harbor:80` (ns `platform`) |
| Jenkins | `jenkins-platform.apps.ocp01.npd.co` | `jenkins:http` |
| Vault | `vault-platform.apps.ocp01.npd.co` | `vault:8200` (ns `vault`) |
| Coroot | `coroot-platform.apps.ocp01.npd.co` | `coroot-coroot:8080` (ns `observability`) |
| Linkerd Viz | `linkerd-viz-platform.apps.ocp01.npd.co` | `web:8084` (ns `linkerd-viz`) |

Manifest: [`environments/dev-ocp/ocp-values/routes/`](./environments/dev-ocp/ocp-values/routes/)

### 5.4 Harbor

1. UI: **https://harbor-platform.apps.ocp01.npd.co** — đổi admin password
2. Tạo project **`banking-demo`**
3. Robot accounts: **`ci-push`** (Jenkins push), **`k8s-pull`** (cluster pull)

**Pull secret** — seed Vault `secret/platform/harbor-pull` (robot `k8s-pull`); ESO tự tạo `harbor-pull-creds` trong ns `banking` + `platform` (xem [vault/README.md](./vault/README.md) mục 5.5). **Không** `oc create secret` thủ công.

```bash
# Trong pod vault-0 (sau khi tạo robot k8s-pull trên Harbor UI)
vault kv put secret/platform/harbor-pull \
  registry='harbor-platform.apps.ocp01.npd.co' \
  username='robot$banking-demo+k8s-pull' \
  password='ROBOT_TOKEN'
```

Sau sync `platform-external-secrets-config`:

```bash
oc get externalsecret harbor-pull-creds -n banking
oc get secret harbor-pull-creds -n banking
```

> **OCP vs k3d:** Không cần registry mirror `registries.yaml`. Kaniko dùng `kanikoSkipTlsVerify: true` trong `Jenkinsfile`; kubelet pull qua Route TLS của OpenShift Router.

### 5.5 Vault + External Secrets

Chi tiết CLI: [vault/README.md](./vault/README.md). **Thứ tự bắt buộc** — đảo bước sẽ lỗi `InvalidProviderConfig` / `SecretSyncedError`.

#### Bước 1 — Seed KV trong pod Vault

```bash
oc get pods -n vault   # vault-0 Running
oc exec -it vault-0 -n vault -- sh
```

Trong pod:

```sh
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

vault kv put secret/banking/db \
  DATABASE_URL='postgresql://banking:bankingpass@postgres-ha-postgresql.postgres.svc.cluster.local:5432/banking' \
  REDIS_URL='redis://redis-ha-redis-master.redis.svc.cluster.local:6379/0'

vault kv put secret/banking/rabbitmq \
  RABBITMQ_URL='amqp://banking:bankingpass@rabbitmq.rabbit.svc.cluster.local:5672/'

vault kv put secret/rabbitmq/admin \
  username='banking' \
  password='bankingpass'

vault kv put secret/platform/harbor-pull \
  registry='harbor-platform.apps.ocp01.npd.co' \
  username='robot$banking-demo+k8s-pull' \
  password='HARBOR_K8S_PULL_TOKEN'
```

UI lab: **https://vault-platform.apps.ocp01.npd.co**, token **`root`**.

#### Bước 2 — Sync ESO controller

ArgoCD: `platform-external-secrets` → Synced / Healthy.

#### Bước 3 — Tạo `vault-token` trước ClusterSecretStore

```bash
oc create secret generic vault-token \
  --from-literal=token=root \
  -n external-secrets
```

#### Bước 4 — Namespace + sync ExternalSecret

```bash
oc create ns banking --dry-run=client -o yaml | oc apply -f -
oc create ns rabbit --dry-run=client -o yaml | oc apply -f -
```

ArgoCD: `platform-external-secrets-config`

#### Bước 5 — Kiểm tra

```bash
oc get clustersecretstore vault-backend
oc get externalsecret -A
oc get secret banking-db-secret -n banking
oc get secret harbor-pull-creds -n banking
```

Force reconcile nếu cần:

```bash
oc annotate clustersecretstore vault-backend force-sync=$(date +%s) --overwrite
oc annotate externalsecret banking-db-secret -n banking force-sync=$(date +%s) --overwrite
```

### 5.6 Jenkins — cấu hình CI

**Mục tiêu:** push nhánh `dev-ocp` → Jenkins Kaniko → Harbor → commit `values-images.yaml`.

#### Bước 1 — Đợi Jenkins Running

```bash
oc get pods -n platform -l app.kubernetes.io/component=jenkins-controller
```

#### Bước 2 — Đăng nhập

| | |
|---|---|
| URL | https://jenkins-platform.apps.ocp01.npd.co |
| User | `admin` |
| Password | `ChangeMe-Jenkins` (hoặc lấy từ secret) |

```bash
oc get secret jenkins -n platform \
  -o jsonpath='{.data.jenkins-admin-password}' | base64 -d; echo
```

#### Bước 3 — Shared Library (tự động JCasC)

| Tham số | Giá trị |
|---------|---------|
| Library | `banking-demo` |
| Branch | **`dev-ocp`** |
| Path | `phase9-gitops-platform/jenkins-shared-library` |

#### Bước 4 — Secret trong Vault (admin + CI)

Seed Vault (trong pod `vault-0`):

```bash
# Robot Harbor — pipeline đọc trực tiếp (không Jenkins credential)
vault kv put secret/platform/harbor \
  username='robot$banking-demo+ci-push' \
  password='HARBOR_ROBOT_TOKEN'

# GitHub PAT — push GitOps
vault kv put secret/platform/github \
  username='kevinram164' \
  pat='github_pat_xxxx'

# Chỉ admin Jenkins (+ webhook tùy chọn)
vault kv put secret/platform/jenkins \
  admin_username='admin' \
  admin_password='YOUR_JENKINS_ADMIN_PASSWORD'
```

Bật Vault Kubernetes auth cho agent `jenkins-kaniko` (một lần, trên bastion):

```bash
export VAULT_TOKEN=root
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/vault-setup-jenkins-k8s-auth.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/vault-setup-jenkins-k8s-auth.sh
```

Kiểm tra ESO (chỉ admin):

```bash
oc get externalsecret jenkins-platform-credentials -n platform
oc get secret jenkins-platform-credentials -n platform
```

Sync Jenkins → restart pod nếu cần:

```bash
oc delete pod jenkins-0 -n platform
```

#### Bước 5 — ServiceAccount Kaniko + SCC (UID 0)

Kaniko trên OpenShift cần **UID 0** để `chown` layer (`operation not permitted` nếu chỉ dùng restricted SCC).

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/jenkins-kaniko-scc-setup.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/jenkins-kaniko-scc-setup.sh
```

Script tạo SA `jenkins-kaniko` + SCC `jenkins-kaniko-root` (chỉ SA này, không `anyuid` cả namespace).

#### Bước 6 — Multibranch Pipeline

1. **New Item** → `banking-demo` → **Multibranch Pipeline**
2. Git: `https://github.com/kevinram164/banking-demo.git`
3. **Filter by name:** Include `dev-ocp`
4. Script Path: `Jenkinsfile` (root — đã cấu hình Harbor OCP)

#### Bước 7 — Webhook (tùy chọn)

GitHub → Webhooks → `https://jenkins-platform.apps.ocp01.npd.co/github-webhook/`

**Checkpoint Giai đoạn 2:** Harbor UI + project `banking-demo`; Vault seeded (harbor/github/jenkins); Jenkins login OK; Vault K8s auth cho `jenkins-kaniko`.

---

## 6. Giai đoạn 2b — Observability (tùy chọn)

Coroot + OpenTelemetry + Linkerd. Chi tiết: [observability/README.md](./observability/README.md)

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/observability-app-of-apps.yaml -n argocd
```

ArgoCD UI → **`observability-app-of-apps-dev-ocp`** → **Sync**.

> **AppProject:** Chart `linkerd-viz` tạo `ClusterRoleBinding` trong **`kube-system`** (`tap-auth-reader`). AppProject `banking-platform` phải cho phép destination `kube-system` — xem `environments/dev-ocp/appproject.yaml`. Nếu thiếu → `namespace kube-system is not permitted in project 'banking-platform'`.

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
```

| Wave | App |
|------|-----|
| 0 | coroot-operator, linkerd-crds, linkerd-identity-bootstrap |
| 1 | otel-collector, linkerd-control-plane |
| 2 | coroot-ce, linkerd-viz |

Linkerd trên OCP có thể cần SCC `privileged` cho namespace `linkerd`:

```bash
oc adm policy add-scc-to-group privileged system:serviceaccounts:linkerd
oc adm policy add-scc-to-group privileged system:serviceaccounts:linkerd-viz
```

**Coroot Prometheus** (embedded) chạy UID **65534** — không khớp dải UID namespace `observability`:

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/coroot-scc-setup.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/coroot-scc-setup.sh
```

Nếu ReplicaSet `prometheus-*` báo `runAsUser: Invalid value: 65534` → chạy script trên.

**Routes UI** (GitOps — cùng app `platform-routes-dev-ocp`, sync sau observability pods Running):

| UI | URL |
|----|-----|
| Coroot | https://coroot-platform.apps.ocp01.npd.co |
| Linkerd Viz | https://linkerd-viz-platform.apps.ocp01.npd.co |

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-routes-app-of-apps.yaml -n argocd
# ArgoCD → Sync platform-routes-dev-ocp
oc get route -n observability coroot-platform
oc get route -n linkerd-viz linkerd-viz-platform
```

**Checkpoint Giai đoạn 2b:** `oc get pods -n observability`; `linkerd check` pass (nếu dùng mesh).

---

## 7. Giai đoạn 3 — Infra (Postgres, Redis, RabbitMQ, Kong)

### StorageClass

Trên `dev-ocp`, mọi StatefulSet dùng **`nfs-csi`** (đã cấu hình trong ArgoCD Application manifests).

| Thành phần | StorageClass |
|------------|--------------|
| Harbor, Jenkins | `nfs-csi` |
| Postgres, Redis | `nfs-csi` |
| RabbitMQ | `nfs-csi` |

Nếu PVC cũ sai SC — xóa STS + PVC rồi sync lại (chỉ khi chưa có data quan trọng):

```bash
oc delete sts -n redis redis-ha-node --cascade=orphan
oc delete pvc -n redis --all
```

### 7.1 Apply infra App of Apps

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/infra-app-of-apps.yaml -n argocd
```

ArgoCD UI → **`infra-app-of-apps-dev-ocp`** → **Sync**.

Thứ tự sync wave:

| Wave | App | Ghi chú |
|------|-----|---------|
| 0 | Postgres, Redis | PVC Bound + pod Running |
| 1 | RabbitMQ | Sau postgres/redis |
| 2 | Kong | PreSync hook chờ PG Ready + tạo DB `kong` |

Theo dõi:

```bash
oc get pods -n postgres
oc get pods -n redis
oc get pods -n rabbit
oc get pods -n kong
```

> **Bitnami OCI 401:** Chart phải dùng `https://charts.bitnami.com/bitnami`, không `oci://registry-1.docker.io/bitnamicharts`.
>
> **ImagePullBackOff:** Values dùng `bitnamilegacy/*` + `global.security.allowInsecureImages: true`.

**Checkpoint Giai đoạn 3:** Tất cả pod infra Running; ESO secret `banking` / `rabbit` đã sync.

---

## 8. Giai đoạn 4 — CI/CD (Jenkins → Harbor → Git)

Mục tiêu: pipeline build image và commit tag vào Git **trước khi** ArgoCD deploy app.

### 8.1 Chạy pipeline lần đầu

```bash
# Sửa code Phase 8 hoặc trigger build trên Jenkins UI
git add phase8-application-v3/
git commit -m "feat: first CI build on dev-ocp"
git push origin dev-ocp
```

Jenkins pipeline kỳ vọng:

1. Kaniko build từ Dockerfile Phase 8
2. Push `harbor-platform.apps.ocp01.npd.co/banking-demo/<service>:<short-sha>`
3. Commit + push `phase9-gitops-platform/gitops/values-images.yaml`

Verify:

```bash
# Harbor UI — project banking-demo có image
git pull origin dev-ocp
git log -1 --oneline -- phase9-gitops-platform/gitops/values-images.yaml
```

### 8.2 Checklist CI/CD

- [ ] Vault `secret/platform/harbor` + `secret/platform/github` seeded
- [ ] Vault `secret/platform/harbor-pull` + ESO `harbor-pull-creds` (ns banking)
- [ ] Vault K8s auth + role `jenkins-kaniko` (`vault-setup-jenkins-k8s-auth.sh`)
- [ ] Vault `secret/platform/jenkins` (admin) + ESO sync
- [ ] SA `jenkins-kaniko` tồn tại
- [ ] Multibranch filter **`dev-ocp`**
- [ ] Pipeline green end-to-end

**Checkpoint Giai đoạn 4:** Harbor có image; `values-images.yaml` committed; Jenkins green.

---

## 9. Giai đoạn 5 — ArgoCD deploy banking app

**Chỉ thực hiện sau Giai đoạn 4.**

### 9.1 Apply banking App of Apps

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/banking-app-of-apps.yaml -n argocd
```

ArgoCD UI → **`banking-app-of-apps-dev-ocp`** → **Sync** (lần đầu sync thủ công).

Apps:

- `banking-namespace`
- `banking-api-producer`, auth, account, transfer, notification
- `banking-frontend`, `banking-ingress` (ingress Helm **tắt** — Route thay thế)

```bash
oc get applications -n argocd | grep banking
oc get pods -n banking
```

`ImagePullBackOff` → kiểm tra Vault `platform/harbor-pull`, ESO `harbor-pull-creds`, tag trong `values-images.yaml`, CI đã push image.

### 9.2 Banking Routes

Routes banking đã nằm trong `platform-routes-dev-ocp` (sync ở Giai đoạn 2):

| Route | Path | Backend |
|-------|------|---------|
| `npd-banking.co` | `/` | `frontend` |
| `npd-banking.co` | `/api` | `kong-proxy-ext` → Kong |
| `npd-banking.co` | `/ws` | `kong-proxy-ext` → Kong |

**DNS:** `npd-banking.co` trỏ A/CNAME tới OpenShift Router IP, hoặc thêm vào hosts file máy client.

```bash
oc get route -n banking
oc get route -n kong kong-proxy
```

### 9.3 Kong Phase 8 routes

```bash
oc apply -f phase8-application-v3/kong-ha/kong-import-job.yaml
oc wait -n kong --for=condition=complete job/kong-config-import-phase8 --timeout=300s
oc logs -n kong job/kong-config-import-phase8 --tail=20
oc rollout restart deployment -n kong -l app.kubernetes.io/name=kong
```

CORS origins trong job đã trỏ `https://npd-banking.co`.

Verify:

```bash
curl -sk https://npd-banking.co/ | head
curl -sk https://npd-banking.co/api/health
```

### 9.4 (Tùy chọn) Root App of Apps

Sau khi mọi thứ ổn:

```bash
./phase9-gitops-platform/environments/dev-ocp/apply-argocd.sh
# hoặc:
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/app-of-apps.yaml -n argocd
```

Root adopt các nhóm app-of-apps đã apply trước.

**Checkpoint Giai đoạn 5:** Banking pods Running; **https://npd-banking.co** mở được.

---

## 10. Luồng phát triển hàng ngày

```text
git push dev-ocp  →  Jenkins build  →  Harbor  →  commit values-images.yaml
                                                          ↓
                                              ArgoCD auto-sync banking apps
                                                          ↓
                                              rollout pods ns banking
```

```bash
git push origin dev-ocp
oc get applications -n argocd -w
oc get pods -n banking
```

---

## 11. Checklist hoàn tất

### Giai đoạn 0
- [ ] `oc get sc nfs-csi` — default hoặc chỉ định trong values
- [ ] PVC test `Bound`

### Giai đoạn 1
- [ ] `oc login` OK
- [ ] ArgoCD pods Running (SCC đã gán)
- [ ] **https://argocd-server-argocd.apps.`<domain>`** — login OK
- [ ] Repo connected, branch `dev-ocp`

### Giai đoạn 2 — Platform
- [ ] Harbor UI + project `banking-demo` + robot accounts
- [ ] Routes Harbor / Jenkins / Vault truy cập được
- [ ] Vault seeded + ESO sync
- [ ] Jenkins + Multibranch job `dev-ocp`

### Giai đoạn 3 — Infra
- [ ] Postgres, Redis, RabbitMQ, Kong pods Running
- [ ] PVC dùng `nfs-csi`

### Giai đoạn 4 — CI/CD
- [ ] Push code → Jenkins green
- [ ] Image trên Harbor
- [ ] `values-images.yaml` committed

### Giai đoạn 5 — App
- [ ] Banking pods Running trong `banking`
- [ ] Kong routes imported
- [ ] **https://npd-banking.co** — Banking Demo UI

---

## 12. Xử lý lỗi nhanh (OCP)

**Runbook đầy đủ:** [environments/dev-ocp/INSTALL-TROUBLESHOOTING.md](./environments/dev-ocp/INSTALL-TROUBLESHOOTING.md) (Vault image UBI, Harbor SCC/NFS, CSR kubelet, Jenkins ESO).

| Triệu chứng | Cách sửa |
|-------------|----------|
| Pod `Forbidden` SCC | `namespace-scc-setup.sh <ns>` — xem INSTALL-SCC-HARDENED.md |
| Prometheus `runAsUser 65534` invalid | `coroot-scc-setup.sh` (Coroot embedded Prometheus) |
| Harbor `Permission denied` entrypoint | `harbor-scc-setup.sh` — **không** patch harbor-* bằng namespace-scc-setup |
| Harbor DB `initdb Permission denied` | `chmod 777` subdir PVC trên NFS server — xem INSTALL-TROUBLESHOOTING.md §3.3 |
| `oc logs` tls internal error | Approve CSR Pending: `oc get csr -o name \| xargs oc adm certificate approve` |
| Vault ImagePullBackOff Red Hat | Image `*-ubi`; tắt injector — xem INSTALL-TROUBLESHOOTING.md §2 |
| ArgoCD Route 502 | `server.insecure=true` + Route TLS `edge` + `targetPort: http` — xem [INSTALL-ARGOCD-UPSTREAM.md](./environments/dev-ocp/INSTALL-ARGOCD-UPSTREAM.md) |
| PVC Pending | Kiểm tra NFS CSI pods; worker mount được NFS server |
| `jenkins-platform-credentials` not found | Seed Vault + vault-token + sync ESO config — xem INSTALL-TROUBLESHOOTING.md §6 |
| `vault-token` not found | Tạo secret trước ClusterSecretStore |
| ImagePullBackOff | Vault `platform/harbor-pull` seeded? ESO `harbor-pull-creds` synced? CI đã push image? |
| Banking sync quá sớm | Quay lại Giai đoạn 4 |
| ArgoCD OutOfSync | Sync từng app; kiểm tra branch `dev-ocp` |
| Kaniko push 401 | Robot Harbor sai user/token |
| Route `Missing` / not found | Sync `platform-routes-dev-ocp` — xem INSTALL-TROUBLESHOOTING.md §9 |

---

## 13. Lệnh tham chiếu nhanh

```bash
# Trạng thái tổng
oc get pods -A | grep -v Running
oc get applications -n argocd

# Apply theo giai đoạn (dev-ocp)
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-app-of-apps.yaml -n argocd
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-routes-app-of-apps.yaml -n argocd
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/observability-app-of-apps.yaml -n argocd
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/infra-app-of-apps.yaml -n argocd
# ... CI/CD pipeline green ...
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/banking-app-of-apps.yaml -n argocd

# Logs app
oc logs -n banking -l app=auth-service --tail=50
```

---

## 14. Cấu trúc nhánh `dev-ocp`

```text
phase9-gitops-platform/
├── OCP-DEPLOY-GUIDE.md          # File này
├── OCP-ARCHITECTURE.md
├── gitops-platform/             # ArgoCD Application manifests (Helm sources)
│   └── applications/
│       ├── platform/            # Harbor, Vault, ESO, Jenkins (nfs-csi, no Ingress)
│       ├── observability/
│       ├── infra/               # Postgres, Redis, RabbitMQ, Kong
│       └── banking/
├── gitops/
│   ├── values-images.yaml       # CI cập nhật image tag
│   └── values-observability.yaml
└── environments/dev-ocp/
    ├── README.md
    ├── gitops-env.yaml          # Domain, Harbor host, branch
    ├── appproject.yaml
    ├── apply-argocd.sh
    ├── INSTALL-NFS-CSI.md
    ├── INSTALL-ARGOCD-UPSTREAM.md
    ├── ocp-values/routes/       # OpenShift Routes
    ├── scripts/
    └── argocd/applications/     # App of Apps dev-ocp
```

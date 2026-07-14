# Troubleshooting — OpenShift dev-ocp (ocp01.npd.co)

Runbook xử lý lỗi thường gặp khi triển khai Phase 9 trên **OpenShift UPI/bare metal**. Dùng kèm [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md).

---

## Mục lục

1. [Thứ tự SCC / script](#1-thứ-tự-scc--script)
2. [Vault](#2-vault)
3. [Harbor](#3-harbor)
4. [NFS CSI & PVC](#4-nfs-csi--pvc)
5. [Kubelet TLS / CSR (oc logs, UI log)](#5-kubelet-tls--csr-oc-logs-ui-log)
6. [Jenkins & External Secrets](#6-jenkins--external-secrets)
7. [Lệnh chẩn đoán nhanh](#7-lệnh-chẩn-đoán-nhanh)
8. [Script tham chiếu](#8-script-tham-chiếu)

---

## 1. Thứ tự SCC / script

```text
NFS CSI (INSTALL-NFS-CSI.md)
  → ArgoCD + namespace-scc-setup.sh argocd
  → Sync platform-app-of-apps
  → harbor-scc-setup.sh          # Harbor TRƯỚC hoặc SAU, nhưng BẮT BUỘC cho harbor-*
  → namespace-scc-setup.sh platform   # Jenkins; BỎ QUA harbor-* (script tự skip)
  → namespace-scc-setup.sh vault
```

| Namespace | Component | Cách xử lý SCC |
|-----------|-----------|----------------|
| `argocd` | ArgoCD upstream | `namespace-scc-setup.sh argocd` |
| `platform` | Jenkins | `namespace-scc-setup.sh platform` |
| `platform` | Harbor | **`harbor-scc-setup.sh`** — UID **999–10000**, không patch dải OCP |
| `vault` | Vault server | `namespace-scc-setup.sh vault` + image UBI (xem §2) |
| `csi-driver-nfs` | NFS CSI | `ocp-values/nfs-csi/scc.sh` — privileged |

Chi tiết SCC: [INSTALL-SCC-HARDENED.md](./INSTALL-SCC-HARDENED.md)

---

## 2. Vault

### 2.1 `vault-k8s:1.4.2` / `vault:1.17.2` — Image not found (Red Hat registry)

**Triệu chứng**

```text
registry.connect.redhat.com/hashicorp/vault-k8s:1.4.2 — name unknown
registry.connect.redhat.com/hashicorp/vault:1.17.2 — name unknown
```

**Nguyên nhân:** OpenShift redirect image HashiCorp sang `registry.connect.redhat.com`; tag Docker Hub **không có** trên Red Hat (cần suffix `-ubi`).

**Cấu hình Git** (`gitops-platform/applications/platform/vault.yaml`):

- `injector.enabled: false` — Phase 9 dùng ESO, không cần Agent Injector
- `global.openshift: true`
- `server.image`: `registry.connect.redhat.com/hashicorp/vault:1.17.2-ubi`
- `syncPolicy.automated.prune: true` — xóa deployment injector cũ

**Trên cluster**

```bash
# Xóa injector còn sót (prune:false trước đó)
./phase9-gitops-platform/environments/dev-ocp/scripts/vault-remove-injector.sh

argocd app refresh platform-vault --hard
argocd app sync platform-vault --force

./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh vault
oc get pods -n vault
```

### 2.2 Pod injector vẫn tạo lại sau sync

```bash
argocd app get platform-vault -o yaml | grep -A2 injector
helm get values vault -n vault | grep injector
```

Phải thấy `injector.enabled: false`. Nếu không — sync `platform-app-of-apps-dev-ocp` rồi sync lại `platform-vault`.

---

## 3. Harbor

### 3.1 `Permission denied` — `/harbor/entrypoint.sh` hoặc `/docker-entrypoint.sh`

**Triệu chứng:** `harbor-core`, `harbor-jobservice`, `harbor-database` CrashLoop; log:

```text
exec container process '/harbor/entrypoint.sh': Permission denied
```

**Nguyên nhân:** Chart Harbor hard-code `runAsUser: 10000` (DB/Redis: **999**). `namespace-scc-setup.sh platform` đã patch sang UID dải namespace → image không execute được entrypoint.

**Sửa**

```bash
./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-scc-setup.sh
# KHÔNG patch lại harbor-* bằng namespace-scc-setup
```

Manifest: `ocp-values/scc/harbor-scc.yaml`, SA `harbor`, Helm `serviceAccountName: harbor` trên mọi component.

### 3.2 `CAP_MCK invalid capability`

**Triệu chứng**

```text
Error: failed to drop cap CAP_MCK invalid capability: CAP_MCK
```

**Nguyên nhân:** SCC có `requiredDropCapabilities: MCK` — capability không hợp lệ trên OCP 4.x.

**Sửa:** `harbor-scc.yaml` **không** set `requiredDropCapabilities`. Apply lại:

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/scc/harbor-scc.yaml
oc delete pod -n platform -l app.kubernetes.io/instance=harbor
```

### 3.3 `initdb: Permission denied` — `pgdata` (Harbor Postgres trên NFS)

**Triệu chứng**

```text
initdb: error: could not create directory "/var/lib/postgresql/data/pgdata": Permission denied
```

**Nguyên nhân:** NFS CSI tạo subdir với `mountPermissions` mặc định **0750** (root). Postgres chạy UID **999** không ghi được.

**Lưu ý:** `parameters` của StorageClass **không sửa được** sau khi tạo (`updates to parameters are forbidden`).

**Sửa PVC hiện tại — trên NFS server** (`10.100.1.180`):

```bash
chmod -R 777 /shares/registry/platform/database-data-harbor-database-0

# Các PVC platform khác (phòng lỗi tương tự)
chmod -R 777 /shares/registry/platform/harbor-jobservice
chmod -R 777 /shares/registry/platform/harbor-registry
chmod -R 777 /shares/registry/platform/data-harbor-redis-0
chmod -R 777 /shares/registry/platform/jenkins
```

**Trên bastion**

```bash
oc delete pod harbor-database-0 -n platform --force --grace-period=0
oc logs harbor-database-0 -n platform -c database --tail=30
```

**Reset PVC (lab)**

```bash
./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-reset-database-pvc.sh
```

Script dùng `oc delete pvc --wait=false` để tránh treo chờ CSI.

**PVC mới sau này:** tạo StorageClass mới có `mountPermissions: "0777"` (xem [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md) §4.1).

### 3.3b ImagePull `x509: certificate signed by unknown authority`

**Triệu chứng:** Banking pods `ErrImagePull` / `ImagePullBackOff`:

```text
pinging container registry harbor-platform.apps.ocp01.npd.co: …
tls: failed to verify certificate: x509: certificate signed by unknown authority
```

**Nguyên nhân:** Image dùng host Route HTTPS (`harbor-platform.apps…`). Cert do OpenShift Router ký — CRI-O/kubelet **không** tin CA đó (khác pull secret auth).

**Sửa (Vault + ESO + ConfigMap):**

```bash
export VAULT_TOKEN=root
./phase9-gitops-platform/environments/dev-ocp/scripts/vault-seed-harbor-registry-ca.sh
# Sync platform-external-secrets-config trên ArgoCD UI
./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-registry-trust-setup.sh
oc get mcp
oc delete pod -n npd-banking --all --force --grace-period=0
```

**Lab nhanh** (không Vault — insecure registry hoặc trust router-ca trực tiếp):

```bash
INSECURE=1 ./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-registry-trust-setup.sh
# hoặc script không có ESO Secret sẽ fallback router-ca
./phase9-gitops-platform/environments/dev-ocp/scripts/harbor-registry-trust-setup.sh
```

### 3.4 `nfs.csi.k8s.io not found` (FailedMount)

**Triệu chứng:** PVC Bound nhưng pod `FailedMount` trên **một worker** cụ thể.

**Kiểm tra**

```bash
oc get csidriver nfs.csi.k8s.io
oc get pods -n csi-driver-nfs -o wide
oc get csinode <worker-hostname> -o yaml | grep nfs.csi
```

**Sửa**

```bash
# Restart CSI node trên worker lỗi
oc delete pod -n csi-driver-nfs <csi-nfs-node-xxx>

# Hoặc schedule tạm sang worker khác
oc patch sts harbor-database -n platform --type=merge -p '
{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":"npd-ocp-worker02.ocp01.npd.co"}}}}}'
oc delete pod harbor-database-0 -n platform --force --grace-period=0
```

---

## 4. NFS CSI & PVC

| Kiểm tra | Lệnh | Kỳ vọng |
|----------|------|---------|
| Driver | `oc get csidriver nfs.csi.k8s.io` | Tồn tại |
| Pods | `oc get pods -n csi-driver-nfs` | Controller + node/worker Running |
| SC | `oc get sc nfs-csi` | Default |
| PVC | `oc get pvc -n platform` | Bound |

Cài đặt đầy đủ: [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md)

**PVC Bound ≠ mount OK trên mọi node** — luôn kiểm tra worker pod đang schedule và CSINode.

---

## 5. Kubelet TLS / CSR (`oc logs`, UI log)

### 5.1 Triệu chứng

```text
Get "https://10.100.1.51:10250/containerLogs/...": remote error: tls: internal error
```

`oc logs`, `oc exec`, Console log **chỉ lỗi trên một số worker** (ví dụ worker01).

### 5.2 Nguyên nhân

Cluster **UPI/bare metal**: CSR `kubernetes.io/kubelet-serving` **Pending** — machine-approver không auto-approve serving cert.

```bash
oc get csr | grep Pending
# REQUESTOR: system:node:npd-ocp-worker01.ocp01.npd.co
```

### 5.3 Approve CSR — lệnh ĐÚNG

**SAI** (tên CSR không chứa `worker01`):

```bash
oc get csr -o name | grep worker01 | xargs oc adm certificate approve   # không match gì
```

**ĐÚNG**

```bash
# Approve tất cả CSR Pending (lab)
oc get csr -o name | xargs oc adm certificate approve

# Hoặc một CSR cụ thể (mới nhất)
oc adm certificate approve csr-xxxxx

# Chỉ worker01
oc get csr -o jsonpath='{range .items[?(@.status.conditions==null)]}{.metadata.name}{"\t"}{.spec.username}{"\n"}{end}' \
  | awk '$2 ~ /worker01/ {print $1}' | xargs oc adm certificate approve
```

**Kiểm tra**

```bash
oc get csr <tên-csr>   # CONDITION: Approved
oc logs harbor-database-0 -n platform -c database --tail=20
```

### 5.4 Dài hạn (UPI)

- Cron trên bastion mỗi 30 phút: `oc get csr -o name | xargs oc adm certificate approve`
- Hoặc [openshift-csr-approver](https://github.com/adfinis/openshift-csr-approver)
- Red Hat: [Approving CSRs on UPI](https://docs.redhat.com/en/documentation/openshift_container_platform/4.17/html/machine_management/managing-user-provisioned-infrastructure-manually)

### 5.5 Dọn CSR Pending cũ

Sau khi một CSR **Approved** mới hoạt động, CSR Pending cũ (hết hạn) có thể xóa:

```bash
oc delete csr csr-old1 csr-old2 ...
```

---

## 6. Jenkins & External Secrets

### 6.1 `secret "jenkins-platform-credentials" not found`

**Nguyên nhân:** Jenkins (wave 2) mount secret trước khi ESO tạo từ Vault.

**Thứ tự**

```text
1. vault-0 Running
2. Seed Vault: secret/platform/jenkins  (thủ công)
3. platform-external-secrets → Synced
4. oc create secret vault-token -n external-secrets
5. platform-external-secrets-config → Synced
6. platform-jenkins → Synced
```

**Seed Vault**

```bash
oc exec -it vault-0 -n vault -- sh -c '
export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root
vault kv put secret/platform/jenkins \
  admin_username=admin \
  admin_password=ChangeMe-Jenkins \
  harbor_username="robot\$banking-demo+ci-push" \
  harbor_password=HARBOR_TOKEN \
  github_username=YOUR_GH_USER \
  github_pat=github_pat_xxxx
'
```

**Kiểm tra ESO**

```bash
oc create secret generic vault-token --from-literal=token=root -n external-secrets --dry-run=client -o yaml | oc apply -f -
oc get externalsecret jenkins-platform-credentials -n platform
oc get secret jenkins-platform-credentials -n platform
```

Chi tiết: [vault/README.md](../../vault/README.md), [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md) §5.5–5.6.

---

## 7. Lệnh chẩn đoán nhanh

```bash
# Pod không Running
oc get pods -A | grep -v Running

# SCC pod đang dùng
./phase9-gitops-platform/environments/dev-ocp/scripts/discover-pod-scc.sh platform

# Platform checkpoint
oc get pods -n platform
oc get pods -n vault
oc get pods -n external-secrets
oc get applications -n argocd | grep -E 'platform|vault|harbor|jenkins'

# Harbor tổng thể
oc get pods -n platform -l app.kubernetes.io/instance=harbor
oc get pvc -n platform

# ArgoCD app
argocd app get platform-harbor
argocd app get platform-vault
```

---

## 8. Script tham chiếu

| Script | Mục đích |
|--------|----------|
| `scripts/harbor-scc-setup.sh` | SA `harbor` + SCC UID 999–10000 + sync Harbor |
| `scripts/harbor-registry-trust-setup.sh` | Trust CA Route Harbor / insecureRegistries (fix x509 pull) |
| `scripts/vault-seed-harbor-registry-ca.sh` | Seed Vault `platform/harbor-registry-ca` từ router-ca |
| `scripts/harbor-reset-database-pvc.sh` | Reset PVC Postgres Harbor (NFS permission / lab) |
| `scripts/vault-remove-injector.sh` | Xóa vault-agent-injector còn sót |
| `scripts/namespace-scc-setup.sh` | Patch UID dải namespace + `nonroot` (skip `harbor-*`) |
| `scripts/discover-pod-scc.sh` | Chẩn đoán SCC từng pod |
| `ocp-values/nfs-csi/scc.sh` | privileged cho CSI node/controller |
| `scripts/coroot-scc-setup.sh` | SCC UID 65534 cho Coroot embedded Prometheus |
| `scripts/coroot-node-agent-scc-setup.sh` | privileged SCC cho Coroot node-agent DaemonSet |
| `scripts/kong-scc-setup.sh` | SCC UID 1000 cho Kong (`kong-uid1000`) |
| `scripts/linkerd-scc-setup.sh` | privileged cho ns `linkerd` + `linkerd-viz` + **`banking`** (sidecar mesh) |
| `scripts/linkerd-load-xt-modules.sh` | modprobe xt_multiport/… trên node (fix linkerd-init) |
| `scripts/approve-pending-csrs.sh` | Approve CSR Pending (UPI lab) |

### Linkerd `Init:CrashLoopBackOff` (`linkerd-init`)

SCC đã OK (pod tạo được) nhưng init exit 1 → thường **iptables-legacy** trên RHCOS.

```bash
oc logs -n linkerd deploy/linkerd-proxy-injector -c linkerd-init 2>&1 | head -20
```

| Log | Fix |
|-----|-----|
| `iptables-save … (legacy): Permission denied` | values `proxyInit.iptablesMode=nft` + `runAsRoot=true` + sync |
| `Extension multiport … missing kernel module` | `./scripts/linkerd-load-xt-modules.sh` rồi `oc apply …/machineconfig/linkerd-xt-modules.yaml` |

**`xt_*` modules:** extension iptables trong kernel (`xt_multiport`, `xt_owner`, `xt_comment`, `xt_REDIRECT`). Linkerd cần chúng để redirect traffic vào sidecar; RHCOS đôi khi không autoload → `modprobe` / MachineConfig. Chi tiết: [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md) (mục Linkerd / `linkerd-init`).


---

## 9. OpenShift Routes — `Missing` / Resource not found

### 9.1 Triệu chứng (ArgoCD)

```text
Health: Missing
Resource not found in cluster: route.openshift.io/v1/Route:harbor-platform
```

Các Route platform: `harbor-platform`, `vault-platform`, `jenkins-platform`, `coroot-platform`, `linkerd-viz-platform` trong app **`platform-routes-dev-ocp`**.

### 9.2 Nguyên nhân

ArgoCD **đã đọc Git** (desired state có Route) nhưng **cluster chưa có** Route đó — chưa sync app routes hoặc sync lỗi.

Đây **không** phải lỗi tên file sai; là **chưa apply** lên cluster.

### 9.3 Sửa

**Bước A — Kiểm tra app (chưa sync thì Route không tồn tại)**

```bash
oc get application platform-routes-dev-ocp -n argocd \
  -o jsonpath='sync={.status.sync.status} health={.status.health.status}{"\n"}'

oc describe application platform-routes-dev-ocp -n argocd | tail -25
```

**Bước B — Sync ArgoCD (bắt buộc sau `oc apply` Application)**

```bash
# Cần git push dev-ocp trước (ArgoCD đọc GitHub, không đọc bastion)
argocd app get platform-routes-dev-ocp
argocd app refresh platform-routes-dev-ocp --hard
argocd app sync platform-routes-dev-ocp --force
```

**Bước C — Apply tay (nếu chưa có argocd CLI hoặc sync lỗi)**

```bash
cd banking-demo
git pull origin dev-ocp

oc apply -k phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/

# Chỉ 3 route platform (nhanh)
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/harbor-route.yaml
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/jenkins-route.yaml
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/vault-route.yaml
```

**Bước D — Kiểm tra**

```bash
oc get route -n platform harbor-platform jenkins-platform
oc get route -n vault vault-platform
```

**Thứ tự:** Harbor/Jenkins/Vault pods **Running** trước → sync `platform-routes-dev-ocp` (wave 3).

### 9.4 Đổi tên `*-banking` → `*-platform` (Harbor/Vault)

| Cũ | Mới |
|----|-----|
| `harbor-banking.apps.ocp01.npd.co` | `harbor-platform.apps.ocp01.npd.co` |
| `vault-banking.apps.ocp01.npd.co` | `vault-platform.apps.ocp01.npd.co` |

Route metadata `name`: `harbor-platform`, `vault-platform` (namespace `platform` / `vault`).

Sau đổi tên Git: sync `platform-routes-dev-ocp` + `platform-harbor` (externalURL) + xóa Route cũ nếu còn:

```bash
oc delete route harbor-banking -n platform --ignore-not-found
oc delete route vault-banking -n vault --ignore-not-found
```

### 9.5 Harbor Route 503 (pod Running nhưng curl 503)

**Triệu chứng:** `curl -skI https://harbor-platform...` → `HTTP/1.0 503`, pod Harbor đều Running.

**Chẩn đoán**

```bash
# Service + endpoint (phải trỏ nginx :8080)
oc describe svc harbor -n platform
oc get endpoints harbor -n platform
oc get pod -n platform -l component=nginx -o wide

# Từ trong cluster
oc run curl-harbor -n platform --rm -it --restart=Never --image=curlimages/curl -- \
  curl -sI http://harbor.platform.svc.cluster.local/

# Trực tiếp nginx pod (thay IP từ oc get pod -o wide)
oc exec -n platform deploy/harbor-nginx -- curl -sI http://127.0.0.1:8080/
```

| Kết quả curl nội bộ | Nguyên nhân |
|---------------------|-------------|
| `200` / `302` | Route OCP — dùng `targetPort: http` (tên port Service), re-apply route |
| `503` | Nginx upstream lỗi — `oc logs deploy/harbor-core -n platform` |
| Connection refused | Service selector / nginx không listen |

**Sửa Route** (`harbor-route.yaml`):

```yaml
port:
  targetPort: http   # không dùng 80 — Service đặt tên port là http
```

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/harbor-route.yaml
curl -skI https://harbor-platform.apps.ocp01.npd.co | head -5
```

**externalURL** phải khớp host Route — sync `platform-harbor`:

```bash
argocd app sync platform-harbor
```

---

## Liên kết

| Tài liệu | Nội dung |
|----------|----------|
| [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md) | Triển khai end-to-end |
| [INSTALL-SCC-HARDENED.md](./INSTALL-SCC-HARDENED.md) | SCC namespace |
| [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md) | NFS storage |
| [INSTALL-ARGOCD-UPSTREAM.md](./INSTALL-ARGOCD-UPSTREAM.md) | ArgoCD + Route |
| [vault/README.md](../../vault/README.md) | Vault + ESO |

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
| `scripts/harbor-reset-database-pvc.sh` | Reset PVC Postgres Harbor (NFS permission / lab) |
| `scripts/vault-remove-injector.sh` | Xóa vault-agent-injector còn sót |
| `scripts/namespace-scc-setup.sh` | Patch UID dải namespace + `nonroot` (skip `harbor-*`) |
| `scripts/discover-pod-scc.sh` | Chẩn đoán SCC từng pod |
| `ocp-values/nfs-csi/scc.sh` | privileged cho CSI node/controller |
| `scripts/approve-pending-csrs.sh` | Approve CSR Pending (UPI lab) |

---

## Liên kết

| Tài liệu | Nội dung |
|----------|----------|
| [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md) | Triển khai end-to-end |
| [INSTALL-SCC-HARDENED.md](./INSTALL-SCC-HARDENED.md) | SCC namespace |
| [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md) | NFS storage |
| [INSTALL-ARGOCD-UPSTREAM.md](./INSTALL-ARGOCD-UPSTREAM.md) | ArgoCD + Route |
| [vault/README.md](../../vault/README.md) | Vault + ESO |

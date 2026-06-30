# NFS CSI Storage — OpenShift (dev-ocp)

Dynamic provisioning PVC qua **NFS CSI driver** (`nfs.csi.k8s.io`) trỏ storage server lab NPD.

| Mục | Giá trị |
|-----|---------|
| NFS server | `10.100.1.180` |
| Export | `/shares/registry` |
| Client được phép | `10.100.1.0/24` |
| StorageClass | `nfs-csi` (default) |
| Driver chart | `csi-driver-nfs` v4.11.0 |

Manifest trong repo: [`ocp-values/nfs-csi/`](./ocp-values/nfs-csi/)

---

## 0. Kiến trúc

```text
PVC (Harbor, Jenkins, Postgres…)
  → StorageClass nfs-csi
    → CSI provisioner nfs.csi.k8s.io
      → subdir trên NFS: /shares/registry/<namespace>/<pvc-name>
        → mount vào pod trên worker OCP
```

**Yêu cầu:** Mọi **worker OCP** phải mount được `10.100.1.180:/shares/registry` (cùng subnet hoặc route/firewall cho phép port NFS).

---

## 1. Kiểm tra NFS server

Trên **NFS server** (`10.100.1.180`):

```bash
exportfs -v
# Kỳ vọng: /shares/registry  10.100.1.0/24(...)
```

---

## 2. Kiểm tra từ bastion (client NFS)

### 2.1 Cài nfs-utils

Lỗi `bad option … need mount.<type> helper` = thiếu client:

```bash
sudo dnf install -y nfs-utils
sudo systemctl enable --now rpcbind 2>/dev/null || true
```

### 2.2 Mount thử

```bash
showmount -e 10.100.1.180

sudo mkdir -p /mnt/nfstest

# Thử NFSv4 trước
sudo mount -t nfs4 10.100.1.180:/shares/registry /mnt/nfstest

# Nếu fail — thử NFSv3
# sudo mount -t nfs -o nfsvers=3 10.100.1.180:/shares/registry /mnt/nfstest

touch /mnt/nfstest/write-test
sudo umount /mnt/nfstest
```

| Lỗi | Xử lý |
|-----|--------|
| `Connection refused` / timeout | Firewall server: TCP/UDP **2049**; worker trong `10.100.1.0/24` |
| `access denied` | Sửa `/etc/exports`, `exportfs -ra` |
| `No such file` | Sai path export |

### 2.3 Kiểm tra từ worker OCP (khuyến nghị)

```bash
NODE=$(oc get nodes -o name | head -1 | cut -d/ -f2)
oc debug node/$NODE -- chroot /host bash -c '
  mount -t nfs4 10.100.1.180:/shares/registry /mnt 2>/dev/null || \
  mount -t nfs -o nfsvers=3 10.100.1.180:/shares/registry /mnt
  touch /mnt/ocp-node-test && umount /mnt
'
```

---

## 3. Cài NFS CSI driver (Helm)

Trên bastion (`oc login` cluster-admin):

```bash
helm repo add csi-driver-nfs https://raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs/master/charts
helm repo update
```

### 3.1 Namespace + PodSecurity (OpenShift bắt buộc)

CSI cần **privileged**, hostPath, hostNetwork — namespace `restricted` sẽ **chặn pod** (triệu chứng: `helm install` OK nhưng **0 pods**).

```bash
oc create namespace csi-driver-nfs --dry-run=client -o yaml | oc apply -f -

oc label namespace csi-driver-nfs \
  pod-security.kubernetes.io/enforce=privileged \
  pod-security.kubernetes.io/audit=privileged \
  pod-security.kubernetes.io/warn=privileged \
  --overwrite
```

Hoặc apply manifest repo:

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/00-namespace.yaml
```

### 3.2 Helm install

```bash
helm upgrade --install csi-driver-nfs csi-driver-nfs/csi-driver-nfs \
  --namespace csi-driver-nfs \
  --version 4.11.0 \
  --set controller.replicas=2 \
  --set kubeletDir=/var/lib/kubelet
```

### 3.3 SCC cho ServiceAccount

```bash
oc adm policy add-scc-to-user privileged \
  system:serviceaccount:csi-driver-nfs:csi-nfs-node-sa

oc adm policy add-scc-to-user privileged \
  system:serviceaccount:csi-driver-nfs:csi-nfs-controller-sa
```

Nếu tên SA khác:

```bash
oc get sa -n csi-driver-nfs
```

### 3.4 Xác nhận driver

```bash
watch oc get pods -n csi-driver-nfs
```

Kỳ vọng:

| Pod | Số lượng |
|-----|----------|
| `csi-nfs-node-*` | 1 / worker |
| `csi-nfs-controller-*` | 2 (hoặc 1) |

```bash
oc get csidriver nfs.csi.k8s.io
```

**Gỡ cài lại** (nếu cài trước khi label/SCC):

```bash
helm uninstall csi-driver-nfs -n csi-driver-nfs
# label + SCC lại → helm upgrade --install ...
```

---

## 4. StorageClass `nfs-csi`

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/storageclass.yaml
oc get sc nfs-csi
```

Nội dung chính:

```yaml
provisioner: nfs.csi.k8s.io
parameters:
  server: "10.100.1.180"
  share: "/shares/registry"
  subDir: "${pvc.metadata.namespace}/${pvc.metadata.name}"
mountOptions:
  - nfsvers=4.1
  - hard
```

Nếu provision fail — đổi sang NFSv3:

```bash
oc patch storageclass nfs-csi --type=json \
  -p='[{"op":"replace","path":"/mountOptions","value":["nfsvers=3","hard"]}]'
```

### 4.1 `mountPermissions` và Harbor Postgres

CSI driver mặc định tạo subdir NFS với quyền **0750** (root). Harbor Postgres (UID **999**) cần ghi `pgdata` → lỗi:

```text
initdb: error: could not create directory ".../pgdata": Permission denied
```

**Khi tạo StorageClass lần đầu**, thêm trong `parameters`:

```yaml
mountPermissions: "0777"   # lab; production dùng 0770 + chown 999 trên NFS
```

**Lưu ý:** Kubernetes **cấm sửa** `parameters` sau khi SC đã tạo:

```text
updates to parameters are forbidden
```

| Tình huống | Cách xử lý |
|------------|------------|
| PVC **đã Bound** | `chmod -R 777` subdir trên NFS server (`/shares/registry/<ns>/<pvc-name>`) |
| Cluster **mới** / PVC mới | Tạo SC mới `nfs-csi-v2` có `mountPermissions: "0777"` (xem [INSTALL-TROUBLESHOOTING.md](./INSTALL-TROUBLESHOOTING.md) §3.3) |

---

## 5. Test PVC

**Không** test trong project `default` trên OCP (dễ nhầm `oc project`). Dùng project riêng:

```bash
oc new-project nfs-test --dry-run=client -o yaml | oc apply -f - 2>/dev/null || oc project nfs-test

oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/nfs-csi/test-pvc.yaml

# Luôn chỉ rõ -n khi get
oc get pvc -n nfs-test
oc describe pvc test-nfs -n nfs-test
```

| STATUS | Ý nghĩa |
|--------|---------|
| **Bound** | NFS CSI hoạt động |
| **Pending** | Xem `oc describe pvc` + `oc get pods -n csi-driver-nfs` |

Trên NFS server sau khi Bound:

```bash
ls -la /shares/registry/nfs-test/test-nfs/
```

Dọn test:

```bash
oc delete pvc test-nfs -n nfs-test
oc delete project nfs-test
```

### Lệnh hay nhầm

```bash
# PVC — cần đúng namespace
oc get pvc -n nfs-test
oc get pvc -A | grep test-nfs

# PV — cluster-scoped, KHÔNG dùng -n
oc get pv
```

---

## 6. Gắn vào banking-demo (Phase 9)

Sau `nfs-csi` Bound, đổi StorageClass trong GitOps values:

| File | Field |
|------|--------|
| `environments/dev-ocp/gitops-env.yaml` | `openshift.storageClass: nfs-csi` |
| `gitops-platform/applications/platform/harbor.yaml` | `persistence.*.storageClass` |
| `gitops-platform/applications/platform/jenkins.yaml` | `persistence.storageClass` |
| Infra Postgres/Redis/Rabbit values | `storageClass` |

```bash
oc get sc
# DEFAULT = nfs-csi
```

Sync lại ArgoCD apps platform + infra. PVC mới dùng NFS; PVC cũ (gp3/local) **không** tự migrate.

---

## 7. Xử lý lỗi

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| `mount: bad option` (bastion) | Thiếu `nfs-utils` | `dnf install nfs-utils` |
| Helm OK, **0 pods** `csi-driver-nfs` | PodSecurity restricted | Label namespace `privileged` + SCC |
| Pod CSI CrashLoop | Thiếu SCC | `privileged` cho node/controller SA |
| PVC Pending `provisioning failed` | NFS unreachable từ worker | Test mount từ node; firewall |
| PVC Pending mount error v4 | Server chỉ v3 | `mountOptions: nfsvers=3` |
| `oc get pvc` NotFound | Sai namespace | `oc project` / `oc get pvc -A` |
| `storageclass gp3-csi not found` | Chưa đổi values | `nfs-csi` trong Helm/ArgoCD |

### Log hữu ích

```bash
oc get events -n nfs-test --sort-by='.lastTimestamp'
oc logs -n csi-driver-nfs -l app=csi-nfs-controller --tail=50
oc describe pvc <name> -n <namespace>
```

---

## 8. Gỡ NFS CSI (lab)

```bash
helm uninstall csi-driver-nfs -n csi-driver-nfs
oc delete sc nfs-csi
oc delete namespace csi-driver-nfs
# Dữ liệu trên NFS server: xóa thủ công subdir trong /shares/registry/
```

---

## Tham chiếu

- [kubernetes-csi/csi-driver-nfs](https://github.com/kubernetes-csi/csi-driver-nfs)
- [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md)
- [ocp-values/README.md](./ocp-values/README.md)

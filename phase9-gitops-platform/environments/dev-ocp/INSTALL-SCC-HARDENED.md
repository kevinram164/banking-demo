# SCC theo namespace — OpenShift (dev-ocp)

**Hướng chính:** mỗi namespace có dải UID riêng (`openshift.io/sa.scc.uid-range`). Patch workload vào dải đó, gán SCC **`nonroot`** cho **`system:serviceaccounts:<namespace>`** — một lần cho cả namespace.

Không dùng `anyuid` (cho phép mọi UID kể cả root).

---

## Mô hình

```text
Namespace argocd
  annotation: openshift.io/sa.scc.uid-range = 1000740000/10000
       │
       ├─ Patch Deployment/STS: runAsUser → 1000740000 (MIN của dải)
       ├─ oc adm policy add-scc-to-group nonroot system:serviceaccounts:argocd
       └─ Gỡ anyuid / privileged (nếu lab trước đó đã gán)
```

| | `anyuid` (lab cũ) | **Namespace + nonroot** (khuyến nghị) |
|--|-------------------|--------------------------------------|
| Gán SCC | `system:serviceaccounts:argocd` | `system:serviceaccounts:argocd` |
| UID | Bất kỳ | Trong dải namespace |
| Root (UID 0) | Có thể | **Không** (`nonroot`) |
| Patch manifest | Không | Có — đưa UID vào dải |

---

## 1. Script tự động (khuyến nghị)

Sau khi cài ArgoCD upstream (hoặc sync Helm platform):

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh

# ArgoCD
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh argocd

# Platform (Jenkins, Harbor) — sau khi ArgoCD sync platform-app-of-apps
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh platform

# Vault
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh vault
```

Script sẽ:

1. Đọc `MIN_UID` / `MAX_UID` từ annotation namespace
2. Patch mọi Deployment/StatefulSet có `runAsUser` ngoài dải (redis 999, jenkins 1000, …)
3. Scale `argocd-dex-server` → 0 (trừ khi `--keep-dex`)
4. Gỡ `anyuid` / `privileged` khỏi namespace
5. Gán **`nonroot`** cho `system:serviceaccounts:<ns>`
6. Restart workloads

Chẩn đoán lỗi:

```bash
./phase9-gitops-platform/environments/dev-ocp/scripts/discover-pod-scc.sh argocd
```

---

## 2. Thủ công (hiểu cơ chế)

### Lấy dải UID

```bash
NS=argocd
oc get ns "$NS" -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}'; echo
# 1000740000/10000  →  MIN=1000740000, MAX=1000749999
MIN_UID=$(oc get ns "$NS" -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}' | cut -d/ -f1)
```

### Patch một workload

```bash
oc patch statefulset argocd-redis -n argocd --type='json' -p="[
  {\"op\":\"replace\",\"path\":\"/spec/template/spec/securityContext/runAsUser\",\"value\":$MIN_UID},
  {\"op\":\"replace\",\"path\":\"/spec/template/spec/securityContext/fsGroup\",\"value\":$MIN_UID}
]"
```

### Gán SCC cho namespace

```bash
oc adm policy add-scc-to-group nonroot system:serviceaccounts:argocd
oc adm policy remove-scc-from-group anyuid system:serviceaccounts:argocd
oc adm policy remove-scc-from-group privileged system:serviceaccounts:argocd
oc rollout restart deployment,statefulset -n argocd
```

### Dex (ArgoCD SSO)

Manifest Dex hay conflict `restricted` + seccomp. **Lab:** tắt Dex:

```bash
oc scale deployment argocd-dex-server -n argocd --replicas=0
```

Login ArgoCD vẫn dùng `admin` + password local.

---

## 3. Jenkins / Helm values

Chart Jenkins **không** hard-code `runAsUser: 1000` — chỉ `runAsNonRoot: true`. OpenShift gán UID trong dải `platform` khi pod schedule.

Sau sync `platform-jenkins`, chạy:

```bash
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh platform
```

---

## 4. Namespace đặc biệt (ngoại lệ)

Một số component **không** fit `nonroot` cả namespace — gán **privileged chỉ SA cụ thể**, không `anyuid` cả NS:

| Namespace | Component | SCC |
|-----------|-----------|-----|
| `csi-driver-nfs` | node/controller plugin | `privileged` → `csi-nfs-node-sa`, `csi-nfs-controller-sa` |
| `platform` | Harbor (jobservice, core, …) | `harbor-uid-range` → SA `harbor` (UID **999–10000**) — `harbor-scc-setup.sh` |
| `kong` | Kong HA (UID 1000) | `kong-uid1000` → SA `kong-kong` — `kong-scc-setup.sh` |
| `linkerd` / `linkerd-viz` | control plane + viz | `privileged` → group SA — `linkerd-scc-setup.sh` |

Xem [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md) §3.3.

---

## 5. Thứ tự trên cluster đã dùng `anyuid`

```bash
./namespace-scc-setup.sh argocd
./namespace-scc-setup.sh platform
watch oc get pods -A | grep -v Running
```

---

## 6. Custom SCC từng SA (dự phòng)

Chỉ khi **không patch được** UID (image bắt buộc 999) và không muốn đổi image:

- [ocp-values/scc/argocd-redis-scc.yaml](./ocp-values/scc/argocd-redis-scc.yaml)
- Script cũ: `argocd-scc-hardened.sh`

**Ưu tiên namespace** trước khi dùng các file trên.

---

## Liên kết

- Cài ArgoCD: [INSTALL-ARGOCD-UPSTREAM.md](./INSTALL-ARGOCD-UPSTREAM.md)
- Triển khai: [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md)
- **Troubleshooting:** [INSTALL-TROUBLESHOOTING.md](./INSTALL-TROUBLESHOOTING.md) (Harbor, Vault, CSR, NFS)
- Lab nhanh (không khuyến nghị): `scripts/argocd-scc-anyuid.sh`

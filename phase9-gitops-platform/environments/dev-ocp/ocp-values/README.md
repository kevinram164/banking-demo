# OpenShift value overrides (dev-ocp)

Nhánh **`dev-ocp`** dùng **OpenShift Route** thay Ingress và **NFS CSI** (`nfs-csi`) thay `local-path`.

| Thành phần | OpenShift (dev-ocp) |
|------------|---------------------|
| StorageClass | **`nfs-csi`** — [INSTALL-NFS-CSI.md](../INSTALL-NFS-CSI.md) |
| Expose UI | **Route** (`routes/*.yaml`) |
| Domain apps | `*.apps.ocp01.npd.co` |
| Banking domain | `npd-banking.co` (DNS tùy chỉnh → Router) |
| ArgoCD NS | `argocd` (upstream) |
| SCC | `namespace-scc-setup.sh` — [INSTALL-SCC-HARDENED.md](../INSTALL-SCC-HARDENED.md) |

## NFS CSI (`nfs-csi/`)

| File | Mục đích |
|------|----------|
| `nfs-csi/00-namespace.yaml` | Namespace + PodSecurity privileged |
| `nfs-csi/storageclass.yaml` | SC `nfs-csi` → `10.100.1.180:/shares/registry` |
| `nfs-csi/test-pvc.yaml` | PVC test |
| `nfs-csi/scc.sh` | Gán SCC sau Helm install |

Hướng dẫn: [INSTALL-NFS-CSI.md](../INSTALL-NFS-CSI.md)

## Routes (GitOps)

| File | Host | Service | NS |
|------|------|---------|-----|
| `routes/harbor-route.yaml` | `harbor-platform.apps.ocp01.npd.co` | `harbor:80` | `platform` |
| `routes/jenkins-route.yaml` | `jenkins-platform.apps.ocp01.npd.co` | `jenkins:http` | `platform` |
| `routes/vault-route.yaml` | `vault-platform.apps.ocp01.npd.co` | `vault:8200` | `vault` |
| `routes/argocd-route.yaml` | `argocd-server-argocd.apps.ocp01.npd.co` | `argocd-server` | `argocd` |
| `routes/banking-route-frontend.yaml` | `npd-banking.co` `/` | `frontend` | `npd-banking` |
| `routes/banking-route-api.yaml` | `npd-banking.co` `/api` | `kong-proxy-ext` | `npd-banking` |
| `routes/banking-route-ws.yaml` | `npd-banking.co` `/ws` | `kong-proxy-ext` | `npd-banking` |
| `routes/kong-route.yaml` | `kong.apps.ocp01.npd.co` | `kong-kong-proxy:8000` | `kong` |
| `routes/banking-kong-proxy-ext.yaml` | — | Deployment bridge + Service `kong-proxy-ext` → `kong-kong-proxy.kong.svc` (DNS) | `npd-banking` |

> **Thiết kế gốc:** 3 Route cùng ns app. Không Endpoints/IP pod (OCP cấm + IP đổi). Bridge TCP trong ns app proxy tới Kong qua DNS.

ArgoCD Application: **`platform-routes-dev-ocp`** (path `ocp-values/routes`).

Đổi cluster domain:

```bash
./scripts/customize-cluster-domain.sh ocp01.npd.co
```

## Kiểm tra cluster

```bash
oc get sc
oc get ingresses.config cluster -o jsonpath='{.spec.domain}'; echo
oc get route -n platform
oc get route -n vault
oc get route argocd-server -n argocd
```

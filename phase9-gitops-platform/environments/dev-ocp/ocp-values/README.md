# OpenShift value overrides (dev-ocp)

Manifest dùng chung `gitops-platform/applications/` được tune cho **k3d** (`local-path`, Traefik Ingress, `*-npd.co`).

Trên nhánh **`dev-ocp`**, platform Helm đã tắt Ingress; expose bằng **Route** trong thư mục `routes/`.

| Thành phần | k3d (dev-k3d) | OpenShift (dev-ocp) |
|------------|---------------|---------------------|
| StorageClass | `local-path` | `gp3-csi` / `ocs-storagecluster-ceph-rbd` / `oc get sc` |
| Expose UI | Traefik Ingress + Nginx WSL2 | **Route** (`routes/*.yaml`) |
| Domain | `*-npd.co` + hosts file | `*.apps.ocp01.npd.co` |
| ArgoCD NS | `argocd` | `openshift-gitops` |
| SCC | relaxed (k3d) | `anyuid` / `nonroot` — Jenkins, Harbor có thể cần điều chỉnh UID |

## Routes (GitOps)

| File | Host | Service | NS |
|------|------|---------|-----|
| `routes/harbor-route.yaml` | `harbor-banking.apps.ocp01.npd.co` | `harbor:80` | `platform` |
| `routes/jenkins-route.yaml` | `jenkins-platform.apps.ocp01.npd.co` | `jenkins:http` | `platform` |
| `routes/vault-route.yaml` | `vault-banking.apps.ocp01.npd.co` | `vault:8200` | `vault` |
| `routes/argocd-route.yaml` | `openshift-gitops-server-openshift-gitops.apps.ocp01.npd.co` | `openshift-gitops-server:https` | `openshift-gitops` |
| `routes/banking-route-*.yaml` | `npd-banking.co` (`/`, `/api`, `/ws`) | `frontend`, `kong-proxy-ext` | `banking` |
| `routes/kong-route.yaml` | `kong.apps.ocp01.npd.co` | `kong-kong-proxy:8000` | `kong` |
| `routes/banking-kong-proxy-ext.yaml` | — | ExternalName → `kong-kong-proxy.kong` | `banking` |

**DNS:** `npd-banking.co` là domain tùy chỉnh — trỏ A/CNAME tới OpenShift Router (không nằm trong `*.apps.ocp01.npd.co`).

ArgoCD Application: `argocd/applications/platform-routes-app-of-apps.yaml` (sync-wave `3`, sau Harbor/Vault/Jenkins).

Đổi cluster domain:

```bash
./scripts/customize-cluster-domain.sh ocp01.npd.co
# hoặc sửa host trong routes/*.yaml + gitops-env.yaml
```

## Kiểm tra cluster

```bash
oc get sc
oc get ingresses.config cluster -o jsonpath='{.spec.domain}'; echo
oc get route -n platform
oc get route -n vault
oc get route openshift-gitops-server -n openshift-gitops
```

## File khác (bổ sung dần)

- `infra-storage.yaml` — `storageClass` cho Postgres/Redis/RabbitMQ

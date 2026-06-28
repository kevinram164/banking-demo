# Environment: dev-ocp (OpenShift — ocp01.npd.co)

Cấu hình ArgoCD + GitOps cho nhánh **`dev-ocp`** trên cluster **OpenShift**.

**Hướng dẫn đầy đủ:** [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md)

## URL cluster (đã cấu hình)

| Service | URL |
|---------|-----|
| OpenShift Console | https://console-openshift-console.apps.ocp01.npd.co |
| ArgoCD (GitOps) | https://argocd-server-argocd.apps.ocp01.npd.co |
| Harbor | https://harbor-banking.apps.ocp01.npd.co |
| Jenkins | https://jenkins-platform.apps.ocp01.npd.co |
| Vault | https://vault-banking.apps.ocp01.npd.co |
| Banking app | https://npd-banking.co |
| Kong proxy | https://kong.apps.ocp01.npd.co |

Cluster domain: **`ocp01.npd.co`** — route pattern: `<tên>.apps.ocp01.npd.co`

**Kiến trúc (Route thay Traefik/Nginx):** [OCP-ARCHITECTURE.md](../../OCP-ARCHITECTURE.md)

---

## Thứ tự triển khai

| Bước | File apply | Giai đoạn |
|------|------------|-----------|
| 0 | **NFS CSI** — [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md) | Trước platform (PVC Harbor/Postgres…) |
| 1 | ArgoCD upstream — [INSTALL-ARGOCD-UPSTREAM.md](./INSTALL-ARGOCD-UPSTREAM.md) | Pods Running trong `argocd` |
| 2 | `appproject.yaml` | |
| 3 | `argocd/applications/platform-app-of-apps.yaml` | Platform (Harbor, Vault, ESO, Jenkins) |
| 3a | `argocd/applications/platform-routes-app-of-apps.yaml` | Routes (sau platform Running) |
| 3b | `argocd/applications/observability-app-of-apps.yaml` | Observability (tùy chọn) |
| 4 | `argocd/applications/infra-app-of-apps.yaml` | Infra |
| 5 | Jenkins pipeline → Harbor → Git | CI/CD |
| 6 | `argocd/applications/banking-app-of-apps.yaml` | **Banking app** |

**Lưu ý:** Sau Kong import, cập nhật CORS origins thành `https://npd-banking.co` trong `kong-import-job.yaml`.

```bash
export ARGOCD_NS=argocd
./phase9-gitops-platform/environments/dev-ocp/apply-argocd.sh
```

## Khác dev-k3d

| | dev-k3d | dev-ocp |
|---|---------|---------|
| ArgoCD NS | `argocd` | `argocd` (upstream + Route) |
| Domain | `*-npd.co` (hosts file) | `*.apps.ocp01.npd.co` |
| Storage | `local-path` | **`nfs-csi`** (10.100.1.180) |

Xem overlay: [ocp-values/README.md](./ocp-values/README.md)

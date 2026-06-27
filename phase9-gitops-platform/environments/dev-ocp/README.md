# Environment: dev-ocp (OpenShift — ocp01.npd.co)

Cấu hình ArgoCD + GitOps cho nhánh **`dev-ocp`** trên cluster **OpenShift**.

**Hướng dẫn đầy đủ:** [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md)

## URL cluster (đã cấu hình)

| Service | URL |
|---------|-----|
| OpenShift Console | https://console-openshift-console.apps.ocp01.npd.co |
| ArgoCD (GitOps) | https://openshift-gitops-server-openshift-gitops.apps.ocp01.npd.co |
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
| 1 | `appproject.yaml` | Sau OpenShift GitOps Operator |
| 2 | `argocd/applications/platform-app-of-apps.yaml` | Platform (Harbor, Vault, ESO, Jenkins) |
| 2a | `argocd/applications/platform-routes-app-of-apps.yaml` | **Routes** (sau platform pods Running) |
| 2b | `argocd/applications/observability-app-of-apps.yaml` | Observability |
| 3 | `argocd/applications/infra-app-of-apps.yaml` | Infra |
| 4 | Jenkins pipeline → Harbor → Git | CI/CD |
| 5 | `argocd/applications/banking-app-of-apps.yaml` | **Banking app** |
| 5b | `platform-routes-app-of-apps.yaml` (nếu chưa sync) | Routes banking + Kong |

**Lưu ý:** Sau Kong import, cập nhật CORS origins thành `https://npd-banking.co` trong `kong-import-job.yaml`.

```bash
export ARGOCD_NS=openshift-gitops
./phase9-gitops-platform/environments/dev-ocp/apply-argocd.sh
```

## Khác dev-k3d

| | dev-k3d | dev-ocp |
|---|---------|---------|
| ArgoCD NS | `argocd` | `openshift-gitops` |
| Domain | `*-npd.co` (hosts file) | `*.apps.ocp01.npd.co` |
| Storage | `local-path` | `gp3-csi` (kiểm tra `oc get sc`) |

Xem overlay: [ocp-values/README.md](./ocp-values/README.md)

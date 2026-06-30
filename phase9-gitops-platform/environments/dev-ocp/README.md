# Environment: dev-ocp (OpenShift — ocp01.npd.co)

Cấu hình ArgoCD + GitOps cho nhánh **`dev-ocp`** trên cluster **OpenShift**.

**Hướng dẫn đầy đủ:** [OCP-DEPLOY-GUIDE.md](../../OCP-DEPLOY-GUIDE.md)

## URL cluster (đã cấu hình)

| Service | URL |
|---------|-----|
| OpenShift Console | https://console-openshift-console.apps.ocp01.npd.co |
| ArgoCD | https://argocd-server-argocd.apps.ocp01.npd.co |
| Harbor | https://harbor-banking.apps.ocp01.npd.co |
| Jenkins | https://jenkins-platform.apps.ocp01.npd.co |
| Vault | https://vault-banking.apps.ocp01.npd.co |
| Banking app | https://npd-banking.co |
| Kong proxy | https://kong.apps.ocp01.npd.co |

Cluster domain: **`ocp01.npd.co`** — route pattern: `<tên>.apps.ocp01.npd.co`

**Kiến trúc:** [OCP-ARCHITECTURE.md](../../OCP-ARCHITECTURE.md)

---

## Thứ tự triển khai

| Bước | File / tài liệu | Giai đoạn |
|------|-----------------|-----------|
| 0 | [INSTALL-NFS-CSI.md](./INSTALL-NFS-CSI.md) | NFS CSI + `nfs-csi` SC |
| — | [INSTALL-TROUBLESHOOTING.md](./INSTALL-TROUBLESHOOTING.md) | **Runbook xử lý lỗi** (Vault, Harbor, CSR, NFS) |
| 1 | [INSTALL-ARGOCD-UPSTREAM.md](./INSTALL-ARGOCD-UPSTREAM.md) | ArgoCD + SCC + Route |
| 2 | `appproject.yaml` | AppProject |
| 3 | `argocd/applications/platform-app-of-apps.yaml` | Platform |
| 3a | `argocd/applications/platform-routes-app-of-apps.yaml` | Routes |
| 3b | `argocd/applications/observability-app-of-apps.yaml` | Observability (tùy chọn) |
| 4 | `argocd/applications/infra-app-of-apps.yaml` | Infra |
| 5 | Jenkins pipeline → Harbor → Git | CI/CD |
| 6 | `argocd/applications/banking-app-of-apps.yaml` | **Banking app** |

**Lưu ý:** Sau Kong import, CORS origins là `https://npd-banking.co` trong `kong-import-job.yaml`.

```bash
export ARGOCD_NS=argocd
./phase9-gitops-platform/environments/dev-ocp/apply-argocd.sh
```

## Đặc thù OpenShift

| Hạng mục | Giá trị |
|----------|---------|
| ArgoCD NS | `argocd` (upstream + Route) |
| Storage | **`nfs-csi`** (NFS `10.100.1.180`) |
| Expose | Route (không Ingress Helm) |
| SCC | `namespace-scc-setup.sh` — nonroot + UID range namespace |

Overlay: [ocp-values/README.md](./ocp-values/README.md)

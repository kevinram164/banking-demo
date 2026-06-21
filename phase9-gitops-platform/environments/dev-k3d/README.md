# Environment: dev-k3d

Cấu hình ArgoCD + GitOps cho nhánh **`dev-k3d`** trên cluster **k3d-npd**.

## Thứ tự triển khai

**Không apply banking app cho đến khi platform + infra + CI/CD sẵn sàng.**

| Bước | File apply | Giai đoạn |
|------|------------|-----------|
| 1 | `phase9-gitops-platform/gitops-platform/project.yaml` | ArgoCD bootstrap xong |
| 2 | `applications/platform-app-of-apps.yaml` | Platform |
| 2b | `applications/observability-app-of-apps.yaml` | Coroot + OTEL + Linkerd |
| 3 | `applications/infra-app-of-apps.yaml` | Infra |
| 4 | Jenkins pipeline green + image trên Harbor | CI/CD |
| 5 | `applications/banking-app-of-apps.yaml` | **Deploy app** |
| 6 | `app-of-apps.yaml` (tùy chọn) | Quản lý tập trung |

Chi tiết: [K3D-DEPLOY-GUIDE.md](../../K3D-DEPLOY-GUIDE.md)

## Khác với `main`

| File | `main` | `dev-k3d` |
|------|--------|-----------|
| ArgoCD `targetRevision` | `main` | **`dev-k3d`** |
| CI | GitHub Actions | Jenkins |
| Root App of Apps | `gitops-platform/app-of-apps.yaml` | **`environments/dev-k3d/argocd/app-of-apps.yaml`** |
| Thứ tự deploy | App of Apps một lần | **Platform → Infra → CI/CD → Banking** |

## gitops-env.yaml

Chỉnh `harbor.host` cho lab trước khi cấu hình Jenkins.

# Environment: dev-k3d

Cấu hình ArgoCD + GitOps cho nhánh **`dev-k3d`** trên cluster **k3d-npd**.

## Khác với `main`

| File | `main` | `dev-k3d` |
|------|--------|-----------|
| ArgoCD `targetRevision` | `main` | **`dev-k3d`** |
| CI | GitHub Actions | Jenkins |
| Root App of Apps | `argocd/app-of-apps.yaml` | **`environments/dev-k3d/argocd/app-of-apps.yaml`** |

## Apply (một lần / sau khi sửa manifest)

```bash
# Từ repo root, đã kubectl context = k3d-npd
kubectl apply -f phase9-gitops-platform/argocd/project.yaml -n argocd
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/app-of-apps.yaml -n argocd
```

## Chỉ banking (lab nhẹ — bỏ platform/infra lúc đầu)

Comment hoặc không apply `platform-app-of-apps` / `infra-app-of-apps` trong root dev-k3d; chỉ sync:

```bash
kubectl apply -f phase9-gitops-platform/argocd/applications/banking-app-of-apps.yaml -n argocd
# Sửa targetRevision trong file banking-app-of-apps thành dev-k3d trước khi apply
# Hoặc dùng app-of-apps dev-k3d đầy đủ
```

## gitops-env.yaml

Chỉnh `repoUrl`, `harbor.host` cho lab của bạn trước khi cấu hình Jenkins.
